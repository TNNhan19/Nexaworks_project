# NexaWorks frontend

Phase 5A provides the React application shell, routing, localization foundation,
typed API access, dashboard connectivity check, and lightweight placeholder
workspaces. It intentionally contains no scenario editor, charts, comparison
logic, or explanation rendering.

## Run locally

Start the FastAPI backend on port 8000, then:

    npm install
    npm run dev

Vite proxies /health and /api to http://127.0.0.1:8000 by default. Copy
.env.example to .env.local to change the proxy target. For a deployed API,
set VITE_API_BASE_URL to its public base URL and configure that server to
allow the frontend origin.

## Verify

    npm test
    npm run build
