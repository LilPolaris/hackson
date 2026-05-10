const http = require("node:http");
const fs = require("node:fs");
const path = require("node:path");
const { spawn, execFileSync } = require("node:child_process");

const projectRoot = path.resolve(process.argv[2] || path.join(__dirname, "..", ".."));
const shouldOpen = process.argv.includes("--open");
const host = "127.0.0.1";
const port = Number(process.env.GITHUB_PUSH_WEB_PORT || 47653);
const publicDir = __dirname;

const commonExcludes = [
  "node_modules/",
  ".env",
  ".env.*",
  "textbooks/",
  "*.zip",
  ".venv/",
  "venv/",
  "__pycache__/",
  "*.pyc",
  ".next/",
  "dist/",
  "build/",
  ".DS_Store",
];

const largeLimitBytes = 90 * 1024 * 1024;

function normalizeSlashes(value) {
  return value.replace(/\\/g, "/");
}

function defaultRepoName(root) {
  const leaf = path.basename(root);
  const cleaned = leaf
    .toLowerCase()
    .replace(/[^a-z0-9._-]/g, "-")
    .replace(/-+/g, "-")
    .replace(/^[-._]+|[-._]+$/g, "");
  return cleaned.length >= 3 ? cleaned : "ai-hackathon-project";
}

function fileExists(filePath) {
  try {
    return fs.existsSync(filePath);
  } catch {
    return false;
  }
}

function findTool(name, fallbacks) {
  const candidates = [];
  try {
    const output = execFileSync("where.exe", [name], { encoding: "utf8" });
    output
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
      .forEach((line) => candidates.push(line));
  } catch {
    // The PATH in this app may lag behind newly installed tools, so fallbacks matter.
  }

  fallbacks.forEach((item) => candidates.push(item));
  return candidates.find((item) => item && fileExists(item)) || null;
}

function getTools() {
  return {
    git: findTool("git.exe", [
      "D:\\Git\\cmd\\git.exe",
      "C:\\Program Files\\Git\\cmd\\git.exe",
      "C:\\Program Files\\Git\\bin\\git.exe",
    ]),
    gh: findTool("gh.exe", [
      "C:\\Program Files\\GitHub CLI\\gh.exe",
      "C:\\Program Files (x86)\\GitHub CLI\\gh.exe",
      path.join(process.env.LOCALAPPDATA || "", "GitHub CLI", "gh.exe"),
    ]),
  };
}

function runCommand(file, args, options = {}) {
  const timeoutMs = options.timeoutMs || 180000;
  return new Promise((resolve) => {
    const child = spawn(file, args, {
      cwd: options.cwd || projectRoot,
      windowsHide: true,
      shell: false,
      env: process.env,
    });

    let stdout = "";
    let stderr = "";
    let timedOut = false;

    const timer = setTimeout(() => {
      timedOut = true;
      child.kill();
    }, timeoutMs);

    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString("utf8");
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString("utf8");
    });
    child.on("error", (error) => {
      clearTimeout(timer);
      resolve({
        ok: false,
        code: -1,
        stdout,
        stderr: stderr + error.message,
        command: commandLabel(file, args),
      });
    });
    child.on("close", (code) => {
      clearTimeout(timer);
      resolve({
        ok: code === 0 && !timedOut,
        code,
        stdout,
        stderr: timedOut ? `${stderr}\nCommand timed out.` : stderr,
        command: commandLabel(file, args),
      });
    });
  });
}

function commandLabel(file, args) {
  return [quoteIfNeeded(file), ...args.map(quoteIfNeeded)].join(" ");
}

function quoteIfNeeded(value) {
  if (!value.includes(" ")) {
    return value;
  }
  return `"${value.replace(/"/g, '\\"')}"`;
}

function combineOutput(result) {
  return [result.stdout, result.stderr].filter(Boolean).join("\n").trim();
}

function appendLog(logs, result) {
  logs.push(`> ${result.command}`);
  const output = combineOutput(result);
  if (output) {
    logs.push(output);
  }
}

async function requireSuccess(logs, file, args, message, options = {}) {
  const result = await runCommand(file, args, options);
  appendLog(logs, result);
  if (!result.ok) {
    const detail = combineOutput(result);
    throw new Error(detail ? `${message}\n${detail}` : message);
  }
  return result;
}

