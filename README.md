# AI Sales Dashboard

AI Sales Dashboard is a Frappe/ERPNext app for sales intelligence, KPI analytics, and AI-assisted executive insights.

This repository contains the complete app code (DocTypes, Pages, Reports, APIs, assets, and settings UI).

## Repository Contents

This GitHub repository includes the complete app package required for installation on another server.

- App source code
- API endpoints
- DocTypes
- Pages
- Reports
- Dashboard charts
- Number cards
- Workspace assets
- Public JavaScript assets
- Documentation folder
- Image folder for screenshots

Main paths included in the repository:

- `ai_sales_dashboard/api.py`
- `ai_sales_dashboard/hooks.py`
- `ai_sales_dashboard/ai_providers.py`
- `ai_sales_dashboard/ai_sales_dashboard/doctype/`
- `ai_sales_dashboard/ai_sales_dashboard/page/`
- `ai_sales_dashboard/ai_sales_dashboard/report/`
- `ai_sales_dashboard/ai_sales_dashboard/dashboard_chart/`
- `ai_sales_dashboard/ai_sales_dashboard/number_card/`
- `ai_sales_dashboard/public/js/`
- `docs/`
- `docs/images/`

## What Is Included

- AI Executive Summary dashboard with KPI, trends, risks, and AI narrative
- AI Sales Agent / Chatbot pages
- Multi-provider AI settings with saved provider profiles
- Provider health diagnostics (test all saved providers)
- Statistical fallback engine (offline)
- Workspace, reports, dashboard charts, and number cards

## Dependencies

## Runtime

- Frappe Bench (v5+)
- Frappe Framework v15
- ERPNext v15 (required app)
- Python >= 3.10
- Node.js (as required by Frappe v15, typically 18+)

## App-level dependency

- `erpnext` (declared in `hooks.py` as `required_apps = ["erpnext"]`)

## Optional AI dependencies

- External providers: Groq, OpenRouter, Gemini, Together AI, etc.
- Local provider: Ollama (for offline/local inference)

## 1. Install on New Server

Assumption: Bench + Frappe + ERPNext are already installed on client server.

```bash
cd /home/frappe/frappe-bench

# download app from GitHub
bench get-app https://github.com/ERPNEXT-PAKISTAN/AI-Sales-Dashboard.git --branch main

# install app on target site
bench --site site1.local install-app ai_sales_dashboard

# apply schema/doctype updates
bench --site site1.local migrate

# build assets
bench build --app ai_sales_dashboard

# restart services
bench restart
```

## 2. Update on Already Installed Server

Use this on servers where `ai_sales_dashboard` is already installed.

```bash
cd /home/frappe/frappe-bench

# pull latest app code
bench --site site1.local backup --with-files
bench update --apps ai_sales_dashboard --reset

# ensure schema and assets are updated
bench --site site1.local migrate
bench build --app ai_sales_dashboard
bench restart
```

If you prefer app-only git pull:

```bash
cd /home/frappe/frappe-bench/apps/ai_sales_dashboard
git pull origin main

cd /home/frappe/frappe-bench
bench --site site1.local migrate
bench build --app ai_sales_dashboard
bench restart
```

## 3. Download Commands

```bash
# clone only repository
git clone https://github.com/ERPNEXT-PAKISTAN/AI-Sales-Dashboard.git

# bench-aware download into apps/
bench get-app https://github.com/ERPNEXT-PAKISTAN/AI-Sales-Dashboard.git --branch main
```

## 4. Post-Install Configuration

1. Open desk: `/app/ai-sales-ai-settings`
2. Enable AI Insights
3. Select provider and model
4. Save API key
5. Click `Test Connection`
6. (Recommended) Save provider profiles and run `Test Saved Providers`

## 5. Verification Checklist

After install/update, verify:

```bash
cd /home/frappe/frappe-bench

bench --site site1.local list-apps | grep ai_sales_dashboard
bench --site site1.local execute ai_sales_dashboard.api.get_ai_engine_status
bench --site site1.local execute ai_sales_dashboard.api.get_saved_ai_provider_profiles
```

UI checks:

- `/app/ai-sales-dashboard`
- `/app/ai-executive-summary`
- `/app/ai-sales-agent`
- `/app/ai-chatbot`

## 6. Optional One-Step Deployment Script

