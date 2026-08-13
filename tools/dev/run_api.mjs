import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const repositoryRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const environmentFile = resolve(repositoryRoot, ".env");
const uvExecutable = process.platform === "win32" ? "uv.exe" : "uv";

const uvArguments = ["run"];
if (existsSync(environmentFile)) {
  uvArguments.push("--env-file", ".env");
}
uvArguments.push("hawkeye", "app", "--data", "data", "--port", "8760");

const apiProcess = spawn(uvExecutable, uvArguments, {
  cwd: repositoryRoot,
  env: process.env,
  stdio: "inherit",
});

for (const signal of ["SIGINT", "SIGTERM"]) {
  process.on(signal, () => {
    if (!apiProcess.killed) {
      apiProcess.kill(signal);
    }
  });
}

apiProcess.on("error", (error) => {
  console.error(`Unable to start the HAWK-EYE API: ${error.message}`);
  process.exitCode = 1;
});

apiProcess.on("exit", (code) => {
  process.exit(code ?? 0);
});