function listLargeFiles(root) {
  const skipDirs = new Set([".git", "node_modules", ".next", "dist", "build", ".venv", "venv"]);
  const results = [];

  function walk(dir) {
    let entries = [];
    try {
      entries = fs.readdirSync(dir, { withFileTypes: true });
    } catch {
      return;
    }

    for (const entry of entries) {
      const fullPath = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        if (!skipDirs.has(entry.name)) {
          walk(fullPath);
        }
        continue;
      }

      if (!entry.isFile()) {
        continue;
      }

      let stat;
      try {
        stat = fs.statSync(fullPath);
      } catch {
        continue;
      }

      if (stat.size > largeLimitBytes) {
        results.push({
          path: normalizeSlashes(path.relative(root, fullPath)),
          size: stat.size,
        });
      }
    }
  }

  walk(root);
  return results;
}

function ensureLocalExcludes(root, largeFiles) {
  const excludeDir = path.join(root, ".git", "info");
  const excludePath = path.join(excludeDir, "exclude");
  fs.mkdirSync(excludeDir, { recursive: true });
  if (!fs.existsSync(excludePath)) {
    fs.writeFileSync(excludePath, "", "utf8");
  }

  const existing = fs.readFileSync(excludePath, "utf8").split(/\r?\n/);
  const next = [...commonExcludes, ...largeFiles.map((item) => item.path)];
  const toAdd = next.filter((item) => item && !existing.includes(item));
  if (toAdd.length) {
    const prefix = existing.length && existing[existing.length - 1] !== "" ? "\n" : "";
    fs.appendFileSync(excludePath, `${prefix}${toAdd.join("\n")}\n`, "utf8");
  }
  return next;
}

async function gitValue(git, args) {
  const result = await runCommand(git, args);
  return result.ok ? result.stdout.trim() : "";
}

async function getStatus() {
  const tools = getTools();
  const status = {
    projectRoot,
    defaultRepoName: defaultRepoName(projectRoot),
    tools: {
      git: { ok: Boolean(tools.git), path: tools.git, version: "" },
      gh: { ok: Boolean(tools.gh), path: tools.gh, version: "" },
    },
    ghAuth: { ok: false, text: "GitHub CLI not checked yet." },
    git: {
      isRepo: false,
      hasHead: false,
      branch: "",
      origin: "",
      changes: [],
      changesCount: 0,
      userName: "",
      userEmail: "",
      largeFiles: listLargeFiles(projectRoot),
      excludes: [...commonExcludes],
    },
  };

  if (tools.git) {
    const version = await runCommand(tools.git, ["--version"]);
    status.tools.git.version = combineOutput(version);

    const isRepo = await runCommand(tools.git, ["rev-parse", "--is-inside-work-tree"]);
    status.git.isRepo = isRepo.ok && isRepo.stdout.trim() === "true";
    status.git.userName = await gitValue(tools.git, ["config", "user.name"]);
    status.git.userEmail = await gitValue(tools.git, ["config", "user.email"]);

    if (status.git.isRepo) {
      const hasHead = await runCommand(tools.git, ["rev-parse", "--verify", "HEAD"]);
      status.git.hasHead = hasHead.ok;
      status.git.branch = await gitValue(tools.git, ["branch", "--show-current"]);
      status.git.origin = await gitValue(tools.git, ["remote", "get-url", "origin"]);
      const changes = await runCommand(tools.git, ["status", "--short"]);
      status.git.changes = changes.stdout.split(/\r?\n/).filter(Boolean);
      status.git.changesCount = status.git.changes.length;
    }
  }

  if (tools.gh) {
    const version = await runCommand(tools.gh, ["--version"]);
    status.tools.gh.version = version.stdout.split(/\r?\n/)[0] || combineOutput(version);
    const auth = await runCommand(tools.gh, ["auth", "status", "-h", "github.com"]);
    status.ghAuth.ok = auth.ok;
    status.ghAuth.text = combineOutput(auth) || (auth.ok ? "Logged in." : "Not logged in.");
  }

  return status;
}

