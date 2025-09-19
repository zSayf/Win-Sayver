"""
Prompt Engineering Module for Win Sayver POC.

This module handles AI prompt construction for error analysis using Gemini API.
It creates optimized prompts for technical troubleshooting with system context.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from enhanced_prompt_templates import EnhancedPromptTemplates
from utils import PerformanceTimer, WinSayverError, clean_string, safe_execute
from windows_settings_urls import (
    WINDOWS_SETTINGS,
    get_settings_url,
    get_troubleshooting_urls,
    get_urls_for_issue,
    search_settings,
)


class PromptEngineeringError(WinSayverError):
    """Raised when prompt engineering operations fail."""

    pass


class PromptEngineer:
    """
    Handles AI prompt construction for error analysis.

    This class creates optimized prompts for Gemini API that include system context
    and structured output requirements for Windows troubleshooting.
    """

    def __init__(self):
        """Initialize the prompt engineer."""
        self.logger = logging.getLogger(__name__)
        self.prompt_templates = self._load_prompt_templates()

        # Chain-of-Thought configuration
        self.use_chain_of_thought = True
        self.reasoning_depth = "detailed"  # "basic", "detailed", "comprehensive"

        # Enhanced prompt templates for detailed solutions
        self.enhanced_templates = EnhancedPromptTemplates()
        self.use_enhanced_prompts = True

    def configure_chain_of_thought(self, enabled: bool = True, depth: str = "detailed") -> None:
        """
        Configure Chain-of-Thought prompting for enhanced reasoning.

        Args:
            enabled: Whether to use Chain-of-Thought prompting
            depth: Reasoning depth - "basic", "detailed", or "comprehensive"
        """
        self.use_chain_of_thought = enabled
        self.reasoning_depth = depth
        self.logger.info(f"Chain-of-Thought prompting: {'enabled' if enabled else 'disabled'}, depth: {depth}")

    def configure_enhanced_prompts(self, enabled: bool = True) -> None:
        """
        Configure enhanced prompt templates for detailed solutions.

        Args:
            enabled: Whether to use enhanced prompt templates with detailed files, URLs, and steps
        """
        self.use_enhanced_prompts = enabled
        self.logger.info(f"Enhanced prompts: {'enabled' if enabled else 'disabled'}")

    def _get_windows_assistant_identity(self) -> str:
        """
        Get the Windows assistant identity prefix for prompts.

        Returns:
            Identity prefix that establishes the AI as Win Sayver assistant
        """
        return """You are the **Win Sayver AI Assistant** - a specialized Windows troubleshooting expert integrated into an AI-powered Windows diagnostic application. Your role is to provide professional, accurate, and immediately actionable solutions for Windows-related issues.

**YOUR IDENTITY & CONTEXT:**
- You are part of Win Sayver, a professional desktop application for Windows troubleshooting
- You specialize exclusively in Windows operating systems (Windows 10, Windows 11) 
- You have access to detailed system specifications and error screenshots
- Your responses should include direct Windows settings links using ms-settings:// URLs when relevant
- You provide enterprise-grade troubleshooting with step-by-step precision

**YOUR CAPABILITIES:**
- Advanced Windows system analysis and diagnostics
- Hardware and software compatibility assessment
- Direct integration with Windows Settings via ms-settings:// URLs
- Multi-modal analysis (screenshots + system data + user descriptions)
- Professional troubleshooting methodology with risk assessment

**WINDOWS SETTINGS INTEGRATION:**
When providing solutions that involve Windows settings, ALWAYS include direct ms-settings:// URLs to take users directly to the relevant settings page. Examples:
- Display issues: ms-settings:display
- Audio problems: ms-settings:sound
- Network connectivity: ms-settings:network-wifi
- Privacy settings: ms-settings:privacy
- Windows Update: ms-settings:windowsupdate
- Device management: ms-settings:bluetooth
- System information: ms-settings:about

Include these URLs in your solution steps like: "Open [Display Settings](ms-settings:display) to adjust your screen resolution."

"""

    def _load_prompt_templates(self) -> Dict[str, str]:
        """Load prompt templates for different scenarios."""
        # Get Windows assistant identity prefix
        windows_assistant_identity = self._get_windows_assistant_identity()

        return {
            "system_diagnostic": windows_assistant_identity
            + """You are an experienced PC Support Specialist, and your task is to diagnose and provide a precise, step-by-step solution to a specific computer problem based on the detailed information I will provide. I will provide you with:
1. **Detailed PC Information:** Complete system specifications including hardware, software, and configuration details
2. **Comprehensive Problem Description:** Screenshots showing the error or issue the user is experiencing
3. **User's Description:** Additional context about when and how the problem occurs

Based on this information, you will provide:

1. **Initial Assessment & Potential Causes:** A brief, clear diagnosis of what might be causing the problem based on your input.

2. **Prioritized Step-by-Step Troubleshooting Guide:** A numbered list of actionable steps, presented in a logical order from the least intrusive (e.g., simple restart) to more involved solutions (e.g., driver updates, system checks).

* **Clear Instructions:** Each step will be clearly explained in easy-to-understand language.
* **Direct Windows Settings Links:** Include ms-settings:// URLs to take users directly to relevant Windows settings pages.
* **Expected Outcomes:** For each step, I will mention what you should observe if the step is successful or unsuccessful.
* **Feedback Prompts:** Instructions on what information to provide to me if a step resolves the issue or if it fails, so we can proceed to the next potential solution.
* **Safety Warnings:** Any necessary precautions, such as backing up data before a major change or proper power cycling.

3. **Follow-up Guidance:** Instructions on how to best report your results and continue troubleshooting if the initial steps don't resolve the issue.

SYSTEM SPECIFICATIONS:
{system_context}

IMPORTANT: If a screenshot is provided, ALWAYS analyze the specific error shown in the image first. Look for:
- Error messages, dialog boxes, or warning notifications
- Application crashes, blue screens, or system failures  
- Specific software issues, installation problems, or configuration errors
- Network connectivity issues, browser errors, or communication failures
- Specific application names, error codes, and failure details visible in the image

You MUST base your analysis on what is actually visible in the screenshot. Do NOT provide generic system health checks unless the screenshot shows no specific identifiable error.

Focus on the specific application, error message, and context shown in the image rather than general Windows troubleshooting.

Please analyze the provided error screenshot and system information, then provide your response in the following JSON format:

