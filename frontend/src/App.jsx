import React, { useEffect, useMemo, useState } from "react";
import { Activity, ArrowUpRight, CheckCircle2, FileText, Network, Save, Settings, Sparkles, X } from "lucide-react";
import {
  buildGraphV2,
  chat,
  checkLLMProvider,
  deleteTextbook,
  fetchLLMModels,
  generateReport,
  getGraphV2,
  getGraphBuildStatus,
  listLLMProviders,
  listTextbooks,
  mergeTextbooks,
  parseUploadedTextbook,
  ragQuery,
  updateLLMProvider,
  uploadTextbook,
} from "./api";
import KnowledgeGraph from "./components/KnowledgeGraph.jsx";
import RightTabs from "./components/RightTabs.jsx";
import TextbookManager from "./components/TextbookManager.jsx";

const EMPTY_GRAPH = { nodes: [], edges: [] };
const PROVIDER_ORDER = [
  "openai",
  "anthropic",
  "qwen",
  "deepseek",
  "gemini",
  "xai",
  "moonshot",
  "zhipu",
  "siliconflow",
  "volcengine",
  "minimax",
  "baichuan",
  "baidu_qianfan",
  "tencent_hunyuan",
  "mistral",
  "groq",
  "together",
  "openrouter",
  "perplexity",
  "ollama",
  "lmstudio",
  "custom",
];

