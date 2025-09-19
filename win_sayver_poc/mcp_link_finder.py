"""
MCP-powered Link Finder for Win Sayver
======================================

This module uses MCP (Model Context Protocol) tools to find current, working URLs
for Windows troubleshooting and support documentation.
"""

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass
class SearchResult:
    """Result from MCP search."""

    title: str
    url: str
    snippet: str
    relevance_score: float = 0.0


class MCPLinkFinder:
    """
    Uses MCP tools to find current, working URLs for troubleshooting topics.

    This class integrates with available MCP servers to provide real-time
    URL discovery and validation using web search and browser automation.
    """

    def __init__(self):
        """Initialize MCP link finder."""
        self.logger = logging.getLogger(__name__)

        # Domain-specific search strategies with specificity preservation
        self.search_strategies = {
            "microsoft_support": {
                "domains": ["support.microsoft.com", "docs.microsoft.com", "techcommunity.microsoft.com"],
                "search_templates": [
                    'site:support.microsoft.com "{topic}" Windows 11 current 2024',
                    'site:docs.microsoft.com "{topic}" troubleshooting detailed steps',
                    'Microsoft "{topic}" official documentation specific procedures 2024',
                    'Microsoft KB "{topic}" Windows 11 current version',
                ],
            },
            "discord_support": {
                "domains": ["support.discord.com", "discord.com"],
                "search_templates": [
                    'site:support.discord.com "{topic}" Windows current',
                    'Discord "{topic}" installation Windows 11 official guide',
                    'Discord help "{topic}" fix specific error',
                ],
            },
            "general_windows": {
                "domains": ["microsoft.com", "answers.microsoft.com"],
                "search_templates": [
                    '"{topic}" Windows 11 official solution specific',
                    '"{topic}" Microsoft support 2024 detailed',
                    'Windows 11 "{topic}" troubleshooting guide specific steps',
                    '"{topic}" Windows 11 registry fix specific keys',
                ],
            },
        }

    async def find_working_urls(
        self, topic: str, category: str = "microsoft_support", max_results: int = 5
    ) -> List[SearchResult]:
        """
        Find working URLs for a given topic using MCP tools.

        Args:
            topic: Topic to search for
            category: Category of search (microsoft_support, discord_support, general_windows)
            max_results: Maximum number of results to return

        Returns:
            List of SearchResult objects with working URLs
        """
        try:
            results = []

            # Get search strategy for category
            strategy = self.search_strategies.get(category, self.search_strategies["microsoft_support"])

            # Try each search template
            for template in strategy["search_templates"]:
                query = template.format(topic=topic)

                try:
                    # Use MCP Brave Search
                    search_results = await self._search_with_mcp(query, max_results=3)

                    # Filter results by trusted domains
                    filtered_results = self._filter_by_domains(search_results, strategy["domains"])

                    # Validate URLs using MCP browser tools
                    validated_results = await self._validate_urls_with_browser(filtered_results)

                    results.extend(validated_results)

                    # Stop if we have enough good results
                    if len(results) >= max_results:
                        break

                except Exception as e:
                    self.logger.warning(f"Search failed for query '{query}': {e}")
                    continue

            # Remove duplicates and sort by relevance
            unique_results = self._deduplicate_results(results)
            sorted_results = sorted(unique_results, key=lambda x: x.relevance_score, reverse=True)

            return sorted_results[:max_results]

        except Exception as e:
            self.logger.error(f"MCP link finding failed for topic '{topic}': {e}")
            return []

    async def _search_with_mcp(self, query: str, max_results: int = 5) -> List[SearchResult]:
        """
        Perform web search using MCP Brave Search tool.

        Args:
            query: Search query
            max_results: Maximum results to return

        Returns:
            List of search results
        """
        try:
            # Try to use actual MCP Brave Search if available
            # TODO: Implement actual MCP tool integration when available
            # For now, use simulated results as fallback

            # Simulated results for development
            results = []

            if "support.microsoft.com" in query:
                results.append(
                    SearchResult(
                        title="Microsoft Support - Windows Help",
                        url="https://support.microsoft.com/en-us/windows",
                        snippet="Official Microsoft Windows support and troubleshooting",
                    )
                )

            if "docs.microsoft.com" in query:
                results.append(
                    SearchResult(
                        title="Microsoft Docs - Windows Troubleshooting",
                        url="https://docs.microsoft.com/en-us/troubleshoot/windows-client",
                        snippet="Comprehensive Windows troubleshooting documentation",
                    )
                )

            if "discord" in query.lower():
                results.append(
                    SearchResult(
                        title="Discord Support Center",
                        url="https://support.discord.com/",
                        snippet="Official Discord help and support",
                    )
                )

            return results

        except Exception as e:
            self.logger.error(f"MCP search failed for query '{query}': {e}")
            return []

    def _filter_by_domains(self, results: List[SearchResult], trusted_domains: List[str]) -> List[SearchResult]:
        """
        Filter search results to only include trusted domains.

        Args:
            results: List of search results
            trusted_domains: List of trusted domain names

        Returns:
            Filtered list of results
        """
        filtered = []

        for result in results:
            try:
                from urllib.parse import urlparse

                domain = urlparse(result.url).netloc.lower()

                if any(trusted_domain in domain for trusted_domain in trusted_domains):
                    filtered.append(result)

            except Exception as e:
                self.logger.warning(f"Failed to parse URL {result.url}: {e}")
                continue

        return filtered

    async def _validate_urls_with_browser(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        Validate URLs using MCP browser tools.

        Args:
            results: List of search results to validate

        Returns:
            List of validated results with relevance scores
        """
        validated = []

        for result in results:
            try:
                # This would use MCP Playwright browser tools to test URLs
                # For implementation, we'll do basic HTTP validation

                is_valid = await self._test_url_accessibility(result.url)

                if is_valid:
                    # Calculate relevance score based on domain and content
                    result.relevance_score = self._calculate_relevance_score(result)
                    validated.append(result)

            except Exception as e:
                self.logger.warning(f"URL validation failed for {result.url}: {e}")
                continue

        return validated

    async def _test_url_accessibility(self, url: str) -> bool:
        """
        Test if URL is accessible using basic HTTP check.

        In full implementation, this would use MCP browser tools.

        Args:
            url: URL to test

        Returns:
            True if URL is accessible
        """
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.head(url, timeout=aiohttp.ClientTimeout(total=5)) as response:
                    return response.status < 400

        except Exception:
            return False

    def _calculate_initial_relevance(self, url: str, title: str) -> float:
        """
        Calculate initial relevance score for a URL and title.

        Args:
            url: URL to score
            title: Title to score

        Returns:
            Relevance score from 0.0 to 1.0
        """
        score = 0.0

        # Domain authority scoring
        domain = url.lower()

        if "support.microsoft.com" in domain:
            score += 0.4
        elif "docs.microsoft.com" in domain:
            score += 0.35
        elif "techcommunity.microsoft.com" in domain:
            score += 0.3
        elif "microsoft.com" in domain:
            score += 0.25
        elif "support.discord.com" in domain:
            score += 0.35
        elif "discord.com" in domain:
            score += 0.3

        # Content relevance (based on title)
        content_score = 0.0
        content_text = title.lower()

        # Look for quality indicators
        quality_terms = [
            "official",
            "support",
            "documentation",
            "help",
            "guide",
            "troubleshooting",
            "kb",
            "knowledge base",
        ]
        for term in quality_terms:
            if term in content_text:
                content_score += 0.1

        score += min(content_score, 0.4)  # Cap content score at 0.4

        return min(score, 1.0)

    def _calculate_relevance_score(self, result: SearchResult) -> float:
        """
        Calculate relevance score for a search result.

        Args:
            result: Search result to score

        Returns:
            Relevance score from 0.0 to 1.0
        """
        score = 0.0

        # Domain authority scoring
        domain = result.url.lower()

        if "support.microsoft.com" in domain:
            score += 0.4
        elif "docs.microsoft.com" in domain:
            score += 0.35
        elif "techcommunity.microsoft.com" in domain:
            score += 0.3
        elif "microsoft.com" in domain:
            score += 0.25
        elif "support.discord.com" in domain:
            score += 0.35
        elif "discord.com" in domain:
            score += 0.3

        # Content relevance (based on title and snippet)
        content_score = 0.0
        content_text = (result.title + " " + result.snippet).lower()

        # Look for quality indicators
        quality_terms = [
            "official",
            "support",
            "documentation",
            "help",
            "guide",
            "troubleshooting",
            "kb",
            "knowledge base",
        ]
        for term in quality_terms:
            if term in content_text:
                content_score += 0.1

        score += min(content_score, 0.4)  # Cap content score at 0.4

        return min(score, 1.0)

    def _deduplicate_results(self, results: List[SearchResult]) -> List[SearchResult]:
        """
        Remove duplicate results based on URL.

        Args:
            results: List of search results

        Returns:
            List with duplicates removed
        """
        seen_urls = set()
        unique_results = []

        for result in results:
            if result.url not in seen_urls:
                seen_urls.add(result.url)
                unique_results.append(result)

        return unique_results


# Convenience function for synchronous usage
def find_working_urls_sync(topic: str, category: str = "microsoft_support", max_results: int = 5) -> List[SearchResult]:
    """
    Synchronous wrapper for finding working URLs.

    Args:
        topic: Topic to search for
        category: Category of search
        max_results: Maximum number of results

    Returns:
        List of SearchResult objects
    """
    try:
        finder = MCPLinkFinder()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            return loop.run_until_complete(finder.find_working_urls(topic, category, max_results))
        finally:
            loop.close()

    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Synchronous URL finding failed: {e}")
        return []