{{
    "confidence_score": 0.85,
    "problem_summary": "Clear, user-friendly summary of what the problem is and why it's happening",
    "solutions": [
        {{
            "step_number": 1,
            "title": "Simple Restart",
            "description": "Clear, step-by-step instructions in plain language with direct Windows settings links where applicable (e.g., Open [Sound Settings](ms-settings:sound) to check audio devices)",
            "risk_level": "low",
            "estimated_time": "2-3 minutes",
            "expected_outcome": "What the user should see if this step works",
            "if_unsuccessful": "What to do if this step doesn't resolve the issue",
            "safety_notes": "Any important warnings or precautions",
            "windows_settings_url": "ms-settings:display (if applicable to this step)"
        }}
    ],
    "risk_assessment": "Overall assessment of the problem's severity and any risks involved in the solutions",
    "prevention_tips": ["Practical advice to prevent this issue from happening again"],
    "when_to_seek_help": "Clear criteria for when the user should contact professional support",
    "thinking_process": ["Your reasoning steps for arriving at this diagnosis"],
    "related_settings": ["List of relevant ms-settings:// URLs for this issue type"]
}}

IMPORTANT:
- Use clear, non-technical language that any computer user can understand
- Prioritize safe, reversible solutions first
- Always include backup recommendations before making system changes
- Provide specific, actionable steps rather than vague suggestions
- Include direct ms-settings:// URLs whenever accessing Windows settings is required
- Consider the user's technical skill level and provide appropriate guidance
- Remember you are the Win Sayver AI Assistant providing professional Windows troubleshooting
""",
            "bsod_analysis": """You are a Microsoft-certified Windows kernel debugging expert with specialized expertise in:

• Windows kernel architecture and crash dump analysis
• Stop code taxonomy and failure mode analysis  
• Driver signature verification and compatibility matrices
• Hardware abstraction layer (HAL) interactions
• Memory management unit (MMU) and virtual memory subsystems
• Interrupt handling and system call failures
• Critical system service dependencies
• Windows Kernel Debug (WinDbg) analysis patterns

SPECIALIZED TASK: Blue Screen of Death (BSOD) Expert Analysis

SYSTEM SPECIFICATIONS:
{system_context}

BSOD ANALYSIS PROTOCOL:
1. **Stop Code Interpretation**: Decode the specific stop code in context of this system's hardware and software configuration
2. **Driver Stack Analysis**: Identify which drivers in the system could cause this specific failure mode
3. **Hardware Correlation**: How do the CPU, RAM, storage, and motherboard specs relate to this crash pattern?
4. **Timing Analysis**: When does this crash occur (boot, idle, load, sleep/wake) and what does that indicate?
5. **System State Reconstruction**: What was the kernel doing when it crashed based on the stop code and system configuration?

CRITICAL FOCUS AREAS:
- Stop code and parameter analysis with system-specific interpretation
- Driver compatibility with this exact Windows build and hardware
- Memory configuration issues (timing, capacity, compatibility)
- Power management and hardware interaction failures
- Recent Windows updates or driver changes that could trigger this crash
- Hardware degradation patterns consistent with this system's age and configuration

Provide your analysis using the enhanced JSON format specified in the system_diagnostic template, with BSOD-specific technical details including:
- Specific stop codes and their meaning for this hardware configuration
- Memory diagnostic commands (mdsched.exe, memtest86)
- Driver rollback procedures for implicated drivers
- Hardware stress testing recommendations
- Crash dump analysis steps for advanced users
- Safe mode diagnostic procedures
""",
            "application_crash": """You are an expert in Windows application troubleshooting with deep knowledge of software conflicts, compatibility issues, and runtime errors.

SPECIALIZED TASK: Application Crash Analysis

APPLICATION ANALYSIS PROTOCOL:
1. Identify the failing application and error type
2. Check for .NET Framework, Visual C++ redistributable requirements
3. Analyze compatibility with current Windows version
4. Consider user permissions and security settings

Focus on:
- Missing dependencies and redistributables
- Application compatibility settings
- User Account Control (UAC) issues
- Registry corruption affecting applications
- Antivirus/security software conflicts

{system_context}

Provide structured JSON output as specified in the main template with emphasis on application-specific solutions.
""",
            "driver_error": """You are an expert in Windows driver troubleshooting with extensive knowledge of hardware drivers, device management, and compatibility issues.

SPECIALIZED TASK: Driver Error Analysis

DRIVER ANALYSIS PROTOCOL:
1. Identify the problematic device and driver
2. Check driver version compatibility with Windows version
3. Analyze hardware-specific requirements and conflicts
4. Provide manufacturer-specific driver solutions

Focus on:
- Graphics driver issues (NVIDIA, AMD, Intel)
- Audio driver problems
- Network adapter driver conflicts
- USB and peripheral device drivers
- Signed vs unsigned driver issues

{system_context}

Provide structured JSON output as specified in the main template with emphasis on driver-specific solutions.
""",
        }

    def _get_chain_of_thought_instructions(self) -> str:
        """
        Get Chain-of-Thought reasoning instructions based on configuration.

        Returns:
            Chain-of-Thought instruction text
        """
        if not self.use_chain_of_thought:
            return ""

        if self.reasoning_depth == "basic":
            return """
THINKING PROCESS:
Before providing your final analysis, think through this step-by-step:
1. What do I see in the error screenshot?
2. What system information is relevant?
3. What is the most likely cause?
4. What solution steps should I recommend?
"""

        elif self.reasoning_depth == "comprehensive":
            return """
COMPREHENSIVE THINKING PROCESS:
Before providing your final analysis, work through this systematic reasoning:

1. ERROR OBSERVATION:
   - What specific error messages, codes, or visual indicators do I see?
   - What application or system component is affected?
   - When did this error likely occur (startup, runtime, shutdown)?

2. SYSTEM CONTEXT ANALYSIS:
   - What hardware specifications are relevant to this error?
   - Are there any recent system changes or updates?
   - What software and drivers might be involved?

3. ROOT CAUSE INVESTIGATION:
   - What are the possible causes given the error and system context?
   - Which cause is most likely based on the evidence?
   - Are there any patterns or known issues with this configuration?

4. SOLUTION STRATEGY:
   - What is the safest approach to resolve this issue?
   - What are the potential risks of each solution?
   - What order should solutions be attempted?

5. VERIFICATION PLAN:
   - How can the user verify the solution worked?
   - What follow-up actions are recommended?
"""

        else:  # detailed
            return """
DETAILED THINKING PROCESS:
Before providing your final analysis, reason through this systematically:

1. ERROR ANALYSIS:
   - What specific error indicators do I observe?
   - What system component or process is affected?

2. SYSTEM CORRELATION:
   - How do the system specifications relate to this error?
   - What compatibility or resource issues might exist?

3. CAUSE DETERMINATION:
   - What is the most probable root cause?
   - What supporting evidence leads to this conclusion?

