"""MetaAI API - Python SDK for Meta AI.

A modern, feature-rich Python SDK providing seamless access to Meta AI's capabilities:
- Chat with Llama (with real-time internet access)
- Generate AI images
- Upload images for analysis and generation
- No API key required

Uses browser automation (agent-browser) as the primary method, which works
for ANY prompt. Also supports legacy HTTP/WebSocket methods for advanced users.
"""
print(' Initializing init.py')


from .main import MetaAI  # noqa
from .generation import GenerationAPI  # noqa
from .exceptions import (
    MetaAIError,
    AuthenticationError,
    GenerationError,
    TimeoutError,
    RateLimitError,
    ConnectionError,
    BrowserNotInstalledError,
    InvalidResponseError,
)

__all__ = [
    "MetaAI",
    "GenerationAPI",
    "MetaAIError",
    "AuthenticationError",
    "GenerationError",
    "TimeoutError",
    "RateLimitError",
    "ConnectionError",
    "BrowserNotInstalledError",
    "InvalidResponseError",
]