const FALLBACK_PROVIDER_OPTIONS = [
  {
    key: "openai",
    display_name: "OpenAI",
    default_model: "gpt-5.5",
    default_base_url: "https://api.openai.com/v1",
    env_key_name: "OPENAI_API_KEY",
    available_models: ["gpt-5.5", "gpt-5.2", "gpt-5.2-chat-latest", "gpt-5.2-pro", "gpt-5-mini", "gpt-5-nano", "gpt-4o-mini"],
    base_url_candidates: ["https://api.openai.com/v1"],
    website_url: "https://platform.openai.com",
    docs_url: "https://platform.openai.com/docs/models",
  },
  {
    key: "anthropic",
    display_name: "Anthropic",
    default_model: "claude-3-5-sonnet-latest",
    default_base_url: "https://api.anthropic.com",
    env_key_name: "ANTHROPIC_API_KEY",
    available_models: ["claude-3-5-sonnet-latest", "claude-3-5-haiku-latest", "claude-3-opus-latest", "claude-sonnet-4-5", "claude-haiku-4-5"],
    base_url_candidates: ["https://api.anthropic.com"],
    website_url: "https://console.anthropic.com",
    docs_url: "https://docs.anthropic.com/en/docs/about-claude/models",
  },
  {
    key: "qwen",
    display_name: "通义千问",
    default_model: "qwen3.6-plus",
    default_base_url: "https://dashscope.aliyuncs.com/compatible-mode/v1",
    env_key_name: "DASHSCOPE_API_KEY",
    available_models: ["qwen3.6-plus", "qwen3.6-flash", "qwen3.6-max-preview", "qwen-plus", "qwen-turbo", "qwen-max"],
    base_url_candidates: ["https://dashscope.aliyuncs.com/compatible-mode/v1"],
    website_url: "https://dashscope.aliyun.com",
    docs_url: "https://help.aliyun.com/zh/model-studio/getting-started/models",
  },
  {
    key: "gemini",
    display_name: "Google Gemini",
    default_model: "gemini-3.1-pro-preview",
    default_base_url: "https://generativelanguage.googleapis.com/v1beta/openai/",
    env_key_name: "GEMINI_API_KEY",
    available_models: [
      "gemini-3.1-pro-preview",
      "gemini-3.1-flash-lite",
      "gemini-3.1-flash-lite-preview",
      "gemini-3.1-flash-image-preview",
      "gemini-3-pro-preview",
      "gemini-2.5-pro",
      "gemini-2.5-flash",
      "gemini-2.0-flash",
    ],
    base_url_candidates: ["https://generativelanguage.googleapis.com/v1beta/openai/"],
    website_url: "https://aistudio.google.com",
    docs_url: "https://ai.google.dev/gemini-api/docs/openai",
  },
  {
    key: "xai",
    display_name: "xAI Grok",
    default_model: "grok-4",
    default_base_url: "https://api.x.ai/v1",
    env_key_name: "XAI_API_KEY",
    available_models: ["grok-4", "grok-3", "grok-3-mini", "grok-2-vision-1212"],
    base_url_candidates: ["https://api.x.ai/v1"],
    website_url: "https://console.x.ai",
    docs_url: "https://docs.x.ai",
  },
  {
    key: "moonshot",
    display_name: "Moonshot / Kimi",
    default_model: "kimi-k2-0711-preview",
    default_base_url: "https://api.moonshot.cn/v1",
    env_key_name: "MOONSHOT_API_KEY",
    available_models: ["kimi-k2-0711-preview", "moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
    base_url_candidates: ["https://api.moonshot.cn/v1"],
    website_url: "https://platform.moonshot.cn",
    docs_url: "https://platform.moonshot.cn/docs",
  },
  {
    key: "zhipu",
    display_name: "智谱 GLM",
    default_model: "glm-4-plus",
    default_base_url: "https://open.bigmodel.cn/api/paas/v4",
    env_key_name: "ZHIPU_API_KEY",
    available_models: ["glm-4-plus", "glm-4-air", "glm-4-flash", "glm-4.5", "glm-4.5-air"],
    base_url_candidates: ["https://open.bigmodel.cn/api/paas/v4"],
    website_url: "https://bigmodel.cn",
    docs_url: "https://docs.bigmodel.cn",
  },
  {
    key: "siliconflow",
    display_name: "SiliconFlow",
    default_model: "Qwen/Qwen2.5-72B-Instruct",
    default_base_url: "https://api.siliconflow.cn/v1",
    env_key_name: "SILICONFLOW_API_KEY",
    available_models: ["Qwen/Qwen2.5-72B-Instruct", "deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-R1", "THUDM/glm-4-9b-chat"],
    base_url_candidates: ["https://api.siliconflow.cn/v1"],
    website_url: "https://cloud.siliconflow.cn",
    docs_url: "https://docs.siliconflow.cn",
  },
  {
    key: "volcengine",
    display_name: "火山方舟 / Doubao",
    default_model: "doubao-1-5-pro-32k",
    default_base_url: "https://ark.cn-beijing.volces.com/api/v3",
    env_key_name: "VOLCENGINE_API_KEY",
    available_models: ["doubao-1-5-pro-32k", "doubao-1-5-lite-32k", "doubao-pro-32k", "doubao-lite-32k"],
    base_url_candidates: ["https://ark.cn-beijing.volces.com/api/v3"],
    website_url: "https://console.volcengine.com/ark",
    docs_url: "https://www.volcengine.com/docs/82379",
  },
  {
    key: "minimax",
    display_name: "MiniMax",
    default_model: "MiniMax-Text-01",
    default_base_url: "https://api.minimax.chat/v1",
    env_key_name: "MINIMAX_API_KEY",
    available_models: ["MiniMax-Text-01", "abab6.5s-chat", "abab6.5g-chat", "abab6.5t-chat"],
    base_url_candidates: ["https://api.minimax.chat/v1"],
    website_url: "https://platform.minimaxi.com",
    docs_url: "https://platform.minimaxi.com/document",
  },
  {
    key: "baichuan",
    display_name: "百川智能",
    default_model: "Baichuan4",
    default_base_url: "https://api.baichuan-ai.com/v1",
    env_key_name: "BAICHUAN_API_KEY",
    available_models: ["Baichuan4", "Baichuan3-Turbo", "Baichuan3-Turbo-128k"],
    base_url_candidates: ["https://api.baichuan-ai.com/v1"],
    website_url: "https://platform.baichuan-ai.com",
    docs_url: "https://platform.baichuan-ai.com/docs",
  },
  {
    key: "baidu_qianfan",
    display_name: "百度千帆 / ERNIE",
    default_model: "ernie-4.0-turbo-8k",
    default_base_url: "https://qianfan.baidubce.com/v2",
    env_key_name: "QIANFAN_API_KEY",
    available_models: ["ernie-4.0-turbo-8k", "ernie-4.0-8k", "ernie-speed-8k", "ernie-lite-8k"],
    base_url_candidates: ["https://qianfan.baidubce.com/v2"],
    website_url: "https://console.bce.baidu.com/qianfan",
    docs_url: "https://cloud.baidu.com/doc/WENXINWORKSHOP/index.html",
  },
  {
    key: "tencent_hunyuan",
    display_name: "腾讯混元",
    default_model: "hunyuan-turbos-latest",
    default_base_url: "https://api.hunyuan.cloud.tencent.com/v1",
    env_key_name: "HUNYUAN_API_KEY",
    available_models: ["hunyuan-turbos-latest", "hunyuan-turbo", "hunyuan-large", "hunyuan-standard"],
    base_url_candidates: ["https://api.hunyuan.cloud.tencent.com/v1"],
    website_url: "https://cloud.tencent.com/product/hunyuan",
    docs_url: "https://cloud.tencent.com/document/product/1729",
  },
  {
    key: "mistral",
    display_name: "Mistral",
    default_model: "mistral-large-latest",
    default_base_url: "https://api.mistral.ai/v1",
    env_key_name: "MISTRAL_API_KEY",
    available_models: ["mistral-large-latest", "mistral-small-latest", "codestral-latest", "open-mixtral-8x22b"],
    base_url_candidates: ["https://api.mistral.ai/v1"],
    website_url: "https://console.mistral.ai",
    docs_url: "https://docs.mistral.ai",
  },
  {
    key: "groq",
    display_name: "Groq",
    default_model: "llama-3.3-70b-versatile",
    default_base_url: "https://api.groq.com/openai/v1",
    env_key_name: "GROQ_API_KEY",
    available_models: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768", "gemma2-9b-it"],
    base_url_candidates: ["https://api.groq.com/openai/v1"],
    website_url: "https://console.groq.com",
    docs_url: "https://console.groq.com/docs",
  },
  {
    key: "together",
    display_name: "Together AI",
    default_model: "meta-llama/Llama-3.3-70B-Instruct-Turbo",
    default_base_url: "https://api.together.xyz/v1",
    env_key_name: "TOGETHER_API_KEY",
    available_models: ["meta-llama/Llama-3.3-70B-Instruct-Turbo", "Qwen/Qwen2.5-72B-Instruct-Turbo", "deepseek-ai/DeepSeek-V3"],
    base_url_candidates: ["https://api.together.xyz/v1"],
    website_url: "https://api.together.ai",
    docs_url: "https://docs.together.ai",
  },
  {
    key: "openrouter",
    display_name: "OpenRouter",
    default_model: "openai/gpt-4o-mini",
    default_base_url: "https://openrouter.ai/api/v1",
    env_key_name: "OPENROUTER_API_KEY",
    available_models: ["openai/gpt-4o-mini", "anthropic/claude-3.5-sonnet", "google/gemini-2.5-pro", "deepseek/deepseek-chat"],
    base_url_candidates: ["https://openrouter.ai/api/v1"],
    website_url: "https://openrouter.ai",
    docs_url: "https://openrouter.ai/docs",
  },
  {
    key: "perplexity",
    display_name: "Perplexity",
    default_model: "sonar-pro",
    default_base_url: "https://api.perplexity.ai",
    env_key_name: "PERPLEXITY_API_KEY",
    available_models: ["sonar-pro", "sonar", "sonar-reasoning-pro", "sonar-deep-research"],
    base_url_candidates: ["https://api.perplexity.ai"],
    website_url: "https://www.perplexity.ai/settings/api",
    docs_url: "https://docs.perplexity.ai",
  },
  {
    key: "ollama",
    display_name: "Ollama",
    default_model: "llama3.1",
    default_base_url: "http://127.0.0.1:11434/v1",
    env_key_name: "OLLAMA_API_KEY",
    available_models: ["llama3.1", "qwen2.5", "deepseek-r1", "mistral"],
    base_url_candidates: ["http://127.0.0.1:11434/v1", "http://localhost:11434/v1"],
    website_url: "https://ollama.com",
    docs_url: "https://github.com/ollama/ollama/blob/main/docs/openai.md",
  },
  {
    key: "lmstudio",
    display_name: "LM Studio",
    default_model: "local-model",
    default_base_url: "http://localhost:1234/v1",
    env_key_name: "LMSTUDIO_API_KEY",
    available_models: ["local-model"],
    base_url_candidates: ["http://localhost:1234/v1", "http://127.0.0.1:1234/v1"],
    website_url: "https://lmstudio.ai",
    docs_url: "https://lmstudio.ai/docs",
  },
  {
    key: "deepseek",
    display_name: "DeepSeek",
    default_model: "deepseek-v4-flash",
    default_base_url: "https://api.deepseek.com/v1",
    env_key_name: "DEEPSEEK_API_KEY",
    available_models: ["deepseek-v4-flash", "deepseek-v4-pro", "deepseek-chat", "deepseek-reasoner"],
    base_url_candidates: ["https://api.deepseek.com/v1", "https://api.deepseek.com"],
    website_url: "https://www.deepseek.com",
    docs_url: "https://api-docs.deepseek.com",
  },
  {
    key: "custom",
    display_name: "自定义",
    default_model: "",
    default_base_url: "",
    env_key_name: "CUSTOM_LLM_API_KEY",
    available_models: [],
    base_url_candidates: ["http://127.0.0.1:11434/v1", "http://localhost:1234/v1", "https://api.openai.com/v1"],
    website_url: "",
    docs_url: "",
  },
];

function providerOptionsFromRegistry(registry) {
  const fallbackBuiltins = FALLBACK_PROVIDER_OPTIONS.filter((provider) => provider.key !== "custom");
  const fallbackCustom = FALLBACK_PROVIDER_OPTIONS.find((provider) => provider.key === "custom");
  const backendBuiltins = Array.isArray(registry?.builtins) ? registry.builtins : [];
  const byKey = new Map();

  for (const provider of fallbackBuiltins) {
    byKey.set(provider.key, provider);
  }
  for (const provider of backendBuiltins) {
    byKey.set(provider.key, { ...(byKey.get(provider.key) || {}), ...provider });
  }

  const ordered = fallbackBuiltins
    .map((provider) => byKey.get(provider.key))
    .filter(Boolean);
  for (const provider of backendBuiltins) {
    if (!ordered.some((item) => item.key === provider.key)) {
      ordered.push(provider);
    }
  }
  ordered.sort((left, right) => {
    const leftIndex = PROVIDER_ORDER.indexOf(left.key);
    const rightIndex = PROVIDER_ORDER.indexOf(right.key);
    return (leftIndex === -1 ? 999 : leftIndex) - (rightIndex === -1 ? 999 : rightIndex);
  });

  const custom = registry?.custom ? { ...(fallbackCustom || {}), ...registry.custom } : fallbackCustom;
  return custom && !ordered.some((provider) => provider.key === "custom") ? [...ordered, custom] : ordered;
}

function draftFromRegistry(registry, activeKey) {
  const options = providerOptionsFromRegistry(registry);
  const active = activeKey || registry?.active || "qwen";
  const option = options.find((item) => item.key === active) || options[0];
  const configured = registry?.configured?.[option.key] || {};
  return {
    active: option.key,
    api_key: configured.api_key || "",
    base_url: configured.base_url || option.default_base_url || "",
    model: configured.model || option.default_model || "",
    display_name: configured.display_name || "",
    notes: configured.notes || "",
  };
}

function formatGraphBuildStatus(status) {
  if (!status) {
    return "";
  }
  const current = Number.isFinite(Number(status.current)) ? Number(status.current) : 0;
  const total = Number.isFinite(Number(status.total)) ? Number(status.total) : 0;
  const prefix = total > 0 ? `${current}/${total}` : "";
  return [prefix, status.message].filter(Boolean).join(" · ");
}

function App() {
  const [textbooks, setTextbooks] = useState([]);
  const [activeTextbookId, setActiveTextbookId] = useState(null);
  const [graph, setGraph] = useState(EMPTY_GRAPH);
  const [graphMeta, setGraphMeta] = useState({ status: "empty", provider: null, model: null, error: null });
  const [graphBuildStatus, setGraphBuildStatus] = useState(null);
  const [selectedNode, setSelectedNode] = useState(null);
  const [panelData, setPanelData] = useState({
    parse: "等待上传教材",
    merge: "等待合并结果",
    rag: "等待检索结果",
    chat: "等待教师反馈",
    report: "等待报告生成",
  });
  const [isLoading, setIsLoading] = useState(false);
  const [notice, setNotice] = useState("");
  const [isLLMSettingsOpen, setIsLLMSettingsOpen] = useState(false);
  const [llmRegistry, setLLMRegistry] = useState(null);
  const [llmDraft, setLLMDraft] = useState(() => draftFromRegistry(null, "qwen"));
  const [isProviderSaving, setIsProviderSaving] = useState(false);
  const [isProviderChecking, setIsProviderChecking] = useState(false);
  const [isModelFetching, setIsModelFetching] = useState(false);
  const [providerStatus, setProviderStatus] = useState(null);
  const [modelFetchStatus, setModelFetchStatus] = useState(null);
  const [fetchedModels, setFetchedModels] = useState({});
  const [providerFilter, setProviderFilter] = useState("");

  const activeTextbook = useMemo(
    () => textbooks.find((item) => item.textbook_id === activeTextbookId),
    [activeTextbookId, textbooks],
  );
  const providerOptions = useMemo(() => providerOptionsFromRegistry(llmRegistry), [llmRegistry]);
  const activeProvider = providerOptions.find((item) => item.key === llmDraft.active);
  const activeModelOptions = useMemo(
    () =>
      Array.from(
        new Set([
          activeProvider?.default_model,
          ...(activeProvider?.available_models || []),
          ...(fetchedModels[llmDraft.active] || []),
          llmDraft.model,
        ].filter(Boolean)),
      ),
    [activeProvider, fetchedModels, llmDraft.active, llmDraft.model],
  );
  const activeBaseUrlCandidates = useMemo(
    () => Array.from(new Set([...(activeProvider?.base_url_candidates || []), activeProvider?.default_base_url, llmDraft.base_url].filter(Boolean))),
    [activeProvider, llmDraft.base_url],
  );
  const filteredProviderOptions = useMemo(() => {
    const keyword = providerFilter.trim().toLowerCase();
    if (!keyword) {
      return providerOptions;
    }
    return providerOptions.filter((provider) => {
      const haystack = `${provider.key} ${provider.display_name} ${provider.default_model}`.toLowerCase();
      return haystack.includes(keyword);
    });
  }, [providerFilter, providerOptions]);

  const parsedCount = textbooks.filter((item) => item.parse_status === "parsed").length;
  const graphNodeCount = graph?.nodes?.length || 0;
  const graphEdgeCount = graph?.edges?.length || 0;
  const graphTextbookId = activeTextbookId || "demo-textbook";

  useEffect(() => {
    refreshTextbooks();
    refreshProviders();
  }, []);

  useEffect(() => {
    let cancelled = false;
    setGraphBuildStatus(null);
    getGraphV2(graphTextbookId)
      .then((data) => {
        if (cancelled) {
          return;
        }
        setGraph(data.graph || EMPTY_GRAPH);
        setGraphMeta({
          status: data.status || "empty",
          provider: data.provider || null,
          model: data.model || null,
          error: data.error || null,
        });
        setSelectedNode(null);
      })
      .catch(() => {
        if (!cancelled) {
          setGraph(EMPTY_GRAPH);
          setGraphMeta({ status: "empty", provider: null, model: null, error: null });
          setSelectedNode(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [graphTextbookId]);

  async function refreshProviders({ showErrors = false } = {}) {
    try {
      const registry = await listLLMProviders();
      setLLMRegistry(registry);
      setLLMDraft(draftFromRegistry(registry, registry.active));
      setProviderStatus(null);
      setModelFetchStatus(null);
    } catch (error) {
      setLLMRegistry(null);
      if (showErrors) {
        setNotice(error.message || "LLM Provider 接口不可用，请确认后端已重启");
      }
    }
  }

  async function refreshTextbooks(selectTextbookId) {
    const data = await listTextbooks();
    setTextbooks(data.textbooks);

    const nextActiveId =
      selectTextbookId ||
      (activeTextbookId && data.textbooks.some((item) => item.textbook_id === activeTextbookId)
        ? activeTextbookId
        : data.textbooks[0]?.textbook_id || null);

    setActiveTextbookId(nextActiveId);
  }

  async function handleUpload(file) {
    setNotice("");
    setIsLoading(true);
    try {
      const uploaded = await uploadTextbook(file);
      setPanelData((current) => ({ ...current, parse: uploaded }));
      await refreshTextbooks(uploaded.textbook_id);
    } catch (error) {
      setNotice(error.message || "上传失败");
    } finally {
      setIsLoading(false);
    }
  }

  async function handleParse(textbookId = activeTextbookId) {
    if (!textbookId) {
      setNotice("请先上传或选择一本教材");
      return;
    }

    setNotice("");
    setIsLoading(true);
    try {
      const parsed = await parseUploadedTextbook(textbookId);
      setPanelData((current) => ({ ...current, parse: parsed }));
      await refreshTextbooks(textbookId);
    } catch (error) {
      setNotice(error.message || "解析失败");
      await refreshTextbooks(textbookId);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleDeleteTextbook(item) {
    if (!item?.textbook_id) {
      return;
    }
    const ok = window.confirm(`删除“${item.filename}”？该操作会同时删除解析结果和图谱缓存。`);
    if (!ok) {
      return;
    }

    setNotice("");
    setIsLoading(true);
    try {
      const deleted = await deleteTextbook(item.textbook_id);
      const remaining = textbooks.filter((textbook) => textbook.textbook_id !== item.textbook_id);
      const nextActiveId =
        item.textbook_id === activeTextbookId
          ? remaining[0]?.textbook_id || null
          : activeTextbookId;
      setPanelData((current) => ({ ...current, parse: deleted }));
      await refreshTextbooks(nextActiveId);
      if (!nextActiveId) {
        setGraph(EMPTY_GRAPH);
        setGraphMeta({ status: "empty", provider: null, model: null, error: null });
        setSelectedNode(null);
      }
      setNotice(`已删除 ${item.filename}`);
    } catch (error) {
      setNotice(error.message || "删除失败");
    } finally {
      setIsLoading(false);
    }
  }

  async function runAction(action) {
    if (action === "parse") {
      await handleParse();
      return;
    }

    setIsLoading(true);
    setNotice("");
    let graphPoller = null;
    try {
      if (action === "graph") {
        const pollGraphBuildStatus = async () => {
          try {
            const status = await getGraphBuildStatus(graphTextbookId);
            setGraphBuildStatus(status);
            if (status.status === "running") {
              setNotice(formatGraphBuildStatus(status));
            }
          } catch {
            // Polling is only for visibility; the build request below owns errors.
          }
        };

        setGraphBuildStatus({ status: "running", current: 0, total: 0, message: "已提交图谱构建请求" });
        setNotice("正在构建图谱...");
        const buildPromise = buildGraphV2(graphTextbookId);
        graphPoller = window.setInterval(pollGraphBuildStatus, 1500);
        await pollGraphBuildStatus();

        const data = await buildPromise;
        if (graphPoller) {
          window.clearInterval(graphPoller);
          graphPoller = null;
        }
        try {
          setGraphBuildStatus(await getGraphBuildStatus(graphTextbookId));
        } catch {
          setGraphBuildStatus(null);
        }
        setGraph(data.graph || EMPTY_GRAPH);
        setGraphMeta({
          status: data.status || "empty",
          provider: data.provider || null,
          model: data.model || null,
          error: data.error || null,
        });
        setSelectedNode(null);
        if (data.status === "mock") {
          setNotice(`LLM 调用不可用，已显示演示图谱：${data.error || "fallback"}`);
        } else if (data.error) {
          setNotice(data.error);
        }
        if (data.status !== "mock" && !data.error) {
          setNotice(
            data.limited
              ? `图谱已构建：已处理 ${data.processed_chapters}/${data.total_chapters} 个片段，可通过 GRAPH_BUILD_MAX_CHAPTERS 调整上限`
              : "图谱构建完成",
          );
        }
      }

      if (action === "merge") {
        const data = await mergeTextbooks(textbooks.map((item) => item.textbook_id));
        setPanelData((current) => ({ ...current, merge: data }));
      }

      if (action === "rag") {
        const data = await ragQuery("一次函数与图像性质的教学关联是什么？");
        setPanelData((current) => ({ ...current, rag: data }));
      }

      if (action === "chat") {
        const data = await chat("请评价当前知识点合并方案");
        setPanelData((current) => ({ ...current, chat: data }));
      }

      if (action === "report") {
        const data = await generateReport(textbooks.map((item) => item.textbook_id));
        setPanelData((current) => ({ ...current, report: data }));
      }
    } catch (error) {
      setNotice(error.message || "操作失败");
    } finally {
      if (graphPoller) {
        window.clearInterval(graphPoller);
      }
      setIsLoading(false);
    }
  }

  function openLLMSettings() {
    setIsLLMSettingsOpen(true);
    refreshProviders({ showErrors: true });
  }

  function handleProviderChange(event) {
    selectProvider(event.target.value);
  }

  function selectProvider(providerKey) {
    setLLMDraft(draftFromRegistry(llmRegistry, providerKey));
    setProviderStatus(null);
    setModelFetchStatus(null);
  }

  function updateLLMDraft(patch) {
    setLLMDraft((current) => ({ ...current, ...patch }));
    setProviderStatus(null);
    setModelFetchStatus(null);
  }

  function buildProviderConfig() {
    const config = {
      api_key: llmDraft.api_key,
      base_url: llmDraft.base_url,
      model: llmDraft.model,
      notes: llmDraft.notes,
    };
    if (llmDraft.active === "custom") {
      config.display_name = llmDraft.display_name;
    }
    return config;
  }

  async function handleProviderCheck() {
    setIsProviderChecking(true);
    setProviderStatus(null);
    try {
      const result = await checkLLMProvider(llmDraft.active, buildProviderConfig());
      setProviderStatus(result);
      if (!result.ok) {
        setNotice("LLM 配置健康检查未通过，请检查 API Key、Base URL 和模型名");
      }
    } catch (error) {
      setProviderStatus({ ok: false, error: error.message });
      setNotice(error.message || "LLM 配置健康检查失败");
    } finally {
      setIsProviderChecking(false);
    }
  }

  async function handleModelFetch() {
    setIsModelFetching(true);
    setModelFetchStatus(null);
    try {
      const result = await fetchLLMModels(llmDraft.active, buildProviderConfig());
      if (!result.success) {
        setModelFetchStatus({ ok: false, message: result.error || "模型列表获取失败" });
        return;
      }
      setFetchedModels((current) => ({ ...current, [llmDraft.active]: result.models || [] }));
      setModelFetchStatus({ ok: true, message: `已获取 ${result.count || 0} 个模型` });
      if (!llmDraft.model && result.models?.[0]) {
        updateLLMDraft({ model: result.models[0] });
      }
    } catch (error) {
      setModelFetchStatus({ ok: false, message: error.message || "模型列表获取失败" });
    } finally {
      setIsModelFetching(false);
    }
  }

  async function handleProviderSave(event) {
    event.preventDefault();
    setIsProviderSaving(true);
    setNotice("");
    try {
      const saved = await updateLLMProvider(llmDraft.active, buildProviderConfig());
      const registry = saved.registry || (await listLLMProviders());
      setLLMRegistry(registry);
      setLLMDraft(draftFromRegistry(registry, registry.active));
      setIsLLMSettingsOpen(false);
      setProviderStatus(null);
      setModelFetchStatus(null);
      setNotice(`LLM Provider 已保存并切换为 ${activeProvider?.display_name || llmDraft.active}`);
    } catch (error) {
      setNotice(error.message || "LLM 设置保存失败");
    } finally {
      setIsProviderSaving(false);
    }
  }

  const graphStatusText =
    graphMeta.status === "built"
      ? `${graphMeta.provider || "provider"} · ${graphMeta.model || "model"}`
      : graphMeta.status === "mock"
        ? "演示数据"
        : "待构建";

  const graphBuildStatusText = formatGraphBuildStatus(graphBuildStatus);
  const graphBuildProgress =
    graphBuildStatus?.total > 0
      ? Math.max(0, Math.min(100, Math.round((graphBuildStatus.current / graphBuildStatus.total) * 100)))
      : 0;
  const isGraphBuilding = graphBuildStatus?.status === "running" || (isLoading && notice.includes("构建"));

  return (
    <div className="app-root">
      <header className="topbar">
        <div className="brand-mark" aria-hidden="true">
          <Sparkles size={17} />
        </div>
        <div className="brand-copy">
          <strong>Knowledge Integration Agent</strong>
          <span>AI 全栈黑客松</span>
        </div>
        <div className="topbar-actions">
          <span className="status-pill">{graphStatusText}</span>
          <button className="button ghost-button" type="button" onClick={openLLMSettings}>
            <Settings size={16} />
            LLM 设置
          </button>
          <button className="button ghost-button" type="button" onClick={() => runAction("report")}>
            <FileText size={16} />
            生成报告
          </button>
        </div>
      </header>

      {isLLMSettingsOpen && (
        <div className="settings-backdrop" onMouseDown={() => setIsLLMSettingsOpen(false)}>
          <form className="llm-settings-panel" onSubmit={handleProviderSave} onMouseDown={(event) => event.stopPropagation()}>
            <header>
              <div>
                <span className="agent-kicker">LLM Provider</span>
                <h2>模型设置</h2>
              </div>
              <button className="icon-button" type="button" onClick={() => setIsLLMSettingsOpen(false)}>
                <X size={17} />
              </button>
            </header>

            <label>
              <span>搜索 Provider</span>
              <input
                value={providerFilter}
                onChange={(event) => setProviderFilter(event.target.value)}
                placeholder="OpenAI / DeepSeek / Claude / Kimi / Gemini / 本地模型..."
              />
            </label>

            <div className="provider-switcher" role="radiogroup" aria-label="Provider">
              {filteredProviderOptions.map((provider) => {
                const isActive = provider.key === llmDraft.active;
                return (
                  <button
                    key={provider.key}
                    className={isActive ? "provider-option active" : "provider-option"}
                    type="button"
                    aria-pressed={isActive}
                    onClick={() => selectProvider(provider.key)}
                  >
                    <span>
                      {provider.display_name}
                      {llmRegistry?.active === provider.key && <CheckCircle2 size={14} />}
                    </span>
                    <small>{provider.default_model || "自定义模型"}</small>
                  </button>
                );
              })}
            </div>

            <label className="select-fallback">
              <span>Provider</span>
              <select value={llmDraft.active} onChange={handleProviderChange}>
                {providerOptions.map((provider) => (
                  <option key={provider.key} value={provider.key}>
                    {provider.display_name}
                  </option>
                ))}
              </select>
            </label>

            <div className="provider-summary">
              <span>当前 Provider</span>
              <strong>{activeProvider?.display_name || llmDraft.active}</strong>
              <small>{activeProvider?.default_base_url || "自定义 OpenAI 兼容地址"}</small>
              {(activeProvider?.website_url || activeProvider?.docs_url) && (
                <div className="provider-links">
                  {activeProvider.website_url && (
                    <a href={activeProvider.website_url} target="_blank" rel="noreferrer">
                      控制台
                    </a>
                  )}
                  {activeProvider.docs_url && (
                    <a href={activeProvider.docs_url} target="_blank" rel="noreferrer">
                      模型文档
                    </a>
                  )}
                </div>
              )}
            </div>

            {llmDraft.active === "custom" && (
              <label>
                <span>显示名</span>
                <input
                  value={llmDraft.display_name}
                  onChange={(event) => updateLLMDraft({ display_name: event.target.value })}
                  placeholder="自定义 Provider"
                />
              </label>
            )}

            <label>
              <span>API Key</span>
              <input
                value={llmDraft.api_key}
                onChange={(event) => updateLLMDraft({ api_key: event.target.value })}
                placeholder={activeProvider?.env_key_name ? `留空则读取 ${activeProvider.env_key_name}` : "留空则读取后端环境变量"}
                type="password"
              />
            </label>
            <label>
              <span>Base URL</span>
              <input
                value={llmDraft.base_url}
                onChange={(event) => updateLLMDraft({ base_url: event.target.value })}
                placeholder={activeProvider?.default_base_url || "https://.../v1"}
              />
            </label>

            {activeBaseUrlCandidates.length > 0 && (
              <div className="model-chip-row compact">
                {activeBaseUrlCandidates.slice(0, 4).map((baseUrl) => (
                  <button
                    key={baseUrl}
                    className={llmDraft.base_url === baseUrl ? "model-chip active" : "model-chip"}
                    type="button"
                    onClick={() => updateLLMDraft({ base_url: baseUrl })}
                    title={baseUrl}
                  >
                    {baseUrl.replace(/^https?:\/\//, "")}
                  </button>
                ))}
              </div>
            )}

            <label>
              <span>Model</span>
              <input
                list="llm-model-options"
                value={llmDraft.model}
                onChange={(event) => updateLLMDraft({ model: event.target.value })}
                placeholder={activeProvider?.default_model || "model-id"}
              />
              <datalist id="llm-model-options">
                {activeModelOptions.map((model) => (
                  <option key={model} value={model} />
                ))}
              </datalist>
            </label>

            {activeModelOptions.length > 0 && (
              <div className="model-chip-row">
                {activeModelOptions.slice(0, 6).map((model) => (
                  <button
                    key={model}
                    className={llmDraft.model === model ? "model-chip active" : "model-chip"}
                    type="button"
                    onClick={() => updateLLMDraft({ model })}
                  >
                    {model}
                  </button>
                ))}
              </div>
            )}

            <label>
              <span>备注 / 用途</span>
              <input
                value={llmDraft.notes}
                onChange={(event) => updateLLMDraft({ notes: event.target.value })}
                placeholder="例如：图谱抽取、演示备用、低成本模型"
              />
            </label>

            {providerStatus && (
              <div className={providerStatus.ok ? "provider-status ok" : "provider-status error"}>
                {providerStatus.ok ? "健康检查通过" : providerStatus.error || "健康检查未通过"}
              </div>
            )}

            {modelFetchStatus && (
              <div className={modelFetchStatus.ok ? "provider-status ok" : "provider-status error"}>
                {modelFetchStatus.message}
              </div>
            )}

            <div className="settings-actions">
              <button className="button cream-button" type="button" onClick={handleModelFetch} disabled={isProviderSaving || isProviderChecking || isModelFetching}>
                <Network size={16} />
                {isModelFetching ? "获取中" : "获取模型"}
              </button>
              <button className="button cream-button" type="button" onClick={handleProviderCheck} disabled={isProviderSaving || isProviderChecking}>
                <Activity size={16} />
                {isProviderChecking ? "检查中" : "测试连接"}
              </button>
              <button className="button dark-button" type="submit" disabled={isProviderSaving || isProviderChecking}>
                <Save size={16} />
                {isProviderSaving ? "保存中" : "保存设置"}
              </button>
            </div>
          </form>
        </div>
      )}

      <main className="app-shell">
        <TextbookManager
          textbooks={textbooks}
          activeTextbookId={activeTextbookId}
          onSelect={setActiveTextbookId}
          onUpload={handleUpload}
          onParse={handleParse}
          onDelete={handleDeleteTextbook}
          onRunAction={runAction}
          isLoading={isLoading}
          notice={notice}
        />

        <section className="graph-workspace" aria-label="知识图谱">
          <header className="workspace-header">
            <div>
              <p className="eyebrow">Single Map</p>
              <h1>{activeTextbook?.filename || "教材工作台"}</h1>
            </div>
            <button
              className="button dark-button graph-build-button"
              type="button"
              onClick={() => runAction("graph")}
              disabled={isLoading}
            >
              <Network size={16} />
              <span className="button-label">
                {isGraphBuilding && graphBuildStatus?.total
                  ? `构建中 ${graphBuildStatus.current}/${graphBuildStatus.total}`
                  : "构建图谱"}
              </span>
              构建图谱
            </button>
          </header>

          <div className="metric-strip" aria-label="项目状态">
            <article>
              <span>教材</span>
              <strong>{textbooks.length}</strong>
            </article>
            <article>
              <span>已解析</span>
              <strong>{parsedCount}</strong>
            </article>
            <article>
              <span>节点 / 关系</span>
              <strong>
                {graphNodeCount} / {graphEdgeCount}
              </strong>
            </article>
          </div>

          {graphBuildStatusText && (
            <div className={isGraphBuilding ? "build-status-card running" : "build-status-card"}>
              <div>
                <span>{graphBuildStatus?.status || "idle"}</span>
                <strong>{graphBuildStatusText}</strong>
              </div>
              {graphBuildStatus?.total > 0 && (
                <div className="build-progress" aria-hidden="true">
                  <span style={{ width: `${graphBuildProgress}%` }} />
                </div>
              )}
            </div>
          )}

          <KnowledgeGraph graph={graph} onNodeClick={setSelectedNode} />

          <footer className="workspace-footer">
            <span>{graphMeta.status || "empty"}</span>
            <p>
              {graphMeta.status === "mock"
                ? "当前为 Mock Fallback 演示数据，后端真实抽取失败时会自动启用。"
                : "教材解析完成后，知识点抽取结果会写入 SQLite，并在这里持久化展示。"}
            </p>
            <ArrowUpRight size={16} />
          </footer>
        </section>

        <RightTabs data={panelData} onRunAction={runAction} isLoading={isLoading} selectedNode={selectedNode} />
      </main>
    </div>
  );
}

export default App;