4. SOLUTION PLANNING:
   - What is the optimal sequence of troubleshooting steps?
   - What precautions should be taken?
"""

    def _add_troubleshooting_methodology(self, prompt: str) -> str:
        """
        Add advanced troubleshooting methodology to the prompt.

        Args:
            prompt: Base prompt text

        Returns:
            Enhanced prompt with troubleshooting methodology
        """
        methodology = """
ADVANCED TROUBLESHOOTING METHODOLOGY:

1. SYSTEMATIC APPROACH:
   - Start with least disruptive solutions
   - Document each step for potential rollback
   - Test one change at a time to isolate variables

2. EVIDENCE-BASED DIAGNOSIS:
   - Use system specifications to validate compatibility
   - Cross-reference error codes with Microsoft documentation
   - Consider recent system changes as potential triggers

3. RISK MITIGATION:
   - Always recommend system backup before major changes
   - Provide rollback instructions for each solution
   - Assess data loss and system stability risks

4. SOLUTION VALIDATION:
   - Include verification steps for each solution
   - Provide monitoring recommendations
   - Suggest preventive measures
"""
        return prompt + "\n" + methodology

    def _get_windows_settings_context(self, additional_context: str) -> str:
        """
        Generate Windows settings context based on the error description.

        Args:
            additional_context: Additional context information containing error description

        Returns:
            Windows settings context with relevant ms-settings:// URLs
        """
        try:
            # Get relevant Windows settings URLs based on issue description
            relevant_urls = get_urls_for_issue(additional_context)

            if not relevant_urls:
                return ""

            context_parts = [
                "RELEVANT WINDOWS SETTINGS:",
                "The following Windows Settings pages may be relevant to this issue:",
            ]

            for setting_name, url in relevant_urls:
                # Create user-friendly names for settings
                friendly_name = setting_name.replace("-", " ").title()
                context_parts.append(f"• {friendly_name}: {url}")

            context_parts.append("")
            context_parts.append("Include these URLs in your solution steps when directing users to Windows settings.")
            context_parts.append("Example: Open [Display Settings](ms-settings:display) to adjust screen resolution.")

            return "\n".join(context_parts)

        except Exception as e:
            self.logger.warning(f"Failed to generate Windows settings context: {e}")
            return ""

    def build_analysis_prompt(
        self, error_type: str, system_specs: Dict[str, Any], additional_context: Optional[str] = None
    ) -> str:
        """
        Construct optimized prompt for Gemini API with Chain-of-Thought reasoning and enhanced templates.

        Args:
            error_type: Type of error (system_diagnostic, bsod_analysis, etc.)
            system_specs: Complete system specifications dictionary
            additional_context: Optional additional context information

        Returns:
            Formatted prompt string for AI analysis

        Raises:
            PromptEngineeringError: If prompt construction fails
        """
        try:
            with PerformanceTimer("Prompt construction"):
                # Format system context
                system_context = self.format_system_context(system_specs)

                # Use enhanced prompts if available and enabled
                if self.use_enhanced_prompts:
                    enhanced_templates = self.enhanced_templates.get_all_enhanced_templates()

                    # Map error types to enhanced templates
                    enhanced_mapping = {
                        "system_diagnostic": "enhanced_system_diagnostic",
                        "discord_installation": "enhanced_discord_installation",
                        "sfc_diagnostic": "enhanced_sfc_diagnostic",
                    }

                    # Check for Discord-related errors
                    if additional_context and "discord" in additional_context.lower():
                        error_type = "discord_installation"

                    # Check for system file corruption indicators
                    if additional_context and any(
                        term in additional_context.lower() for term in ["system file", "sfc", "corrupt", "integrity"]
                    ):
                        error_type = "sfc_diagnostic"

                    enhanced_key = enhanced_mapping.get(error_type, "enhanced_system_diagnostic")

                    if enhanced_key in enhanced_templates:
                        prompt_template = enhanced_templates[enhanced_key]
                        self.logger.info(f"Using enhanced template: {enhanced_key}")
                    else:
                        # Fallback to original templates
                        template_key = error_type if error_type in self.prompt_templates else "system_diagnostic"
                        prompt_template = self.prompt_templates[template_key]
                        self.logger.info(f"Using original template: {template_key}")
                else:
                    # Use original templates
                    template_key = error_type if error_type in self.prompt_templates else "system_diagnostic"
                    prompt_template = self.prompt_templates[template_key]

                # Build the complete prompt
                prompt = prompt_template.format(system_context=system_context)

                # Add Chain-of-Thought instructions for original templates only
                if self.use_chain_of_thought and not self.use_enhanced_prompts:
                    cot_instructions = self._get_chain_of_thought_instructions()
                    prompt = cot_instructions + "\n" + prompt

                # Add advanced troubleshooting methodology for original templates only
                if not self.use_enhanced_prompts:
                    prompt = self._add_troubleshooting_methodology(prompt)

                # Add additional context if provided
                if additional_context:
                    prompt += f"\n\nADDITIONAL CONTEXT:\n{additional_context}\n"

                # Add Windows settings context and suggestions
                if additional_context:
                    windows_context = self._get_windows_settings_context(additional_context)
                    if windows_context:
                        prompt += f"\n\n{windows_context}"

                # Add final instruction (enhanced templates have their own)
                if not self.use_enhanced_prompts:
                    if self.use_chain_of_thought:
                        prompt += "\n\nNow think through this step-by-step using the thinking process above, then analyze the provided error screenshot and system specifications, and provide your analysis in the exact JSON format specified."
                    else:
                        prompt += "\n\nNow analyze the provided error screenshot and system specifications, then provide your analysis in the exact JSON format specified above."

                self.logger.debug(
                    f"Constructed prompt for {error_type} with {len(prompt)} characters (Enhanced: {self.use_enhanced_prompts}, CoT: {self.use_chain_of_thought})"
                )
                return prompt

        except Exception as e:
            self.logger.error(f"Failed to construct prompt: {e}")
            raise PromptEngineeringError(f"Prompt construction failed: {e}")

    def format_system_context(self, specs: Dict[str, Any]) -> str:
        """
        Format system specifications for AI context with enhanced intelligence.

        Args:
            specs: System specifications dictionary

        Returns:
            Formatted system context string with intelligent analysis
        """
        try:
            context_parts = []

            # Operating System Information with compatibility analysis
            if "os_information" in specs:
                os_info = specs["os_information"]
                context_parts.append("\n=== OPERATING SYSTEM ANALYSIS ===")

                windows_edition = os_info.get("windows_edition", "Unknown")
                build_number = os_info.get("build_number", "Unknown")
                architecture = os_info.get("architecture", "Unknown")

                context_parts.append(f"Windows Edition: {windows_edition}")
                context_parts.append(f"Build Number: {build_number}")
                context_parts.append(f"Architecture: {architecture}")
                context_parts.append(f"System Type: {os_info.get('system_type', 'Unknown')}")

                # Add intelligence about Windows version
                if "build_number" in os_info:
                    build = str(build_number)
                    if build.startswith("22"):
                        context_parts.append(
                            "[ANALYSIS] Windows 11 detected - modern troubleshooting procedures applicable"
                        )
                    elif build.startswith("19"):
                        context_parts.append(
                            "[ANALYSIS] Windows 10 detected - standard troubleshooting procedures applicable"
                        )
                    elif build.startswith("10"):
                        context_parts.append(
                            "[ANALYSIS] Older Windows version detected - legacy compatibility considerations required"
                        )
                        context_parts.append(
                            "\nℹ️ Windows 11 detected - Consider new hardware requirements and compatibility"
                        )
                        context_parts.append("- TPM 2.0 and Secure Boot requirements may affect driver compatibility")
                        context_parts.append("- New Windows 11 power management may cause hardware interaction issues")
                    elif build.startswith("19"):
                        context_parts.append("\nℹ️ Windows 10 detected - Mature platform with extensive driver support")
                        context_parts.append("- Consider Windows 10 end-of-life timeline for long-term compatibility")

                    # Add update channel analysis
                    if build.endswith("1"):
                        context_parts.append("⚠️ Beta/Insider build detected - May have stability issues")

                context_parts.append("")

            # Hardware Specifications with compatibility intelligence
            if "hardware_specs" in specs:
                hw_specs = specs["hardware_specs"]
                context_parts.append("=== HARDWARE COMPATIBILITY ANALYSIS ===")

                # CPU Analysis with architecture implications
                if "cpu" in hw_specs:
                    cpu = hw_specs["cpu"]
                    cpu_name = cpu.get("name", "Unknown")
                    core_count = cpu.get("core_count", "Unknown")
                    thread_count = cpu.get("thread_count", "Unknown")
                    max_speed = cpu.get("max_speed_ghz", "Unknown")

                    context_parts.append(f"CPU: {cpu_name}")
                    context_parts.append(f"Cores/Threads: {core_count}C/{thread_count}T @ {max_speed}GHz")

                    # Add CPU-specific intelligence
                    if "Intel" in str(cpu_name):
                        context_parts.append(
                            "ℹ️ Intel CPU - Check for Intel Management Engine and graphics driver conflicts"
                        )
                        if any(gen in str(cpu_name) for gen in ["12th", "13th", "14th"]):
                            context_parts.append(
                                "⚠️ Recent Intel generation - Ensure latest microcode and power management drivers"
                            )
                    elif "AMD" in str(cpu_name):
                        context_parts.append("ℹ️ AMD CPU - Verify AMD chipset drivers and Ryzen Master compatibility")
                        if "Ryzen" in str(cpu_name):
                            context_parts.append("⚠️ AMD Ryzen - Check for AGESA BIOS updates and memory compatibility")

                # Memory Analysis with configuration intelligence
                if "memory" in hw_specs:
                    memory = hw_specs["memory"]
                    total_memory = memory.get("total_gb", "Unknown")
                    available_memory = memory.get("available_gb", "Unknown")
                    memory_slots = memory.get("memory_slots", [])

                    context_parts.append(f"\nMemory: {total_memory}GB total, {available_memory}GB available")

                    if memory_slots:
                        context_parts.append(f"Memory Configuration: {len(memory_slots)} slots populated")
                        for i, slot in enumerate(memory_slots[:4]):
                            capacity = slot.get("capacity_gb", "Unknown")
                            speed = slot.get("speed_mhz", "Unknown")
                            context_parts.append(f"  Slot {i+1}: {capacity}GB @ {speed}MHz")

                    # Add memory-specific intelligence
                    try:
                        total_gb = float(total_memory) if total_memory != "Unknown" else 0
                        if total_gb < 8:
                            context_parts.append(
                                "⚠️ Low memory configuration - May cause performance issues with modern applications"
                            )
                        elif total_gb >= 32:
                            context_parts.append("ℹ️ High memory configuration - Check for memory-related BSOD patterns")

                        if len(memory_slots) == 1:
                            context_parts.append(
                                "⚠️ Single memory module - May indicate dual-channel configuration not optimal"
                            )
                    except (ValueError, TypeError):
                        pass

                # Graphics Analysis with driver intelligence
                if "graphics" in hw_specs:
                    graphics = hw_specs["graphics"]
                    context_parts.append(f"\nGraphics Controllers:")

                    for gpu in graphics.get("controllers", []):
                        name = gpu.get("name", "Unknown GPU")
                        driver_version = gpu.get("driver_version", "Unknown")
                        driver_date = gpu.get("driver_date", "Unknown")

                        context_parts.append(f"  • {name}")
                        context_parts.append(f"    Driver: v{driver_version} ({driver_date})")

                        # Add GPU-specific intelligence
                        if "NVIDIA" in name:
                            context_parts.append("    ℹ️ NVIDIA GPU - Check GeForce Experience and CUDA compatibility")
                        elif "AMD" in name or "Radeon" in name:
                            context_parts.append("    ℹ️ AMD GPU - Verify Adrenalin drivers and OpenCL compatibility")
                        elif "Intel" in name:
                            context_parts.append(
                                "    ℹ️ Intel Graphics - Check for integrated graphics conflicts with discrete GPU"
                            )

                        # Check driver age
                        if driver_date != "Unknown":
                            try:
                                from datetime import datetime, timedelta

                                driver_dt = datetime.strptime(driver_date, "%Y-%m-%d")
                                if datetime.now() - driver_dt > timedelta(days=365):
                                    context_parts.append("    ⚠️ Driver over 1 year old - Update recommended")
                            except (ValueError, TypeError):
                                pass

                context_parts.append("")

            # Software Environment Analysis
            if "software_environment" in specs:
                software = specs["software_environment"]
                context_parts.append("=== SOFTWARE ENVIRONMENT ANALYSIS ===")

                # .NET Framework Analysis
                if "dotnet_versions" in software:
                    dotnet_versions = software["dotnet_versions"]
                    context_parts.append(
                        f"\n.NET Framework: {', '.join(dotnet_versions[:5])}{'...' if len(dotnet_versions) > 5 else ''}"
                    )

                    # Check for missing common versions
                    required_versions = ["4.8", "4.7.2", "4.6.2"]
                    missing_versions = [
                        v for v in required_versions if not any(v in installed for installed in dotnet_versions)
                    ]
                    if missing_versions:
                        context_parts.append(f"  ⚠️ Missing recommended .NET versions: {', '.join(missing_versions)}")

                # Visual C++ Redistributables Analysis
                if "visual_cpp_redist" in software:
                    vcredist = software["visual_cpp_redist"]
                    context_parts.append(f"\nVisual C++ Redistributables: {len(vcredist)} installed")

                    # Check for common missing redistributables
                    common_years = ["2015", "2017", "2019", "2022"]
                    installed_years = [str(r.get("year", "")) for r in vcredist]
                    missing_years = [
                        y for y in common_years if not any(y in installed for installed in installed_years)
                    ]
                    if missing_years:
                        context_parts.append(
                            f"  ⚠️ Missing common Visual C++ redistributables: {', '.join(missing_years)}"
                        )

                context_parts.append("")

            # System Health Intelligence
            context_parts.append("=== SYSTEM HEALTH INDICATORS ===")

            # Uptime analysis
            if "system_health" in specs:
                health = specs["system_health"]
                uptime = health.get("uptime_hours", 0)

                if uptime > 720:  # 30 days
                    context_parts.append(f"⚠️ System uptime: {uptime}h (>30 days) - Consider restart for stability")
                elif uptime < 1:
                    context_parts.append(f"ℹ️ Recent restart detected ({uptime}h) - Error may be boot-related")

            # Temperature and performance indicators
            if "performance_metrics" in specs:
                perf = specs["performance_metrics"]
                cpu_usage = perf.get("cpu_usage_percent", 0)
                memory_usage = perf.get("memory_usage_percent", 0)

                if cpu_usage > 80:
                    context_parts.append(f"⚠️ High CPU usage: {cpu_usage}% - May indicate resource contention")
                if memory_usage > 85:
                    context_parts.append(f"⚠️ High memory usage: {memory_usage}% - May cause stability issues")

            context_parts.append("")
            context_parts.append("=== DIAGNOSTIC RECOMMENDATIONS ===")
            context_parts.append("ℹ️ Focus on hardware-software compatibility based on above configuration")
            context_parts.append("ℹ️ Consider recent changes to drivers, Windows updates, or hardware")
            context_parts.append("ℹ️ Prioritize solutions specific to this exact hardware and Windows build combination")

            return "\n".join(context_parts)

        except Exception as e:
            self.logger.error(f"Error formatting system context: {e}")
            return f"System specifications available but formatting failed: {e}"

    def validate_prompt_response(self, response: str) -> Dict[str, Any]:
        """
        Validate and parse AI response for proper JSON structure.

        Args:
            response: Raw AI response string

        Returns:
            Parsed and validated response dictionary

        Raises:
            PromptEngineeringError: If response validation fails
        """
        try:
            # Try to extract JSON from response
            response_clean = response.strip()

            # Remove markdown code blocks if present
            if response_clean.startswith("```json"):
                response_clean = response_clean[7:]
            if response_clean.endswith("```"):
                response_clean = response_clean[:-3]
            if response_clean.startswith("```"):
                response_clean = response_clean[3:]

            response_clean = response_clean.strip()

            # Handle streaming responses that might be incomplete
            # Try to find complete JSON objects in the response
            if not response_clean.startswith("{") and "{" in response_clean:
                # Extract JSON from mixed content
                start_idx = response_clean.find("{")
                response_clean = response_clean[start_idx:]

            # Fix common streaming JSON issues
            if response_clean.endswith(","):
                response_clean = response_clean[:-1]

            # Try to auto-complete incomplete JSON if possible
            if response_clean.count("{") > response_clean.count("}"):
                missing_braces = response_clean.count("{") - response_clean.count("}")
                response_clean += "}" * missing_braces

            # Handle incomplete strings by removing them
            if response_clean.count('"') % 2 != 0:
                # Find the last opening quote and remove everything after it
                last_quote = response_clean.rfind('"')
                if last_quote > 0:
                    # Look backwards for the previous complete field
                    prev_comma = response_clean.rfind(",", 0, last_quote)
                    if prev_comma > 0:
                        response_clean = response_clean[:prev_comma] + "}" * (
                            response_clean[:prev_comma].count("{") - response_clean[:prev_comma].count("}")
                        )
                    else:
                        # If no previous comma found, truncate to last complete brace
                        last_brace = response_clean.rfind("}", 0, last_quote)
                        if last_brace > 0:
                            response_clean = response_clean[: last_brace + 1]

            # Parse JSON
            try:
                parsed_response = json.loads(response_clean)
            except json.JSONDecodeError as json_error:
                # Try alternative parsing approaches for streaming responses
                self.logger.warning(f"Initial JSON parsing failed: {json_error}, attempting recovery")

                # Try extracting just the visible complete JSON portion
                lines = response_clean.split("\n")
                json_lines = []
                brace_count = 0
                for line in lines:
                    json_lines.append(line)
                    brace_count += line.count("{") - line.count("}")
                    if brace_count == 0 and json_lines:
                        # Found a complete JSON object
                        break

                if json_lines:
                    recovery_json = "\n".join(json_lines)
                    try:
                        parsed_response = json.loads(recovery_json)
                        self.logger.info("Successfully recovered JSON from streaming response")
                    except json.JSONDecodeError:
                        # Final fallback: create a basic response structure
                        self.logger.warning("JSON recovery failed, creating fallback response")
                        parsed_response = self._create_fallback_response(response_clean)
                else:
                    parsed_response = self._create_fallback_response(response_clean)

            # Handle nested response structures (e.g. troubleshooting_report wrapper)
            if "troubleshooting_report" in parsed_response:
                # Extract nested analysis from troubleshooting_report
                nested_data = parsed_response["troubleshooting_report"]
                # Look for required fields in nested structure and flatten them
                for field in [
                    "confidence_score",
                    "problem_summary",
                    "solutions",
                    "risk_assessment",
                    "prevention_tips",
                    "when_to_seek_help",
                    "thinking_process",
                ]:
                    if field not in parsed_response and field in nested_data:
                        parsed_response[field] = nested_data[field]
                    # Also check in sub-objects like error_analysis, solution_planning, etc.
                    elif field not in parsed_response:
                        for sub_obj in nested_data.values():
                            if isinstance(sub_obj, dict) and field in sub_obj:
                                parsed_response[field] = sub_obj[field]
                                break

            # Handle complex nested structures with different field names
            elif any(
                key in parsed_response
                for key in ["analysis_summary", "error_analysis", "solution_planning", "cause_determination"]
            ):
                # This is a complex analysis response - extract key information

                # Extract problem summary from cause_determination or analysis_summary
                if "problem_summary" not in parsed_response or not parsed_response["problem_summary"]:
                    # Check detailed_analysis -> cause_determination first
                    if (
                        "detailed_analysis" in parsed_response
                        and "cause_determination" in parsed_response["detailed_analysis"]
                        and "most_probable_root_cause" in parsed_response["detailed_analysis"]["cause_determination"]
                    ):
                        parsed_response["problem_summary"] = parsed_response["detailed_analysis"][
                            "cause_determination"
                        ]["most_probable_root_cause"]
                    # Check direct cause_determination
                    elif (
                        "cause_determination" in parsed_response
                        and "most_probable_root_cause" in parsed_response["cause_determination"]
                    ):
                        parsed_response["problem_summary"] = parsed_response["cause_determination"][
                            "most_probable_root_cause"
                        ]
                    # Check analysis_summary as fallback
                    elif "analysis_summary" in parsed_response:
                        if "error_description" in parsed_response["analysis_summary"]:
                            parsed_response["problem_summary"] = (
                                f"Discord installation issue: {parsed_response['analysis_summary']['error_description'][:200]}"
                            )
                        elif "initial_hypothesis" in parsed_response["analysis_summary"]:
                            parsed_response["problem_summary"] = parsed_response["analysis_summary"][
                                "initial_hypothesis"
                            ]

                # Extract risk assessment
                if "risk_assessment" not in parsed_response or not parsed_response["risk_assessment"]:
                    parsed_response["risk_assessment"] = (
                        "Based on analysis, risk is generally low with proper precautions"
                    )

                # Extract prevention tips from solution_planning
                if "prevention_tips" not in parsed_response or not parsed_response["prevention_tips"]:
                    if (
                        "solution_planning" in parsed_response
                        and "preventive_measures" in parsed_response["solution_planning"]
                    ):
                        parsed_response["prevention_tips"] = parsed_response["solution_planning"]["preventive_measures"]
                    else:
                        parsed_response["prevention_tips"] = ["Follow best practices", "Keep system updated"]

                # Extract when to seek help
                if "when_to_seek_help" not in parsed_response:
                    parsed_response["when_to_seek_help"] = (
                        "If solutions don't resolve the issue after following all steps"
                    )

                # Extract thinking process from error analysis and cause determination
                if "thinking_process" not in parsed_response or not parsed_response["thinking_process"]:
                    thinking = []
                    if (
                        "error_analysis" in parsed_response
                        and "specific_error_indicators" in parsed_response["error_analysis"]
                    ):
                        thinking.extend(parsed_response["error_analysis"]["specific_error_indicators"][:2])
                    if (
                        "cause_determination" in parsed_response
                        and "supporting_evidence" in parsed_response["cause_determination"]
                    ):
                        thinking.extend(parsed_response["cause_determination"]["supporting_evidence"][:2])
                    parsed_response["thinking_process"] = (
                        thinking if thinking else ["Analyzed Discord installation error symptoms"]
                    )

            # Validate required fields
            required_fields = [
                "confidence_score",
                "problem_summary",
                "solutions",
                "risk_assessment",
                "prevention_tips",
                "when_to_seek_help",
                "thinking_process",
            ]

            # Special handling for solutions - check if they're in a different structure
            if "solutions" not in parsed_response or not parsed_response["solutions"]:
                # Look for solutions in nested structures
                if "troubleshooting_report" in parsed_response:
                    report = parsed_response["troubleshooting_report"]
                    # Check solution_planning for optimal_troubleshooting_sequence
                    if (
                        "solution_planning" in report
                        and "optimal_troubleshooting_sequence" in report["solution_planning"]
                    ):
                        sequence = report["solution_planning"]["optimal_troubleshooting_sequence"]
                        if isinstance(sequence, list):
                            # Convert detailed steps to simplified solution format
                            parsed_response["solutions"] = []
                            for step in sequence[:5]:  # Take first 5 steps
                                if isinstance(step, dict):
                                    solution = {
                                        "step_number": step.get("step", len(parsed_response["solutions"]) + 1),
                                        "title": step.get(
                                            "description",
                                            f"Step {step.get('step', len(parsed_response['solutions']) + 1)}",
                                        ),
                                        "description": step.get(
                                            "details", step.get("description", "No description available")
                                        ),
                                        "risk_level": "low",  # Default risk level
                                        "estimated_time": "5-10 minutes",
                                        "expected_outcome": "Issue resolution",
                                        "if_unsuccessful": "Try next step",
                                        "safety_notes": step.get("precautions", "Follow instructions carefully"),
                                    }
                                    parsed_response["solutions"].append(solution)
                # Check for solution_planning in direct response (not nested)
                elif (
                    "solution_planning" in parsed_response
                    and "optimal_sequence_of_troubleshooting_steps" in parsed_response["solution_planning"]
                ):
                    sequence = parsed_response["solution_planning"]["optimal_sequence_of_troubleshooting_steps"]
                    if isinstance(sequence, list):
                        # Convert detailed steps to simplified solution format
                        parsed_response["solutions"] = []
                        for step in sequence[:5]:  # Take first 5 steps
                            if isinstance(step, dict):
                                solution = {
                                    "step_number": step.get("step", len(parsed_response["solutions"]) + 1),
                                    "title": step.get(
                                        "description", f"Step {step.get('step', len(parsed_response['solutions']) + 1)}"
                                    ),
                                    "description": step.get(
                                        "reasoning", step.get("description", "No description available")
                                    ),
                                    "risk_level": "low",  # Default risk level
                                    "estimated_time": "5-10 minutes",
                                    "expected_outcome": "Issue resolution",
                                    "if_unsuccessful": "Try next step",
                                    "safety_notes": "Follow instructions carefully",
                                }
                                parsed_response["solutions"].append(solution)
                # Check for detailed_analysis -> solution_planning structure
                elif (
                    "detailed_analysis" in parsed_response
                    and "solution_planning" in parsed_response["detailed_analysis"]
                ):
                    solution_planning = parsed_response["detailed_analysis"]["solution_planning"]
                    if "optimal_sequence_of_troubleshooting_steps" in solution_planning:
                        sequence = solution_planning["optimal_sequence_of_troubleshooting_steps"]
                        if isinstance(sequence, list):
                            # Convert detailed steps to simplified solution format
                            parsed_response["solutions"] = []
                            for step in sequence[:5]:  # Take first 5 steps
                                if isinstance(step, dict):
                                    # Handle both 'step' and string keys
                                    step_title = step.get("step", "")
                                    step_details = step.get(
                                        "details", step.get("description", "No description available")
                                    )
                                    step_relevance = step.get("relevance", "")

                                    solution = {
                                        "step_number": len(parsed_response["solutions"]) + 1,
                                        "title": (
                                            step_title
                                            if step_title
                                            else f"Step {len(parsed_response['solutions']) + 1}"
                                        ),
                                        "description": step_details,
                                        "risk_level": "low",  # Default risk level
                                        "estimated_time": "5-10 minutes",
                                        "expected_outcome": "Issue resolution",
                                        "if_unsuccessful": "Try next step",
                                        "safety_notes": (
                                            step_relevance if step_relevance else "Follow instructions carefully"
                                        ),
                                    }
                                    parsed_response["solutions"].append(solution)

            # Special handling for problem_summary
            if "problem_summary" not in parsed_response or not parsed_response["problem_summary"]:
                if "troubleshooting_report" in parsed_response:
                    report = parsed_response["troubleshooting_report"]
                    # Check cause_determination for most_probable_root_cause
                    if "cause_determination" in report and "most_probable_root_cause" in report["cause_determination"]:
                        parsed_response["problem_summary"] = report["cause_determination"]["most_probable_root_cause"]

            for field in required_fields:
                if field not in parsed_response:
                    self.logger.warning(f"Missing required field: {field}, adding default")
                    parsed_response[field] = self._get_default_field_value(field)

            # Validate confidence score
            confidence = parsed_response.get("confidence_score", 0)
            if not (0 <= confidence <= 1):
                self.logger.warning(f"Invalid confidence score: {confidence}, adjusting to valid range")
                parsed_response["confidence_score"] = max(0, min(1, confidence))

            # Ensure solutions is a list
            if not isinstance(parsed_response.get("solutions"), list):
                self.logger.warning("solutions not a list, converting")
                steps = parsed_response.get("solutions", "")
                if isinstance(steps, str):
                    parsed_response["solutions"] = [steps] if steps else ["Please retry analysis for detailed steps"]
                else:
                    parsed_response["solutions"] = ["Please retry analysis for detailed steps"]

            # Validate thinking process if present
            if "thinking_process" in parsed_response:
                self.logger.debug(f"Thinking process: {parsed_response['thinking_process']}")

            self.logger.debug("Response validation successful")
            return parsed_response

        except Exception as e:
            self.logger.error(f"Response validation failed: {e}")
            # Return a fallback response instead of raising an exception
            return self._create_fallback_response(response)

    def _create_fallback_response(self, original_response: str) -> Dict[str, Any]:
        """
        Create a fallback response when JSON parsing fails.

        Args:
            original_response: The original response text

        Returns:
            A valid response dictionary with fallback values
        """
        # Try to extract some useful information from the original response
        response_preview = original_response[:200] if original_response else "No response received"

        # Check if the response contains any recognizable error patterns
        if "BSOD" in original_response.upper() or "BLUE SCREEN" in original_response.upper():
            problem_type = "Blue Screen of Death (BSOD) Error"
            solutions = [
                {
                    "step_number": 1,
                    "title": "Restart Computer",
                    "description": "Restart your computer to see if the issue resolves temporarily",
                    "risk_level": "low",
                    "estimated_time": "2-3 minutes",
                    "expected_outcome": "Temporary resolution of the immediate issue",
                    "if_unsuccessful": "Continue to next step for deeper analysis",
                    "safety_notes": "Save any open work before restarting",
                },
                {
                    "step_number": 2,
                    "title": "Check for Windows Updates",
                    "description": "Run Windows Update to install any pending system updates",
                    "risk_level": "low",
                    "estimated_time": "10-30 minutes",
                    "expected_outcome": "System stability improvements",
                    "if_unsuccessful": "Check hardware issues or run memory diagnostic",
                    "safety_notes": "Ensure stable power connection during updates",
                },
            ]
        elif "DRIVER" in original_response.upper() or "DEVICE" in original_response.upper():
            problem_type = "Driver or Device Issue"
            solutions = [
                {
                    "step_number": 1,
                    "title": "Update Device Drivers",
                    "description": "Update drivers through Device Manager or manufacturer website",
                    "risk_level": "low",
                    "estimated_time": "10-15 minutes",
                    "expected_outcome": "Improved device compatibility and performance",
                    "if_unsuccessful": "Try rolling back recent driver changes",
                    "safety_notes": "Create system restore point before driver changes",
                }
            ]
        else:
            problem_type = "System Analysis Required"
            solutions = [
                {
                    "step_number": 1,
                    "title": "Retry Analysis",
                    "description": "Please retry the analysis to get complete results. Ensure stable internet connection.",
                    "risk_level": "low",
                    "estimated_time": "1-2 minutes",
                    "expected_outcome": "You should get a detailed analysis",
                    "if_unsuccessful": "Check your network connection and try again",
                    "safety_notes": "No safety concerns with retrying",
                }
            ]

        return {
            "confidence_score": 0.5,
            "problem_summary": f"Response parsing failed for {problem_type} - please retry analysis",
            "solutions": solutions,
            "risk_assessment": "Analysis incomplete but system not affected",
            "prevention_tips": ["Ensure stable internet connection for AI analysis", "Keep system updated regularly"],
            "when_to_seek_help": "If analysis continues to fail, contact technical support",
            "thinking_process": [
                "Parsing failed, providing fallback response",
                f"Original response preview: {response_preview}",
            ],
            "raw_response": original_response[:500] + "..." if len(original_response) > 500 else original_response,
        }

    def _get_default_field_value(self, field_name: str) -> Any:
        """
        Get default value for missing required fields.

        Args:
            field_name: Name of the missing field

        Returns:
            Default value for the field
        """
        defaults = {
            "confidence_score": 0.5,
            "problem_summary": "Analysis incomplete",
            "solutions": [
                {
                    "step_number": 1,
                    "title": "Retry Analysis",
                    "description": "Please retry analysis for detailed steps",
                    "risk_level": "low",
                    "estimated_time": "1-2 minutes",
                    "expected_outcome": "Complete analysis results",
                    "if_unsuccessful": "Contact support if issues persist",
                    "safety_notes": "No safety concerns",
                }
            ],
            "risk_assessment": "Unknown - requires further analysis",
            "prevention_tips": ["Follow best practices for system maintenance"],
            "when_to_seek_help": "Contact professional support if needed",
            "thinking_process": ["Analysis incomplete - default response provided"],
        }
        return defaults.get(field_name, f"Default value for {field_name}")

    def generate_followup_prompt(self, original_analysis: Dict[str, Any], user_feedback: str) -> str:
        """
        Generate a follow-up prompt based on original analysis and user feedback.

        Args:
            original_analysis: Original AI analysis results
            user_feedback: User feedback on the original solution

        Returns:
            Follow-up prompt for refinement
        """
        try:
            followup_prompt = f"""
