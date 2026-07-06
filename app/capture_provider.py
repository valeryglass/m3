from __future__ import annotations

from app.capture_extraction import UnavailableCaptureExtractionProvider
from app.config import Settings
from app.deepseek_capture_extractor import DeepSeekCaptureExtractionProvider
from app.openai_capture_extractor import OpenAICaptureExtractionProvider


def capture_extraction_provider_for_settings(settings: Settings):
    provider = getattr(settings, "capture_extraction_provider", "unavailable")
    model = getattr(settings, "capture_extraction_model", "")

    if provider == "unavailable":
        return UnavailableCaptureExtractionProvider(model)
    if provider == "deepseek":
        api_key = getattr(settings, "deepseek_api_key", "")
        if not api_key or not model:
            return UnavailableCaptureExtractionProvider(model or "deepseek-unconfigured")
        return DeepSeekCaptureExtractionProvider(
            api_key=api_key,
            model=model,
            base_url=getattr(settings, "deepseek_base_url", ""),
        )
    if provider == "openai":
        api_key = getattr(settings, "openai_api_key", "")
        if not api_key or not model:
            return UnavailableCaptureExtractionProvider(model or "openai-unconfigured")
        return OpenAICaptureExtractionProvider(api_key=api_key, model=model)
    raise ValueError(f"unsupported capture extraction provider: {provider}")
