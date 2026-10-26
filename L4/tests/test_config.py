import pytest

from assistente.config import ConfigError, load_settings

BASE = {"LMSTUDIO_BASE_URL": "http://localhost:1234/v1", "LMSTUDIO_MODEL": "google/gemma-4-e2b"}


def test_missing_required_variables_are_named():
    with pytest.raises(ConfigError) as err:
        load_settings({})
    assert "LMSTUDIO_BASE_URL" in str(err.value) and "LMSTUDIO_MODEL" in str(err.value)


def test_blank_value_counts_as_missing():
    with pytest.raises(ConfigError, match="LMSTUDIO_MODEL"):
        load_settings({**BASE, "LMSTUDIO_MODEL": "  "})


def test_values_are_read_and_stripped():
    s = load_settings({**BASE, "LMSTUDIO_MODEL": " google/gemma-4-e2b "})
    assert (s.base_url, s.model, s.log_level) == ("http://localhost:1234/v1", "google/gemma-4-e2b", "INFO")


def test_log_level_is_normalized_and_validated():
    assert load_settings({**BASE, "LOG_LEVEL": "debug"}).log_level == "DEBUG"
    with pytest.raises(ConfigError, match="LOG_LEVEL"):
        load_settings({**BASE, "LOG_LEVEL": "verbose"})


def test_environment_wins_over_dotenv(tmp_path, monkeypatch):
    (tmp_path / ".env").write_text(
        "LMSTUDIO_BASE_URL=http://file/v1\nLMSTUDIO_MODEL=dal-file\n", encoding="utf-8"
    )
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("LMSTUDIO_MODEL", "dall-ambiente")
    # setenv prima di delenv: così monkeypatch ripristina anche il valore scritto da load_dotenv
    monkeypatch.setenv("LMSTUDIO_BASE_URL", "provvisorio")
    monkeypatch.delenv("LMSTUDIO_BASE_URL")
    s = load_settings()
    assert (s.base_url, s.model) == ("http://file/v1", "dall-ambiente")


def test_tool_defaults():
    s = load_settings(BASE)
    assert (s.default_timezone, s.max_tool_steps) == ("Europe/Rome", 3)


@pytest.mark.parametrize("value", ["0", "-1", "tre"])
def test_invalid_max_tool_steps(value):
    with pytest.raises(ConfigError, match="MAX_TOOL_STEPS"):
        load_settings({**BASE, "MAX_TOOL_STEPS": value})


def test_default_timezone_is_validated_and_canonical():
    assert load_settings({**BASE, "DEFAULT_TIMEZONE": "europe/rome"}).default_timezone == "Europe/Rome"
    with pytest.raises(ConfigError, match="DEFAULT_TIMEZONE"):
        load_settings({**BASE, "DEFAULT_TIMEZONE": "Marte/Base"})