FOLLOW-UP ANALYSIS REQUEST

ORIGINAL ANALYSIS SUMMARY:
- Confidence Score: {original_analysis.get('confidence_score', 'Unknown')}
- Root Cause: {original_analysis.get('root_cause', {}).get('primary_cause', 'Unknown')}
- Solution Steps Provided: {len(original_analysis.get('solution_steps', []))}

USER FEEDBACK:
{user_feedback}

REFINED ANALYSIS REQUEST:
Please provide an updated analysis considering the user feedback. Focus on:
1. Alternative solutions if the original didn't work
2. Additional diagnostic steps based on user experience
3. More specific troubleshooting for the reported symptoms
4. Different approach considering user's technical level

Provide the updated analysis in the same JSON format as before, with improved confidence and alternative approaches.
"""

            return followup_prompt

        except Exception as e:
            self.logger.error(f"Failed to generate follow-up prompt: {e}")
            raise PromptEngineeringError(f"Follow-up prompt generation failed: {e}")

    def build_optimization_prompt(self, system_specs: Dict[str, Any], performance_mode: str = "balanced") -> str:
        """
        Build an optimization prompt for system performance analysis.

        Args:
            system_specs: Complete system specifications dictionary
            performance_mode: Optimization mode ("speed", "balanced", "quality")

        Returns:
            Optimization-focused prompt
        """
        system_context = self.format_system_context(system_specs)

        optimization_prompt = f"""
