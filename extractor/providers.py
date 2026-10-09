"""LLM providers. Each takes raw document bytes + mime type and returns an Invoice.

Both Gemini and Claude read PDFs (including scanned ones) and images natively,
so there is no separate OCR step to maintain.

Configuration (environment variables):
    GEMINI_API_KEY      free key from https://aistudio.google.com/apikey
    GEMINI_MODEL        optional, defaults to "gemini-flash-latest"
    ANTHROPIC_API_KEY   key from https://console.anthropic.com/settings/keys
    ANTHROPIC_MODEL     optional, defaults to "claude-haiku-4-5"
"""

from __future__ import annotations

import base64
import os
from typing import Protocol

from .schema import EXTRACTION_PROMPT, Invoice


class Provider(Protocol):
    name: str

    def extract(self, data: bytes, mime_type: str) -> Invoice: ...


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        from google import genai

        key = api_key or os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set. Get a free key at https://aistudio.google.com/apikey")
        self.client = genai.Client(api_key=key)
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-flash-latest")

    def extract(self, data: bytes, mime_type: str) -> Invoice:
        from google.genai import types

        response = self.client.models.generate_content(
            model=self.model,
            contents=[types.Part.from_bytes(data=data, mime_type=mime_type), EXTRACTION_PROMPT],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=Invoice,
                temperature=0,
            ),
        )
        if isinstance(response.parsed, Invoice):
            return response.parsed
        return Invoice.model_validate_json(response.text)


class ClaudeProvider:
    name = "claude"

    def __init__(self, api_key: str | None = None, model: str | None = None):
        import anthropic

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set. Get a key at https://console.anthropic.com/settings/keys")
        self.client = anthropic.Anthropic(api_key=key)
        self.model = model or os.environ.get("ANTHROPIC_MODEL", "claude-haiku-4-5")

    def extract(self, data: bytes, mime_type: str) -> Invoice:
        encoded = base64.standard_b64encode(data).decode()
        block_type = "document" if mime_type == "application/pdf" else "image"
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            temperature=0,
            tools=[{
                "name": "record_invoice",
                "description": "Record the data extracted from the document.",
                "input_schema": Invoice.model_json_schema(),
            }],
            tool_choice={"type": "tool", "name": "record_invoice"},
            messages=[{
                "role": "user",
                "content": [
                    {"type": block_type, "source": {"type": "base64", "media_type": mime_type, "data": encoded}},
                    {"type": "text", "text": EXTRACTION_PROMPT},
                ],
            }],
        )
        tool_use = next(b for b in response.content if b.type == "tool_use")
        return Invoice.model_validate(tool_use.input)


def available_providers() -> list[str]:
    names = []
    if os.environ.get("GEMINI_API_KEY"):
        names.append("gemini")
    if os.environ.get("ANTHROPIC_API_KEY"):
        names.append("claude")
    return names


def get_provider(name: str, api_key: str | None = None) -> Provider:
    if name == "gemini":
        return GeminiProvider(api_key=api_key)
    if name == "claude":
        return ClaudeProvider(api_key=api_key)
    raise ValueError(f"Unknown provider: {name}")
