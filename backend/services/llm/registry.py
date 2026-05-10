import json
import os
from pathlib import Path
from threading import Lock

from .base import BaseLLMProvider
from .providers import (
    AnthropicProvider,
    BaichuanProvider,
    BaiduQianfanProvider,
    CustomProvider,
    DeepSeekProvider,
    GeminiProvider,
    GroqProvider,
    LMStudioProvider,
    MiniMaxProvider,
    MistralProvider,
    MoonshotProvider,
    OllamaProvider,
    OpenAIProvider,
    OpenRouterProvider,
    PerplexityProvider,
    QwenProvider,
    SiliconFlowProvider,
    TencentHunyuanProvider,
    TogetherProvider,
    VolcengineProvider,
    XAIProvider,
    ZhipuProvider,
)

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "data" / "llm_config.json"
_lock = Lock()

_BUILTIN_CLASSES = {
    "openai": OpenAIProvider,
    "anthropic": AnthropicProvider,
    "qwen": QwenProvider,
    "deepseek": DeepSeekProvider,
    "gemini": GeminiProvider,
    "xai": XAIProvider,
    "moonshot": MoonshotProvider,
    "zhipu": ZhipuProvider,
    "siliconflow": SiliconFlowProvider,
    "volcengine": VolcengineProvider,
    "minimax": MiniMaxProvider,
    "baichuan": BaichuanProvider,
    "baidu_qianfan": BaiduQianfanProvider,
    "tencent_hunyuan": TencentHunyuanProvider,
    "mistral": MistralProvider,
    "groq": GroqProvider,
    "together": TogetherProvider,
    "openrouter": OpenRouterProvider,
    "perplexity": PerplexityProvider,
    "ollama": OllamaProvider,
    "lmstudio": LMStudioProvider,
    "custom": CustomProvider,
}

def _default_active_provider() -> str:
    return os.getenv("LLM_ACTIVE_PROVIDER", "qwen").strip() or "qwen"


_state: dict = {"active": _default_active_provider(), "providers": {}}
_instances: dict[str, BaseLLMProvider] = {}

_CONFIG_FIELDS = {"api_key", "base_url", "model", "display_name", "notes"}


def _load_state() -> None:
    global _state
    if not _CONFIG_PATH.exists():
        _state = {"active": _default_active_provider(), "providers": {}}
        return
    try:
        loaded = json.loads(_CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return
    if isinstance(loaded, dict):
        _state = {"active": loaded.get("active", _default_active_provider()), "providers": loaded.get("providers", {})}


def _save_state() -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(json.dumps(_state, ensure_ascii=False, indent=2), encoding="utf-8")


def _provider_template(key: str, cls: type[BaseLLMProvider]) -> dict:
    return {
        "key": key,
        "display_name": cls.display_name,
        "default_model": cls.default_model,
        "default_base_url": cls.default_base_url,
        "env_key_name": getattr(cls, "env_key_name", ""),
        "available_models": list(getattr(cls, "available_models", [])),
        "base_url_candidates": list(getattr(cls, "base_url_candidates", [])),
        "website_url": getattr(cls, "website_url", ""),
        "docs_url": getattr(cls, "docs_url", ""),
    }


def _normalize_config(config: dict | None) -> dict:
    if not isinstance(config, dict):
        return {}
    return {
        field: value.strip() if isinstance(value, str) else value
        for field, value in config.items()
        if field in _CONFIG_FIELDS and value is not None
    }


def provider_registry() -> dict:
    """Return provider templates and persisted runtime configuration for the UI."""
    _load_state()
    return {
        "active": _state.get("active", "qwen"),
        "builtins": [
            _provider_template(key, cls)
            for key, cls in _BUILTIN_CLASSES.items()
            if key != "custom"
        ],
        "custom": _provider_template("custom", CustomProvider),
        "configured": _state.get("providers", {}),
    }


def set_active_provider(key: str, config: dict | None = None) -> None:
    """Switch the active provider and persist optional provider configuration."""
    with _lock:
        _load_state()
        if key not in _BUILTIN_CLASSES:
            raise ValueError(f"未知的 provider key: {key}")
        _state["active"] = key
        if config is not None:
            existing = _state.setdefault("providers", {}).get(key, {})
            _state["providers"][key] = {**existing, **_normalize_config(config)}
        _save_state()
        _instances.pop(key, None)


def check_provider_config(key: str, config: dict | None = None) -> dict:
    """Run a lightweight provider health check without changing the saved active provider."""
    _load_state()
    if key not in _BUILTIN_CLASSES:
        raise ValueError(f"未知的 provider key: {key}")

    cls = _BUILTIN_CLASSES[key]
    saved = _state.get("providers", {}).get(key, {})
    merged_config = {**saved, **_normalize_config(config)}
    provider = cls(
        api_key=merged_config.get("api_key"),
        base_url=merged_config.get("base_url") or None,
        model=merged_config.get("model") or None,
        display_name=merged_config.get("display_name") or None,
    )
    ok = provider.health_check()
    return {
        "ok": ok,
        "active": key,
        "provider": provider.display_name,
        "model": provider.model,
        "base_url": provider.base_url,
    }


def fetch_provider_models(key: str, config: dict | None = None) -> dict:
    """Fetch model ids from an OpenAI-compatible provider using the draft settings."""
    _load_state()
    if key not in _BUILTIN_CLASSES:
        raise ValueError(f"未知的 provider key: {key}")

    cls = _BUILTIN_CLASSES[key]
    saved = _state.get("providers", {}).get(key, {})
    merged_config = {**saved, **_normalize_config(config)}
    provider = cls(
        api_key=merged_config.get("api_key"),
        base_url=merged_config.get("base_url") or None,
        model=merged_config.get("model") or None,
        display_name=merged_config.get("display_name") or None,
    )

    try:
        models = provider.list_models()
    except Exception as exc:
        return {
            "success": False,
            "active": key,
            "models": [],
            "error": str(exc),
        }

    return {
        "success": True,
        "active": key,
        "models": models,
        "count": len(models),
    }


def get_active_provider() -> BaseLLMProvider:
    with _lock:
        _load_state()
        key = _state.get("active", "qwen")
        if key not in _BUILTIN_CLASSES:
            key = "qwen"
            _state["active"] = key
        if key in _instances:
            return _instances[key]
        cls = _BUILTIN_CLASSES[key]
        cfg = _state.get("providers", {}).get(key, {})
        instance = cls(
            api_key=cfg.get("api_key"),
            base_url=cfg.get("base_url") or None,
            model=cfg.get("model") or None,
            display_name=cfg.get("display_name") or None,
        )
        _instances[key] = instance
        return instance
