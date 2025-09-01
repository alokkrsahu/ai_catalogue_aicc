#!/usr/bin/env python3
"""
Test script to verify CORS configuration for public chatbot API
Tests both preflight OPTIONS requests and actual POST requests
"""

import requests
import sys
import json
from typing import Dict, Any

def test_cors_endpoint(base_url: str, origin: str = "https://oxfordcompetencycenters.github.io") -> Dict[str, Any]:
    """Test CORS configuration for a specific endpoint"""
    results = {
        'base_url': base_url,
        'origin': origin,
        'preflight_test': {},
        'actual_request_test': {},
        'health_check_test': {}
    }
    
    # Test 1: Preflight OPTIONS request to