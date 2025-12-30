"""
Abstract base classes for AI provider integration.

This module provides a unified interface for different AI providers (Gemini, GLM, OpenAI, etc.)
enabling easy switching between providers and reuse across different AI-powered features.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from enum import Enum


class AIRole(str, Enum):
    """Message roles for AI conversations."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class AIMessage(BaseModel):
    """A message in an AI conversation."""
    role: AIRole
    content: str


class VisionInput(BaseModel):
    """Input for vision-capable AI models."""
    image_base64: str = Field(..., description="Base64-encoded image data")
    mime_type: str = Field(..., description="Image MIME type (image/jpeg, image/png, image/webp)")


class AIProviderConfig(BaseModel):
    """Configuration for an AI provider."""
    api_key: str = Field(..., description="API key for the provider")
    model: str = Field(..., description="Model name/ID to use")
    max_tokens: int = Field(default=4000, description="Maximum tokens in response")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Sampling temperature")
    timeout: int = Field(default=120, description="Request timeout in seconds")


class AIProvider(ABC):
    """
    Abstract base class for AI providers.

    All AI providers (Gemini, GLM, OpenAI, Anthropic, etc.) should implement this interface
    to ensure consistent behavior across the application.

    Example usage:
        provider = get_ai_provider(AIProviderType.GEMINI)
        response = await provider.complete(messages, vision_input)
    """

    def __init__(self, config: AIProviderConfig):
        self.config = config

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable name of the provider."""
        pass

    @property
    @abstractmethod
    def supports_vision(self) -> bool:
        """Whether this provider supports vision/image inputs."""
        pass

    @property
    @abstractmethod
    def supports_json_mode(self) -> bool:
        """Whether this provider supports structured JSON output mode."""
        pass

    @abstractmethod
    async def complete(
        self,
        messages: List[AIMessage],
        vision_input: Optional[VisionInput] = None,
    ) -> str:
        """
        Generate a text completion from the AI model.

        Args:
            messages: List of conversation messages
            vision_input: Optional image input for vision models

        Returns:
            Generated text response

        Raises:
            AIProviderError: If the API call fails
        """
        pass

    @abstractmethod
    async def complete_json(
        self,
        messages: List[AIMessage],
        vision_input: Optional[VisionInput] = None,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Generate a structured JSON completion from the AI model.

        Args:
            messages: List of conversation messages
            vision_input: Optional image input for vision models
            json_schema: Optional JSON schema for structured output

        Returns:
            Parsed JSON response as a dictionary

        Raises:
            AIProviderError: If the API call fails or JSON parsing fails
        """
        pass


class AIProviderError(Exception):
    """Base exception for AI provider errors."""

    def __init__(
        self,
        message: str,
        provider: str,
        status_code: Optional[int] = None,
        response_body: Optional[str] = None,
    ):
        super().__init__(message)
        self.provider = provider
        self.status_code = status_code
        self.response_body = response_body

    def __str__(self) -> str:
        base = f"[{self.provider}] {super().__str__()}"
        if self.status_code:
            base += f" (status: {self.status_code})"
        return base
