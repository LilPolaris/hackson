import os
from typing import Any

from anthropic import Anthropic
from openai import OpenAI

from .base import BaseLLMProvider, LLMResponse


class _OpenAICompatibleProvider(BaseLLMProvider):
    """Shared implementation for providers that expose the OpenAI Chat Completions API."""

    env_key_name: str
    available_models: list[str] = []
    website_url: str = ""
    docs_url: str = ""
    base_url_candidates: list[str] = []

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        display_name: str | None = None,
    ):
        self.api_key = api_key or os.getenv(self.env_key_name, "")
        self.base_url = base_url or self.default_base_url
        self.model = model or self.default_model
        if display_name:
            self.display_name = display_name
        self._client: OpenAI | None = None

    def _client_lazy(self) -> OpenAI:
        if self._client is None:
            if not self.api_key:
                raise RuntimeError(f"{self.display_name} API key 未配置（env: {self.env_key_name}）")
            if not self.base_url:
                raise RuntimeError(f"{self.display_name} base_url 未配置")
            self._client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        return self._client

    def _create_completion(self, kwargs: dict[str, Any]):
        return self._client_lazy().chat.completions.create(**kwargs)

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
        kwargs: dict[str, Any] = {
            "model": model or self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "timeout": timeout,
        }
        if response_format_json:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = self._create_completion(kwargs)
        except Exception:
            if "response_format" not in kwargs:
                raise
            kwargs.pop("response_format", None)
            resp = self._create_completion(kwargs)

        usage = resp.usage.model_dump() if getattr(resp, "usage", None) else None
        return LLMResponse(
            content=resp.choices[0].message.content or "",
            model=resp.model,
            provider=self.key,
            usage=usage,
        )

    def health_check(self) -> bool:
        try:
            self.chat(
                "你是健康检查助手，只输出 JSON。",
                '请回复 {"ok": true}',
                temperature=0,
                timeout=10.0,
            )
            return True
        except Exception:
            return False

    def list_models(self) -> list[str]:
        models = self._client_lazy().models.list()
        return sorted(
            {
                model_id
                for item in getattr(models, "data", [])
                if (model_id := getattr(item, "id", None))
            }
        )


class OpenAIProvider(_OpenAICompatibleProvider):
    key = "openai"
    display_name = "OpenAI"
    default_model = "gpt-5.5"
    default_base_url = "https://api.openai.com/v1"
    env_key_name = "OPENAI_API_KEY"
    website_url = "https://platform.openai.com"
    docs_url = "https://platform.openai.com/docs/models"
    base_url_candidates = ["https://api.openai.com/v1"]
    available_models = [
        "gpt-5.5",
        "gpt-5.2",
        "gpt-5.2-chat-latest",
        "gpt-5.2-pro",
        "gpt-5-mini",
        "gpt-5-nano",
        "gpt-4o-mini",
    ]


class AnthropicProvider(BaseLLMProvider):
    key = "anthropic"
    display_name = "Anthropic"
    default_model = "claude-3-5-sonnet-latest"
    default_base_url = "https://api.anthropic.com"
    env_key_name = "ANTHROPIC_API_KEY"
    website_url = "https://console.anthropic.com"
    docs_url = "https://docs.anthropic.com/en/docs/about-claude/models"
    base_url_candidates = ["https://api.anthropic.com"]
    available_models = [
        "claude-3-5-sonnet-latest",
        "claude-3-5-haiku-latest",
        "claude-3-opus-latest",
        "claude-sonnet-4-5",
        "claude-haiku-4-5",
    ]

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        display_name: str | None = None,
    ):
        self.api_key = api_key or os.getenv(self.env_key_name, "")
        self.base_url = base_url or self.default_base_url
        self.model = model or self.default_model
        if display_name:
            self.display_name = display_name
        self._client: Anthropic | None = None

    def _client_lazy(self) -> Anthropic:
        if self._client is None:
            if not self.api_key:
                raise RuntimeError(f"{self.display_name} API key 未配置（env: {self.env_key_name}）")
            self._client = Anthropic(api_key=self.api_key, base_url=self.base_url)
        return self._client

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
        if response_format_json:
            system_prompt = f"{system_prompt}\n只输出 JSON，不要输出解释或 Markdown。"

        resp = self._client_lazy().messages.create(
            model=model or self.model,
            max_tokens=4096,
            temperature=temperature,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
            timeout=timeout,
        )
        content = "".join(block.text for block in resp.content if getattr(block, "type", "") == "text")
        usage = resp.usage.model_dump() if getattr(resp, "usage", None) else None
        return LLMResponse(content=content, model=resp.model, provider=self.key, usage=usage)

    def health_check(self) -> bool:
        try:
            self.chat(
                "你是健康检查助手，只输出 JSON。",
                '请回复 {"ok": true}',
                temperature=0,
                timeout=10.0,
            )
            return True
        except Exception:
            return False

    def list_models(self) -> list[str]:
        models = self._client_lazy().models.list()
        return sorted({item.id for item in getattr(models, "data", []) if getattr(item, "id", None)})


