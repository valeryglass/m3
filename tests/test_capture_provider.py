import json
from types import SimpleNamespace

from app.capture_extraction import UnavailableCaptureExtractionProvider
from app.capture_provider import capture_extraction_provider_for_settings
from app.deepseek_capture_extractor import DeepSeekCaptureExtractionProvider
from app.journal import JournalLog
from app.openai_capture_extractor import OpenAICaptureExtractionProvider


def _settings(**overrides):
    values = {
        "capture_extraction_provider": "unavailable",
        "capture_extraction_model": "",
        "deepseek_api_key": "",
        "deepseek_base_url": "https://api.deepseek.com",
        "capture_debug_dir": None,
        "capture_debug_raw_provider_output": False,
        "openai_api_key": "",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_unavailable_provider_is_default_free_mode_boundary():
    provider = capture_extraction_provider_for_settings(_settings())

    assert isinstance(provider, UnavailableCaptureExtractionProvider)
    assert provider.model == "unconfigured"


def test_deepseek_provider_is_selected_when_configured(monkeypatch):
    created = {}

    def fake_init(self, **kwargs):
        created.update(kwargs)
        self.model = kwargs["model"]

    monkeypatch.setattr(DeepSeekCaptureExtractionProvider, "__init__", fake_init)

    provider = capture_extraction_provider_for_settings(
        _settings(
            capture_extraction_provider="deepseek",
            capture_extraction_model="deepseek-v4-flash",
            deepseek_api_key="key",
            deepseek_base_url="https://deepseek.test",
        )
    )

    assert isinstance(provider, DeepSeekCaptureExtractionProvider)
    assert created == {
        "api_key": "key",
        "model": "deepseek-v4-flash",
        "base_url": "https://deepseek.test",
        "capture_debug_dir": None,
        "capture_debug_raw_provider_output": False,
    }


def test_missing_deepseek_credentials_returns_unavailable_provider():
    provider = capture_extraction_provider_for_settings(
        _settings(
            capture_extraction_provider="deepseek",
            capture_extraction_model="deepseek-v4-flash",
        )
    )

    assert isinstance(provider, UnavailableCaptureExtractionProvider)
    assert provider.model == "deepseek-v4-flash"


def test_missing_deepseek_model_returns_unavailable_provider():
    provider = capture_extraction_provider_for_settings(
        _settings(
            capture_extraction_provider="deepseek",
            deepseek_api_key="key",
        )
    )

    assert isinstance(provider, UnavailableCaptureExtractionProvider)
    assert provider.model == "deepseek-unconfigured"


def test_missing_deepseek_config_writes_provider_journal(tmp_path):
    journal_path = tmp_path / "journal.jsonl"

    provider = capture_extraction_provider_for_settings(
        _settings(
            capture_extraction_provider="deepseek",
            capture_extraction_model="deepseek-v4-flash",
        ),
        journal_log=JournalLog(journal_path),
    )

    assert isinstance(provider, UnavailableCaptureExtractionProvider)
    event = json.loads(journal_path.read_text(encoding="utf-8"))
    assert event["event_type"] == "capture_provider.unavailable"
    assert event["reason"] == "missing_key_or_model"
    assert event["details"]["provider"] == "deepseek"


def test_openai_provider_remains_available_when_configured(monkeypatch):
    created = {}

    def fake_init(self, **kwargs):
        created.update(kwargs)
        self.model = kwargs["model"]

    monkeypatch.setattr(OpenAICaptureExtractionProvider, "__init__", fake_init)

    provider = capture_extraction_provider_for_settings(
        _settings(
            capture_extraction_provider="openai",
            capture_extraction_model="gpt-test",
            openai_api_key="key",
        )
    )

    assert isinstance(provider, OpenAICaptureExtractionProvider)
    assert created == {"api_key": "key", "model": "gpt-test"}
