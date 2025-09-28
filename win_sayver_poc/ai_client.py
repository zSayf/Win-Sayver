#!/usr/bin/env python3
"""
AI Client Module for Win Sayver POC - Updated for Official Google GenAI SDK.

This module handles communication with Google Gemini API for error analysis using
the official google-genai library released in 2024.
"""

import base64
import io
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    from google import genai
    from google.genai import types

    GENAI_AVAILABLE = True
except ImportError:
    GENAI_AVAILABLE = False
    genai = None
    types = None

from prompt_engineer import PromptEngineer, PromptEngineeringError
from utils import (
    ErrorHandler,
    PerformanceTimer,
    WinSayverError,
    retry_on_exception,
    safe_execute,
)


class AIClientError(WinSayverError):
    """Raised when AI client operations fail."""

    pass


class APIKeyError(AIClientError):
    """Raised when API key is missing or invalid."""

    pass


class ImageProcessingError(AIClientError):
    """Raised when image processing fails."""

    pass


class AIResponseError(AIClientError):
    """Raised when AI response is invalid or unexpected."""

    pass


def is_interactive() -> bool:
    """
    Check if the current environment is interactive.

    Returns:
        True if running in an interactive shell, False otherwise
    """
    import sys

    return hasattr(sys, "ps1") or sys.stdin.isatty() or sys.stdout.isatty()


class StreamResponse:
    """
    Class to handle streaming responses with thinking steps.
    """

    def __init__(self, text: str, candidates: List[Dict[str, Any]], usage: Optional[Dict[str, Any]] = None):
        self.text = text
        self.candidates = candidates
        self.usage = usage

    def set_usage(self, usage: Optional[Dict[str, Any]]) -> None:
        """Set usage metrics for the response."""
        self.usage = usage


class ModelFallbackManager:
    """
    Manages intelligent model fallback during rate limiting and errors.

    Provides seamless degradation from Pro models to Flash models when needed,
    while maintaining analysis quality and user experience.
    """

    def __init__(self, logger):
        self.logger = logger
        self.fallback_chain = [
            "gemini-2.5-pro",
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-1.5-pro",
            "gemini-1.5-flash",
        ]
        self.rate_limit_tracker = {}
        self.quota_exhausted_models = set()  # Track models with quota issues
        self.quota_reset_time = {}  # Track when quotas might reset
        self.last_successful_model = None

    def mark_quota_exhausted(self, model: str, retry_delay: int = 3600) -> None:
        """
        Mark a model as having quota exhausted.

        Args:
            model: Model name that hit quota limit
            retry_delay: Seconds until quota might reset (default: 1 hour)
        """
        import time

        self.quota_exhausted_models.add(model)
        self.quota_reset_time[model] = time.time() + retry_delay
        self.logger.warning(f"Model {model} quota exhausted, marked for {retry_delay}s cooldown")

    def is_quota_available(self, model: str) -> bool:
        """
        Check if a model's quota might be available.

        Args:
            model: Model name to check

        Returns:
            True if quota might be available, False if known to be exhausted
        """
        import time

        if model not in self.quota_exhausted_models:
            return True

        # Check if cooldown period has passed
        reset_time = self.quota_reset_time.get(model, 0)
        if time.time() > reset_time:
            self.quota_exhausted_models.discard(model)
            if model in self.quota_reset_time:
                del self.quota_reset_time[model]
            self.logger.info(f"Model {model} quota cooldown expired, re-enabling")
            return True

        return False

    def get_next_available_model(self, current_model: str, error_type: str = "unknown") -> Optional[str]:
        """
        Get the next available model in the fallback chain.

        Args:
            current_model: Model that failed
            error_type: Type of error encountered

        Returns:
            Next model to try, or None if all options exhausted
        """
        try:
            # Handle quota exhaustion specifically
            if "429" in error_type or "quota" in error_type.lower() or "RESOURCE_EXHAUSTED" in error_type:
                self.mark_quota_exhausted(current_model)

                # Find next available model that hasn't hit quota
                for model in self.fallback_chain:
                    if model != current_model and self.is_quota_available(model):
                        self.logger.info(f"Quota fallback: {current_model} -> {model}")
                        return model

                self.logger.error("All models appear to have quota issues")
                return None

            current_index = self.fallback_chain.index(current_model)

            # If rate limited, skip to next model
            if "rate" in error_type.lower():
                self.logger.info(f"Rate limit detected for {current_model}, falling back to next model")

                # Try next models in chain
                for i in range(current_index + 1, len(self.fallback_chain)):
                    next_model = self.fallback_chain[i]
                    if not self._is_rate_limited(next_model) and self.is_quota_available(next_model):
                        self.logger.info(f"Falling back to {next_model}")
                        return next_model

            # For other errors, try the next model
            if current_index + 1 < len(self.fallback_chain):
                next_model = self.fallback_chain[current_index + 1]
                if self.is_quota_available(next_model):
                    self.logger.info(f"Error with {current_model}, trying {next_model}")
                    return next_model

        except ValueError:
            # Current model not in chain, start from Flash
            for model in self.fallback_chain:
                if self.is_quota_available(model):
                    self.logger.warning(f"Unknown model {current_model}, falling back to {model}")
                    return model

        return None

    def _is_rate_limited(self, model: str) -> bool:
        """
        Check if a model is currently rate limited.

        Args:
            model: Model name to check

        Returns:
            True if model should be avoided due to rate limiting
        """
        import time

        if model not in self.rate_limit_tracker:
            return False

        last_rate_limit = self.rate_limit_tracker[model]
        # Avoid Pro models for 60 seconds after rate limit
        # Avoid Flash models for 30 seconds after rate limit
        cooldown = 60 if "pro" in model.lower() else 30

        return (time.time() - last_rate_limit) < cooldown

    def record_rate_limit(self, model: str) -> None:
        """
        Record when a model hit rate limits.

        Args:
            model: Model that was rate limited
        """
        import time

        self.rate_limit_tracker[model] = time.time()
        self.logger.info(f"Recorded rate limit for {model}")

    def record_success(self, model: str) -> None:
        """
        Record successful analysis with a model.

        Args:
            model: Model that succeeded
        """
        self.last_successful_model = model
        # Clear rate limit tracking on success
        if model in self.rate_limit_tracker:
            del self.rate_limit_tracker[model]

    def get_optimal_model(self, complexity: str = "standard") -> str:
        """
        Get the optimal model based on analysis complexity and availability.

        Args:
            complexity: Analysis complexity ("simple", "standard", "complex")

        Returns:
            Optimal model name
        """
        if complexity == "simple":
            # For simple analysis, prefer faster models
            candidates = ["gemini-2.5-flash-lite", "gemini-2.5-flash", "gemini-1.5-flash"]
        elif complexity == "complex":
            # For complex analysis, prefer thinking models
            candidates = ["gemini-2.5-pro", "gemini-1.5-pro", "gemini-2.5-flash"]
        else:
            # Standard complexity
            candidates = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"]

        # Return first available model
        for model in candidates:
            if not self._is_rate_limited(model):
                return model

        # Fallback to last successful model or default
        return self.last_successful_model or "gemini-2.5-flash"

    def get_quota_status(self) -> Dict[str, Any]:
        """
        Get current quota status for all models.

        Returns:
            Dictionary with quota status information
        """
        import time

        current_time = time.time()

        status = {
            "quota_exhausted_models": list(self.quota_exhausted_models),
            "available_models": [],
            "quota_reset_times": {},
            "recommended_model": None,
        }

        # Check which models are available
        for model in self.fallback_chain:
            if self.is_quota_available(model):
                status["available_models"].append(model)
            elif model in self.quota_reset_time:
                reset_time = self.quota_reset_time[model]
                status["quota_reset_times"][model] = max(0, int(reset_time - current_time))

        # If no models were specifically marked as quota exhausted, all should be available
        if not self.quota_exhausted_models:
            status["available_models"] = self.fallback_chain.copy()

        # Recommend the best available model (skip the first one if it's exhausted)
        if status["available_models"]:
            status["recommended_model"] = status["available_models"][0]

        return status


