from __future__ import annotations

from app.capture_extraction import UnavailableCaptureExtractionProvider
from app.config import Settings
from app.deepseek_capture_extractor import DeepSeekCaptureExtractionProvider
from app.journal import JournalLog, journal_event, record_journal_event
from app.openai_capture_extractor import OpenAICaptureExtractionProvider


def capture_extraction_provider_for_settings(
    settings: Settings,
    *,
    journal_log: JournalLog | None = None,
):
    provider = getattr(settings, "capture_extraction_provider", "unavailable")
    model = getattr(settings, "capture_extraction_model", "")

    if provider == "unavailable":
        _record_provider_unavailable(journal_log, provider, model, "provider_unavailable")
        return UnavailableCaptureExtractionProvider(model)
    if provider == "deepseek":
        api_key = getattr(settings, "deepseek_api_key", "")
        if not api_key or not model:
            _record_provider_unavailable(
                journal_log,
                provider,
                model or "deepseek-unconfigured",
                "missing_key_or_model",
            )
            return UnavailableCaptureExtractionProvider(model or "deepseek-unconfigured")
        return DeepSeekCaptureExtractionProvider(
            api_key=api_key,
            model=model,
            base_url=getattr(settings, "deepseek_base_url", ""),
            capture_debug_dir=getattr(settings, "capture_debug_dir", None),
            capture_debug_raw_provider_output=getattr(
                settings,
                "capture_debug_raw_provider_output",
                False,
            ),
        )
    if provider == "openai":
        api_key = getattr(settings, "openai_api_key", "")
        if not api_key or not model:
            _record_provider_unavailable(
                journal_log,
                provider,
                model or "openai-unconfigured",
                "missing_key_or_model",
            )
            return UnavailableCaptureExtractionProvider(model or "openai-unconfigured")
        return OpenAICaptureExtractionProvider(api_key=api_key, model=model)
    raise ValueError(f"unsupported capture extraction provider: {provider}")


def _record_provider_unavailable(
    journal_log: JournalLog | None,
    provider: str,
    model: str,
    reason: str,
) -> None:
    record_journal_event(
        journal_log,
        journal_event(
            component="capture_provider",
            event_type="capture_provider.unavailable",
            stage="blocked",
            level="warning",
            reason=reason,
            details={
                "provider": provider,
                "model": model or "unconfigured",
            },
        ),
    )
