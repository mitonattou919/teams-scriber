"""LLM呼び出しのプロバイダ非依存な薄い抽象層。

議事録生成ロジック(brain/minutes.py)はここで定義する `LLMClient` インターフェース
のみに依存し、Azure OpenAI / Anthropic のSDK差異を知らない。将来ツール呼び出しや
MCPクライアント化する際もこの層だけを差し替えれば済む設計にしている。
"""

from __future__ import annotations

import os
from typing import Protocol

from anthropic import AsyncAnthropic
from openai import AsyncOpenAI

DEFAULT_AZURE_OPENAI_MODEL = "gpt-5.5-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-5"


class LLMClient(Protocol):
    async def complete(self, *, system: str, user: str) -> str: ...


class AzureOpenAIClient:
    def __init__(self, client: AsyncOpenAI, model: str) -> None:
        self._client = client
        self._model = model

    async def complete(self, *, system: str, user: str) -> str:
        response = await self._client.chat.completions.create(
            model=self._model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        return response.choices[0].message.content


class AnthropicClient:
    def __init__(self, client: AsyncAnthropic, model: str) -> None:
        self._client = client
        self._model = model

    async def complete(self, *, system: str, user: str) -> str:
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        return response.content[0].text


def build_llm_client_from_env() -> LLMClient:
    provider = os.environ.get("LLM_PROVIDER", "azure_openai")

    if provider == "azure_openai":
        endpoint = os.environ.get("AZURE_OPENAI_ENDPOINT")
        api_key = os.environ.get("AZURE_OPENAI_API_KEY")
        if not endpoint or not api_key:
            raise RuntimeError(
                "AZURE_OPENAI_ENDPOINT と AZURE_OPENAI_API_KEY が必要です"
            )
        model = os.environ.get("AZURE_OPENAI_MODEL", DEFAULT_AZURE_OPENAI_MODEL)
        client = AsyncOpenAI(base_url=endpoint, api_key=api_key)
        return AzureOpenAIClient(client, model=model)

    if provider == "anthropic":
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY が必要です")
        model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
        client = AsyncAnthropic(api_key=api_key)
        return AnthropicClient(client, model=model)

    raise ValueError(f"unknown LLM_PROVIDER: {provider}")