async function pushProject(payload) {
  const tools = getTools();
  const logs = [];
  if (!tools.git) {
    throw new Error("Git was not found.");
  }

  const repoCheck = await runCommand(tools.git, ["rev-parse", "--is-inside-work-tree"]);
  appendLog(logs, repoCheck);
  if (!repoCheck.ok) {
    await requireSuccess(logs, tools.git, ["init"], "git init failed.");
  }

  const largeFiles = listLargeFiles(projectRoot);
  ensureLocalExcludes(projectRoot, largeFiles);
  if (largeFiles.length) {
    logs.push("Large files were added to .git/info/exclude:");
    largeFiles.forEach((file) => logs.push(`  ${file.path}`));
  }

  const userName = await gitValue(tools.git, ["config", "user.name"]);
  const userEmail = await gitValue(tools.git, ["config", "user.email"]);
  if (!userName && payload.gitName) {
    await requireSuccess(logs, tools.git, ["config", "user.name", payload.gitName], "Failed to set git user.name.");
  }
  if (!userEmail && payload.gitEmail) {
    await requireSuccess(logs, tools.git, ["config", "user.email", payload.gitEmail], "Failed to set git user.email.");
  }

  const finalName = await gitValue(tools.git, ["config", "user.name"]);
  const finalEmail = await gitValue(tools.git, ["config", "user.email"]);
  if (!finalName || !finalEmail) {
    throw new Error("Git name/email is missing. Fill in the two identity fields and try again.");
  }

  await requireSuccess(logs, tools.git, ["add", "-A"], "git add failed.");

  const afterAdd = await runCommand(tools.git, ["status", "--short"]);
  appendLog(logs, afterAdd);
  const hasChanges = afterAdd.stdout.split(/\r?\n/).some(Boolean);
  const head = await runCommand(tools.git, ["rev-parse", "--verify", "HEAD"]);
  const hasHead = head.ok;

  if (hasChanges) {
    const message = (payload.message || "").trim() || `update ${new Date().toISOString().slice(0, 16).replace("T", " ")}`;
    await requireSuccess(logs, tools.git, ["commit", "-m", message], "git commit failed.");
  } else if (!hasHead) {
    throw new Error("No commit-ready files were found after safety excludes.");
  } else {
    logs.push("No local changes to commit. Push will continue.");
  }

  let origin = await gitValue(tools.git, ["remote", "get-url", "origin"]);
  const hadOrigin = Boolean(origin);
  if (!origin) {
    const repoUrl = (payload.repoUrl || "").trim();
    if (repoUrl) {
      await requireSuccess(logs, tools.git, ["remote", "add", "origin", repoUrl], "Failed to add origin remote.");
    } else {
      if (!tools.gh) {
        throw new Error("No remote repository URL was provided. Create a GitHub repository in the browser, paste its HTTPS URL, then try again.");
      }

      const auth = await runCommand(tools.gh, ["auth", "status", "-h", "github.com"]);
      appendLog(logs, auth);
      if (!auth.ok) {
        throw new Error("GitHub CLI login is invalid. To avoid GitHub CLI, create the repository in your browser and paste the HTTPS URL into the existing-repo field.");
      }

      const repoName = (payload.repoName || "").trim() || defaultRepoName(projectRoot);
      const visibility = payload.visibility === "private" ? "--private" : "--public";
      await requireSuccess(
        logs,
        tools.gh,
        ["repo", "create", repoName, visibility, "--source", projectRoot, "--remote", "origin"],
        "Failed to create GitHub repository.",
        { timeoutMs: 300000 },
      );
    }
    origin = await gitValue(tools.git, ["remote", "get-url", "origin"]);
  }

  let branch = await gitValue(tools.git, ["branch", "--show-current"]);
  if (!branch) {
    branch = "main";
    await requireSuccess(logs, tools.git, ["checkout", "-B", branch], "Failed to create main branch.");
  }

  if (!hadOrigin && branch !== "main") {
    await requireSuccess(logs, tools.git, ["branch", "-M", "main"], "Failed to rename branch to main.");
    branch = "main";
  }

  await requireSuccess(logs, tools.git, ["push", "-u", "origin", branch], "git push failed.", {
    timeoutMs: 600000,
  });

  return {
    ok: true,
    origin,
    branch,
    logs: logs.join("\n\n"),
  };
}

function sendJson(response, statusCode, data) {
  const body = JSON.stringify(data, null, 2);
  response.writeHead(statusCode, {
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
  });
  response.end(body);
}

function parseBody(request) {
  return new Promise((resolve, reject) => {
    let raw = "";
    request.on("data", (chunk) => {
      raw += chunk.toString("utf8");
      if (raw.length > 1024 * 1024) {
        reject(new Error("Request body is too large."));
      }
    });
    request.on("end", () => {
      if (!raw.trim()) {
        resolve({});
        return;
      }
      try {
        resolve(JSON.parse(raw));
      } catch {
        reject(new Error("Invalid JSON body."));
      }
    });
  });
}