```bash
cd /home/frappe/frappe-bench

SITE=site1.local
REPO=https://github.com/ERPNEXT-PAKISTAN/AI-Sales-Dashboard.git
BRANCH=main

bench get-app "$REPO" --branch "$BRANCH" || true
bench --site "$SITE" install-app ai_sales_dashboard || true
bench --site "$SITE" migrate
bench build --app ai_sales_dashboard
bench restart
```

## 7. Ollama / Local AI Setup

Use Ollama when you want local AI on your laptop, desktop, or VPS without sending data to cloud providers.

### Install Ollama on Ubuntu / VPS

```bash
curl -fsSL https://ollama.com/install.sh | sh
ollama serve
```

If you want Ollama to run in background as a service, install it normally and start the system service.

### Pull Models Used in This App

Light models for low-spec servers:

```bash
ollama pull qwen2.5:1.5b
ollama pull phi3:mini
ollama pull llama3.2:3b
```

Larger models if server is stronger:

```bash
ollama pull deepseek-r1:latest
ollama pull llama3.1:8b
```

### Recommended for Low VPS / Low RAM

- `qwen2.5:1.5b`
- `phi3:mini`
- `llama3.2:3b`

### Configure App to Use Ollama

Open `/app/ai-sales-ai-settings` and set:

- Provider: `Ollama`
- Base URL: `http://127.0.0.1:11434`
- Model: `qwen2.5:1.5b` or `phi3:mini`

Then click `Test Connection`.

### Example Server-Side Setup Command

```bash
cd /home/frappe/frappe-bench
bench --site site1.local execute frappe.client.set_value --kwargs '{"doctype":"AI Sales AI Settings","name":"AI Sales AI Settings","fieldname":{"provider":"Ollama","base_url":"http://127.0.0.1:11434","model":"qwen2.5:1.5b","enabled":1}}'
```

## 8. Free AI API Signup Links

### 🔥 Groq

- Signup: [https://console.groq.com/login](https://console.groq.com/login)
- Dashboard / API Keys: [https://console.groq.com/keys](https://console.groq.com/keys)
- Steps:
	1. Signup
	2. Open dashboard
	3. Generate API key
- Notes:
	- ✅ Ultra fast
	- ✅ Free tier available
	- ✅ Best for chatbot and analytics

### 🔀 OpenRouter

- Signup: [https://openrouter.ai/signup](https://openrouter.ai/signup)
- Tokens: [https://openrouter.ai/settings/keys](https://openrouter.ai/settings/keys)
- Steps:
	1. Signup
	2. Go to Settings -> Tokens
	3. Create token
- Notes:
	- ✅ Thousands of models
	- ✅ Free usage available on selected models

### ✨ Gemini

- Signup / API Key: [https://aistudio.google.com/app/apikey](https://aistudio.google.com/app/apikey)
- Dashboard: [https://aistudio.google.com/](https://aistudio.google.com/)
- Steps:
	1. Login with Google account
	2. Open AI Studio
	3. Generate API key
- Notes:
	- ✅ Free tier available
	- ✅ Good for fast cloud inference

### 🚀 Together AI

- Signup: [https://api.together.xyz/](https://api.together.xyz/)
- API Keys: [https://api.together.xyz/settings/api-keys](https://api.together.xyz/settings/api-keys)
- Steps:
	1. Signup
	2. Open API Keys page
	3. Generate key
- Notes:
	- ✅ Large model catalog
	- ✅ Credits may be available

### 🧠 Cerebras

- Signup: [https://cloud.cerebras.ai/](https://cloud.cerebras.ai/)
- API Keys: [https://cloud.cerebras.ai/platform/api-keys](https://cloud.cerebras.ai/platform/api-keys)
- Steps:
	1. Signup
	2. Open platform dashboard
	3. Generate API key
- Notes:
	- ✅ Very fast inference when configured correctly
	- ⚠ Verify endpoint and account access before production use

## 9. Troubleshooting

- `Could not reach the AI provider`: check API key, base URL, model, provider quota
- `429`: provider rate limit/quota exceeded
- `401`: invalid or unauthorized key
- `404`: wrong endpoint/model/base URL
- Missing UI changes: hard refresh browser (`Ctrl+Shift+R`) after `bench build`

## Development

```bash
cd /home/frappe/frappe-bench/apps/ai_sales_dashboard
pre-commit install
```

Pre-commit tools:

- ruff
- eslint
- prettier
- pyupgrade

## License

MIT
