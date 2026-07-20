from unittest.mock import AsyncMock, MagicMock

import pytest

from brain.llm import AnthropicClient, AzureOpenAIClient, build_llm_client_from_env


async def test_azure_openai_client_sends_system_and_user_messages_and_returns_content():
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content='{"decisions": []}'))]
    fake_client = MagicMock()
    fake_client.chat.completions.create = AsyncMock(return_value=response)

    client = AzureOpenAIClient(fake_client, model="gpt-5.5-mini")
    result = await client.complete(system="sys", user="usr")

    assert result == '{"decisions": []}'
    fake_client.chat.completions.create.assert_awaited_once_with(
        model="gpt-5.5-mini",
        messages=[{"role": "system", "content": "sys"}, {"role": "user", "content": "usr"}],
        response_format={"type": "json_object"},
    )


async def test_anthropic_client_sends_system_and_user_messages_and_returns_text():
    response = MagicMock()
    response.content = [MagicMock(text='{"decisions": []}')]
    fake_client = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=response)

    client = AnthropicClient(fake_client, model="claude-sonnet-5")
    result = await client.complete(system="sys", user="usr")

    assert result == '{"decisions": []}'
    fake_client.messages.create.assert_awaited_once_with(
        model="claude-sonnet-5",
        max_tokens=4096,
        system="sys",
        messages=[{"role": "user", "content": "usr"}],
    )


def test_build_llm_client_from_env_defaults_to_azure_openai(monkeypatch):
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    monkeypatch.setenv("AZURE_OPENAI_ENDPOINT", "https://example.openai.azure.com")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "dummy")
    monkeypatch.setenv("AZURE_OPENAI_MODEL", "gpt-5.5-mini")

    client = build_llm_client_from_env()

    assert isinstance(client, AzureOpenAIClient)


def test_build_llm_client_from_env_selects_anthropic(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "dummy")

    client = build_llm_client_from_env()

    assert isinstance(client, AnthropicClient)


def test_build_llm_client_from_env_raises_for_unknown_provider(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "bogus")

    with pytest.raises(ValueError):
        build_llm_client_from_env()


def test_build_llm_client_from_env_raises_when_azure_config_missing(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "azure_openai")
    monkeypatch.delenv("AZURE_OPENAI_ENDPOINT", raising=False)
    monkeypatch.delenv("AZURE_OPENAI_API_KEY", raising=False)

    with pytest.raises(RuntimeError):
        build_llm_client_from_env()


def test_build_llm_client_from_env_raises_when_anthropic_config_missing(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(RuntimeError):
        build_llm_client_from_env()
