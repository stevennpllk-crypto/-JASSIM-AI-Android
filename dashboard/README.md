# JASSIM AI Cloud Dashboard

Static Arabic RTL control panel for the JASSIM AI backend.

## Local preview
Open `index.html` in a browser. For browser API access, serve this directory over HTTP(S), then configure the backend URL from Settings.

## Deploy
The GitHub Actions workflow `.github/workflows/pages.yml` publishes this directory to GitHub Pages. Enable Pages with **GitHub Actions** as the deployment source in repository Settings if it is not already enabled.

## Connect
Configure the base URL of the JASSIM API (without `/api/chat`). The dashboard calls:
- `GET /health`
- `POST /api/chat`
- `GET /api/history?conversation_id=...`

The current API must permit browser CORS from the dashboard origin. Do not expose an unauthenticated API publicly. Use HTTPS, authentication, rate limits, and private networking before public deployment.

This dashboard displays only values actually returned by the server; it does not fabricate CPU, RAM, GPU, or online status.
