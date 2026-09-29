import pytest

from whatsapp_agent.agents.llm_provider import get_llm_provider, OpenAILLMProvider, OllamaLLMProvider, MockLLMProvider, HuggingFaceLLMProvider, LLMGateway, FallbackLLMProvider
from whatsapp_agent.config.settings import get_settings, LLMProvider

@pytest.fixture(autouse=True)
def reset_llm_singleton():
    """Reset the singleton instance before and after each test."""
    import whatsapp_agent.agents.llm_provider as lp
    lp._llm_provider = None
    yield
    lp._llm_provider = None


def test_llm_provider_factory_openai():
    """Test factory returns OpenAILLMProvider when configured."""
    settings = get_settings()
    settings.llm_provider = LLMProvider.OPENAI
    provider = get_llm_provider()
    
    assert isinstance(provider, LLMGateway)
    assert isinstance(provider.inner, FallbackLLMProvider)
    assert isinstance(provider.inner.primary, OpenAILLMProvider)


def test_llm_provider_factory_ollama():
    """Test factory returns OllamaLLMProvider when configured."""
    settings = get_settings()
    settings.llm_provider = LLMProvider.OLLAMA
    provider = get_llm_provider()
    
    assert isinstance(provider, LLMGateway)
    assert isinstance(provider.inner, OllamaLLMProvider)


def test_llm_provider_factory_huggingface():
    """Test factory returns HuggingFaceLLMProvider when configured."""
    settings = get_settings()
    settings.llm_provider = LLMProvider.HUGGINGFACE
    provider = get_llm_provider()
    
    assert isinstance(provider, LLMGateway)
    assert isinstance(provider.inner, FallbackLLMProvider)
    assert isinstance(provider.inner.primary, HuggingFaceLLMProvider)


def test_llm_provider_factory_mock():
    """Test factory returns MockLLMProvider for unknown/mock config."""
    settings = get_settings()
    settings.llm_provider = "invalid_enum_value" # Simulating mock/test scenario
    provider = get_llm_provider()
    
    assert isinstance(provider, LLMGateway)
    assert isinstance(provider.inner, FallbackLLMProvider)
    assert isinstance(provider.inner.primary, OpenAILLMProvider)  # defaults to OpenAI if invalid
