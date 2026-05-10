from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    content: str
    model: str
    provider: str
    usage: dict[str, Any] | None = None


class BaseLLMProvider(ABC):
    """Common interface implemented by every LLM provider."""

    key: str
    display_name: str
    default_model: str
    default_base_url: str

    @abstractmethod
    def chat(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str | None = None,
        temperature: float = 0.2,
        response_format_json: bool = True,
        timeout: float = 60.0,
    ) -> LLMResponse:
        """Call the model. Failures are raised so callers can decide fallback behavior."""
        ...

    @abstractmethod
    def health_check(self) -> bool:
        """Return True when the current provider configuration is usable."""
        ...

    def list_models(self) -> list[str]:
        """Return model ids when the provider exposes a model listing endpoint."""
        return []
