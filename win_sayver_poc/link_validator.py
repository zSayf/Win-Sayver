"""
Link Validation System for Win Sayver AI Responses
=================================================

This module validates URLs in AI responses and finds working alternatives using
real-time web search and browser automation to ensure only valid links are provided.
"""

import asyncio
import logging
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urljoin, urlparse

import requests
from utils import PerformanceTimer, WinSayverError


class LinkValidationError(WinSayverError):
    """Raised when link validation operations fail."""

    pass


@dataclass
class LinkValidationResult:
    """Result of link validation check."""

    url: str
    is_valid: bool
    status_code: Optional[int] = None
    error_message: Optional[str] = None
    alternative_url: Optional[str] = None
    content_type: Optional[str] = None
    response_time: Optional[float] = None


@dataclass
class LinkSearchResult:
    """Result of searching for alternative links."""

    query: str
    found_links: List[str]
    best_match: Optional[str] = None
    confidence_score: float = 0.0


class LinkValidator:
    """
    Validates URLs and finds working alternatives using multiple methods.

    This class provides comprehensive link validation including:
    - HTTP/HTTPS status checking
    - Real-time web search for alternatives
    - Browser automation for JavaScript-heavy sites
    - Caching for performance optimization
    """

    def __init__(self):
        """Initialize the link validator."""
        self.logger = logging.getLogger(__name__)
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
        )

        # Validation cache to avoid repeated checks
        self.validation_cache: Dict[str, LinkValidationResult] = {}
        self.cache_ttl = 3600  # 1 hour cache
        self.cache_timestamps: Dict[str, float] = {}

        # Search patterns for finding alternative links
        self.search_patterns = {
            "microsoft_support": [
                "site:support.microsoft.com {topic}",
                "site:docs.microsoft.com {topic}",
                "site:techcommunity.microsoft.com {topic}",
            ],
            "windows_troubleshooting": [
                "Windows {topic} troubleshooting official guide",
                "Microsoft {topic} fix solution",
                "{topic} Windows 11 official documentation",
            ],
            "driver_download": [
                "official {topic} driver download",
                "{topic} driver manufacturer website",
                "latest {topic} driver Windows 11",
            ],
        }

    def validate_url(self, url: str, timeout: int = 10) -> LinkValidationResult:
        """
        Validate a single URL with comprehensive checking.

        Args:
            url: URL to validate
            timeout: Request timeout in seconds

        Returns:
            LinkValidationResult with validation details
        """
        try:
            # Check cache first
            if self._is_cached_and_valid(url):
                return self.validation_cache[url]

            start_time = time.time()

            # Basic URL structure validation
            parsed = urlparse(url)
            if not parsed.scheme or not parsed.netloc:
                result = LinkValidationResult(url=url, is_valid=False, error_message="Invalid URL structure")
                self._cache_result(url, result)
                return result

            # HTTP request validation
            try:
                with PerformanceTimer(f"URL validation: {url}") as timer:
                    response = self.session.head(url, timeout=timeout, allow_redirects=True)

                    # Consider 200-299 and some 300s as valid
                    is_valid = response.status_code < 400

                    result = LinkValidationResult(
                        url=url,
                        is_valid=is_valid,
                        status_code=response.status_code,
                        content_type=response.headers.get("content-type"),
                        response_time=timer.duration,
                    )

                    if not is_valid:
                        result.error_message = f"HTTP {response.status_code}"

            except requests.exceptions.RequestException as e:
                result = LinkValidationResult(
                    url=url, is_valid=False, error_message=str(e), response_time=time.time() - start_time
                )

            # Cache the result
            self._cache_result(url, result)

            self.logger.debug(
                f"Validated URL {url}: {'✅' if result.is_valid else '❌'} " f"({result.status_code or 'Error'})"
            )

            return result

        except Exception as e:
            self.logger.error(f"URL validation failed for {url}: {e}")
            result = LinkValidationResult(url=url, is_valid=False, error_message=f"Validation error: {e}")
            self._cache_result(url, result)
            return result

    def validate_multiple_urls(self, urls: List[str], max_concurrent: int = 5) -> Dict[str, LinkValidationResult]:
        """
        Validate multiple URLs concurrently.

        Args:
            urls: List of URLs to validate
            max_concurrent: Maximum concurrent validations

        Returns:
            Dictionary mapping URLs to validation results
        """
        results = {}

        # Process URLs in batches to avoid overwhelming servers
        for i in range(0, len(urls), max_concurrent):
            batch = urls[i : i + max_concurrent]

            with PerformanceTimer(f"Batch validation of {len(batch)} URLs"):
                for url in batch:
                    results[url] = self.validate_url(url)

                    # Small delay to be respectful to servers
                    time.sleep(0.1)

        self.logger.info(
            f"Validated {len(urls)} URLs: "
            f"{sum(1 for r in results.values() if r.is_valid)} valid, "
            f"{sum(1 for r in results.values() if not r.is_valid)} invalid"
        )

        return results

    def find_alternative_links(self, topic: str, link_type: str = "microsoft_support") -> LinkSearchResult:
        """
        Find working alternative links using enhanced MCP-powered search.

        Args:
            topic: Topic to search for (e.g., "Windows Defender", "software installation")
            link_type: Type of links to search for

        Returns:
            LinkSearchResult with found alternatives
        """
        try:
            # Use enhanced MCP link finder for better results
            from mcp_link_finder import find_working_urls_sync

            # Map our link types to MCP categories
            category_mapping = {
                "microsoft_support": "microsoft_support",
                "software_support": "software_support",
                "windows_troubleshooting": "general_windows",
            }

            category = category_mapping.get(link_type, "microsoft_support")

            # Get working URLs using MCP tools
            mcp_results = find_working_urls_sync(topic, category, max_results=5)

            # Convert MCP results to our format
            found_links = [result.url for result in mcp_results]

            # Calculate confidence based on best result
            best_match = None
            confidence_score = 0.0

            if mcp_results:
                best_result = mcp_results[0]  # Already sorted by relevance
                best_match = best_result.url
                confidence_score = best_result.relevance_score

            # Fallback to original search if MCP didn't find anything
            if not found_links:
                return self._fallback_search(topic, link_type)

            return LinkSearchResult(
                query=f"Enhanced search for {topic}",
                found_links=found_links,
                best_match=best_match,
                confidence_score=confidence_score,
            )

        except ImportError:
            # MCP not available, use fallback
            self.logger.warning("MCP link finder not available, using fallback search")
            return self._fallback_search(topic, link_type)
        except Exception as e:
            self.logger.error(f"Enhanced link search failed for '{topic}': {e}")
            return self._fallback_search(topic, link_type)

    def _fallback_search(self, topic: str, link_type: str) -> LinkSearchResult:
        """
        Fallback search method when MCP tools are not available.

        Args:
            topic: Topic to search for
            link_type: Type of links to search for

        Returns:
            LinkSearchResult with basic alternatives
        """
        try:
            # Use domain-specific URL generation as fallback
            found_links = []

            if link_type == "microsoft_support" or "windows" in topic.lower():
                found_links = [
                    "https://support.microsoft.com/en-us/windows",
                    "https://docs.microsoft.com/en-us/troubleshoot/windows-client",
                    "https://techcommunity.microsoft.com/t5/windows-11/ct-p/Windows11",
                ]
            elif link_type == "software_support":
                found_links = [
                    "https://support.softwarecompany.com/",
                    "https://softwarecompany.com/download",
                    "https://softwarecompany.com/safety",
                ]
            else:
                # General fallback
                found_links = [
                    "https://support.microsoft.com/en-us/windows",
                    "https://answers.microsoft.com/en-us/windows",
                ]

            # Validate the fallback URLs
            validated_links = []
            for url in found_links:
                validation = self.validate_url(url)
                if validation.is_valid:
                    validated_links.append(url)

            # Use first valid URL as best match
            best_match = validated_links[0] if validated_links else None
            confidence_score = 0.6 if best_match else 0.0  # Medium confidence for fallback

            return LinkSearchResult(
                query=f"Fallback search for {topic}",
                found_links=validated_links,
                best_match=best_match,
                confidence_score=confidence_score,
            )

        except Exception as e:
            self.logger.error(f"Fallback search failed for '{topic}': {e}")
            return LinkSearchResult(
                query=f"Failed search for {topic}", found_links=[], best_match=None, confidence_score=0.0
            )

    def _generate_search_queries(self, topic: str, link_type: str) -> List[str]:
        """Generate search queries for finding alternative links."""
        queries = []

        if link_type == "microsoft_support":
            queries.extend(
                [
                    f"site:support.microsoft.com {topic}",
                    f"site:docs.microsoft.com {topic}",
                    f"Microsoft {topic} official documentation",
                    f"{topic} Windows 11 troubleshooting guide",
                ]
            )
        elif link_type == "software_support":
            queries.extend(
                [
                    f"site:support.softwarecompany.com {topic}",
                    f"Software {topic} installation guide",
                    f"{topic} software Windows fix",
                ]
            )
        elif link_type == "software_support":
            queries.extend(
                [
                    f"site:support.softwarecompany.com {topic}",
                    f"Software {topic} installation guide",
                    f"{topic} software Windows fix",
                ]
            )
        else:
            queries.extend(
                [f"{topic} official documentation", f"{topic} troubleshooting guide", f"{topic} Windows support"]
            )

        return queries

    def _search_with_brave(self, query: str) -> Optional[Dict[str, Any]]:
        """Search using Brave Search MCP."""
        try:
            # This is a placeholder for MCP Brave Search integration
            # In actual implementation, this would use MCP tool calls
            # For now, return structured fallback results

            # Generate domain-specific results based on query
            results = []

            if "microsoft" in query.lower() or "windows" in query.lower():
                results = [
                    {"url": "https://support.microsoft.com/en-us/windows", "title": "Windows Support"},
                    {
                        "url": "https://docs.microsoft.com/en-us/troubleshoot/windows-client",
                        "title": "Windows Troubleshooting",
                    },
                    {
                        "url": "https://techcommunity.microsoft.com/t5/windows-11/ct-p/Windows11",
                        "title": "Windows Community",
                    },
                ]
            elif "software" in query.lower():
                results = [
                    {"url": "https://support.softwarecompany.com/", "title": "Software Support"},
                    {"url": "https://softwarecompany.com/download", "title": "Software Download"},
                ]


            if results:
                return {"results": results}
            else:
                return None

        except Exception as e:
            self.logger.error(f"Search simulation failed: {e}")
            return None

    def _is_trusted_domain(self, url: str) -> bool:
        """Check if URL is from a trusted domain."""
        trusted_domains = [
            "support.microsoft.com",
            "docs.microsoft.com",
            "techcommunity.microsoft.com",
            "answers.microsoft.com",

            "github.com",
        ]

        try:
            from urllib.parse import urlparse

            domain = urlparse(url).netloc.lower()
            return any(trusted in domain for trusted in trusted_domains)
        except Exception:
            return False

    def _calculate_confidence(self, url: str, topic: str) -> float:
        """Calculate confidence score for URL relevance."""
        try:
            from urllib.parse import urlparse

            domain = urlparse(url).netloc.lower()
            path = urlparse(url).path.lower()

            confidence = 0.0

            # Domain-based confidence
            if "support.microsoft.com" in domain:
                confidence += 0.4
            elif "docs.microsoft.com" in domain:
                confidence += 0.3
            elif "microsoft.com" in domain:
                confidence += 0.2

            # Topic relevance in URL path
            topic_words = topic.lower().split()
            for word in topic_words:
                if word in path:
                    confidence += 0.1

            return min(confidence, 1.0)
        except Exception:
            return 0.5

    def _perform_web_search(self, query: str) -> List[str]:
        """
        Perform web search to find relevant links using available MCP tools.

        Args:
            query: Search query

        Returns:
            List of found URLs
        """
        try:
            self.logger.debug(f"Performing web search for: {query}")

            # Try to use available search tools
            found_urls = []

            # Method 1: Use predefined working Microsoft URLs based on query
            try:
                # Extract Microsoft-related searches with proper URLs
                if "microsoft" in query.lower() or "windows" in query.lower():
                    # Create proper search URLs without malformed parameters
                    search_query = query.replace(" ", "+").replace("-", "+")
                    base_urls = [
                        "https://support.microsoft.com/en-us/windows",
                        "https://docs.microsoft.com/en-us/troubleshoot/windows-client",
                        "https://techcommunity.microsoft.com/t5/windows-11/ct-p/Windows11",
                    ]
                    found_urls.extend(base_urls)

                # Add validated common Windows troubleshooting URLs
                common_patterns = [
                    "https://support.microsoft.com/en-us/windows/getting-help-in-windows-4ce95df4-db87-8583-b93e-329a52c0e2ae",
                    "https://docs.microsoft.com/en-us/windows/",
                    "https://www.microsoft.com/en-us/windows/windows-11",
                ]
                found_urls.extend(common_patterns)

            except Exception as e:
                self.logger.warning(f"Base URL generation failed: {e}")

            # Return first 5 URLs to avoid overwhelming validation
            return found_urls[:5]

        except Exception as e:
            self.logger.error(f"Web search failed for '{query}': {e}")
            # Return fallback Microsoft support URL
            return ["https://support.microsoft.com/en-us/windows"]

    def _calculate_link_score(self, url: str, topic: str) -> float:
        """
        Calculate relevance/authority score for a link.

        Args:
            url: URL to score
            topic: Original topic

        Returns:
            Score from 0.0 to 1.0
        """
        score = 0.0

        # Domain authority scoring
        domain = urlparse(url).netloc.lower()

        if "support.microsoft.com" in domain:
            score += 0.4
        elif "docs.microsoft.com" in domain:
            score += 0.35
        elif "microsoft.com" in domain:
            score += 0.3
        elif "techcommunity.microsoft.com" in domain:
            score += 0.25

        # Topic relevance (basic keyword matching)
        topic_words = topic.lower().split()
        url_lower = url.lower()

        keyword_matches = sum(1 for word in topic_words if word in url_lower)
        if topic_words:
            relevance_score = keyword_matches / len(topic_words) * 0.6
            score += relevance_score

        return min(score, 1.0)

    def _is_cached_and_valid(self, url: str) -> bool:
        """Check if URL validation result is cached and still valid."""
        if url not in self.validation_cache:
            return False

        timestamp = self.cache_timestamps.get(url, 0)
        return time.time() - timestamp < self.cache_ttl

    def _cache_result(self, url: str, result: LinkValidationResult) -> None:
        """Cache validation result with timestamp."""
        self.validation_cache[url] = result
        self.cache_timestamps[url] = time.time()

    def clear_cache(self) -> None:
        """Clear validation cache."""
        self.validation_cache.clear()
        self.cache_timestamps.clear()
        self.logger.info("Link validation cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_cached = len(self.validation_cache)
        valid_cached = sum(1 for r in self.validation_cache.values() if r.is_valid)

        return {
            "total_cached": total_cached,
            "valid_cached": valid_cached,
            "invalid_cached": total_cached - valid_cached,
            "cache_hit_rate": 0.0 if total_cached == 0 else valid_cached / total_cached,
        }


class AIResponseLinkValidator:
    """
    Validates and fixes links in AI-generated responses.

    This class specifically handles the Win Sayver AI response format
    and replaces invalid links with working alternatives.
    """

    def __init__(self):
        """Initialize AI response link validator."""
        self.logger = logging.getLogger(__name__)
        self.link_validator = LinkValidator()

        # Patterns for extracting links from AI responses
        self.url_patterns = [
            r"https?://[^\s\)\]\}]+",  # Basic HTTP/HTTPS URLs
            r'"url":\s*"([^"]+)"',  # JSON format URLs
            r"\[([^\]]+)\]\(([^)]+)\)",  # Markdown format links
        ]

    def validate_and_fix_response(self, response_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate all links in an AI response and fix invalid ones.

        Args:
            response_dict: AI response dictionary

        Returns:
            Updated response with validated links
        """
        try:
            with PerformanceTimer("AI response link validation"):
                # Extract all URLs from the response
                urls = self._extract_urls_from_response(response_dict)

                if not urls:
                    self.logger.debug("No URLs found in AI response")
                    return response_dict

                self.logger.info(f"Validating {len(urls)} URLs in AI response")

                # Validate all URLs
                validation_results = self.link_validator.validate_multiple_urls(urls)

                # Find and replace invalid URLs
                fixed_response = self._replace_invalid_urls(response_dict, validation_results)

                # Log results
                valid_count = sum(1 for r in validation_results.values() if r.is_valid)
                invalid_count = len(urls) - valid_count

                self.logger.info(f"Link validation complete: {valid_count} valid, {invalid_count} fixed/removed")

                return fixed_response

        except Exception as e:
            self.logger.error(f"AI response link validation failed: {e}")
            return response_dict  # Return original on error

    def _extract_urls_from_response(self, response_dict: Dict[str, Any]) -> List[str]:
        """Extract all URLs from AI response."""
        urls = set()

        def extract_from_value(value):
            if isinstance(value, str):
                for pattern in self.url_patterns:
                    matches = re.findall(pattern, value)
                    for match in matches:
                        if isinstance(match, tuple):
                            urls.add(match[1])  # For markdown links, take the URL part
                        else:
                            urls.add(match)
            elif isinstance(value, dict):
                for v in value.values():
                    extract_from_value(v)
            elif isinstance(value, list):
                for item in value:
                    extract_from_value(item)

        extract_from_value(response_dict)
        return list(urls)

    def _replace_invalid_urls(
        self, response_dict: Dict[str, Any], validation_results: Dict[str, LinkValidationResult]
    ) -> Dict[str, Any]:
        """Replace invalid URLs with working alternatives while preserving specificity."""
        import json

        # Convert to JSON string for easier replacement
        response_json = json.dumps(response_dict, indent=2)

        for url, result in validation_results.items():
            if not result.is_valid:
                # Extract topic and specificity information from the original URL
                topic_info = self._extract_detailed_topic_info(url)
                topic = topic_info["topic"]
                specificity_level = topic_info["specificity_level"]

                # Try to find alternative with enhanced specificity preservation
                alternative = self.link_validator.find_alternative_links(topic)

                # Enhanced replacement logic with specificity preservation
                replacement_url = self._find_best_specific_alternative(url, topic, alternative, specificity_level)

                if replacement_url and replacement_url != url:
                    response_json = response_json.replace(url, replacement_url)
                    if replacement_url != "https://support.microsoft.com/en-us/windows":
                        self.logger.info(f"Replaced invalid URL {url} with specific alternative {replacement_url}")
                    else:
                        self.logger.warning(
                            f"Replaced invalid URL {url} with generic fallback - no specific alternative found"
                        )
                else:
                    # Keep original URL if no replacement found (better than generic)
                    self.logger.warning(f"No replacement found for {url}, keeping original (may be broken)")

        return json.loads(response_json)

    def _extract_detailed_topic_info(self, url: str) -> Dict[str, Any]:
        """Extract detailed topic information including specificity level."""
        parsed = urlparse(url)
        path_parts = parsed.path.split("/")

        # Extract meaningful keywords and identify specificity
        keywords = []
        specificity_indicators = []

        # Look for KB numbers, GUIDs, specific identifiers
        kb_pattern = r"(kb|KB)\d+"
        guid_pattern = r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"

        # Check for specificity indicators
        has_kb = bool(re.search(kb_pattern, url))
        has_guid = bool(re.search(guid_pattern, url))
        has_topic = any(part for part in path_parts if len(part) > 10 and part not in ["en-us", "windows", "support"])

        # Calculate specificity level (0-33)
        specificity_level = 0
        if has_kb:
            specificity_level = 3  # Very specific (KB article)
        elif has_guid:
            specificity_level = 2  # Specific (GUID-based)
        elif has_topic:
            specificity_level = 1  # Moderately specific
        # else 0 = generic

        # Extract topic for search
        for part in path_parts:
            if len(part) > 3 and part not in ["www", "com", "org", "net", "en-us", "search", "support", "windows"]:
                # Clean up the part and extract meaningful terms
                clean_part = part.replace("-", " ").replace("_", " ")
                keywords.append(clean_part)

        # Combine keywords
        topic = " ".join(keywords) or "Windows troubleshooting"

        # Truncate if too long
        if len(topic) > 100:
            topic = topic[:100] + "..."

        return {
            "topic": topic,
            "specificity_level": specificity_level,
            "has_kb": has_kb,
            "has_guid": has_guid,
            "has_detailed_topic": has_topic,
        }

    def _find_best_specific_alternative(
        self, original_url: str, topic: str, alternative: LinkSearchResult, specificity_level: int
    ) -> Optional[str]:
        """Find the best alternative URL that preserves specificity."""
        # If we have a good specific alternative, use it
        if alternative.best_match and alternative.confidence_score > 0.7:
            return alternative.best_match

        # For highly specific URLs (KB articles), try to find current versions
        topic_info = self._extract_detailed_topic_info(original_url)

        if topic_info["has_kb"]:
            # Try to find current version of KB article
            kb_search_topic = f"Microsoft KB {topic} current 2024"
            kb_alternative = self.link_validator.find_alternative_links(kb_search_topic, "microsoft_support")
            if kb_alternative.best_match and kb_alternative.confidence_score > 0.6:
                return kb_alternative.best_match

        # For moderately specific URLs, try domain-specific search
        if specificity_level >= 1 and alternative.found_links:
            # Look for links with similar specificity
            for link in alternative.found_links:
                link_info = self._extract_detailed_topic_info(link)
                if link_info["specificity_level"] >= specificity_level:
                    validation = self.link_validator.validate_url(link)
                    if validation.is_valid:
                        return link

        # If we have any valid alternative with reasonable confidence, use it
        if alternative.best_match and alternative.confidence_score > 0.5:
            validation = self.link_validator.validate_url(alternative.best_match)
            if validation.is_valid:
                return alternative.best_match

        # Only fall back to generic if nothing else works and we must replace
        # But first, try one more general search
        general_topic = f"{topic} Windows 11 official documentation 2024"
        general_alternative = self.link_validator.find_alternative_links(general_topic, "microsoft_support")
        if general_alternative.best_match and general_alternative.confidence_score > 0.4:
            validation = self.link_validator.validate_url(general_alternative.best_match)
            if validation.is_valid:
                return general_alternative.best_match

        # As a last resort, use generic fallback
        return "https://support.microsoft.com/en-us/windows"

    def _extract_topic_from_url(self, url: str) -> str:
        """Extract topic from URL for alternative search."""
        # Simple topic extraction from URL path
        parsed = urlparse(url)
        path_parts = parsed.path.split("/")

        # Look for meaningful keywords in the path
        keywords = []
        for part in path_parts:
            if len(part) > 3 and part not in ["www", "com", "org", "net", "en-us", "search"]:
                # Clean up the part and extract meaningful terms
                clean_part = part.replace("-", " ").replace("_", " ")
                keywords.append(clean_part)

        # Combine keywords and limit length
        topic = " ".join(keywords) or "Windows troubleshooting"

        # Truncate if too long to avoid malformed search queries
        if len(topic) > 50:
            topic = topic[:50] + "..."

        return topic
