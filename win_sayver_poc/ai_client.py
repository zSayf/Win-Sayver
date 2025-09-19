#!/usr/bin/env python3
"""
Basic AI client for Win Sayver.

Simplified version for CI/CD testing.
"""

import logging
from typing import Dict, Any, Optional

from utils import WinSayverError


class AIClientError(WinSayverError):
    """Raised when AI client operations fail."""
    pass


class AIClient:
    """
    Basic AI client for testing purposes.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """Initialize AI client."""
        self.logger = logging.getLogger(__name__)
        self.api_key = api_key
        
    def analyze_error(self, system_specs: Dict[str, Any], images: list = None, description: str = "") -> Dict[str, Any]:
        """
        Analyze error with AI (mock implementation for testing).
        
        Args:
            system_specs: System specifications
            images: List of image paths
            description: Error description
            
        Returns:
            Analysis result
        """
        self.logger.info("Mock AI analysis performed")
        
        return {
            'analysis': 'Mock AI analysis result',
            'confidence': 0.85,
            'suggestions': [
                'This is a mock suggestion for testing',
                'Check system logs for more details',
                'Consider updating drivers'
            ],
            'metadata': {
                'model': 'mock-model',
                'timestamp': '2025-01-19T12:00:00Z'
            }
        }