const { spawn, spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const root = __dirname;
const backend = path.join(root, "backend");
const frontend = path.join(root, "frontend");
const healthUrl = "http://127.0.0.1:8000/health/";
let backendProcess;
let frontendProcess;
let stopping = false;

function pythonCommand() {
  if (process.env.PYTHON) return { command: process.env.PYTHON, args: [] };

  const candidates = process.platform === "win32"
    ? [
        [path.join(root, ".venv", "Scripts", "python.exe"), []],
        [path.join(root, "venv", "Scripts", "python.exe"), []],
      ]
    : [
        [path.join(root, ".venv", "bin", "python"), []],
        [path.join(root, "venv", "bin", "python"), []],
      ];

  const venv = candidates.find(([executable]) => fs.existsSync(executable));
  if (venv) return { command: venv[0], args: venv[1] };
  return process.platform === "win32"
    ? { command: "py", args: ["-3.12"] }
    : { command: "python3.12", args: [] };
}

function runPython(args) {
  const python = pythonCommand();
  const result = spawnSync(python.command, [...python.args, ...args], {
    cwd: backend,
    stdio: "inherit",
  });
  if (result.error) throw new Error(`Could not start Python (${result.error.message}).`);
  if (result.status !== 0) throw new Error(`Python command failed with exit code ${result.status}.`);
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function apiIsHealthy() {
  try {
    const response = await fetch(healthUrl, { signal: AbortSignal.timeout(2000) });
    if (!response.ok) return false;
    const body = await response.json();
    return body.status === "ok" && body.database === "connected";
  } catch {
    return false;
  }
}

async function frontendIsRunning() {
  try {
    const response = await fetch("http://localhost:3000/", {
      signal: AbortSignal.timeout(1000),
    });
    return response.ok;
  } catch {
    return false;
  }
}

async function waitForBackend() {
  for (let attempt = 0; attempt < 30; attempt += 1) {
    if (await apiIsHealthy()) return;
    if (backendProcess.exitCode !== null) {
      throw new Error(`Django exited before becoming ready (code ${backendProcess.exitCode}).`);
    }
    await sleep(1000);
  }
  throw new Error("Django did not become ready within 30 seconds; React was not started.");
}

function stopChild(child) {
  if (child && child.exitCode === null) child.kill("SIGTERM");
}

async function shutdown(exitCode = 0) {
  if (stopping) return;
  stopping = true;
  stopChild(frontendProcess);
  stopChild(backendProcess);
  process.exitCode = exitCode;
}

async function main() {
  if (await apiIsHealthy()) {
    console.log("Using the healthy Django API already running on port 8000.");
  } else {
    console.log("Checking the configured MySQL connection and applying migrations...");
    runPython(["manage.py", "check", "--database", "default"]);
    runPython(["manage.py", "migrate", "--noinput"]);

    const python = pythonCommand();
    backendProcess = spawn(
      python.command,
      [...python.args, "manage.py", "runserver", "--noreload", "127.0.0.1:8000"],
      { cwd: backend, stdio: "inherit" },
    );
    backendProcess.on("error", (error) => {
      console.error(`Could not start Django: ${error.message}`);
      void shutdown(1);
    });
    backendProcess.on("exit", (code) => {
      if (!stopping) {
        console.error(`Django stopped${code === null ? "" : ` (code ${code})`}.`);
        void shutdown(code || 1);
      }
    });
    await waitForBackend();
  }

  if (await frontendIsRunning()) {
    console.log("React is already running on port 3000; keeping the Django API available.");
    return;
  }

  console.log("Starting React frontend on http://localhost:3000...");
  const npmCli = process.env.npm_execpath;
  if (!npmCli) throw new Error("Run this command with npm run dev so npm can locate its CLI.");
  frontendProcess = spawn(process.execPath, [npmCli, "start", "--prefix", frontend], {
    cwd: root,
    stdio: "inherit",
  });
  frontendProcess.on("error", (error) => {
    console.error(`Could not start React: ${error.message}`);
    void shutdown(1);
  });
  frontendProcess.on("exit", (code) => {
    if (!stopping) void shutdown(code || 0);
  });
}

process.on("SIGINT", () => void shutdown(130));
process.on("SIGTERM", () => void shutdown(143));

main().catch((error) => {
  console.error(error.message);
  console.error("Check Python 3.12, backend dependencies, MySQL credentials, and backend/.env.");
  void shutdown(1);
});