class GroundingResponse:
    """
    Enhanced response object that includes grounding metadata and citations.
    """

    def __init__(
        self, text: str, grounding_metadata: Optional[Dict[str, Any]] = None, usage: Optional[Dict[str, Any]] = None
    ):
        self.text = text if text is not None else "No response generated"
        self.grounding_metadata = grounding_metadata or {}
        self.usage = usage or {}
        self.has_grounding = bool(grounding_metadata and any(grounding_metadata.values()))

        # Parse grounding data if available
        try:
            self.search_queries = self._extract_search_queries()
            self.sources = self._extract_sources()
            self.citations = self._extract_citations()
        except Exception as e:
            # If extraction fails, initialize with empty values
            self.search_queries = []
            self.sources = []
            self.citations = []
            self.has_grounding = False

    def _extract_search_queries(self) -> List[str]:
        """Extract search queries used by the AI."""
        if not self.grounding_metadata:
            return []
        queries = self.grounding_metadata.get("webSearchQueries", [])
        return queries if queries is not None else []

    def _extract_sources(self) -> List[Dict[str, str]]:
        """Extract source information from grounding chunks."""
        if not self.grounding_metadata:
            return []

        sources = []
        chunks = self.grounding_metadata.get("groundingChunks", [])
        if chunks is None:
            return []

        for i, chunk in enumerate(chunks):
            if chunk and "web" in chunk:
                sources.append(
                    {
                        "index": i,
                        "title": chunk["web"].get("title", "Unknown Source"),
                        "uri": chunk["web"].get("uri", ""),
                        "snippet": chunk.get("snippet", ""),
                    }
                )
        return sources

    def _extract_citations(self) -> List[Dict[str, Any]]:
        """Extract citation mappings from grounding supports."""
        if not self.grounding_metadata:
            return []

        citations = []
        supports = self.grounding_metadata.get("groundingSupports", [])
        if supports is None:
            return []

        for support in supports:
            if support and "segment" in support and "groundingChunkIndices" in support:
                segment = support["segment"]
                citations.append(
                    {
                        "text": segment.get("text", ""),
                        "start_index": segment.get("startIndex", 0),
                        "end_index": segment.get("endIndex", 0),
                        "source_indices": support["groundingChunkIndices"] or [],
                    }
                )
        return citations

    def get_text_with_citations(self) -> str:
        """Get response text with inline citations added."""
        if not self.has_grounding or not self.citations:
            return self.text

        text = self.text
        sources = self.sources

        # Sort citations by end_index in descending order to avoid shifting issues
        sorted_citations = sorted(self.citations, key=lambda c: c["end_index"], reverse=True)

        for citation in sorted_citations:
            end_index = citation["end_index"]
            if citation["source_indices"]:
                # Create citation string like [1](link1), [2](link2)
                citation_links = []
                for i in citation["source_indices"]:
                    if i < len(sources):
                        uri = sources[i]["uri"]
                        title = sources[i]["title"]
                        citation_links.append(f'[{i + 1}]({uri} "{title}")')

                if citation_links:
                    citation_string = ", ".join(citation_links)
                    text = text[:end_index] + citation_string + text[end_index:]

        return text


