"""
ZhipuAI GLM Provider with Vision support.

This module implements the AIProvider interface for ZhipuAI's GLM models,
supporting both text and vision (image) inputs via the GLM-4.6V-Flash model.
"""

import json
import re
from typing import Optional, Dict, Any, List

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.ai.base import (
    AIProvider,
    AIProviderConfig,
    AIMessage,
    AIRole,
    VisionInput,
    AIProviderError,
)

logger = get_logger(__name__)


class GLMProvider(AIProvider):
    """
    ZhipuAI GLM provider with vision support.

    Supports models like:
    - glm-4.6v-flash (vision model, recommended)
    - glm-4.6v (vision model)
    - glm-4.5 (text only)
    - glm-4.6 (text only)
    - glm-4.7 (text only, latest)
    """

    @property
    def name(self) -> str:
        return "ZhipuAI GLM"

    @property
    def supports_vision(self) -> bool:
        # GLM-4.6V-Flash models support vision
        return "4.6v" in self.config.model.lower()

    @property
    def supports_json_mode(self) -> bool:
        return True

    def _get_api_url(self) -> str:
        """Get the API URL from settings or use default."""
        return getattr(settings, "GLM_API_URL", "https://open.bigmodel.cn/api/paas/v4/chat/completions")

    def _build_messages(
        self,
        messages: List[AIMessage],
        vision_input: Optional[VisionInput] = None,
    ) -> List[Dict[str, Any]]:
        """
        Build the messages array for GLM API.

        GLM uses OpenAI-compatible message format with vision support.
        """
        result = []

        for msg in messages:
            role = msg.role.value

            # Handle vision input for user messages
            if vision_input and msg.role == AIRole.USER:
                # Build multimodal content
                content = [
                    {"type": "text", "text": msg.content},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{vision_input.mime_type};base64,{vision_input.image_base64}"
                        }
                    }
                ]
                result.append({"role": role, "content": content})
            else:
                result.append({"role": role, "content": msg.content})

        return result

    async def complete(
        self,
        messages: List[AIMessage],
        vision_input: Optional[VisionInput] = None,
    ) -> str:
        """Generate a text completion from GLM."""
        url = self._get_api_url()

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        payload = {
            "model": self.config.model,
            "messages": self._build_messages(messages, vision_input),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code >= 400:
                    logger.error(f"GLM API error {response.status_code}: {response.text}")
                    raise AIProviderError(
                        message=f"API request failed: {response.text}",
                        provider=self.name,
                        status_code=response.status_code,
                        response_body=response.text,
                    )

                data = response.json()

            # Extract text from response (OpenAI-compatible format)
            return self._extract_text_from_response(data)

        except httpx.TimeoutException as e:
            logger.error(f"GLM API timeout: {e}")
            raise AIProviderError(
                message="Request timed out",
                provider=self.name,
            )
        except httpx.RequestError as e:
            logger.error(f"GLM API request error: {e}")
            raise AIProviderError(
                message=f"Request failed: {str(e)}",
                provider=self.name,
            )

    async def complete_json(
        self,
        messages: List[AIMessage],
        vision_input: Optional[VisionInput] = None,
        json_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Generate a structured JSON completion from GLM."""
        url = self._get_api_url()

        headers = {
            "Authorization": f"Bearer {self.config.api_key}",
            "Content-Type": "application/json",
        }

        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": self._build_messages(messages, vision_input),
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        # Add JSON response format if schema is provided
        if json_schema:
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "response",
                    "schema": json_schema,
                    "strict": True,
                }
            }

        try:
            async with httpx.AsyncClient(timeout=self.config.timeout) as client:
                response = await client.post(url, headers=headers, json=payload)

                if response.status_code >= 400:
                    logger.error(f"GLM API error {response.status_code}: {response.text}")
                    raise AIProviderError(
                        message=f"API request failed: {response.text}",
                        provider=self.name,
                        status_code=response.status_code,
                        response_body=response.text,
                    )

                data = response.json()

            # Extract text from response
            text = self._extract_text_from_response(data)

            # Parse JSON from response
            return self._parse_json_response(text)

        except httpx.TimeoutException as e:
            logger.error(f"GLM API timeout: {e}")
            raise AIProviderError(
                message="Request timed out",
                provider=self.name,
            )
        except httpx.RequestError as e:
            logger.error(f"GLM API request error: {e}")
            raise AIProviderError(
                message=f"Request failed: {str(e)}",
                provider=self.name,
            )

    def _extract_text_from_response(self, data: Dict[str, Any]) -> str:
        """Extract text content from GLM API response (OpenAI-compatible format)."""
        try:
            choices = data.get("choices", [])
            if not choices:
                raise AIProviderError(
                    message="No choices in response",
                    provider=self.name,
                )

            message = choices[0].get("message", {})
            content = message.get("content", "")

            if not content:
                raise AIProviderError(
                    message="No content in response message",
                    provider=self.name,
                )

            return content

        except (KeyError, IndexError) as e:
            logger.error(f"Failed to extract text from GLM response: {e}")
            raise AIProviderError(
                message=f"Invalid response structure: {e}",
                provider=self.name,
            )

    def _parse_json_response(self, text: str) -> Dict[str, Any]:
        """Parse JSON from response text."""
        try:
            # First try direct parsing
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code blocks
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
        if json_match:
            try:
                return json.loads(json_match.group(1).strip())
            except json.JSONDecodeError:
                pass

        # Try to find JSON object in text
        json_match = re.search(r"\{[\s\S]*\}", text)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        logger.error(f"Failed to parse JSON from GLM response: {text[:500]}")
        raise AIProviderError(
            message="Failed to parse JSON from response",
            provider=self.name,
            response_body=text[:1000],
        )
