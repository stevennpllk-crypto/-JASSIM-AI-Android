# JASSIM AI Cloud Dashboard

Static Arabic RTL control panel for the JASSIM AI backend.

## Local preview
Open `index.html` in a browser. For browser API access, serve this directory over HTTP(S), then configure the backend URL from Settings.

## Deploy
The GitHub Actions workflow `.github/workflows/pages.yml` publishes this directory to GitHub Pages. Enable Pages with **GitHub Actions** as the deployment source in repository Settings if it is not already enabled.

## Connect
Configure the HTTPS base URL of the JASSIM API (without an API path). The dashboard supports account registration/login/logout and calls:
- `GET /health`
- `POST /api/auth/register`, `POST /api/auth/login`, and `POST /api/auth/logout`
- `POST /api/chat/stream` for live SSE responses
- `GET /api/history?conversation_id=...`
- `POST /api/images/generate` when a server-side image provider is configured

The backend must allow browser CORS from the exact dashboard origin. Do not expose the API directly over public plain HTTP. Use HTTPS, authentication, rate limits, and private networking before public deployment. The dashboard keeps the session token in tab-scoped session storage and only clears it after server-side logout succeeds (or the server confirms it is already invalid).

This dashboard displays only values actually returned by the server; it does not fabricate CPU, RAM, GPU, or online status.