function serveStatic(request, response) {
  const requestUrl = new URL(request.url, `http://${host}:${port}`);
  let pathname = decodeURIComponent(requestUrl.pathname);
  if (pathname === "/") {
    pathname = "/index.html";
  }

  const filePath = path.resolve(publicDir, `.${pathname}`);
  if (!filePath.startsWith(publicDir)) {
    response.writeHead(403);
    response.end("Forbidden");
    return;
  }

  fs.readFile(filePath, (error, data) => {
    if (error) {
      response.writeHead(404);
      response.end("Not found");
      return;
    }

    const ext = path.extname(filePath).toLowerCase();
    const types = {
      ".html": "text/html; charset=utf-8",
      ".css": "text/css; charset=utf-8",
      ".js": "text/javascript; charset=utf-8",
    };
    response.writeHead(200, {
      "Content-Type": types[ext] || "application/octet-stream",
      "Cache-Control": "no-store",
    });
    response.end(data);
  });
}

function openBrowser(url) {
  const command =
    process.platform === "win32"
      ? ["cmd.exe", ["/c", "start", "", url]]
      : process.platform === "darwin"
        ? ["open", [url]]
        : ["xdg-open", [url]];

  try {
    const child = spawn(command[0], command[1], {
      detached: true,
      stdio: "ignore",
      windowsHide: true,
    });
    child.unref();
  } catch {
    // Opening a browser is helpful, not required.
  }
}

function openLoginWindow() {
  const tools = getTools();
  if (!tools.gh) {
    return false;
  }

  const escapedGh = tools.gh.replace(/'/g, "''");
  const child = spawn(
    "powershell.exe",
    ["-NoExit", "-ExecutionPolicy", "Bypass", "-Command", `& '${escapedGh}' auth login -h github.com`],
    {
      cwd: projectRoot,
      detached: true,
      stdio: "ignore",
      windowsHide: false,
    },
  );
  child.unref();
  return true;
}

async function handleApi(request, response) {
  const requestUrl = new URL(request.url, `http://${host}:${port}`);

  try {
    if (request.method === "GET" && requestUrl.pathname === "/api/status") {
      sendJson(response, 200, await getStatus());
      return;
    }

    if (request.method === "POST" && requestUrl.pathname === "/api/push") {
      const payload = await parseBody(request);
      const result = await pushProject(payload);
      sendJson(response, 200, result);
      return;
    }

    if (request.method === "POST" && requestUrl.pathname === "/api/open-login") {
      const ok = openLoginWindow();
      sendJson(response, ok ? 200 : 500, { ok, message: ok ? "Login window opened." : "GitHub CLI was not found." });
      return;
    }

    if (request.method === "POST" && requestUrl.pathname === "/api/open-repo") {
      const tools = getTools();
      const origin = tools.git ? await gitValue(tools.git, ["remote", "get-url", "origin"]) : "";
      if (origin) {
        const webUrl = origin
          .replace(/^git@github\.com:/, "https://github.com/")
          .replace(/\.git$/, "");
        openBrowser(webUrl);
        sendJson(response, 200, { ok: true });
        return;
      }

      if (!tools.gh) {
        sendJson(response, 500, { ok: false, message: "No origin remote was found, and GitHub CLI is not available." });
        return;
      }
      const child = spawn(tools.gh, ["repo", "view", "--web"], {
        cwd: projectRoot,
        detached: true,
        stdio: "ignore",
        windowsHide: true,
      });
      child.unref();
      sendJson(response, 200, { ok: true });
      return;
    }

    sendJson(response, 404, { ok: false, message: "Unknown API route." });
  } catch (error) {
    sendJson(response, 500, { ok: false, message: error.message || String(error) });
  }
}

const server = http.createServer((request, response) => {
  if (request.url.startsWith("/api/")) {
    handleApi(request, response);
    return;
  }
  serveStatic(request, response);
});

server.on("error", (error) => {
  if (error.code === "EADDRINUSE") {
    console.error(`Port ${port} is already in use. Try opening http://${host}:${port}/ or close the old helper window.`);
  } else {
    console.error(error);
  }
  process.exit(1);
});

server.listen(port, host, () => {
  const url = `http://${host}:${port}/`;
  console.log(`GitHub push web helper is running at ${url}`);
  console.log(`Project folder: ${projectRoot}`);
  console.log("Close this terminal window to stop the helper.");
  if (shouldOpen) {
    openBrowser(url);
  }
});
