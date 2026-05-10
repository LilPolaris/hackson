const $ = (selector) => document.querySelector(selector);

let latestStatus = null;

function nowText() {
  return new Date().toLocaleTimeString("zh-CN", { hour12: false });
}

function defaultCommitMessage() {
  const d = new Date();
  const pad = (value) => String(value).padStart(2, "0");
  return `update ${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

function formatBytes(bytes) {
  if (bytes > 1024 * 1024 * 1024) {
    return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
  }
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}

function setCard(id, state, title, detail) {
  const card = $(id);
  card.classList.remove("good", "warn", "bad");
  if (state) {
    card.classList.add(state);
  }
  card.querySelector("strong").textContent = title;
  card.querySelector("p").textContent = detail || "";
}

function setStep(id, state) {
  const item = $(id);
  item.classList.remove("good", "warn", "bad");
  if (state) {
    item.classList.add(state);
  }
}

function log(message) {
  const output = $("#logOutput");
  if (output.textContent === "等待操作...") {
    output.textContent = "";
  }
  output.textContent += `[${nowText()}] ${message}\n`;
  output.scrollTop = output.scrollHeight;
}

function logBlock(title, body) {
  log(title);
  if (body) {
    $("#logOutput").textContent += `${body.trim()}\n`;
  }
  $("#logOutput").scrollTop = $("#logOutput").scrollHeight;
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.message || "请求失败");
  }
  return data;
}

function renderStatus(data) {
  latestStatus = data;
  $("#projectPath").textContent = data.projectRoot;

  if (!$("#commitMessage").value) {
    $("#commitMessage").value = defaultCommitMessage();
  }
  if (!$("#repoName").value) {
    $("#repoName").value = data.defaultRepoName;
  }

  setCard(
    "#gitStatus",
    data.tools.git.ok ? "good" : "bad",
    data.tools.git.ok ? "可用" : "未找到",
    data.tools.git.version || data.tools.git.path || "需要安装 Git",
  );

  let ghState = "bad";
  let ghTitle = "可选未登录";
  if (!data.tools.gh.ok) {
    ghState = "warn";
    ghTitle = "未找到也没关系";
  } else if (data.ghAuth.ok) {
    ghState = "good";
    ghTitle = "已登录";
  } else {
    ghState = "warn";
  }

  setCard(
    "#ghStatus",
    ghState,
    ghTitle,
    data.tools.gh.version || data.ghAuth.text || "手动填仓库 URL 时不需要它",
  );

  const repoTitle = data.git.isRepo ? "已初始化" : "还不是仓库";
  const repoDetail = data.git.origin
    ? `远程仓库：${data.git.origin}`
    : data.git.branch
      ? `当前分支：${data.git.branch}`
      : "第一次推送时会自动初始化";
  setCard("#repoStatus", data.git.isRepo ? "good" : "warn", repoTitle, repoDetail);

  const changeTitle = data.git.changesCount ? `${data.git.changesCount} 个变化` : "无本地变化";
  const changeDetail = data.git.changes.slice(0, 3).join("；") || "可以继续开发，或直接推送已有提交";
  setCard("#changeStatus", data.git.changesCount ? "warn" : "good", changeTitle, changeDetail);

  const largeNotice = $("#largeFileNotice");
  const largeList = $("#largeFileList");
  largeList.innerHTML = "";
  if (data.git.largeFiles.length) {
    largeNotice.hidden = false;
    data.git.largeFiles.forEach((file) => {
      const li = document.createElement("li");
      li.textContent = `${file.path} (${formatBytes(file.size)})`;
      largeList.appendChild(li);
    });
  } else {
    largeNotice.hidden = true;
  }

  const needsIdentity = !data.git.userName || !data.git.userEmail;
  $("#identityBox").hidden = !needsIdentity;
  if (!$("#gitName").value && data.git.userName) {
    $("#gitName").value = data.git.userName;
  }
  if (!$("#gitEmail").value && data.git.userEmail) {
    $("#gitEmail").value = data.git.userEmail;
  }

  setStep("#stepTools", data.tools.git.ok ? "good" : "bad");
  setStep("#stepFiles", data.git.largeFiles.length ? "warn" : "good");
  setStep("#stepCommit", data.git.changesCount ? "warn" : "good");
  setStep("#stepPush", data.git.origin ? "good" : "warn");
}

async function refreshStatus() {
  $("#refreshBtn").disabled = true;
  try {
    const data = await api("/api/status");
    renderStatus(data);
    log("检查完成。");
  } catch (error) {
    log(`检查失败：${error.message}`);
  } finally {
    $("#refreshBtn").disabled = false;
  }
}

function selectedVisibility() {
  return document.querySelector("input[name='visibility']:checked")?.value || "public";
}

async function pushProject(event) {
  event.preventDefault();
  if (!$("#confirmPush").checked) {
    log("请先勾选确认框，再执行推送。");
    return;
  }

  const payload = {
    message: $("#commitMessage").value.trim(),
    repoName: $("#repoName").value.trim(),
    repoUrl: $("#repoUrl").value.trim(),
    visibility: selectedVisibility(),
    gitName: $("#gitName").value.trim(),
    gitEmail: $("#gitEmail").value.trim(),
  };

  $("#pushBtn").disabled = true;
  log("开始提交并推送，请不要关闭黑色终端窗口。");
  try {
    const result = await api("/api/push", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    logBlock("推送成功。", result.logs);
    if (result.origin) {
      log(`远程仓库：${result.origin}`);
    }
    $("#confirmPush").checked = false;
    await refreshStatus();
  } catch (error) {
    logBlock("推送失败。", error.message);
  } finally {
    $("#pushBtn").disabled = false;
  }
}

async function openLogin() {
  try {
    await api("/api/open-login", { method: "POST", body: "{}" });
    log("已打开 GitHub CLI 登录窗口。登录完成后回到这里点“刷新检查”。");
  } catch (error) {
    log(`打开登录窗口失败：${error.message}`);
  }
}

async function openRepo() {
  try {
    await api("/api/open-repo", { method: "POST", body: "{}" });
    log("正在打开 GitHub 仓库页面。");
  } catch (error) {
    log(`打开仓库失败：${error.message}`);
  }
}

async function copyCommands() {
  const repoName = $("#repoName").value.trim() || latestStatus?.defaultRepoName || "my-ai-project";
  const message = $("#commitMessage").value.trim() || defaultCommitMessage();
  const commands = [
    "git status",
    "git add -A",
    `git commit -m "${message.replace(/"/g, '\\"')}"`,
    `gh repo create ${repoName} --public --source . --remote origin`,
    "git push -u origin main",
  ].join("\n");

  try {
    await navigator.clipboard.writeText(commands);
    log("手动命令已复制。");
  } catch {
    logBlock("复制失败，下面是手动命令。", commands);
  }
}

$("#refreshBtn").addEventListener("click", refreshStatus);
$("#loginBtn").addEventListener("click", openLogin);
$("#openRepoBtn").addEventListener("click", openRepo);
$("#copyCommandsBtn").addEventListener("click", copyCommands);
$("#clearLogBtn").addEventListener("click", () => {
  $("#logOutput").textContent = "等待操作...";
});
$("#pushForm").addEventListener("submit", pushProject);

refreshStatus();
