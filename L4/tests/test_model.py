import httpx
import openai
import pytest
from langchain_openai import ChatOpenAI

from assistente.config import Settings
from assistente.model import ModelCheckError, check_model, create_chat_model


def settings(**overrides) -> Settings:
    values = {"base_url": "http://localhost:1234/v1", "model": "google/gemma-4-e2b"}
    values.update(overrides)
    return Settings(**values)


def test_check_model_accepts_listed_model():
    check_model(settings(model="google/gemma-4-e2b"), lambda url: ["google/gemma-4-e2b", "altro"])


def test_check_model_lists_available_models():
    with pytest.raises(ModelCheckError) as err:
        check_model(settings(model="inventato"), lambda url: ["a/uno", "b/due"])
    msg = str(err.value)
    assert "inventato" in msg and "a/uno" in msg and "b/due" in msg and "http://localhost:1234/v1" in msg


def test_check_model_reports_unreachable_server():
    def down(url):
        raise openai.APIConnectionError(request=httpx.Request("GET", url))

    with pytest.raises(ModelCheckError, match="LM Studio"):
        check_model(settings(), down)


def test_create_chat_model_uses_settings():
    m = create_chat_model(settings())
    assert isinstance(m, ChatOpenAI) and m.model_name == "google/gemma-4-e2b"
    assert str(m.openai_api_base) == "http://localhost:1234/v1"
