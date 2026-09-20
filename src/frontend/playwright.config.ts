import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://127.0.0.1:5173" },
  workers: 1,
  webServer: [
    {
      command: "APP_ENV=local LOCAL_DATABASE_PATH=.local/e2e.sqlite3 PYTHONPATH=src/backend:src/agents/event-guide uv run uvicorn main:app --host 127.0.0.1 --port 8765",
      cwd: "../..",
      url: "http://127.0.0.1:8765/api/health",
      reuseExistingServer: false,
    },
    { command: "npm run dev -- --port 5173", url: "http://127.0.0.1:5173", reuseExistingServer: false },
  ],
});
