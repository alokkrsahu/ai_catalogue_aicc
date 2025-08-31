from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import asyncio
import aiohttp
import time
from dataclasses import dataclass

@dataclass
class LLMResponse:
    text: str
    model: str
    provider: str
    response_time_ms: int
    token_count: Optional[int] = None
    cost_estimate: Optional[float] = None
    error: Optional[str] = None

class LLMProvider(ABC):
    """Abstract base class for all LLM providers"""
    
    def __init__(self, api_key: str, model: str, max_tokens: int = 1000, timeout: int = 30):
        self.api_key = api_key
        self.model = model
        self.max_tokens = max_tokens
        self.timeout = timeout
        self.provider_name = self.__class__.__name__.replace('Provider', '').lower()
    
    @abstractmethod
    async def generate_response(self, prompt: str, **kwargs) -> LLMResponse:
        """Generate response from the LLM provider"""
        pass
    
    @abstractmethod
    def get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests"""
        pass
    
    @abstractmethod
    def format_request_body(self, prompt: str, **kwargs) -> Dict[str, Any]:
        """Format the request body for the provider's API"""
        pass
    
    @abstractmethod
    def parse_response(self, response_data: Dict[str, Any]) -> tuple[str, Optional[int]]:
        """Parse the API response and return (text, token_count)"""
        pass
    
    def estimate_cost(self, token_count: Optional[int]) -> Optional[float]:
        """Estimate cost based on token count - override in subclasses"""
        return None