You are an expert Windows Performance Optimization Specialist.

TASK: Analyze the system specifications and provide performance optimization recommendations.

OPTIMIZATION MODE: {performance_mode.upper()}

SYSTEM SPECIFICATIONS:
{system_context}

Focus on:
- System startup optimization
- Memory usage optimization
- Disk performance improvements
- Background process management
- Driver optimization
- Security without performance impact

Provide recommendations in JSON format with priority levels, estimated impact, and implementation steps.
"""

        if self.use_chain_of_thought:
            cot_instructions = self._get_chain_of_thought_instructions()
            optimization_prompt = cot_instructions + "\n" + optimization_prompt

        return optimization_prompt


# Prompt optimization utilities
class PromptOptimizer:
    """Utilities for optimizing prompts based on testing results."""

    def __init__(self):
        """Initialize the prompt optimizer."""
        self.logger = logging.getLogger(__name__)
        self.optimization_history = []

    def analyze_prompt_performance(
        self, prompt: str, response: Dict[str, Any], success_metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        Analyze prompt performance for optimization opportunities.

        Args:
            prompt: Original prompt text
            response: AI response
            success_metrics: Dictionary of success metrics (accuracy, completeness, etc.)

        Returns:
            Analysis results with optimization recommendations
        """
        try:
            analysis = {
                "prompt_length": len(prompt),
                "response_confidence": response.get("confidence_score", 0),
                "solution_count": len(response.get("solution_steps", [])),
                "success_metrics": success_metrics,
                "optimization_score": self._calculate_optimization_score(response, success_metrics),
                "recommendations": [],
            }

            # Generate optimization recommendations
            if analysis["response_confidence"] < 0.8:
                analysis["recommendations"].append("Increase context specificity")

            if analysis["solution_count"] < 3:
                analysis["recommendations"].append("Request more alternative solutions")

            if success_metrics.get("accuracy", 0) < 0.8:
                analysis["recommendations"].append("Refine error classification prompts")

            self.optimization_history.append(analysis)
            return analysis

        except Exception as e:
            self.logger.error(f"Prompt performance analysis failed: {e}")
            return {"error": str(e)}

    def _calculate_optimization_score(self, response: Dict[str, Any], success_metrics: Dict[str, float]) -> float:
        """Calculate overall optimization score (0-1)."""
        try:
            scores = [
                response.get("confidence_score", 0),
                success_metrics.get("accuracy", 0),
                success_metrics.get("completeness", 0),
                min(1.0, len(response.get("solution_steps", [])) / 5),  # Normalize to 0-1
            ]

            return sum(scores) / len(scores)

        except Exception:
            return 0.0


