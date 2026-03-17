# AI Sales Dashboard

AI Sales Dashboard is a Frappe/ERPNext app for sales intelligence, KPI analytics, and AI-assisted executive insights.

This repository contains the complete app code (DocTypes, Pages, Reports, APIs, assets, and settings UI).

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

## 1. Upload App to GitHub (Complete App)

Run these commands on your development server in `apps/ai_sales_dashboard`.

```bash
cd /home/frappe/frappe-bench/apps/ai_sales_dashboard

# initialize git if needed
git init
git add .
git commit -m "Initial production release: AI Sales Dashboard"

# set main branch
git branch -M main

# add your GitHub repo
git remote add origin https://github.com/<your-org>/ai_sales_dashboard.git

# push complete app
git push -u origin main
```

If remote already exists:

```bash
git remote -v
git push -u origin main
```

## 2. Install on New Client Server (Fresh App Install)

Assumption: Bench + Frappe + ERPNext are already installed on client server.

```bash
cd /home/frappe/frappe-bench

# download app from GitHub
bench get-app https://github.com/<your-org>/ai_sales_dashboard.git --branch main

# install app on target site
bench --site <client-site> install-app ai_sales_dashboard

# apply schema/doctype updates
bench --site <client-site> migrate

# build assets
bench build --app ai_sales_dashboard

# restart services
bench restart
```

## 3. Update on Already Installed Server

Use this on servers where `ai_sales_dashboard` is already installed.

```bash
cd /home/frappe/frappe-bench

# pull latest app code
bench --site <client-site> backup --with-files
bench update --apps ai_sales_dashboard --reset

# ensure schema and assets are updated
bench --site <client-site> migrate
bench build --app ai_sales_dashboard
bench restart
```

If you prefer app-only git pull:

```bash
cd /home/frappe/frappe-bench/apps/ai_sales_dashboard
git pull origin main

cd /home/frappe/frappe-bench
bench --site <client-site> migrate
bench build --app ai_sales_dashboard
bench restart
```

## 4. Download Commands (For Client/Dev)

```bash
# clone only repository
git clone https://github.com/<your-org>/ai_sales_dashboard.git

# bench-aware download into apps/
bench get-app https://github.com/<your-org>/ai_sales_dashboard.git --branch main
```

## 5. Post-Install Configuration

1. Open desk: `/app/ai-sales-ai-settings`
2. Enable AI Insights
3. Select provider and model
4. Save API key
5. Click `Test Connection`
6. (Recommended) Save provider profiles and run `Test Saved Providers`

## 6. Verification Checklist

After install/update, verify:

```bash
cd /home/frappe/frappe-bench

bench --site <client-site> list-apps | grep ai_sales_dashboard
bench --site <client-site> execute ai_sales_dashboard.api.get_ai_engine_status
bench --site <client-site> execute ai_sales_dashboard.api.get_saved_ai_provider_profiles
```

UI checks:

- `/app/ai-sales-dashboard`
- `/app/ai-executive-summary`
- `/app/ai-sales-agent`
- `/app/ai-chatbot`

## 7. Optional: One-Step Deployment Script

```bash
cd /home/frappe/frappe-bench

SITE=<client-site>
REPO=https://github.com/<your-org>/ai_sales_dashboard.git
BRANCH=main

bench get-app "$REPO" --branch "$BRANCH" || true
bench --site "$SITE" install-app ai_sales_dashboard || true
bench --site "$SITE" migrate
bench build --app ai_sales_dashboard
bench restart
```

## 8. Troubleshooting

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
