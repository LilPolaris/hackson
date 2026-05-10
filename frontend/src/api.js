const API_BASE_URLS = Array.from(
  new Set([
    "http://127.0.0.1:8002",
    "http://127.0.0.1:8001",
    import.meta.env.VITE_API_BASE_URL,
    "http://127.0.0.1:8000",
  ].filter(Boolean)),
);

function endpointNeedsFallback(path, response, payload) {
  if (response && response.status === 404 && path.startsWith("/api/llm/")) {
    return true;
  }
  if (path.startsWith("/api/graph/build/")) {
    return (
      payload?.success === false ||
      (payload?.status === "mock" && /parsed JSON not found|未找到 parsed JSON/.test(payload?.error || ""))
    );
  }
  return false;
}

async function request(path, options = {}) {
  const isFormData = options.body instanceof FormData;
  const headers = isFormData
    ? options.headers || {}
    : {
        "Content-Type": "application/json",
        ...(options.headers || {}),
      };

  let firstHttpError;
  let lastNetworkError;
  for (const baseUrl of API_BASE_URLS) {
    try {
      const response = await fetch(`${baseUrl}${path}`, {
        ...options,
        headers,
      });

      if (!response.ok) {
        let message = `Request failed: ${response.status}`;
        try {
          const errorPayload = await response.json();
          message = errorPayload.detail || message;
        } catch {
          message = await response.text();
        }
        if (response.status === 404 && path.startsWith("/api/llm/")) {
          message = "当前后端没有 LLM Provider 接口，请重启后端或确认新版服务已启动。";
        }
        const error = new Error(message);
        if (!firstHttpError) {
          firstHttpError = error;
        }
        if (endpointNeedsFallback(path, response, null)) {
          continue;
        }
        throw error;
      }

      const payload = await response.json();
      if (endpointNeedsFallback(path, response, payload)) {
        if (!firstHttpError) {
          firstHttpError = new Error(payload.error || "Request failed");
        }
        continue;
      }
      return payload;
    } catch (error) {
      if (error instanceof TypeError) {
        lastNetworkError = error;
        continue;
      }
      throw error;
    }
  }

  throw firstHttpError || lastNetworkError || new Error("Request failed");
}

export function listTextbooks() {
  return request("/api/textbooks");
}

export function uploadTextbook(file) {
  const body = new FormData();
  body.append("file", file);

  return request("/api/textbooks/upload", {
    method: "POST",
    body,
  });
}

export function parseUploadedTextbook(textbookId) {
  return request(`/api/textbooks/${encodeURIComponent(textbookId)}/parse`, {
    method: "POST",
  });
}

export function deleteTextbook(textbookId) {
  return request(`/api/textbooks/${encodeURIComponent(textbookId)}`, {
    method: "DELETE",
  });
}

export function getGraph(textbookId = "demo-textbook") {
  return request(`/graph?textbook_id=${encodeURIComponent(textbookId)}`);
}

export function getGraphV2(textbookId = "demo-textbook") {
  return request(`/api/graph/${encodeURIComponent(textbookId)}`);
}

export function parseTextbook(textbookId) {
  return request("/parse", {
    method: "POST",
    body: JSON.stringify({ textbook_id: textbookId }),
  });
}

export function buildGraph(textbookId) {
  return request("/graph/build", {
    method: "POST",
    body: JSON.stringify({ textbook_id: textbookId }),
  });
}

export function buildGraphV2(textbookId) {
  return request(`/api/graph/build/${encodeURIComponent(textbookId)}`, {
    method: "POST",
  });
}

export function listLLMProviders() {
  return request("/api/llm/providers");
}

export function updateLLMProvider(active, config) {
  return request("/api/llm/providers", {
    method: "POST",
    body: JSON.stringify({ active, config }),
  });
}

export function checkLLMProvider(active, config) {
  return request("/api/llm/providers/health", {
    method: "POST",
    body: JSON.stringify({ active, config }),
  });
}

export function fetchLLMModels(active, config) {
  return request("/api/llm/providers/models", {
    method: "POST",
    body: JSON.stringify({ active, config }),
  });
}

export function mergeTextbooks(textbookIds) {
  return request("/api/merge/run", {
    method: "POST",
    body: JSON.stringify({ textbook_ids: textbookIds }),
  });
}

export function ragQuery(query) {
  return request("/rag", {
    method: "POST",
    body: JSON.stringify({ query, top_k: 5 }),
  });
}

export function chat(message, history = []) {
  return request("/chat", {
    method: "POST",
    body: JSON.stringify({ message, history }),
  });
}

export function generateReport(textbookIds) {
  return request("/report", {
    method: "POST",
    body: JSON.stringify({
      topic: "多教材知识整合报告",
      textbook_ids: textbookIds,
    }),
  });
}