class QwenProvider(_OpenAICompatibleProvider):
    key = "qwen"
    display_name = "通义千问"
    default_model = "qwen3.6-plus"
    default_base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    env_key_name = "DASHSCOPE_API_KEY"
    website_url = "https://dashscope.aliyun.com"
    docs_url = "https://help.aliyun.com/zh/model-studio/getting-started/models"
    base_url_candidates = ["https://dashscope.aliyuncs.com/compatible-mode/v1"]
    available_models = [
        "qwen3.6-plus",
        "qwen3.6-flash",
        "qwen3.6-max-preview",
        "qwen-plus",
        "qwen-turbo",
        "qwen-max",
    ]


class DeepSeekProvider(_OpenAICompatibleProvider):
    key = "deepseek"
    display_name = "DeepSeek"
    default_model = "deepseek-v4-flash"
    default_base_url = "https://api.deepseek.com/v1"
    env_key_name = "DEEPSEEK_API_KEY"
    website_url = "https://www.deepseek.com"
    docs_url = "https://api-docs.deepseek.com"
    base_url_candidates = ["https://api.deepseek.com/v1", "https://api.deepseek.com"]
    available_models = ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"]


class GeminiProvider(_OpenAICompatibleProvider):
    key = "gemini"
    display_name = "Google Gemini"
    default_model = "gemini-3.1-pro-preview"
    default_base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
    env_key_name = "GEMINI_API_KEY"
    website_url = "https://aistudio.google.com"
    docs_url = "https://ai.google.dev/gemini-api/docs/openai"
    base_url_candidates = ["https://generativelanguage.googleapis.com/v1beta/openai/"]
    available_models = [
        "gemini-3.1-pro-preview",
        "gemini-3.1-flash-lite",
        "gemini-3.1-flash-lite-preview",
        "gemini-3.1-flash-image-preview",
        "gemini-3-pro-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
    ]


class XAIProvider(_OpenAICompatibleProvider):
    key = "xai"
    display_name = "xAI Grok"
    default_model = "grok-4"
    default_base_url = "https://api.x.ai/v1"
    env_key_name = "XAI_API_KEY"
    website_url = "https://console.x.ai"
    docs_url = "https://docs.x.ai"
    base_url_candidates = ["https://api.x.ai/v1"]
    available_models = ["grok-4", "grok-3", "grok-3-mini", "grok-2-vision-1212"]


class MoonshotProvider(_OpenAICompatibleProvider):
    key = "moonshot"
    display_name = "Moonshot / Kimi"
    default_model = "kimi-k2-0711-preview"
    default_base_url = "https://api.moonshot.cn/v1"
    env_key_name = "MOONSHOT_API_KEY"
    website_url = "https://platform.moonshot.cn"
    docs_url = "https://platform.moonshot.cn/docs"
    base_url_candidates = ["https://api.moonshot.cn/v1"]
    available_models = ["kimi-k2-0711-preview", "moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"]


class ZhipuProvider(_OpenAICompatibleProvider):
    key = "zhipu"
    display_name = "智谱 GLM"
    default_model = "glm-4-plus"
    default_base_url = "https://open.bigmodel.cn/api/paas/v4"
    env_key_name = "ZHIPU_API_KEY"
    website_url = "https://bigmodel.cn"
    docs_url = "https://docs.bigmodel.cn"
    base_url_candidates = ["https://open.bigmodel.cn/api/paas/v4"]
    available_models = ["glm-4-plus", "glm-4-air", "glm-4-flash", "glm-4.5", "glm-4.5-air"]