class AIClient:
    """
    Handles communication with Google Gemini API for error analysis with Google Search Grounding.

    This class manages API authentication, image processing, prompt construction,
    response parsing, and real-time web search grounding for AI-powered Windows
    troubleshooting using the official Google GenAI SDK.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
        thinking_budget: str = "AUTO",
        enable_streaming: bool = False,
        enable_search_grounding: bool = True,
    ):
        """
        Initialize the AI client with thinking configuration and search grounding.

        Args:
            api_key: Google Gemini API key (or set GEMINI_API_KEY env var)
            model_name: Name of the Gemini model to use (default: gemini-2.5-flash for quota efficiency)
            thinking_budget: Configuration for thinking quality (AUTO, SPEED, QUALITY, or specific value)
            enable_streaming: Whether to use streaming API for incremental responses
            enable_search_grounding: Whether to enable Google Search grounding for real-time web data

        Raises:
            AIClientError: If initialization fails
        """
        self.logger = logging.getLogger(__name__)

        # Default to Flash model for quota efficiency - can be overridden
        self.model_name = model_name if model_name else "gemini-2.5-flash"
        self.thinking_budget = thinking_budget
        self.enable_streaming = enable_streaming  # Initialize enable_streaming
        self.enable_search_grounding = enable_search_grounding  # Initialize search grounding
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.rate_limit_delay = 1.0  # Default rate limit delay
        self.total_tokens_used = 0  # Track total tokens including thinking tokens

        # Initialize client-related attributes
        self.client = None
        self._client_initialized = False

        # Initialize request counter
        self.request_count = 0
        self.last_request_time = 0

        # Initialize thinking-specific attributes
        self.thinking_tokens_used = 0
        self.thinking_requests_count = 0
        self.thinking_duration = 0

        # Initialize model fallback manager
        self.fallback_manager = ModelFallbackManager(self.logger)

        try:
            if self.api_key:
                os.environ["GEMINI_API_KEY"] = self.api_key

            # Initialize client
            self._initialize_client()

            # Initialize prompt engineer
            self.prompt_engineer = PromptEngineer()

            self.logger.info(f"AI client initialized successfully with model: {self.model_name}")

        except Exception as e:
            self.logger.error(f"Failed to initialize AI client: {e}")
            raise AIClientError(f"Client initialization failed: {e}")

    def _initialize_client(self) -> None:
        """
        Initialize client components.
        """
        try:
            if not GENAI_AVAILABLE:
                raise AIClientError("google-genai library not available")

            # Initialize client if not already initialized
            if not self._client_initialized:
                # Initialize client with proper type checking
                client = genai.Client() if GENAI_AVAILABLE and genai is not None else None
                if client is None:
                    raise AIClientError("Failed to initialize Gemini client")
                self.client = client
                self._client_initialized = True

        except Exception as e:
            self.logger.error(f"Failed to initialize client: {e}")
            raise

    def set_api_key(self, api_key: str) -> None:
        """
        Set or update the API key.

        Args:
            api_key: Google Gemini API key
        """
        self.api_key = api_key
        self._initialize_client()

    @retry_on_exception(max_retries=3, delay=2.0, exceptions=(AIClientError,))
    def analyze_error_screenshot_with_grounding(
        self,
        image_path: str,
        system_specs: Dict[str, Any],
        error_type: str = "system_diagnostic",
        additional_context: Optional[str] = None,
        url_context: Optional[List[str]] = None,
        enable_search: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Analyze error screenshot using AI with Google Search grounding for real-time web data.

        Args:
            image_path: Path to the error screenshot file
            system_specs: Complete system specification dictionary
            error_type: Type of error analysis to perform
            additional_context: Optional additional context information
            url_context: Optional list of URLs to include as context
            enable_search: Whether to enable search grounding (overrides default)

        Returns:
            Dictionary containing analysis results with confidence score, solutions, and citations

        Raises:
            AIClientError: If analysis fails
            ImageProcessingError: If image processing fails
            APIKeyError: If API key is invalid
        """
        try:
            with PerformanceTimer("Error screenshot analysis with grounding") as timer:
                # Validate inputs
                self._validate_analysis_inputs(image_path, system_specs)

                # Check if client is initialized
                if not self.client:
                    raise APIKeyError("AI client not initialized. Please set API key first.")

                # Get image data
                image_bytes, mime_type = self._process_image_for_genai(image_path)

                # Create proper types.Part object for new SDK
                if not GENAI_AVAILABLE or types is None:
                    raise AIClientError("Google GenAI SDK not available")

                self.logger.info(f"Creating image Part object: size={len(image_bytes)} bytes, mime_type={mime_type}")
                image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
                self.logger.debug(f"Image Part object created successfully for {Path(image_path).name}")

                # Build enhanced prompt for grounding
                prompt = self.prompt_engineer.build_analysis_prompt(
                    error_type=error_type, system_specs=system_specs, additional_context=additional_context
                )

                # Add enhanced grounding instructions for URL specificity
                grounding_instruction = (
                    "\n\n🚨 CRITICAL GOOGLE SEARCH GUIDANCE FOR SPECIFIC URLs:\n"
                    "Use Google Search to find CURRENT, SPECIFIC, and DETAILED URLs. Avoid generic fallbacks.\n\n"
                    "**SEARCH STRATEGY FOR SPECIFICITY:**\n"
                    "1. **Find Current KB Articles**: Search 'Microsoft KB [specific issue] [Windows version] current 2024'\n"
                    "   - Example: 'Microsoft KB software installation error Windows 11 current'\n"
                    "   - Example: 'Microsoft KB Windows Defender disable specific procedure current'\n\n"
                    "2. **Locate Detailed Procedures**: Search '[software] [specific action] official Microsoft detailed steps'\n"
                    "   - Example: 'Software installation troubleshooting official Microsoft detailed steps'\n"
                    "   - Example: 'SFC scan Windows 11 official Microsoft detailed procedure'\n\n"
                    "3. **Find Exact Downloads**: Search '[software] latest version official download [manufacturer] current'\n"
                    "   - Example: 'AMD chipset drivers latest X570 official download current'\n"
                    "   - Example: 'Software latest version official download Windows current'\n\n"
                    "4. **Search Registry Solutions**: Search '[issue] registry fix official Microsoft specific keys'\n"
                    "   - Example: 'Windows Defender disable registry specific keys official Microsoft'\n\n"
                    "**URL PRIORITY ORDER:**\n"
                    "- PRIORITY 1: Specific KB articles (support.microsoft.com/kb/... or /topic/...)\n"
                    "- PRIORITY 2: Detailed procedures (docs.microsoft.com/troubleshoot/...)\n"
                    "- PRIORITY 3: Current official downloads (vendor-specific download pages)\n"
                    "- PRIORITY 4: Specific community solutions (answers.microsoft.com with verified answers)\n"
                    "- AVOID: Generic support pages, general download centers, non-specific links\n\n"
                    "**SPECIFICITY REQUIREMENTS:**\n"
                    "- Include KB numbers (e.g., KB5034441, KB5029244)\n"
                    "- Specify exact Windows versions (Windows 11 22H2, Windows 10 21H1)\n"
                    "- Include specific error codes and messages\n"
                    "- Find exact tool names and version numbers\n"
                    "- Locate precise registry paths and values\n"
                    "- Get current manufacturer driver pages with model numbers\n\n"
                    "Remember: Users want DETAILED, SPECIFIC URLs that provide exact solutions, not generic support pages."
                )

                prompt += grounding_instruction

                # Send grounded request
                use_search = enable_search if enable_search is not None else self.enable_search_grounding
                response = self._send_grounded_multimodal_request(prompt, image_part, url_context, use_search)

                # Parse response
                if isinstance(response, GroundingResponse):
                    parsed_response = self.prompt_engineer.validate_prompt_response(response.text)

                    # Validate and fix URLs in the response
                    try:
                        from link_validator import AIResponseLinkValidator

                        link_validator = AIResponseLinkValidator()
                        parsed_response = link_validator.validate_and_fix_response(parsed_response)
                        self.logger.info("URL validation completed for grounded response")
                    except Exception as e:
                        self.logger.warning(f"URL validation failed: {e} - proceeding with original response")

                    # Add grounding metadata
                    parsed_response["grounding_metadata"] = {
                        "has_grounding": response.has_grounding,
                        "search_queries": response.search_queries,
                        "sources": response.sources,
                        "citations": response.citations,
                        "text_with_citations": response.get_text_with_citations(),
                    }
                else:
                    parsed_response = self.prompt_engineer.validate_prompt_response(response)
                    parsed_response["grounding_metadata"] = {"has_grounding": False}

                # Add metadata
                parsed_response["analysis_metadata"] = {
                    "model_used": self.model_name,
                    "error_type": error_type,
                    "analysis_type": "grounded_image_analysis",
                    "analysis_timestamp": time.time(),
                    "request_id": self.request_count,
                    "sdk_version": "google-genai-official",
                    "image_processed": True,
                    "search_grounding_enabled": use_search,
                }

                self.logger.info(
                    f"Grounded image analysis completed with confidence {parsed_response.get('confidence_score', 0):.2f}"
                )
                return {"success": True, "analysis": parsed_response}

        except Exception as e:
            self.logger.error(f"Grounded error analysis failed: {e}")
            if isinstance(e, (AIClientError, ImageProcessingError, APIKeyError)):
                raise
            raise AIClientError(f"Grounded error analysis failed: {e}")

    def analyze_text_only(
        self, error_description: str, system_specs: Dict[str, Any], error_type: str = "system_diagnostic"
    ) -> Dict[str, Any]:
        """
        Analyze error based on text description only (no image).

        Args:
            error_description: Text description of the error
            system_specs: Complete system specification dictionary
            error_type: Type of error analysis to perform

        Returns:
            Dictionary containing analysis results
        """
        try:
            with PerformanceTimer("Text-only error analysis") as timer:
                # Validate inputs
                if not self.client:
                    raise APIKeyError("AI client not initialized. Please set API key first.")

                # Validate error description with better error handling
                if not error_description:
                    error_description = "Please analyze the specific error shown in the screenshot and provide targeted troubleshooting steps."
                    self.logger.info("Empty error description provided, using screenshot-focused default")
                elif not error_description.strip():
                    error_description = "Please analyze the specific error shown in the screenshot and provide targeted troubleshooting steps."
                    self.logger.info("Whitespace-only error description provided, using screenshot-focused default")

                # Construct the analysis prompt with error description
                prompt = self.prompt_engineer.build_analysis_prompt(
                    error_type=error_type,
                    system_specs=system_specs,
                    additional_context=f"ERROR DESCRIPTION:\\n{error_description.strip()}",
                )

                # Add text-only specific instruction
                prompt += "\\n\\nNOTE: No screenshot is available. Base your analysis solely on the error description and system specifications provided."

                # Send request to Gemini API (text only)
                response = self._send_text_request(prompt)

                # Parse and validate response
                parsed_response = self.prompt_engineer.validate_prompt_response(response)

                # Validate and fix URLs in the response
                try:
                    from link_validator import AIResponseLinkValidator

                    link_validator = AIResponseLinkValidator()
                    parsed_response = link_validator.validate_and_fix_response(parsed_response)
                    self.logger.info("URL validation completed for text-only response")
                except Exception as e:
                    self.logger.warning(f"URL validation failed: {e} - proceeding with original response")

                # Add metadata
                parsed_response["analysis_metadata"] = {
                    "model_used": self.model_name,
                    "error_type": error_type,
                    "analysis_type": "text_only",
                    "analysis_timestamp": time.time(),
                    "request_id": self.request_count,
                    "sdk_version": "google-genai-official",
                }

                self.logger.info(
                    f"Text-only analysis completed with confidence {parsed_response.get('confidence_score', 0):.2f}"
                )
                return {"success": True, "analysis": parsed_response}

        except Exception as e:
            self.logger.error(f"Text-only analysis failed: {e}")
            if isinstance(e, (AIClientError, APIKeyError)):
                return {"success": False, "error": str(e)}
            return {"success": False, "error": f"Text-only analysis failed: {e}"}

    @retry_on_exception(max_retries=3, delay=2.0, exceptions=(AIClientError,))
    def analyze_error_screenshot(
        self,
        image_path: str,
        system_specs: Dict[str, Any],
        error_type: str = "system_diagnostic",
        additional_context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Analyze error screenshot using AI (backward compatibility method).

        This method provides backward compatibility for existing code while
        leveraging the new grounding-enabled functionality.

        Args:
            image_path: Path to the error screenshot file
            system_specs: Complete system specification dictionary
            error_type: Type of error analysis to perform
            additional_context: Optional additional context information

        Returns:
            Dictionary containing analysis results with confidence score and solutions

        Raises:
            AIClientError: If analysis fails
            ImageProcessingError: If image processing fails
            APIKeyError: If API key is invalid
        """
        try:
            # Delegate to the grounding-enabled method
            # Use default grounding setting from the client configuration
            return self.analyze_error_screenshot_with_grounding(
                image_path=image_path,
                system_specs=system_specs,
                error_type=error_type,
                additional_context=additional_context,
                url_context=None,  # No URL context for backward compatibility
                enable_search=self.enable_search_grounding,  # Use client's grounding setting
            )
        except Exception as e:
            self.logger.error(f"Backward compatible error analysis failed: {e}")
            if isinstance(e, (AIClientError, ImageProcessingError, APIKeyError)):
                raise
            raise AIClientError(f"Error analysis failed: {e}")

    def analyze_text_only_with_grounding(
        self,
        error_description: str,
        system_specs: Dict[str, Any],
        error_type: str = "system_diagnostic",
        url_context: Optional[List[str]] = None,
        enable_search: Optional[bool] = None,
    ) -> Dict[str, Any]:
        """
        Analyze error based on text description with Google Search grounding.

        Args:
            error_description: Text description of the error
            system_specs: Complete system specification dictionary
            error_type: Type of error analysis to perform
            url_context: Optional list of URLs to include as context
            enable_search: Whether to enable search grounding (overrides default)

        Returns:
            Dictionary containing analysis results with grounding metadata
        """
        try:
            with PerformanceTimer("Text-only error analysis with grounding") as timer:
                # Validate inputs
                if not self.client:
                    raise APIKeyError("AI client not initialized. Please set API key first.")

                # Validate error description
                if not error_description or not error_description.strip():
                    error_description = "Please provide troubleshooting steps for the described system issue."
                    self.logger.info("Empty error description provided, using default")

                # Construct the analysis prompt
                prompt = self.prompt_engineer.build_analysis_prompt(
                    error_type=error_type,
                    system_specs=system_specs,
                    additional_context=f"ERROR DESCRIPTION:\n{error_description.strip()}",
                )

                # Add grounding-specific instructions
                prompt += "\n\nIMPORTANT: Search for the most current solutions, patches, and troubleshooting guides. Include recent forum discussions and community solutions."
                prompt += "\n\nNOTE: No screenshot is available. Base your analysis on the error description and system specifications, supplemented with current web information."

                # Send grounded request
                use_search = enable_search if enable_search is not None else self.enable_search_grounding
                response = self._send_grounded_text_request(prompt, url_context, use_search)

                # Parse response
                if isinstance(response, GroundingResponse):
                    parsed_response = self.prompt_engineer.validate_prompt_response(response.text)

                    # Add grounding metadata
                    parsed_response["grounding_metadata"] = {
                        "has_grounding": response.has_grounding,
                        "search_queries": response.search_queries,
                        "sources": response.sources,
                        "citations": response.citations,
                        "text_with_citations": response.get_text_with_citations(),
                    }
                else:
                    parsed_response = self.prompt_engineer.validate_prompt_response(response)
                    parsed_response["grounding_metadata"] = {"has_grounding": False}

                # Add metadata
                parsed_response["analysis_metadata"] = {
                    "model_used": self.model_name,
                    "error_type": error_type,
                    "analysis_type": "grounded_text_analysis",
                    "analysis_timestamp": time.time(),
                    "request_id": self.request_count,
                    "sdk_version": "google-genai-official",
                    "search_grounding_enabled": use_search,
                }

                self.logger.info(
                    f"Grounded text analysis completed with confidence {parsed_response.get('confidence_score', 0):.2f}"
                )
                return {"success": True, "analysis": parsed_response}

        except Exception as e:
            self.logger.error(f"Grounded text analysis failed: {e}")
            if isinstance(e, (AIClientError, APIKeyError)):
                return {"success": False, "error": str(e)}
            return {"success": False, "error": f"Grounded text analysis failed: {e}"}

    def test_connection(self) -> Dict[str, Any]:
        """
        Test the API connection and configuration.

        Returns:
            Dictionary with test results
        """
        try:
            if not self.client:
                return {
                    "success": False,
                    "error": "Client not initialized (no API key)",
                    "details": "Please set a valid API key first",
                }

            # Simple test request using new SDK
            test_prompt = "Respond with 'Connection test successful' if you can read this."

            with PerformanceTimer("Connection test") as timer:
                try:
                    response = self.client.models.generate_content(model=self.model_name, contents=test_prompt)

                    # Handle response
                    if hasattr(response, "text") and response.text and "successful" in response.text.lower():
                        # Update token usage - use safe attribute access
                        usage = getattr(response, "usage", None)
                        if usage is not None:
                            # Get total tokens from usage object
                            total_tokens = getattr(usage, "total_tokens", None) or getattr(
                                usage, "total_token_count", 0
                            )
                            if total_tokens > 0:
                                self.total_tokens_used += total_tokens

                        return {
                            "success": True,
                            "model": self.model_name,
                            "response_time": timer.duration or 0.0,
                            "message": "API connection working properly",
                            "sdk_version": "google-genai-official",
                        }
                    else:
                        return {
                            "success": False,
                            "error": "Unexpected response from API",
                            "response": (
                                response.text[:200] if hasattr(response, "text") and response.text else "No response"
                            ),
                        }

                except Exception as api_error:
                    # Handle specific API errors
                    error_str = str(api_error)
                    if "429" in error_str or "quota" in error_str.lower():
                        return {
                            "success": False,
                            "error": error_str,
                            "error_type": "quota_exceeded",
                            "suggestion": "API quota exceeded. Get a new API key or wait for quota reset.",
                        }
                    elif "401" in error_str or "403" in error_str or "INVALID_ARGUMENT" in error_str:
                        return {
                            "success": False,
                            "error": error_str,
                            "error_type": "invalid_api_key",
                            "suggestion": "Invalid API key. Check your API key and try again.",
                        }
                    else:
                        return {
                            "success": False,
                            "error": error_str,
                            "suggestion": "Check API key and internet connection",
                        }

        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return {"success": False, "error": str(e), "suggestion": "Check API key and internet connection"}

    def test_grounding_connection(self) -> Dict[str, Any]:
        """
        Test the Google Search grounding functionality.

        Returns:
            Dictionary with grounding test results
        """
        try:
            if not self.client:
                return {
                    "success": False,
                    "error": "Client not initialized (no API key)",
                    "details": "Please set a valid API key first",
                }

            # Simple grounding test
            test_prompt = "What was the latest Windows 11 update released this month? Provide the version number and key features."

            with PerformanceTimer("Grounding connection test") as timer:
                try:
                    # Create grounding tool using the corrected official SDK format
                    if not GENAI_AVAILABLE or types is None:
                        return {
                            "success": False,
                            "error": "Google GenAI SDK not available",
                            "details": "google-genai library not installed or not accessible",
                        }

                    # Create proper grounding tool
                    grounding_tool = types.Tool(google_search=types.GoogleSearch())
                    config = types.GenerateContentConfig(tools=[grounding_tool])

                    # Send grounded request
                    response = self.client.models.generate_content(
                        model=self.model_name, contents=test_prompt, config=config
                    )

                    # Check if response has grounding metadata
                    has_grounding = False
                    search_queries = []
                    sources_count = 0

                    if hasattr(response, "candidates") and response.candidates:
                        candidate = response.candidates[0]
                        if hasattr(candidate, "grounding_metadata") and candidate.grounding_metadata:
                            has_grounding = True
                            search_queries = getattr(candidate.grounding_metadata, "web_search_queries", [])
                            grounding_chunks = getattr(candidate.grounding_metadata, "grounding_chunks", [])
                            sources_count = len(grounding_chunks)

                    # Update token usage
                    usage = getattr(response, "usage", None)
                    if usage is not None:
                        total_tokens = getattr(usage, "total_tokens", 0)
                        if total_tokens > 0:
                            self.total_tokens_used += total_tokens

                    return {
                        "success": True,
                        "model": self.model_name,
                        "response_time": timer.duration or 0.0,
                        "grounding_enabled": has_grounding,
                        "search_queries_executed": len(search_queries),
                        "sources_found": sources_count,
                        "search_queries": search_queries,
                        "message": f"Grounding test {'successful' if has_grounding else 'completed without grounding'}",
                        "sdk_version": "google-genai-official",
                    }

                except Exception as api_error:
                    error_str = str(api_error)
                    if "429" in error_str or "quota" in error_str.lower():
                        return {
                            "success": False,
                            "error": error_str,
                            "error_type": "quota_exceeded",
                            "suggestion": "API quota exceeded. Get a new API key or wait for quota reset.",
                        }
                    elif "401" in error_str or "403" in error_str or "INVALID_ARGUMENT" in error_str:
                        return {
                            "success": False,
                            "error": error_str,
                            "error_type": "invalid_api_key",
                            "suggestion": "Invalid API key. Check your API key and try again.",
                        }
                    elif "google_search" in error_str.lower() or "tools" in error_str.lower():
                        return {
                            "success": False,
                            "error": error_str,
                            "error_type": "grounding_not_available",
                            "suggestion": "Google Search grounding may not be available for your API key, region, or model.",
                        }
                    else:
                        return {
                            "success": False,
                            "error": error_str,
                            "suggestion": "Check API key, internet connection, and grounding availability",
                        }

        except Exception as e:
            self.logger.error(f"Grounding connection test failed: {e}")
            return {
                "success": False,
                "error": str(e),
                "suggestion": "Check API key, internet connection, and grounding support",
            }

    def _validate_analysis_inputs(self, image_path: str, system_specs: Dict[str, Any]) -> None:
        """
        Validate inputs for error analysis.

        Args:
            image_path: Path to the image file
            system_specs: System specifications dictionary

        Raises:
            AIClientError: If validation fails
        """
        if not self.client:
            raise APIKeyError("AI client not initialized. Please set API key first.")

        if not Path(image_path).exists():
            raise ImageProcessingError(f"Image file not found: {image_path}")

        if not isinstance(system_specs, dict) or not system_specs:
            raise AIClientError("System specifications must be a non-empty dictionary")

        # Check for minimum required system info
        required_sections = ["os_information", "hardware_specs"]
        missing_sections = [section for section in required_sections if section not in system_specs]
        if missing_sections:
            self.logger.warning(f"Missing system specification sections: {missing_sections}")

    def _process_image_for_genai(self, image_path: str) -> tuple[bytes, str]:
        """
        Process and validate image for the new GenAI API.

        Args:
            image_path: Path to the image file

        Returns:
            Tuple of (image_bytes, mime_type) for creating types.Part objects

        Raises:
            ImageProcessingError: If image processing fails
        """
        try:
            image_file = Path(image_path)

            # Check file size (Gemini has limits)
            max_size_mb = 20
            file_size_mb = image_file.stat().st_size / (1024 * 1024)
            if file_size_mb > max_size_mb:
                raise ImageProcessingError(f"Image file too large: {file_size_mb:.1f}MB (max: {max_size_mb}MB)")

            # Check file format
            allowed_formats = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
            if image_file.suffix.lower() not in allowed_formats:
                raise ImageProcessingError(f"Unsupported image format: {image_file.suffix}")

            # Read image data as bytes
            with open(image_file, "rb") as f:
                image_bytes = f.read()

            # Determine MIME type more accurately
            mime_type_mapping = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
                ".bmp": "image/bmp",
            }

            file_ext = image_file.suffix.lower()
            mime_type = mime_type_mapping.get(file_ext, f"image/{file_ext[1:]}")

            self.logger.info(f"Processed image for AI analysis: {image_path} ({file_size_mb:.1f}MB, {mime_type})")

            return image_bytes, mime_type

        except Exception as e:
            self.logger.error(f"Image processing failed: {e}")
            if isinstance(e, ImageProcessingError):
                raise
            raise ImageProcessingError(f"Failed to process image {image_path}: {e}")

    def _get_thinking_config(self) -> Optional[Any]:
        """
        Get the thinking configuration based on model capabilities using official SDK format.

        Returns:
            GenerateContentConfig with thinking configuration or None if not supported
        """
        try:
            # Check if thinking is supported by the current model
            if not GENAI_AVAILABLE or types is None or not hasattr(types, "ThinkingConfig"):
                return None

            # Map user-friendly budget settings to API values
            budget_value = self._map_thinking_budget(self.thinking_budget)

            # Create thinking configuration using official SDK format
            thinking_config = types.ThinkingConfig(thinking_budget=budget_value)

            # Return the complete GenerateContentConfig
            return types.GenerateContentConfig(thinking_config=thinking_config)

        except Exception as e:
            self.logger.warning(f"Failed to create thinking configuration: {e}")
            return None

    def _is_pro_model(self) -> bool:
        """
        Check if the current model is a Pro model with enhanced thinking capabilities.

        Returns:
            True if using a Pro model, False otherwise
        """
        return self.model_name in ["gemini-2.5-pro", "gemini-1.5-pro"]

    def _map_thinking_budget(self, budget: str) -> int:
        """
        Map thinking budget settings to official Google API values.

        Official ranges:
        - Gemini 2.5 Pro: 128-32768 (cannot disable thinking)
        - Gemini 2.5 Flash: 0-24576 (can disable thinking)
        - Gemini 2.5 Flash-Lite: 512-24576 (can disable thinking)

        Args:
            budget: Budget setting (-1 for dynamic, 0 to disable, or numeric value)

        Returns:
            Integer value for API
        """
        try:
            # Handle numeric string values directly (new official format)
            budget_value = int(budget)

            # Validate ranges based on model type
            if "2.5-pro" in self.model_name:
                # Pro model: cannot disable thinking, minimum 128
                if budget_value == 0:
                    self.logger.warning("Cannot disable thinking on Pro models, using minimum (128)")
                    return 128
                elif budget_value == -1:
                    return -1  # Dynamic thinking
                else:
                    return max(128, min(budget_value, 32768))

            elif "2.5-flash-lite" in self.model_name:
                # Flash-Lite model: 512-24576 or 0 to disable
                if budget_value == 0:
                    return 0  # Disable thinking
                elif budget_value == -1:
                    return -1  # Dynamic thinking
                else:
                    return max(512, min(budget_value, 24576))

            elif "2.5-flash" in self.model_name:
                # Flash model: 0-24576
                if budget_value == -1:
                    return -1  # Dynamic thinking
                else:
                    return max(0, min(budget_value, 24576))

            else:
                # Other models: use reasonable defaults
                if budget_value == -1:
                    return -1
                else:
                    return max(0, min(budget_value, 16384))

        except ValueError:
            # Handle legacy string values for backward compatibility
            legacy_mapping = {
                "AUTO": -1,
                "DYNAMIC": -1,
                "HIGH": 4096,
                "MEDIUM": 2048,
                "STANDARD": 1024,
                "LIGHT": 512,
                "DISABLED": 0,
                "SPEED": 1024,
                "QUALITY": 4096,
                "PRO": 4096,
                "MAXIMUM": 8192,
            }

            mapped_value = legacy_mapping.get(budget.upper())
            if mapped_value is not None:
                # Apply model-specific validation to legacy values
                return self._map_thinking_budget(str(mapped_value))

            # Default to dynamic thinking for unrecognized values
            self.logger.warning(f"Unrecognized thinking budget '{budget}', using dynamic (-1)")
            return -1

    @retry_on_exception(max_retries=3, delay=2.0, exceptions=(Exception,))
    def _send_multimodal_request(self, prompt: str, image_part) -> str:
        """
        Send multimodal request to Gemini API with rate limiting.

        Args:
            prompt: Analysis prompt text
            image_part: Image Part object created with types.Part.from_bytes()

        Returns:
            Raw API response text

        Raises:
            AIClientError: If API request fails
        """
        try:
            # Rate limiting
            time_since_last_request = time.time() - self.last_request_time
            if time_since_last_request < self.rate_limit_delay:
                time.sleep(self.rate_limit_delay - time_since_last_request)

            # Prepare the content for new SDK - proper format with Part objects
            # According to official documentation: https://ai.google.dev/gemini-api/docs/vision
            contents = [image_part, prompt]  # types.Part object for image  # Text prompt as string

            # Get thinking configuration
            thinking_config = self._get_thinking_config()

            # Build request configuration
            request_config = {"model": self.model_name, "contents": contents}

            # Add thinking config if available
            if thinking_config:
                request_config["config"] = thinking_config

            # Start thinking timer
            self.thinking_start_time = time.time()

            # Send the request using new SDK
            with PerformanceTimer("Gemini API multimodal request") as timer:
                if not self.client:
                    raise AIClientError("Client not initialized")

                # Use getattr to safely access generate_content
                model = getattr(self.client, "models", None)
                if model is None:
                    raise AIClientError("Client model access failed")

                generate_content = getattr(model, "generate_content", None)
                if generate_content is None:
                    raise AIClientError("generate_content not available")

                # Check if streaming is available
                if hasattr(model, "generate_content_stream") and self.enable_streaming:
                    self.logger.debug("Using streaming API for multimodal request")
                    response = ""
                    thinking_parts = []

                    # Use streaming API
                    for chunk in model.generate_content_stream(**request_config):
                        if hasattr(chunk, "candidates") and chunk.candidates:
                            candidate = chunk.candidates[0]
                            if hasattr(candidate, "content") and candidate.content:
                                for part in candidate.content.parts:
                                    if part and hasattr(part, "thought") and part.thought:
                                        thinking_parts.append(part.text)
                                        self.logger.debug(f"Thinking step: {part.text}")
                                    elif part and hasattr(part, "text") and part.text:
                                        response += part.text
                                        # Only log progress periodically to avoid spam
                                        if len(response) % 100 == 0:  # Log every 100 characters
                                            self.logger.debug(f"Received {len(response)} characters so far...")

                    # Create a response object with combined text
                    candidates = [{"content": {"parts": thinking_parts + [{"text": response}]}}]

                    # Create StreamResponse with usage info
                    usage_info = {"total_tokens": self.total_tokens_used, "thinking_tokens": self.thinking_tokens_used}
                    response_obj = StreamResponse(response, candidates, usage_info)
                else:
                    # Use regular generate_content
                    response_obj = generate_content(**request_config)

            # Update thinking metrics
            self.thinking_requests_count += 1
            if self.thinking_start_time:
                self.thinking_duration += time.time() - self.thinking_start_time

            # Update token usage
            if hasattr(response_obj, "usage") and response_obj.usage is not None:
                usage = response_obj.usage
                # Use getattr with default values to handle missing attributes
                self.total_tokens_used += getattr(usage, "total_tokens", 0)
                self.thinking_tokens_used += getattr(usage, "thinking_tokens", 0)

                # Record thinking metrics
                thinking_tokens = getattr(usage, "thinking_tokens", 0)
                thinking_budget = getattr(usage, "thinking_budget", 0)

                # Update performance timer with thinking metrics
                if hasattr(timer, "record_thinking_metrics"):
                    timer.record_thinking_metrics(
                        thinking_tokens, (thinking_tokens / thinking_budget * 100) if thinking_budget > 0 else 0
                    )

            # Update tracking
            self.request_count += 1
            self.last_request_time = time.time()

            # Record successful model usage
            self.fallback_manager.record_success(self.model_name)

            self.logger.debug(f"Multimodal API request successful, response length: {len(response_obj.text)}")
            return response_obj.text

        except Exception as e:
            self.logger.error(f"Multimodal API request failed: {e}")
            error_str = str(e)

            # Record rate limiting for intelligent fallback
            if "429" in error_str or "RATE_LIMIT" in error_str.upper() or "QUOTA" in error_str.upper():
                self.fallback_manager.record_rate_limit(self.model_name)

                # Try fallback model if available
                fallback_model = self.fallback_manager.get_next_available_model(self.model_name, error_str)
                if fallback_model:
                    self.logger.info(f"Trying fallback model: {fallback_model}")
                    original_model = self.model_name
                    self.model_name = fallback_model
                    try:
                        # Retry with fallback model
                        return self._send_multimodal_request(prompt, image_part)
                    finally:
                        # Restore original model
                        self.model_name = original_model

            # Handle specific error types
            if "API_KEY" in error_str.upper() or "INVALID_ARGUMENT" in error_str.upper():
                raise APIKeyError(f"API key error: {e}")
            if (
                "QUOTA" in error_str.upper()
                or "RATE_LIMIT" in error_str.upper()
                or "429" in error_str
                or "RESOURCE_EXHAUSTED" in error_str
            ):
                # Mark quota exhausted for this model
                self.fallback_manager.mark_quota_exhausted(self.model_name)
                raise AIClientError(f"API quota/rate limit exceeded for {self.model_name}: {e}")
            raise AIClientError(f"Multimodal API request failed: {e}")

    @retry_on_exception(max_retries=3, delay=2.0, exceptions=(Exception,))
    def _send_text_request(self, prompt: str) -> str:
        """
        Send text-only request to Gemini API.

        Args:
            prompt: Analysis prompt text

        Returns:
            Raw API response text
        """
        try:
            # Rate limiting
            time_since_last_request = time.time() - self.last_request_time
            if time_since_last_request < self.rate_limit_delay:
                time.sleep(self.rate_limit_delay - time_since_last_request)

            # Get thinking configuration
            thinking_config = self._get_thinking_config()

            # Build request configuration
            request_config = {"model": self.model_name, "contents": prompt}

            # Add thinking config if available
            if thinking_config:
                request_config["config"] = thinking_config

            # Start thinking timer
            self.thinking_start_time = time.time()

            # Send the request using new SDK
            with PerformanceTimer("Gemini API text request") as timer:
                if not self.client:
                    raise AIClientError("Client not initialized")

                # Use getattr to safely access generate_content
                model = getattr(self.client, "models", None)
                if model is None:
                    raise AIClientError("Client model access failed")

                generate_content = getattr(model, "generate_content", None)
                if generate_content is None:
                    raise AIClientError("generate_content not available")

                response = generate_content(**request_config)

                # Get response text
                if not hasattr(response, "text") or not response.text:
                    raise AIResponseError("Empty response from Gemini API")

                response_text = response.text.strip()

            # Update thinking metrics
            self.thinking_requests_count += 1
            if self.thinking_start_time:
                self.thinking_duration += time.time() - self.thinking_start_time

            # Update token usage
            if hasattr(response, "usage") and response.usage is not None:
                usage = response.usage
                # Use getattr with default values to handle missing attributes
                self.total_tokens_used += getattr(usage, "total_tokens", 0)
                self.thinking_tokens_used += getattr(usage, "thinking_tokens", 0)

                # Record thinking metrics
                thinking_tokens = getattr(usage, "thinking_tokens", 0)
                thinking_budget = getattr(usage, "thinking_budget", 0)

                # Update performance timer with thinking metrics
                if hasattr(timer, "record_thinking_metrics"):
                    timer.record_thinking_metrics(
                        thinking_tokens, (thinking_tokens / thinking_budget * 100) if thinking_budget > 0 else 0
                    )

            # Update tracking
            self.request_count += 1
            self.last_request_time = time.time()

            # Record successful model usage
            self.fallback_manager.record_success(self.model_name)

            self.logger.debug(f"Text API request successful, response length: {len(response_text)}")
            return response_text

        except Exception as e:
            self.logger.error(f"Text API request failed: {e}")
            error_str = str(e)

            # Record rate limiting for intelligent fallback
            if "429" in error_str or "RATE_LIMIT" in error_str.upper() or "QUOTA" in error_str.upper():
                self.fallback_manager.record_rate_limit(self.model_name)

                # Try fallback model if available
                fallback_model = self.fallback_manager.get_next_available_model(self.model_name, error_str)
                if fallback_model:
                    self.logger.info(f"Trying fallback model: {fallback_model}")
                    original_model = self.model_name
                    self.model_name = fallback_model
                    try:
                        # Retry with fallback model
                        return self._send_text_request(prompt)
                    finally:
                        # Restore original model
                        self.model_name = original_model

            # Handle specific error types
            if "API_KEY" in error_str.upper() or "INVALID_ARGUMENT" in error_str.upper():
                raise APIKeyError(f"API key error: {e}")
            if (
                "QUOTA" in error_str.upper()
                or "RATE_LIMIT" in error_str.upper()
                or "429" in error_str
                or "RESOURCE_EXHAUSTED" in error_str
            ):
                # Mark quota exhausted for this model
                self.fallback_manager.mark_quota_exhausted(self.model_name)
                raise AIClientError(f"API quota/rate limit exceeded for {self.model_name}: {e}")
            raise AIClientError(f"Text API request failed: {e}")

    def get_available_models(self) -> List[str]:
        """
        Get list of available Gemini models with dynamic checking.

        Returns:
            List of available model names
        """
        # Core models that should always be available
        core_models = ["gemini-2.5-pro", "gemini-2.5-flash", "gemini-1.5-pro", "gemini-1.5-flash"]

        # Extended models that may be available
        extended_models = ["gemini-2.5-flash-lite", "gemini-2.0-flash"]

        available_models = []

        # Always include core models for backward compatibility
        available_models.extend(core_models)

        # Try to check extended models if client is available
        if self.client:
            try:
                # For now, include extended models by default
                # In the future, this could be enhanced with actual API checking
                available_models.extend(extended_models)
                self.logger.debug(f"Extended models added: {extended_models}")
            except Exception as e:
                self.logger.warning(f"Could not check extended model availability: {e}")

        self.logger.info(f"Available models: {available_models}")
        return available_models

    def validate_model(self, model_name: str) -> bool:
        """
        Validate if a model name is supported.

        Args:
            model_name: Name of the model to validate

        Returns:
            True if model is supported, False otherwise
        """
        available_models = self.get_available_models()
        is_valid = model_name in available_models

        if not is_valid:
            self.logger.warning(f"Model '{model_name}' is not in available models: {available_models}")

        return is_valid

    def get_quota_status(self) -> Dict[str, Any]:
        """
        Get current quota status and recommendations.

        Returns:
            Dictionary with quota status and user-friendly recommendations
        """
        try:
            if not self.client:
                return {
                    "success": False,
                    "error": "Client not initialized",
                    "recommendation": "Please set a valid API key first",
                }

            fallback_status = self.fallback_manager.get_quota_status()

            current_model_available = self.fallback_manager.is_quota_available(self.model_name)

            status = {
                "success": True,
                "current_model": self.model_name,
                "current_model_available": current_model_available,
                "quota_exhausted_models": fallback_status["quota_exhausted_models"],
                "available_models": fallback_status["available_models"],
                "total_requests": self.request_count,
                "total_tokens": self.total_tokens_used,
            }

            # Provide user-friendly recommendations
            if not current_model_available:
                if fallback_status["available_models"]:
                    recommended = fallback_status["available_models"][0]
                    status["recommendation"] = (
                        f"Current model ({self.model_name}) quota exhausted. Try switching to {recommended}."
                    )
                    status["recommended_model"] = recommended
                else:
                    status["recommendation"] = (
                        "All models appear to have quota issues. Please wait or check your API plan."
                    )
            else:
                status["recommendation"] = f"Current model ({self.model_name}) is available and ready to use."

            # Add quota conservation tips
            if len(fallback_status["quota_exhausted_models"]) > 0:
                status["tips"] = [
                    "Consider using Flash models (gemini-2.5-flash) instead of Pro models to conserve quota",
                    "Reduce the frequency of API calls during development",
                    "Check your API usage at https://aistudio.google.com/",
                    "Consider upgrading your API plan for higher quotas",
                ]

            return status

        except Exception as e:
            self.logger.error(f"Failed to get quota status: {e}")
            return {
                "success": False,
                "error": str(e),
                "recommendation": "Unable to check quota status. Please verify your API key and connection.",
            }

    def get_thinking_stats(self) -> Dict[str, Any]:
        """
        Get statistics about thinking process usage.

        Returns:
            Dictionary with thinking process statistics
        """
        if self.thinking_requests_count == 0:
            avg_duration = 0
            avg_tokens = 0
        else:
            avg_duration = self.thinking_duration / self.thinking_requests_count
            avg_tokens = self.thinking_tokens_used / self.thinking_requests_count

        return {
            "thinking_requests": self.thinking_requests_count,
            "total_thinking_duration": self.thinking_duration,
            "average_thinking_duration": avg_duration,
            "thinking_tokens_used": self.thinking_tokens_used,
            "average_tokens_per_request": avg_tokens,
        }

    def get_usage_stats(self) -> Dict[str, Any]:
        """
        Get comprehensive usage statistics for the AI client.

        This method provides detailed usage metrics including token consumption,
        request counts, and thinking process statistics for monitoring and optimization.

        Returns:
            Dictionary containing usage statistics:
            - total_tokens_used: Total API tokens consumed across all requests
            - thinking_tokens_used: Tokens used specifically for thinking processes
            - request_count: Total number of API requests made
            - thinking_requests_count: Number of requests that used thinking
            - model_name: Currently configured model
            - average_tokens_per_request: Average token consumption per request
            - thinking_duration: Total time spent in thinking processes
        """
        # Calculate averages with safe division
        avg_tokens_per_request = self.total_tokens_used / self.request_count if self.request_count > 0 else 0

        avg_thinking_tokens = (
            self.thinking_tokens_used / self.thinking_requests_count if self.thinking_requests_count > 0 else 0
        )

        return {
            "total_tokens_used": self.total_tokens_used,
            "thinking_tokens_used": self.thinking_tokens_used,
            "request_count": self.request_count,
            "thinking_requests_count": self.thinking_requests_count,
            "model_name": self.model_name,
            "average_tokens_per_request": avg_tokens_per_request,
            "average_thinking_tokens_per_request": avg_thinking_tokens,
            "thinking_duration": self.thinking_duration,
            "last_request_time": self.last_request_time,
            "rate_limit_delay": self.rate_limit_delay,
            "grounding_enabled": self.enable_search_grounding,
            "streaming_enabled": self.enable_streaming,
        }

    def _create_search_grounding_tools(self, url_context: Optional[List[str]] = None) -> List[Any]:
        """
        Create Google Search grounding tools for the request (deprecated method for compatibility).

        Note: This method is deprecated. The new implementation uses types.Tool(google_search=types.GoogleSearch())
        directly in the request methods.

        Args:
            url_context: Optional list of URLs to include as context

        Returns:
            Empty list (this method is no longer used)
        """
        self.logger.warning("_create_search_grounding_tools is deprecated - using direct tool creation instead")
        return []

    def _send_grounded_multimodal_request(
        self, prompt: str, image_part, url_context: Optional[List[str]] = None, enable_search: bool = True
    ) -> Union[str, GroundingResponse]:
        """
        Send multimodal request with Google Search grounding.

        Args:
            prompt: Analysis prompt text
            image_part: Image Part object
            url_context: Optional list of URLs for context
            enable_search: Whether to enable search grounding

        Returns:
            GroundingResponse with search metadata or plain text response
        """
        try:
            # If grounding is disabled, fall back to regular multimodal request
            if not enable_search:
                self.logger.debug("Grounding disabled, using regular multimodal request")
                response_text = self._send_multimodal_request(prompt, image_part)
                return GroundingResponse(text=response_text, grounding_metadata=None)

            # Try grounded request first
            try:
                # Rate limiting
                time_since_last_request = time.time() - self.last_request_time
                if time_since_last_request < self.rate_limit_delay:
                    time.sleep(self.rate_limit_delay - time_since_last_request)

                # Prepare the content
                contents = [image_part, prompt]

                # Add URL context to prompt if provided
                if url_context:
                    url_text = "\n\nADDITIONAL CONTEXT URLs:\n" + "\n".join(f"- {url}" for url in url_context)
                    prompt += url_text
                    contents = [image_part, prompt]  # Update with enhanced prompt

                # Get thinking configuration
                thinking_config = self._get_thinking_config()

                # Build request configuration with corrected grounding tools
                if not GENAI_AVAILABLE or types is None:
                    raise AIClientError("Google GenAI SDK not available")

                # Create proper grounding tool using official SDK format
                grounding_tool = types.Tool(google_search=types.GoogleSearch())

                # Build config with correct structure
                config = types.GenerateContentConfig(tools=[grounding_tool])

                # Add thinking config if available
                if thinking_config and hasattr(thinking_config, "thinking_config"):
                    config.thinking_config = thinking_config.thinking_config

                # Send the request
                with PerformanceTimer("Grounded multimodal API request") as timer:
                    if not self.client:
                        raise AIClientError("Client not initialized")

                    model = getattr(self.client, "models", None)
                    if model is None:
                        raise AIClientError("Client model access failed")

                    generate_content = getattr(model, "generate_content", None)
                    if generate_content is None:
                        raise AIClientError("generate_content not available")

                    response = generate_content(model=self.model_name, contents=contents, config=config)

                # Process response and extract grounding metadata
                if hasattr(response, "candidates") and response.candidates:
                    candidate = response.candidates[0]

                    # Extract grounding metadata if available
                    grounding_metadata = None
                    if hasattr(candidate, "grounding_metadata") and candidate.grounding_metadata:
                        grounding_metadata = {
                            "webSearchQueries": getattr(candidate.grounding_metadata, "web_search_queries", []),
                            "groundingChunks": getattr(candidate.grounding_metadata, "grounding_chunks", []),
                            "groundingSupports": getattr(candidate.grounding_metadata, "grounding_supports", []),
                        }
                        search_queries = grounding_metadata.get("webSearchQueries", []) or []
                        self.logger.info(f"Grounding metadata found: {len(search_queries)} search queries")

                    # Create GroundingResponse
                    usage_info = getattr(response, "usage", None)
                    usage_dict = {}
                    if usage_info:
                        usage_dict = {
                            "total_tokens": getattr(usage_info, "total_tokens", 0),
                            "thinking_tokens": getattr(usage_info, "thinking_tokens", 0),
                        }

                    grounded_response = GroundingResponse(
                        text=response.text, grounding_metadata=grounding_metadata, usage=usage_dict
                    )

                    # Update token tracking
                    if usage_info:
                        self.total_tokens_used += getattr(usage_info, "total_tokens", 0)
                        self.thinking_tokens_used += getattr(usage_info, "thinking_tokens", 0)

                    # Update request tracking
                    self.request_count += 1
                    self.last_request_time = time.time()
                    self.fallback_manager.record_success(self.model_name)

                    return grounded_response

                else:
                    # Fallback to text response if no candidates
                    return response.text if hasattr(response, "text") else "No response generated"

            except Exception as grounding_error:
                # Log the grounding error but don't fail the request
                self.logger.warning(f"Grounding failed, falling back to regular analysis: {grounding_error}")

                # Fall back to regular multimodal request
                response_text = self._send_multimodal_request(prompt, image_part)
                return GroundingResponse(
                    text=response_text,
                    grounding_metadata={"fallback_used": True, "grounding_error": str(grounding_error)},
                )

        except Exception as e:
            self.logger.error(f"Grounded multimodal request failed completely: {e}")

            # Handle fallback scenarios
            error_str = str(e)
            if "429" in error_str or "RATE_LIMIT" in error_str.upper():
                self.fallback_manager.record_rate_limit(self.model_name)
                fallback_model = self.fallback_manager.get_next_available_model(self.model_name, error_str)
                if fallback_model:
                    original_model = self.model_name
                    self.model_name = fallback_model
                    try:
                        return self._send_grounded_multimodal_request(prompt, image_part, url_context, enable_search)
                    finally:
                        self.model_name = original_model

            raise AIClientError(f"Grounded multimodal request failed: {e}")

    def _send_grounded_text_request(
        self, prompt: str, url_context: Optional[List[str]] = None, enable_search: bool = True
    ) -> Union[str, GroundingResponse]:
        """
        Send text request with Google Search grounding.

        Args:
            prompt: Analysis prompt text
            url_context: Optional list of URLs for context
            enable_search: Whether to enable search grounding

        Returns:
            GroundingResponse with search metadata or plain text response
        """
        try:
            # If grounding is disabled, fall back to regular text request
            if not enable_search:
                self.logger.debug("Grounding disabled, using regular text request")
                response_text = self._send_text_request(prompt)
                return GroundingResponse(text=response_text, grounding_metadata=None)

            # Try grounded request first
            try:
                # Rate limiting
                time_since_last_request = time.time() - self.last_request_time
                if time_since_last_request < self.rate_limit_delay:
                    time.sleep(self.rate_limit_delay - time_since_last_request)

                # Add URL context to prompt if provided
                if url_context:
                    url_text = "\n\nADDITIONAL CONTEXT URLs:\n" + "\n".join(f"- {url}" for url in url_context)
                    prompt += url_text

                # Get thinking configuration
                thinking_config = self._get_thinking_config()

                # Build request configuration with corrected grounding tools
                if not GENAI_AVAILABLE or types is None:
                    raise AIClientError("Google GenAI SDK not available")

                # Create proper grounding tool using official SDK format
                grounding_tool = types.Tool(google_search=types.GoogleSearch())

                # Build config with correct structure
                config = types.GenerateContentConfig(tools=[grounding_tool])

                # Add thinking config if available
                if thinking_config and hasattr(thinking_config, "thinking_config"):
                    config.thinking_config = thinking_config.thinking_config

                # Send the request
                with PerformanceTimer("Grounded text API request") as timer:
                    if not self.client:
                        raise AIClientError("Client not initialized")

                    model = getattr(self.client, "models", None)
                    if model is None:
                        raise AIClientError("Client model access failed")

                    generate_content = getattr(model, "generate_content", None)
                    if generate_content is None:
                        raise AIClientError("generate_content not available")

                    response = generate_content(model=self.model_name, contents=prompt, config=config)

                # Process response and extract grounding metadata
                if hasattr(response, "candidates") and response.candidates:
                    candidate = response.candidates[0]

                    # Extract grounding metadata if available
                    grounding_metadata = None
                    if hasattr(candidate, "grounding_metadata") and candidate.grounding_metadata:
                        grounding_metadata = {
                            "webSearchQueries": getattr(candidate.grounding_metadata, "web_search_queries", []),
                            "groundingChunks": getattr(candidate.grounding_metadata, "grounding_chunks", []),
                            "groundingSupports": getattr(candidate.grounding_metadata, "grounding_supports", []),
                        }
                        search_queries = grounding_metadata.get("webSearchQueries", []) or []
                        self.logger.info(f"Grounding metadata found: {len(search_queries)} search queries")

                    # Create GroundingResponse
                    usage_info = getattr(response, "usage", None)
                    usage_dict = {}
                    if usage_info:
                        usage_dict = {
                            "total_tokens": getattr(usage_info, "total_tokens", 0),
                            "thinking_tokens": getattr(usage_info, "thinking_tokens", 0),
                        }

                    grounded_response = GroundingResponse(
                        text=response.text, grounding_metadata=grounding_metadata, usage=usage_dict
                    )

                    # Update token tracking
                    if usage_info:
                        self.total_tokens_used += getattr(usage_info, "total_tokens", 0)
                        self.thinking_tokens_used += getattr(usage_info, "thinking_tokens", 0)

                    # Update request tracking
                    self.request_count += 1
                    self.last_request_time = time.time()
                    self.fallback_manager.record_success(self.model_name)

                    return grounded_response

                else:
                    # Fallback to text response if no candidates
                    return response.text if hasattr(response, "text") else "No response generated"

            except Exception as grounding_error:
                # Log the grounding error but don't fail the request
                self.logger.warning(f"Grounding failed, falling back to regular analysis: {grounding_error}")

                # Fall back to regular text request
                response_text = self._send_text_request(prompt)
                return GroundingResponse(
                    text=response_text,
                    grounding_metadata={"fallback_used": True, "grounding_error": str(grounding_error)},
                )

        except Exception as e:
            self.logger.error(f"Grounded text request failed completely: {e}")

            # Handle fallback scenarios
            error_str = str(e)
            if "429" in error_str or "RATE_LIMIT" in error_str.upper():
                self.fallback_manager.record_rate_limit(self.model_name)
                fallback_model = self.fallback_manager.get_next_available_model(self.model_name, error_str)
                if fallback_model:
                    original_model = self.model_name
                    self.model_name = fallback_model
                    try:
                        return self._send_grounded_text_request(prompt, url_context, enable_search)
                    finally:
                        self.model_name = original_model

            raise AIClientError(f"Grounded text request failed: {e}")