# Testing utilities for prompt engineering
class PromptTester:
    """Utilities for testing prompt effectiveness."""

    def __init__(self):
        """Initialize the prompt tester."""
        self.logger = logging.getLogger(__name__)
        self.test_results = []

    def create_test_scenario(
        self, scenario_name: str, error_description: str, expected_solutions: List[str], system_specs: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create a test scenario for prompt evaluation.

        Args:
            scenario_name: Name of the test scenario
            error_description: Description of the error
            expected_solutions: List of expected solution types
            system_specs: System specifications for context

        Returns:
            Test scenario dictionary
        """
        return {
            "scenario_name": scenario_name,
            "error_description": error_description,
            "expected_solutions": expected_solutions,
            "system_specs": system_specs,
            "timestamp": datetime.now().isoformat(),
        }

    def evaluate_response(self, test_scenario: Dict[str, Any], ai_response: Dict[str, Any]) -> Dict[str, float]:
        """
        Evaluate AI response against test scenario expectations.

        Args:
            test_scenario: Test scenario data
            ai_response: AI response to evaluate

        Returns:
            Evaluation metrics
        """
        try:
            metrics = {"accuracy": 0.0, "completeness": 0.0, "relevance": 0.0, "confidence_alignment": 0.0}

            expected_solutions = test_scenario.get("expected_solutions", [])
            provided_solutions = [step.get("type", "") for step in ai_response.get("solution_steps", [])]

            # Calculate accuracy (how many expected solutions were provided)
            if expected_solutions:
                matches = sum(
                    1 for exp in expected_solutions if any(exp.lower() in prov.lower() for prov in provided_solutions)
                )
                metrics["accuracy"] = matches / len(expected_solutions)

            # Calculate completeness (minimum expected solution count)
            min_expected_solutions = max(3, len(expected_solutions))
            metrics["completeness"] = min(1.0, len(provided_solutions) / min_expected_solutions)

            # Calculate relevance (confidence score as proxy)
            metrics["relevance"] = ai_response.get("confidence_score", 0)

            # Calculate confidence alignment
            expected_confidence = 0.8  # Expected baseline
            actual_confidence = ai_response.get("confidence_score", 0)
            metrics["confidence_alignment"] = 1.0 - abs(expected_confidence - actual_confidence)

            return metrics

        except Exception as e:
            self.logger.error(f"Response evaluation failed: {e}")
            return {"accuracy": 0.0, "completeness": 0.0, "relevance": 0.0, "confidence_alignment": 0.0}