class SiliconFlowProvider(_OpenAICompatibleProvider):
    key = "siliconflow"
    display_name = "SiliconFlow"
    default_model = "Qwen/Qwen2.5-72B-Instruct"
    default_base_url = "https://api.siliconflow.cn/v1"
    env_key_name = "SILICONFLOW_API_KEY"
    website_url = "https://cloud.siliconflow.cn"
    docs_url = "https://docs.siliconflow.cn"
    base_url_candidates = ["https://api.siliconflow.cn/v1"]
    available_models = [
        "Qwen/Qwen2.5-72B-Instruct",
        "deepseek-ai/DeepSeek-V3",
        "deepseek-ai/DeepSeek-R1",
        "THUDM/glm-4-9b-chat",
    ]


class VolcengineProvider(_OpenAICompatibleProvider):
    key = "volcengine"
    display_name = "火山方舟 / Doubao"
    default_model = "doubao-1-5-pro-32k"
    default_base_url = "https://ark.cn-beijing.volces.com/api/v3"
    env_key_name = "VOLCENGINE_API_KEY"
    website_url = "https://console.volcengine.com/ark"
    docs_url = "https://www.volcengine.com/docs/82379"
    base_url_candidates = ["https://ark.cn-beijing.volces.com/api/v3"]
    available_models = ["doubao-1-5-pro-32k", "doubao-1-5-lite-32k", "doubao-pro-32k", "doubao-lite-32k"]


class MiniMaxProvider(_OpenAICompatibleProvider):
    key = "minimax"
    display_name = "MiniMax"
    default_model = "MiniMax-Text-01"
    default_base_url = "https://api.minimax.chat/v1"
    env_key_name = "MINIMAX_API_KEY"
    website_url = "https://platform.minimaxi.com"
    docs_url = "https://platform.minimaxi.com/document"
    base_url_candidates = ["https://api.minimax.chat/v1"]
    available_models = ["MiniMax-Text-01", "abab6.5s-chat", "abab6.5g-chat", "abab6.5t-chat"]


class BaichuanProvider(_OpenAICompatibleProvider):
    key = "baichuan"
    display_name = "百川智能"
    default_model = "Baichuan4"
    default_base_url = "https://api.baichuan-ai.com/v1"
    env_key_name = "BAICHUAN_API_KEY"
    website_url = "https://platform.baichuan-ai.com"
    docs_url = "https://platform.baichuan-ai.com/docs"
    base_url_candidates = ["https://api.baichuan-ai.com/v1"]
    available_models = ["Baichuan4", "Baichuan3-Turbo", "Baichuan3-Turbo-128k"]


class BaiduQianfanProvider(_OpenAICompatibleProvider):
    key = "baidu_qianfan"
    display_name = "百度千帆 / ERNIE"
    default_model = "ernie-4.0-turbo-8k"
    default_base_url = "https://qianfan.baidubce.com/v2"
    env_key_name = "QIANFAN_API_KEY"
    website_url = "https://console.bce.baidu.com/qianfan"
    docs_url = "https://cloud.baidu.com/doc/WENXINWORKSHOP/index.html"
    base_url_candidates = ["https://qianfan.baidubce.com/v2"]
    available_models = ["ernie-4.0-turbo-8k", "ernie-4.0-8k", "ernie-speed-8k", "ernie-lite-8k"]


class TencentHunyuanProvider(_OpenAICompatibleProvider):
    key = "tencent_hunyuan"
    display_name = "腾讯混元"
    default_model = "hunyuan-turbos-latest"
    default_base_url = "https://api.hunyuan.cloud.tencent.com/v1"
    env_key_name = "HUNYUAN_API_KEY"
    website_url = "https://cloud.tencent.com/product/hunyuan"
    docs_url = "https://cloud.tencent.com/document/product/1729"
    base_url_candidates = ["https://api.hunyuan.cloud.tencent.com/v1"]
    available_models = ["hunyuan-turbos-latest", "hunyuan-turbo", "hunyuan-large", "hunyuan-standard"]


class MistralProvider(_OpenAICompatibleProvider):
    key = "mistral"
    display_name = "Mistral"
    default_model = "mistral-large-latest"
    default_base_url = "https://api.mistral.ai/v1"
    env_key_name = "MISTRAL_API_KEY"
    website_url = "https://console.mistral.ai"
    docs_url = "https://docs.mistral.ai"
    base_url_candidates = ["https://api.mistral.ai/v1"]
    available_models = ["mistral-large-latest", "mistral-small-latest", "codestral-latest", "open-mixtral-8x22b"]


