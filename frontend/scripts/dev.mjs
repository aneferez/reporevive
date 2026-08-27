#!/usr/bin/env node
/**
 * Dev orchestrator: start the Vite frontend and the FastAPI backend together.
 *
 * `npm run dev` (in frontend/) boots both; Ctrl+C stops both, and if either
 * process exits the other is torn down too. No extra dependency — just Node.
 *
 * Backend Python resolution prefers the project virtualenv
 * (backend/.venv) and falls back to the system interpreter. Override the
 * backend port with BACKEND_PORT (defaults to 8000, which matches the
 * frontend's default VITE_API_BASE_URL of http://localhost:8000).
 */
import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const isWin = process.platform === "win32";
const here = path.dirname(fileURLToPath(import.meta.url));
const frontendDir = path.resolve(here, "..");
const backendDir = path.resolve(here, "..", "..", "backend");

const children = [];
let shuttingDown = false;

/** Kill a child and, on Windows, its whole process tree (uvicorn --reload
 *  spawns a reloader child that a plain kill would orphan). */
function kill(child) {
  if (!child || child.killed || child.exitCode !== null) return;
  if (isWin) {
    try {
      spawn("taskkill", ["/pid", String(child.pid), "/T", "/F"], { stdio: "ignore" });
    } catch {
      /* best effort */
    }
  } else {
    try {
      child.kill("SIGTERM");
    } catch {
      /* best effort */
    }
  }
}

function shutdown(code) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) kill(child);
  process.exit(code);
}

function start(name, command, args, cwd) {
  const child = spawn(command, args, { cwd, stdio: "inherit" });
  child.on("error", (err) => {
    console.error(`\n[dev] failed to start ${name}: ${err.message}`);
    shutdown(1);
  });
  child.on("exit", (exitCode) => {
    if (!shuttingDown) {
      console.log(`\n[dev] ${name} exited (${exitCode ?? 0}); stopping the other process.`);
      shutdown(exitCode ?? 0);
    }
  });
  children.push(child);
  return child;
}

process.on("SIGINT", () => shutdown(0));
process.on("SIGTERM", () => shutdown(0));

// --- Backend: FastAPI via uvicorn, using the project venv if present --------
const venvPython = path.join(
  backendDir,
  ".venv",
  isWin ? "Scripts" : "bin",
  isWin ? "python.exe" : "python",
);
const python = existsSync(venvPython) ? venvPython : isWin ? "python" : "python3";
if (!existsSync(venvPython)) {
  console.log(
    `[dev] backend venv not found at ${venvPython}; falling back to '${python}' on PATH.\n` +
      `      Create it with:  cd backend && python -m venv .venv && ` +
      `pip install -r requirements-dev.txt`,
  );
}
const backendPort = process.env.BACKEND_PORT || "8000";
start(
  "backend",
  python,
  ["-m", "uvicorn", "app.main:app", "--reload", "--port", backendPort],
  backendDir,
);

// --- Frontend: Vite, launched via Node so no shell/.cmd shim is needed ------
const viteEntry = path.join(frontendDir, "node_modules", "vite", "bin", "vite.js");
start("frontend", process.execPath, [viteEntry], frontendDir);