class GroqProvider(_OpenAICompatibleProvider):
    key = "groq"
    display_name = "Groq"
    default_model = "llama-3.3-70b-versatile"
    default_base_url = "https://api.groq.com/openai/v1"
    env_key_name = "GROQ_API_KEY"
    website_url = "https://console.groq.com"
    docs_url = "https://console.groq.com/docs"
    base_url_candidates = ["https://api.groq.com/openai/v1"]
    available_models = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"]


class TogetherProvider(_OpenAICompatibleProvider):
    key = "together"
    display_name = "Together AI"
    default_model = "meta-llama/Llama-3.3-70B-Instruct-Turbo"
    default_base_url = "https://api.together.xyz/v1"
    env_key_name = "TOGETHER_API_KEY"
    website_url = "https://api.together.ai"
    docs_url = "https://docs.together.ai"
    base_url_candidates = ["https://api.together.xyz/v1"]
    available_models = [
        "meta-llama/Llama-3.3-70B-Instruct-Turbo",
        "Qwen/Qwen2.5-72B-Instruct-Turbo",
        "deepseek-ai/DeepSeek-V3",
    ]


class OpenRouterProvider(_OpenAICompatibleProvider):
    key = "openrouter"
    display_name = "OpenRouter"
    default_model = "openai/gpt-4o-mini"
    default_base_url = "https://openrouter.ai/api/v1"
    env_key_name = "OPENROUTER_API_KEY"
    website_url = "https://openrouter.ai"
    docs_url = "https://openrouter.ai/docs"
    base_url_candidates = ["https://openrouter.ai/api/v1"]
    available_models = [
        "openai/gpt-4o-mini",
        "anthropic/claude-3.5-sonnet",
        "google/gemini-2.5-pro",
        "deepseek/deepseek-chat",
    ]


class PerplexityProvider(_OpenAICompatibleProvider):
    key = "perplexity"
    display_name = "Perplexity"
    default_model = "sonar-pro"
    default_base_url = "https://api.perplexity.ai"
    env_key_name = "PERPLEXITY_API_KEY"
    website_url = "https://www.perplexity.ai/settings/api"
    docs_url = "https://docs.perplexity.ai"
    base_url_candidates = ["https://api.perplexity.ai"]
    available_models = ["sonar-pro", "sonar", "sonar-reasoning-pro", "sonar-deep-research"]


class OllamaProvider(_OpenAICompatibleProvider):
    key = "ollama"
    display_name = "Ollama"
    default_model = "llama3.1"
    default_base_url = "http://127.0.0.1:11434/v1"
    env_key_name = "OLLAMA_API_KEY"
    website_url = "https://ollama.com"
    docs_url = "https://github.com/ollama/ollama/blob/main/docs/openai.md"
    base_url_candidates = ["http://127.0.0.1:11434/v1", "http://localhost:11434/v1"]
    available_models = ["llama3.1", "qwen2.5", "deepseek-r1", "mistral"]

    def _client_lazy(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key or "ollama", base_url=self.base_url)
        return self._client


class LMStudioProvider(_OpenAICompatibleProvider):
    key = "lmstudio"
    display_name = "LM Studio"
    default_model = "local-model"
    default_base_url = "http://localhost:1234/v1"
    env_key_name = "LMSTUDIO_API_KEY"
    website_url = "https://lmstudio.ai"
    docs_url = "https://lmstudio.ai/docs"
    base_url_candidates = ["http://localhost:1234/v1", "http://127.0.0.1:1234/v1"]
    available_models = ["local-model"]

    def _client_lazy(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key or "lm-studio", base_url=self.base_url)
        return self._client


class CustomProvider(_OpenAICompatibleProvider):
    key = "custom"
    display_name = "自定义"
    default_model = ""
    default_base_url = ""
    env_key_name = "CUSTOM_LLM_API_KEY"
    website_url = ""
    docs_url = ""
    base_url_candidates = [
        "http://127.0.0.1:11434/v1",
        "http://localhost:1234/v1",
        "https://api.openai.com/v1",
    ]
    available_models = []
