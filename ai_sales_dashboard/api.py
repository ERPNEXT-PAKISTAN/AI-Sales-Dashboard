import json

import frappe
import requests
from frappe import _
from frappe.utils import add_days, cint, flt, getdate, now_datetime, nowdate

from ai_sales_dashboard.ai_providers import PROVIDER_DOCUMENTATION_URLS, get_provider_catalog, get_provider_preset


DEFAULT_AI_AGENT_INSTRUCTIONS = (
	"You are a sales analytics assistant. Answer only from the data provided. "
	"Be concise — max 150 words. Use bullets when helpful. "
	"If data is missing, say so."
)


def _safe_pct_change(current: float, previous: float) -> float:
	if not previous:
		return 0.0
	return ((current - previous) / previous) * 100.0


def _try_direct_query_answer(message: str, context: dict) -> str | None:
	"""Try to answer simple fact-based queries directly without full summary."""
	import re
	q = (message or "").lower().strip()
	kpi = context.get("kpi") or {}
	monthly = (context.get("trends") or {}).get("monthly_revenue") or []
	booked = flt(kpi.get("booked_revenue"))
	company = context.get("company") or ""
	from_date = context.get("from_date") or ""
	to_date = context.get("to_date") or ""

	# Year-specific sales queries — e.g. "sales 2025", "2026 sales", "what is 2025 sales"
	def _year_total(target_year: int) -> float:
		return flt(
			frappe.db.sql(
				"""
				SELECT COALESCE(SUM(base_grand_total), 0)
				FROM `tabSales Invoice`
				WHERE company = %s
				  AND docstatus = 1
				  AND posting_date BETWEEN %s AND %s
				  AND YEAR(posting_date) = %s
				""",
				(company, from_date, to_date, target_year),
			)[0][0]
			or 0
		)

	year_tokens = re.findall(r"\b(20\d{2})\b", q)
	years: list[int] = []
	for token in year_tokens:
		year_val = cint(token)
		if year_val not in years:
			years.append(year_val)

	if years and any(w in q for w in ["sales", "revenue", "total", "earning", "income", "turnover"]):
		# Multi-year comparison query, e.g. "sales 2025 vs 2026"
		if len(years) >= 2 and any(k in q for k in [" vs ", "versus", "compare", "comparison", " and "]):
			totals = [(year, _year_total(year)) for year in years[:4]]
			parts = [f"{year}: {value:,.2f}" for year, value in totals]
			base_year, base_value = totals[0]
			last_year, last_value = totals[-1]
			delta = last_value - base_value
			trend = "up" if delta >= 0 else "down"
			return (
				f"Sales comparison ({company}, {from_date} → {to_date}) | "
				+ " | ".join(parts)
				+ f" | {last_year} is {trend} {abs(delta):,.2f} vs {base_year}"
			)

		target_year = years[0]
		year_total = _year_total(target_year)
		if year_total > 0:
			return (
				f"Sales total for {target_year} ({company}, within selected range {from_date} → {to_date}): "
				f"{year_total:,.2f}"
			)
		return (
			f"No booked revenue found for year {target_year} within selected range {from_date} → {to_date}.\n"
			"Tip: expand the From/To filters if you want full-year totals."
		)

	# Generic sales/revenue total
	if any(w in q for w in ["total sales", "sales total", "total revenue", "revenue total", "booked revenue", "how much sales", "how much revenue"]):
		if booked > 0:
			return f"Total booked revenue for {company} ({from_date} → {to_date}): {booked:,.2f}"
		return f"No booked revenue recorded for {company} in the selected period."

	# Monthly revenue
	if any(w in q for w in ["monthly revenue", "monthly sales", "this month", "last month", "revenue this month"]):
		if monthly:
			latest = monthly[-1]
			month_label = latest.get("month") or "Latest"
			rev = flt(latest.get("monthly_revenue"))
			return f"Monthly revenue for {month_label} ({company}): {rev:,.2f}"
		return "No monthly revenue data available for the selected period."

	# Pipeline/opportunities
	if any(w in q for w in ["pipeline", "open opportunit", "opportunity total"]):
		pipeline = flt(kpi.get("pipeline_value"))
		open_opp = cint(kpi.get("open_opportunities"))
		weighted = flt(kpi.get("weighted_pipeline_value"))
		return (
			f"Open pipeline ({company}): {pipeline:,.2f} across {open_opp} opportunities\n"
			f"Weighted pipeline value: {weighted:,.2f}"
		)

	# Win rate / conversion
	if any(w in q for w in ["win rate", "conversion rate", "conversion ratio", "close rate"]):
		win_rate = flt(kpi.get("win_rate_percent"))
		return f"Win/conversion rate ({company}): {win_rate:.1f}%"

	# Top customers
	if any(w in q for w in ["top customer", "biggest customer", "key customer", "best customer", "largest customer"]):
		top_customers = context.get("top_customers") or []
		if top_customers:
			lines = [f"Top customers for {company} ({from_date} → {to_date}):"]
			for i, cust in enumerate(top_customers[:3], 1):
				name = cust.get("customer_name") or cust.get("customer") or "Unknown"
				rev = flt(cust.get("total_revenue"))
				lines.append(f"  {i}. {name}: {rev:,.2f}")
			return "\n".join(lines)
		return "No customer revenue data available."

	# Customer-wise sales listing
	if any(
		w in q
		for w in [
			"customer wise sales",
			"customer-wise sales",
			"customerwise sales",
			"sales by customer",
			"customer sales",
			"customer revenue",
		]
	):
		rows = (get_customer_analytics(company=company, from_date=from_date, to_date=to_date).get("top_customers") or [])[:10]
		if not rows:
			return f"No customer-wise sales data found for {company} in {from_date} → {to_date}."

		lines = [
			f"Customer-wise sales for {company} ({from_date} → {to_date}):",
			"| # | Customer | Invoices | Revenue |",
			"|---:|---|---:|---:|",
		]
		for i, row in enumerate(rows, 1):
			name = row.get("customer_name") or row.get("customer") or "Unknown"
			invoices = cint(row.get("invoice_count") or 0)
			revenue = flt(row.get("total_revenue") or 0)
			lines.append(f"| {i} | {name} | {invoices} | {revenue:,.2f} |")
		return "\n".join(lines)

	# Forecast
	if any(w in q for w in ["forecast", "predict", "next month", "projection", "outlook"]):
		forecast = context.get("forecast") or _ols_forecast_monthly_revenue(monthly, periods=3)
		if forecast:
			lines = [f"Revenue forecast for {company}:"]
			for row in forecast:
				lines.append(f"  Month +{row['step']}: {row['forecast_revenue']:,.2f}")
			return "\n".join(lines)
		return "Insufficient monthly history to generate a forecast."

	return None


def _ols_forecast_monthly_revenue(monthly_revenue: list[dict], periods: int = 3) -> list[dict]:
	"""Simple OLS forecast using month index as x and monthly revenue as y."""
	values = [flt(row.get("monthly_revenue")) for row in (monthly_revenue or []) if row.get("monthly_revenue") is not None]
	n = len(values)
	if n == 0:
		return []
	if n == 1:
		baseline = max(values[0], 0.0)
		return [{"step": step + 1, "forecast_revenue": round(baseline, 2)} for step in range(periods)]

	x_sum = sum(range(n))
	y_sum = sum(values)
	xx_sum = sum(i * i for i in range(n))
	xy_sum = sum(i * values[i] for i in range(n))
	denominator = (n * xx_sum) - (x_sum * x_sum)
	slope = ((n * xy_sum) - (x_sum * y_sum)) / denominator if denominator else 0.0
	intercept = (y_sum - (slope * x_sum)) / n

	forecast_rows = []
	for step in range(1, periods + 1):
		x_val = n - 1 + step
		prediction = max((slope * x_val) + intercept, 0.0)
		forecast_rows.append({"step": step, "forecast_revenue": round(prediction, 2)})
	return forecast_rows


def _build_statistical_engine_output(context: dict, user_question: str | None = None) -> dict:
	kpi = context.get("kpi") or {}
	monthly = (context.get("trends") or {}).get("monthly_revenue") or []
	risk_flags = context.get("risk_flags") or []
	top_customers = context.get("top_customers") or []
	forecast_rows = _ols_forecast_monthly_revenue(monthly, periods=3)

	def _fmt_money(value: float) -> str:
		return f"{flt(value):,.2f}"

	latest_rev = flt(monthly[-1].get("monthly_revenue")) if monthly else 0.0
	prev_rev = flt(monthly[-2].get("monthly_revenue")) if len(monthly) > 1 else 0.0
	revenue_change = _safe_pct_change(latest_rev, prev_rev)

	booked_revenue = flt(kpi.get("booked_revenue"))
	top_customer_revenue = flt(top_customers[0].get("total_revenue")) if top_customers else 0.0
	customer_concentration = (top_customer_revenue / booked_revenue * 100.0) if booked_revenue else 0.0

	open_opportunities = cint(kpi.get("open_opportunities") or 0)
	pipeline_value = flt(kpi.get("pipeline_value") or 0)
	weighted_pipeline = flt(kpi.get("weighted_pipeline_value") or 0)
	win_rate = flt(kpi.get("win_rate_percent") or 0)
	coverage_pct = (weighted_pipeline / booked_revenue * 100.0) if booked_revenue else 0.0

	risk_rows = []
	if not risk_flags:
		risk_rows.append(("Medium", "No explicit risk flags", "No risk signals were generated from current KPIs."))
	for risk in risk_flags[:3]:
		level = (risk.get("level") or "medium").upper()
		risk_rows.append((level, risk.get("title") or "Risk", risk.get("detail") or ""))
	if customer_concentration >= 40:
		risk_rows.append(
			(
				"HIGH",
				"Customer concentration",
				f"Top customer contributes {customer_concentration:.1f}% of booked revenue.",
			)
		)

	action_rows = []
	if flt(kpi.get("win_rate_percent")) < 20:
		action_rows.append(("Sales Manager", "Run 2-week qualification cleanup for all open deals.", "This week"))
	if flt(kpi.get("weighted_pipeline_value")) < flt(kpi.get("booked_revenue")):
		action_rows.append(("BD Team", "Refill top-of-funnel to increase weighted coverage.", "Next 7 days"))
	if revenue_change < 5:
		action_rows.append(("AR + Sales Ops", "Create delayed quote/invoice recovery tracker with owners.", "Daily follow-up"))
	if not action_rows:
		action_rows.append(("Sales Ops", "Maintain current rhythm and monitor conversion weekly.", "Weekly"))

	kpi_table = (
		"| Metric | Value |\n"
		"|---|---:|\n"
		f"| Company | {context.get('company')} |\n"
		f"| Period | {context.get('from_date')} to {context.get('to_date')} |\n"
		f"| Booked Revenue | {_fmt_money(booked_revenue)} |\n"
		f"| Open Opportunities | {open_opportunities} |\n"
		f"| Pipeline Value | {_fmt_money(pipeline_value)} |\n"
		f"| Weighted Pipeline | {_fmt_money(weighted_pipeline)} |\n"
		f"| Weighted Coverage vs Booked | {coverage_pct:.1f}% |\n"
		f"| Win Rate | {win_rate:.1f}% |\n"
		f"| Latest Monthly Revenue Change | {revenue_change:.1f}% |\n"
	)

	if forecast_rows:
		forecast_table = "| Forecast Step | Revenue Forecast |\n|---|---:|\n" + "\n".join(
			f"| M+{row['step']} | {_fmt_money(row['forecast_revenue'])} |" for row in forecast_rows
		)
	else:
		forecast_table = "Forecast unavailable due to insufficient monthly revenue points."

	risks_table = "| Priority | Risk | Detail |\n|---|---|---|\n" + "\n".join(
		f"| {prio} | {title} | {detail} |" for prio, title, detail in risk_rows
	)

	actions_table = "| Owner | Action | Timeline |\n|---|---|---|\n" + "\n".join(
		f"| {owner} | {action} | {timeline} |" for owner, action, timeline in action_rows
	)

	summary = (
		"## Executive Statistical Report\n"
		"### KPI Snapshot\n"
		+ kpi_table
		+ "\n"
		+ "### OLS Forecast (3-Step)\n"
		+ forecast_table
		+ "\n"
		+ "### Key Risks\n"
		+ risks_table
		+ "\n"
		+ "### Recommended Actions\n"
		+ actions_table
		+ "\n"
	)

	if user_question:
		qa = (
			"### Question Focus\n"
			"| Field | Value |\n"
			"|---|---|\n"
			f"| User Question | {user_question.strip()} |\n"
			"| Response Mode | Internal statistical signals only (no external LLM call) |\n"
		)
	else:
		qa = ""

	return {
		"summary_text": summary + qa,
		"forecast": forecast_rows,
		"growth_percent": round(revenue_change, 2),
		"customer_concentration_percent": round(customer_concentration, 2),
		"engine": "statistical-ols-v1",
	}


def _require_roles(*roles: str) -> None:
	user_roles = set(frappe.get_roles(frappe.session.user))
	if "System Manager" in user_roles:
		return
	if not user_roles.intersection(set(roles)):
		frappe.throw(_("You are not permitted to access AI Sales Dashboard APIs."), frappe.PermissionError)


def has_app_access() -> bool:
	"""Used by hooks.py add_to_apps_screen.has_permission."""
	try:
		_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
		return True
	except frappe.PermissionError:
		return False


def _get_default_company() -> str | None:
	company = frappe.db.get_single_value("AI Sales Dashboard Settings", "company")
	if company:
		return company
	return frappe.defaults.get_user_default("Company")


@frappe.whitelist()
def get_sales_kpi_summary(company: str | None = None, from_date: str | None = None, to_date: str | None = None):
	"""Return a lightweight KPI summary for workspace cards."""
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")

	company = company or _get_default_company()
	if not company:
		frappe.throw(_("Please set Company in AI Sales Dashboard Settings."))

	if not to_date:
		to_date = nowdate()

	if not from_date:
		period_days = cint(frappe.db.get_single_value("AI Sales Dashboard Settings", "analysis_period_days") or 90)
		from_date = add_days(getdate(to_date), -period_days)

	opp_filters = {"company": company, "creation": ["between", [from_date, to_date]]}
	open_opp_count = frappe.db.count("Opportunity", filters={**opp_filters, "status": ["not in", ["Lost", "Converted"]]})

	pipeline_rows = frappe.get_all(
		"Opportunity",
		filters={**opp_filters, "status": ["not in", ["Lost", "Converted"]]},
		fields=["opportunity_amount", "probability"],
	)
	pipeline_value = 0.0
	weighted_pipeline_value = 0.0
	for row in pipeline_rows:
		amount = flt(row.opportunity_amount)
		prob = flt(row.probability)
		pipeline_value += amount
		weighted_pipeline_value += amount * (prob / 100.0)

	total_created = frappe.db.count("Opportunity", filters=opp_filters) or 0
	total_converted = frappe.db.count("Opportunity", filters={**opp_filters, "status": ["in", ["Converted", "Quotation"]]})
	win_rate_percent = (flt(total_converted) / total_created * 100.0) if total_created else 0.0

	revenue_rows = frappe.get_all(
		"Sales Invoice",
		filters={
			"company": company,
			"posting_date": ["between", [from_date, to_date]],
			"docstatus": 1,
		},
		fields=["base_grand_total"],
	)
	booked_revenue = sum(flt(r.base_grand_total) for r in revenue_rows)

	return {
		"company": company,
		"from_date": str(from_date),
		"to_date": str(to_date),
		"open_opportunities": open_opp_count,
		"pipeline_value": pipeline_value,
		"weighted_pipeline_value": weighted_pipeline_value,
		"win_rate_percent": round(win_rate_percent, 2),
		"booked_revenue": booked_revenue,
	}


@frappe.whitelist()
def get_pipeline_breakdown(company: str | None = None, group_by: str = "status"):
	"""Return grouped pipeline rows by status or opportunity owner."""
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")

	company = company or _get_default_company()
	if not company:
		frappe.throw(_("Please set Company in AI Sales Dashboard Settings."))

	group_field = "status" if group_by not in ("status", "opportunity_owner") else group_by

	rows = frappe.db.sql(
		f"""
		SELECT
			COALESCE({group_field}, 'Not Set') AS group_key,
			COUNT(name) AS opportunity_count,
			SUM(COALESCE(opportunity_amount, 0)) AS pipeline_value,
			SUM(COALESCE(opportunity_amount, 0) * COALESCE(probability, 0) / 100) AS weighted_pipeline_value
		FROM `tabOpportunity`
		WHERE company = %s
		  AND status NOT IN ('Lost', 'Converted')
		GROUP BY {group_field}
		ORDER BY pipeline_value DESC
		""",
		(company,),
		as_dict=True,
	)

	return {"company": company, "group_by": group_field, "rows": rows}


@frappe.whitelist()
def enqueue_refresh_kpi(company: str | None = None, snapshot_date: str | None = None):
	"""Queue KPI snapshot generation for one company/date."""
	_require_roles("AI Sales Manager", "Sales Manager")

	company = company or _get_default_company()
	if not company:
		frappe.throw(_("Please set Company in AI Sales Dashboard Settings."))

	snapshot_date = snapshot_date or nowdate()
	job_name = f"ai_sales_dashboard_refresh_kpi::{company}::{snapshot_date}"
	frappe.enqueue(
		"ai_sales_dashboard.utils.kpi.create_snapshot_for_company",
		queue="long",
		job_name=job_name,
		company=company,
		snapshot_date=snapshot_date,
	)

	return {"status": "queued", "job_name": job_name, "company": company, "snapshot_date": snapshot_date}


def get_territory_breakdown(company: str, from_date: str, to_date: str) -> dict:
	"""Get pipeline and revenue by territory."""
	rows = frappe.db.sql(
		"""
		SELECT
			COALESCE(territory, 'Not Set') AS territory,
			COUNT(DISTINCT o.name) AS opportunity_count,
			SUM(COALESCE(o.opportunity_amount, 0)) AS pipeline_value,
			SUM(COALESCE(o.opportunity_amount, 0) * COALESCE(o.probability, 0) / 100) AS weighted_value
		FROM `tabOpportunity` o
		WHERE o.company = %s
		  AND o.creation BETWEEN %s AND %s
		  AND o.status NOT IN ('Lost', 'Converted')
		GROUP BY territory
		ORDER BY pipeline_value DESC
		LIMIT 5
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	return {"territory_breakdown": rows}


def get_salesperson_breakdown(company: str, from_date: str, to_date: str) -> dict:
	"""Get pipeline and revenue by opportunity owner/salesperson."""
	rows = frappe.db.sql(
		"""
		SELECT
			COALESCE(opportunity_owner, 'Unassigned') AS salesperson,
			COUNT(name) AS opportunity_count,
			SUM(COALESCE(opportunity_amount, 0)) AS pipeline_value,
			SUM(COALESCE(opportunity_amount, 0) * COALESCE(probability, 0) / 100) AS weighted_value
		FROM `tabOpportunity`
		WHERE company = %s
		  AND creation BETWEEN %s AND %s
		  AND status NOT IN ('Lost', 'Converted')
		GROUP BY opportunity_owner
		ORDER BY pipeline_value DESC
		LIMIT 5
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	return {"salesperson_breakdown": rows}


def get_item_analytics(company: str, from_date: str, to_date: str) -> dict:
	"""Get top items and item groups by revenue."""
	item_rows = frappe.db.sql(
		"""
		SELECT
			sii.item_code,
			sii.item_name,
			SUM(sii.qty) AS total_qty,
			SUM(sii.base_amount) AS total_amount
		FROM `tabSales Invoice Item` sii
		JOIN `tabSales Invoice` si ON sii.parent = si.name
		WHERE si.company = %s
		  AND si.posting_date BETWEEN %s AND %s
		  AND si.docstatus = 1
		GROUP BY sii.item_code
		ORDER BY total_amount DESC
		LIMIT 5
		""",
		(company, from_date, to_date),
		as_dict=True,
	)

	group_rows = frappe.db.sql(
		"""
		SELECT
			i.item_group,
			COUNT(DISTINCT sii.item_code) AS item_count,
			SUM(sii.qty) AS total_qty,
			SUM(sii.base_amount) AS total_amount
		FROM `tabSales Invoice Item` sii
		JOIN `tabItem` i ON sii.item_code = i.name
		JOIN `tabSales Invoice` si ON sii.parent = si.name
		WHERE si.company = %s
		  AND si.posting_date BETWEEN %s AND %s
		  AND si.docstatus = 1
		GROUP BY i.item_group
		ORDER BY total_amount DESC
		LIMIT 5
		""",
		(company, from_date, to_date),
		as_dict=True,
	)

	return {"top_items": item_rows, "item_groups": group_rows}


def get_customer_analytics(company: str, from_date: str, to_date: str) -> dict:
	"""Get top customers and customer groups by revenue."""
	customer_rows = frappe.db.sql(
		"""
		SELECT
			customer,
			customer_name,
			COUNT(name) AS invoice_count,
			SUM(base_grand_total) AS total_revenue
		FROM `tabSales Invoice`
		WHERE company = %s
		  AND posting_date BETWEEN %s AND %s
		  AND docstatus = 1
		GROUP BY customer
		ORDER BY total_revenue DESC
		LIMIT 5
		""",
		(company, from_date, to_date),
		as_dict=True,
	)

	group_rows = frappe.db.sql(
		"""
		SELECT
			c.customer_group,
			COUNT(DISTINCT si.customer) AS customer_count,
			COUNT(si.name) AS invoice_count,
			SUM(si.base_grand_total) AS total_revenue
		FROM `tabSales Invoice` si
		JOIN `tabCustomer` c ON si.customer = c.name
		WHERE si.company = %s
		  AND si.posting_date BETWEEN %s AND %s
		  AND si.docstatus = 1
		GROUP BY c.customer_group
		ORDER BY total_revenue DESC
		LIMIT 5
		""",
		(company, from_date, to_date),
		as_dict=True,
	)

	return {"top_customers": customer_rows, "customer_groups": group_rows}


def get_monthly_sales_trends(company: str, from_date: str, to_date: str) -> dict:
	"""Get monthly revenue and opportunity trends."""
	revenue_rows = frappe.db.sql(
		"""
		SELECT
			CONCAT(YEAR(posting_date), "-", LPAD(MONTH(posting_date), 2, '0')) AS month,
			COUNT(name) AS invoice_count,
			SUM(base_grand_total) AS monthly_revenue
		FROM `tabSales Invoice`
		WHERE company = %s
		  AND posting_date BETWEEN %s AND %s
		  AND docstatus = 1
		GROUP BY YEAR(posting_date), MONTH(posting_date)
		ORDER BY month ASC
		""",
		(company, from_date, to_date),
		as_dict=True,
	)

	opportunity_rows = frappe.db.sql(
		"""
		SELECT
			CONCAT(YEAR(creation), "-", LPAD(MONTH(creation), 2, '0')) AS month,
			COUNT(name) AS created_opportunities,
			SUM(COALESCE(opportunity_amount, 0)) AS month_pipeline_value
		FROM `tabOpportunity`
		WHERE company = %s
		  AND creation BETWEEN %s AND %s
		GROUP BY YEAR(creation), MONTH(creation)
		ORDER BY month ASC
		""",
		(company, from_date, to_date),
		as_dict=True,
	)

	return {"monthly_revenue": revenue_rows, "monthly_opportunities": opportunity_rows}


def get_daily_sales_trends(company: str, from_date: str, to_date: str) -> dict:
	"""Get daily revenue and invoice trends."""
	revenue_rows = frappe.db.sql(
		"""
		SELECT
			posting_date AS date,
			COUNT(name) AS invoice_count,
			SUM(base_grand_total) AS daily_revenue
		FROM `tabSales Invoice`
		WHERE company = %s
		  AND posting_date BETWEEN %s AND %s
		  AND docstatus = 1
		GROUP BY posting_date
		ORDER BY posting_date ASC
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	return {"daily_revenue": revenue_rows}


def get_weekly_sales_trends(company: str, from_date: str, to_date: str) -> dict:
	"""Get weekly revenue and invoice trends."""
	revenue_rows = frappe.db.sql(
		"""
		SELECT
			CONCAT(YEAR(posting_date), "-W", LPAD(WEEK(posting_date), 2, '0')) AS week,
			MIN(posting_date) AS week_start,
			MAX(posting_date) AS week_end,
			COUNT(name) AS invoice_count,
			SUM(base_grand_total) AS weekly_revenue
		FROM `tabSales Invoice`
		WHERE company = %s
		  AND posting_date BETWEEN %s AND %s
		  AND docstatus = 1
		GROUP BY YEAR(posting_date), WEEK(posting_date)
		ORDER BY week ASC
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	return {"weekly_revenue": revenue_rows}


def get_quarterly_sales_trends(company: str, from_date: str, to_date: str) -> dict:
	"""Get quarterly revenue and invoice trends."""
	revenue_rows = frappe.db.sql(
		"""
		SELECT
			YEAR(posting_date) AS year,
			QUARTER(posting_date) AS quarter,
			CONCAT(YEAR(posting_date), "-Q", QUARTER(posting_date)) AS quarter_label,
			COUNT(name) AS invoice_count,
			SUM(base_grand_total) AS quarterly_revenue
		FROM `tabSales Invoice`
		WHERE company = %s
		  AND posting_date BETWEEN %s AND %s
		  AND docstatus = 1
		GROUP BY YEAR(posting_date), QUARTER(posting_date)
		ORDER BY year ASC, quarter ASC
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	return {"quarterly_revenue": revenue_rows}


def get_yearly_sales_trends(company: str, from_date: str, to_date: str) -> dict:
	"""Get yearly revenue and invoice trends."""
	revenue_rows = frappe.db.sql(
		"""
		SELECT
			YEAR(posting_date) AS year,
			COUNT(name) AS invoice_count,
			SUM(base_grand_total) AS yearly_revenue
		FROM `tabSales Invoice`
		WHERE company = %s
		  AND posting_date BETWEEN %s AND %s
		  AND docstatus = 1
		GROUP BY YEAR(posting_date)
		ORDER BY year ASC
		""",
		(company, from_date, to_date),
		as_dict=True,
	)
	return {"yearly_revenue": revenue_rows}


def get_partner_analytics(company: str, from_date: str, to_date: str) -> dict:
	"""Get analytics by sales partner (dealers, resellers, etc)."""
	# Note: Partner field may not be available in all Sales Invoice instances
	try:
		partner_rows = frappe.db.sql(
			"""
			SELECT
				si.partner,
				COUNT(DISTINCT si.name) AS invoice_count,
				SUM(si.base_grand_total) AS total_revenue
			FROM `tabSales Invoice` si
			WHERE si.company = %s
			  AND si.posting_date BETWEEN %s AND %s
			  AND si.docstatus = 1
			  AND si.partner IS NOT NULL
			  AND si.partner != ''
			GROUP BY si.partner
			ORDER BY total_revenue DESC
			LIMIT 5
			""",
			(company, from_date, to_date),
			as_dict=True,
		)
		return {"partners": partner_rows}
	except Exception:
		# If partner field doesn't exist, return empty
		return {"partners": []}


def _build_risk_flags(kpi: dict, monthly_revenue: list[dict]) -> list[dict]:
	risk_flags = []

	win_rate = flt(kpi.get("win_rate_percent"))
	if win_rate < 20:
		risk_flags.append(
			{
				"level": "red",
				"title": "Low Conversion Efficiency",
				"detail": f"Win rate is {win_rate:.1f}%. Review deal qualification and follow-up cadence.",
			}
		)
	elif win_rate < 35:
		risk_flags.append(
			{
				"level": "yellow",
				"title": "Moderate Conversion Efficiency",
				"detail": f"Win rate is {win_rate:.1f}%. Target late-stage opportunities with coaching.",
			}
		)
	else:
		risk_flags.append(
			{
				"level": "green",
				"title": "Healthy Conversion Efficiency",
				"detail": f"Win rate is {win_rate:.1f}%. Keep current conversion playbook and scale.",
			}
		)

	weighted_pipeline = flt(kpi.get("weighted_pipeline_value"))
	booked_revenue = flt(kpi.get("booked_revenue"))
	coverage = (weighted_pipeline / booked_revenue * 100.0) if booked_revenue else 0.0
	if coverage < 80:
		risk_flags.append(
			{
				"level": "red",
				"title": "Insufficient Weighted Coverage",
				"detail": f"Weighted pipeline is {coverage:.1f}% of booked revenue. Pipeline replenishment is urgent.",
			}
		)
	elif coverage < 120:
		risk_flags.append(
			{
				"level": "yellow",
				"title": "Tight Weighted Coverage",
				"detail": f"Weighted pipeline is {coverage:.1f}% of booked revenue. Improve top-of-funnel inflow.",
			}
		)
	else:
		risk_flags.append(
			{
				"level": "green",
				"title": "Strong Weighted Coverage",
				"detail": f"Weighted pipeline is {coverage:.1f}% of booked revenue, supporting near-term targets.",
			}
		)

	if len(monthly_revenue) >= 2:
		latest = flt(monthly_revenue[-1].get("monthly_revenue"))
		previous = flt(monthly_revenue[-2].get("monthly_revenue"))
		momentum = ((latest - previous) / previous * 100.0) if previous else 0.0
		if momentum < -10:
			risk_flags.append(
				{
					"level": "red",
					"title": "Revenue Momentum Down",
					"detail": f"Recent monthly revenue is down {abs(momentum):.1f}% versus prior month.",
				}
			)
		elif momentum < 5:
			risk_flags.append(
				{
					"level": "yellow",
					"title": "Flat Revenue Momentum",
					"detail": f"Recent monthly revenue change is {momentum:.1f}%. Drive new demand to accelerate growth.",
				}
			)
		else:
			risk_flags.append(
				{
					"level": "green",
					"title": "Positive Revenue Momentum",
					"detail": f"Recent monthly revenue is up {momentum:.1f}% versus prior month.",
				}
			)

	return risk_flags


@frappe.whitelist()
def get_ai_executive_summary_data(company: str | None = None, from_date: str | None = None, to_date: str | None = None):
	"""Return executive-level analytics payload for the AI Executive Summary page."""
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")

	kpi = get_sales_kpi_summary(company=company, from_date=from_date, to_date=to_date)
	revenue_and_pipeline_trends = get_monthly_sales_trends(
		company=kpi["company"],
		from_date=kpi["from_date"],
		to_date=kpi["to_date"],
	)

	sales_orders_count = frappe.db.count(
		"Sales Order",
		filters={
			"company": kpi["company"],
			"transaction_date": ["between", [kpi["from_date"], kpi["to_date"]]],
			"docstatus": 1,
		},
	)
	deliveries_count = frappe.db.count(
		"Delivery Note",
		filters={
			"company": kpi["company"],
			"posting_date": ["between", [kpi["from_date"], kpi["to_date"]]],
			"docstatus": 1,
		},
	)
	invoices_count = frappe.db.count(
		"Sales Invoice",
		filters={
			"company": kpi["company"],
			"posting_date": ["between", [kpi["from_date"], kpi["to_date"]]],
			"docstatus": 1,
		},
	)
	avg_invoice_value = flt(
		frappe.db.sql(
			"""
			SELECT AVG(base_grand_total)
			FROM `tabSales Invoice`
			WHERE company = %s
			  AND posting_date BETWEEN %s AND %s
			  AND docstatus = 1
			""",
			(kpi["company"], kpi["from_date"], kpi["to_date"]),
		)[0][0]
		or 0
	)
	created = frappe.db.count(
		"Opportunity",
		filters={"company": kpi["company"], "creation": ["between", [kpi["from_date"], kpi["to_date"]]]},
	)
	converted = frappe.db.count(
		"Opportunity",
		filters={
			"company": kpi["company"],
			"creation": ["between", [kpi["from_date"], kpi["to_date"]]],
			"status": ["in", ["Converted", "Quotation"]],
		},
	)
	conversion_rate = (flt(converted) / flt(created) * 100.0) if created else 0.0

	kpi.update(
		{
			"sales_orders_count": cint(sales_orders_count or 0),
			"deliveries_count": cint(deliveries_count or 0),
			"invoices_count": cint(invoices_count or 0),
			"avg_invoice_value": avg_invoice_value,
			"opportunities_created": cint(created),
			"opportunities_converted": cint(converted),
			"conversion_rate_percent": round(conversion_rate, 2),
		}
	)

	risk_flags = _build_risk_flags(kpi, revenue_and_pipeline_trends.get("monthly_revenue") or [])

	return {
		"company": kpi["company"],
		"from_date": kpi["from_date"],
		"to_date": kpi["to_date"],
		"kpis": kpi,
		"trends": revenue_and_pipeline_trends,
		"risk_flags": risk_flags,
	}


def _can_use_ai_insights() -> None:
	user_roles = set(frappe.get_roles(frappe.session.user))
	if "System Manager" in user_roles or "AI Sales Manager" in user_roles:
		return

	allow_ai_sales_user = cint(
		frappe.db.get_single_value("AI Sales AI Settings", "allow_ai_sales_user")
		or 0
	)
	if allow_ai_sales_user and "AI Sales User" in user_roles:
		return

	frappe.throw(_("You are not permitted to generate AI insights."), frappe.PermissionError)


def _get_ai_settings() -> dict:
	settings_doc = frappe.get_single("AI Sales AI Settings")
	preset = get_provider_preset(settings_doc.provider)
	api_key = settings_doc.get_password("api_key", raise_exception=False) or ""

	return {
		"enabled": cint(settings_doc.enabled),
		"provider": (settings_doc.provider or "Ollama").strip(),
		"transport": preset["transport"],
		"model": ((settings_doc.model or "").strip() or preset["model"]),
		"base_url": ((settings_doc.base_url or "").strip().rstrip("/") or preset["base_url"]),
		"api_key": api_key,
		"timeout_seconds": cint(settings_doc.timeout_seconds or preset["timeout_seconds"]),
		"max_output_tokens": cint(settings_doc.max_output_tokens or preset["max_output_tokens"]),
		"temperature": flt(settings_doc.temperature or 0.2),
		"system_prompt": settings_doc.system_prompt
		or "You are a sales analytics assistant. Keep response concise and action-oriented.",
	}


def _get_saved_provider_rows(settings_doc) -> list:
	return list(settings_doc.get("saved_providers") or [])


def _find_saved_provider(settings_doc, profile_label: str):
	label = (profile_label or "").strip()
	if not label:
		return None
	for row in _get_saved_provider_rows(settings_doc):
		if (row.profile_label or "").strip() == label:
			return row
	return None


def _serialize_saved_provider_row(row) -> dict:
	return {
		"profile_label": row.profile_label,
		"provider": row.provider,
		"model": row.model,
		"base_url": row.base_url,
		"timeout_seconds": cint(row.timeout_seconds or 0),
		"max_output_tokens": cint(row.max_output_tokens or 0),
		"temperature": flt(row.temperature or 0),
		"is_active": cint(row.is_active or 0),
	}


def _saved_provider_response(settings_doc, active_label: str | None = None) -> dict:
	profiles = [_serialize_saved_provider_row(row) for row in _get_saved_provider_rows(settings_doc)]
	return {
		"profiles": profiles,
		"active_profile": active_label,
		"count": len(profiles),
	}


@frappe.whitelist()
def get_saved_ai_provider_profiles() -> dict:
	_require_roles("AI Sales Manager")
	settings_doc = frappe.get_single("AI Sales AI Settings")
	active_row = next((row for row in _get_saved_provider_rows(settings_doc) if cint(row.is_active)), None)
	return _saved_provider_response(settings_doc, active_label=getattr(active_row, "profile_label", None))


@frappe.whitelist()
def save_current_ai_provider_profile(profile_label: str, overwrite: int | None = 1) -> dict:
	_require_roles("AI Sales Manager")
	label = (profile_label or "").strip()
	if not label:
		frappe.throw(_("Profile label is required."))

	settings_doc = frappe.get_single("AI Sales AI Settings")
	current_api_key = settings_doc.get_password("api_key", raise_exception=False) or ""
	row = _find_saved_provider(settings_doc, label)
	if row and not cint(overwrite):
		frappe.throw(_("A saved provider profile with this label already exists."))
	if not row:
		row = settings_doc.append("saved_providers", {})

	row.profile_label = label
	row.provider = settings_doc.provider
	row.model = settings_doc.model
	row.base_url = settings_doc.base_url
	row.timeout_seconds = cint(settings_doc.timeout_seconds or 0)
	row.max_output_tokens = cint(settings_doc.max_output_tokens or 0)
	row.temperature = flt(settings_doc.temperature or 0)
	row.api_key = current_api_key

	for saved_row in _get_saved_provider_rows(settings_doc):
		saved_row.is_active = 1 if saved_row == row else 0

	settings_doc.save(ignore_permissions=True)
	return {
		"message": _("Saved provider profile updated."),
		**_saved_provider_response(settings_doc, active_label=label),
	}


@frappe.whitelist()
def upsert_saved_ai_provider(
	profile_label: str,
	provider: str,
	api_key: str | None = None,
	model: str | None = None,
	base_url: str | None = None,
	timeout_seconds: int | None = None,
	max_output_tokens: int | None = None,
	temperature: float | None = None,
	mark_active: int | None = 0,
) -> dict:
	_require_roles("AI Sales Manager")
	label = (profile_label or "").strip()
	provider_name = (provider or "").strip()
	if not label or not provider_name:
		frappe.throw(_("Profile label and provider are required."))

	preset = get_provider_preset(provider_name)
	settings_doc = frappe.get_single("AI Sales AI Settings")
	row = _find_saved_provider(settings_doc, label)
	if not row:
		row = settings_doc.append("saved_providers", {})

	row.profile_label = label
	row.provider = provider_name
	row.model = (model or "").strip() or preset.get("model") or ""
	row.base_url = (base_url or "").strip().rstrip("/") or preset.get("base_url") or ""
	row.timeout_seconds = cint(timeout_seconds or preset.get("timeout_seconds") or 90)
	row.max_output_tokens = cint(max_output_tokens or preset.get("max_output_tokens") or 500)
	row.temperature = flt(temperature if temperature is not None else 0.2)
	if api_key is not None:
		row.api_key = api_key.strip()

	if cint(mark_active):
		for saved_row in _get_saved_provider_rows(settings_doc):
			saved_row.is_active = 1 if saved_row == row else 0

	settings_doc.save(ignore_permissions=True)
	return {
		"message": _("Saved provider profile stored."),
		**_saved_provider_response(settings_doc, active_label=label if cint(mark_active) else None),
	}


@frappe.whitelist()
def load_saved_ai_provider(profile_label: str) -> dict:
	_require_roles("AI Sales Manager")
	label = (profile_label or "").strip()
	if not label:
		frappe.throw(_("Profile label is required."))

	settings_doc = frappe.get_single("AI Sales AI Settings")
	row = _find_saved_provider(settings_doc, label)
	if not row:
		frappe.throw(_("Saved provider profile was not found."))

	settings_doc.provider = row.provider
	settings_doc.model = row.model
	settings_doc.base_url = row.base_url
	settings_doc.timeout_seconds = cint(row.timeout_seconds or 0)
	settings_doc.max_output_tokens = cint(row.max_output_tokens or 0)
	settings_doc.temperature = flt(row.temperature or 0)
	settings_doc.api_key = row.get_password("api_key", raise_exception=False) or ""
	settings_doc.provider_documentation_url = PROVIDER_DOCUMENTATION_URLS.get(row.provider, "")

	for saved_row in _get_saved_provider_rows(settings_doc):
		saved_row.is_active = 1 if saved_row.profile_label == label else 0

	settings_doc.save(ignore_permissions=True)
	return {
		"message": _("Saved provider profile loaded into active settings."),
		"provider": settings_doc.provider,
		"model": settings_doc.model,
		"base_url": settings_doc.base_url,
		**_saved_provider_response(settings_doc, active_label=label),
	}


@frappe.whitelist()
def delete_saved_ai_provider(profile_label: str) -> dict:
	_require_roles("AI Sales Manager")
	label = (profile_label or "").strip()
	if not label:
		frappe.throw(_("Profile label is required."))

	settings_doc = frappe.get_single("AI Sales AI Settings")
	row = _find_saved_provider(settings_doc, label)
	if not row:
		frappe.throw(_("Saved provider profile was not found."))

	settings_doc.remove(row)
	settings_doc.save(ignore_permissions=True)
	return {
		"message": _("Saved provider profile deleted."),
		**_saved_provider_response(settings_doc),
	}


@frappe.whitelist()
def test_saved_ai_provider_profiles() -> dict:
	"""Validate connectivity for each saved provider profile without changing active settings."""
	_require_roles("AI Sales Manager")
	settings_doc = frappe.get_single("AI Sales AI Settings")
	rows = _get_saved_provider_rows(settings_doc)
	results = []

	for row in rows:
		provider = (row.provider or "").strip()
		if not provider:
			results.append(
				{
					"profile_label": row.profile_label,
					"provider": provider,
					"model": row.model,
					"ok": False,
					"error": "Provider is missing.",
				}
			)
			continue

		preset = get_provider_preset(provider)
		api_key = row.get_password("api_key", raise_exception=False) or ""
		ai_settings = {
			"provider": provider,
			"transport": preset.get("transport") or "openai_compatible",
			"model": (row.model or "").strip() or preset.get("model") or "",
			"base_url": ((row.base_url or "").strip().rstrip("/") or preset.get("base_url") or ""),
			"api_key": api_key,
			"timeout_seconds": cint(row.timeout_seconds or preset.get("timeout_seconds") or 90),
			"max_output_tokens": min(cint(row.max_output_tokens or preset.get("max_output_tokens") or 120), 120),
			"temperature": flt(row.temperature if row.temperature is not None else 0.1),
			"system_prompt": DEFAULT_AI_AGENT_INSTRUCTIONS,
		}

		if ai_settings["transport"] != "statistical" and not ai_settings["base_url"]:
			results.append(
				{
					"profile_label": row.profile_label,
					"provider": provider,
					"model": ai_settings["model"],
					"ok": False,
					"error": "Base URL is missing.",
				}
			)
			continue

		try:
			preview = _call_ai_provider(
				prompt="Reply with exactly one line: OK",
				ai_settings=ai_settings,
			)
			results.append(
				{
					"profile_label": row.profile_label,
					"provider": provider,
					"model": ai_settings["model"],
					"ok": True,
					"preview": (preview or "").strip()[:140],
				}
			)
		except requests.RequestException as exc:
			results.append(
				{
					"profile_label": row.profile_label,
					"provider": provider,
					"model": ai_settings["model"],
					"ok": False,
					"error": str(exc)[:220],
				}
			)
		except Exception as exc:
			results.append(
				{
					"profile_label": row.profile_label,
					"provider": provider,
					"model": ai_settings["model"],
					"ok": False,
					"error": str(exc)[:220],
				}
			)

	ok_count = len([row for row in results if row.get("ok")])
	return {
		"checked": len(results),
		"ok_count": ok_count,
		"failed_count": len(results) - ok_count,
		"results": results,
	}


@frappe.whitelist()
def get_ai_engine_status() -> dict:
	"""Return active AI engine status for page badges."""
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
	ai_settings = _get_ai_settings()
	transport = ai_settings.get("transport") or "openai_compatible"
	provider = ai_settings.get("provider") or "Unknown"
	model = ai_settings.get("model") or "-"
	is_offline = transport in {"statistical", "ollama"}
	mode = "Offline" if is_offline else "Online"
	return {
		"provider": provider,
		"model": model,
		"transport": transport,
		"mode": mode,
		"is_offline": is_offline,
		"badge_text": f"Engine: {provider} ({mode})",
	}


def _call_openai_compatible(prompt: str, ai_settings: dict, headers: dict) -> str:
	url = f"{ai_settings['base_url']}/chat/completions"
	payload = {
		"model": ai_settings["model"],
		"messages": [
			{"role": "system", "content": ai_settings["system_prompt"]},
			{"role": "user", "content": prompt},
		],
		"temperature": ai_settings["temperature"],
		"max_tokens": ai_settings["max_output_tokens"],
	}
	response = requests.post(url, json=payload, headers=headers, timeout=ai_settings["timeout_seconds"])
	response.raise_for_status()
	data = response.json() or {}
	choices = data.get("choices") or []
	if not choices:
		frappe.throw(_("AI provider returned no choices."))
	content = ((choices[0] or {}).get("message") or {}).get("content")
	if isinstance(content, list):
		content = "\n".join(
			item.get("text", "") if isinstance(item, dict) else str(item) for item in content
		).strip()
	if not content:
		frappe.throw(_("AI provider returned an empty response."))
	return content.strip()


def _call_anthropic(prompt: str, ai_settings: dict) -> str:
	headers = {
		"Content-Type": "application/json",
		"x-api-key": ai_settings["api_key"],
		"anthropic-version": "2023-06-01",
	}
	url = f"{ai_settings['base_url']}/messages"
	payload = {
		"model": ai_settings["model"],
		"system": ai_settings["system_prompt"],
		"messages": [{"role": "user", "content": prompt}],
		"temperature": ai_settings["temperature"],
		"max_tokens": ai_settings["max_output_tokens"],
	}
	response = requests.post(url, json=payload, headers=headers, timeout=ai_settings["timeout_seconds"])
	response.raise_for_status()
	data = response.json() or {}
	content = data.get("content") or []
	text_chunks = [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"]
	result = "\n".join(chunk for chunk in text_chunks if chunk).strip()
	if not result:
		frappe.throw(_("AI provider returned an empty response."))
	return result


def _call_gemini(prompt: str, ai_settings: dict) -> str:
	if not ai_settings.get("api_key"):
		frappe.throw(_("Please set API Key in AI Sales AI Settings for Gemini."))

	base_url = (ai_settings.get("base_url") or "").rstrip("/")
	model = ai_settings.get("model") or "gemini-2.0-flash"
	url = f"{base_url}/models/{model}:generateContent"
	headers = {
		"Content-Type": "application/json",
		"X-goog-api-key": ai_settings["api_key"],
	}
	payload = {
		"contents": [{"role": "user", "parts": [{"text": prompt}]}],
		"systemInstruction": {"parts": [{"text": ai_settings["system_prompt"]}]},
		"generationConfig": {
			"temperature": ai_settings["temperature"],
			"maxOutputTokens": ai_settings["max_output_tokens"],
		},
	}

	response = requests.post(
		url,
		json=payload,
		headers=headers,
		timeout=ai_settings["timeout_seconds"],
	)
	response.raise_for_status()
	data = response.json() or {}

	candidates = data.get("candidates") or []
	if not candidates:
		frappe.throw(_("Gemini returned no candidates."))

	parts = ((candidates[0] or {}).get("content") or {}).get("parts") or []
	text = "\n".join((part or {}).get("text", "") for part in parts if isinstance(part, dict)).strip()
	if not text:
		frappe.throw(_("Gemini returned an empty response."))
	return text


def _call_huggingface(prompt: str, ai_settings: dict) -> str:
	if not ai_settings.get("api_key"):
		frappe.throw(_("Please set API Key in AI Sales AI Settings for Hugging Face."))

	base_url = (ai_settings.get("base_url") or "").rstrip("/")
	model = ai_settings.get("model") or "meta-llama/Llama-3.1-8B-Instruct"
	url = f"{base_url}/models/{model}"
	headers = {
		"Content-Type": "application/json",
		"Authorization": f"Bearer {ai_settings['api_key']}",
	}
	payload = {
		"inputs": f"{ai_settings['system_prompt']}\n\n{prompt}",
		"parameters": {
			"max_new_tokens": ai_settings["max_output_tokens"],
			"temperature": ai_settings["temperature"],
		},
	}

	response = requests.post(url, json=payload, headers=headers, timeout=ai_settings["timeout_seconds"])
	response.raise_for_status()
	data = response.json()

	if isinstance(data, dict) and data.get("error"):
		frappe.throw(_("Hugging Face API error: {0}").format(data.get("error")))

	if isinstance(data, list) and data:
		first = data[0]
		if isinstance(first, dict):
			text = (first.get("generated_text") or first.get("summary_text") or "").strip()
			if text:
				return text
		elif isinstance(first, str) and first.strip():
			return first.strip()

	if isinstance(data, dict):
		text = (data.get("generated_text") or data.get("summary_text") or "").strip()
		if text:
			return text

	frappe.throw(_("Hugging Face returned an empty response."))


def _strip_reasoning_tags(text: str) -> str:
	"""Remove <think>...</think> reasoning blocks emitted by DeepSeek-R1 and similar models."""
	import re
	cleaned = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
	return cleaned.strip()


def _call_ai_provider(prompt: str, ai_settings: dict) -> str:
	provider = ai_settings["provider"].lower()
	transport = ai_settings.get("transport") or provider
	if transport == "statistical":
		frappe.throw(_("Statistical Engine is local-only. Use statistical helpers instead of external provider calls."))

	headers = {"Content-Type": "application/json"}
	if ai_settings["api_key"]:
		headers["Authorization"] = f"Bearer {ai_settings['api_key']}"

	if transport == "ollama":
		url = f"{ai_settings['base_url']}/api/chat"
		payload = {
			"model": ai_settings["model"],
			"stream": False,
			"messages": [
				{"role": "system", "content": ai_settings["system_prompt"]},
				{"role": "user", "content": prompt},
			],
			"options": {
				"temperature": ai_settings["temperature"],
				"num_predict": ai_settings["max_output_tokens"],
			},
		}
		response = requests.post(url, json=payload, headers=headers, timeout=ai_settings["timeout_seconds"])
		response.raise_for_status()
		data = response.json() or {}
		content = (data.get("message") or {}).get("content")
		if not content:
			frappe.throw(_("AI provider returned an empty response."))
		return _strip_reasoning_tags(content)

	if transport == "openai_compatible":
		return _call_openai_compatible(prompt=prompt, ai_settings=ai_settings, headers=headers)

	if transport == "anthropic":
		if not ai_settings["api_key"]:
			frappe.throw(_("Please set API Key in AI Sales AI Settings for Claude."))
		return _call_anthropic(prompt=prompt, ai_settings=ai_settings)

	if transport == "gemini":
		return _call_gemini(prompt=prompt, ai_settings=ai_settings)

	if transport == "huggingface":
		return _call_huggingface(prompt=prompt, ai_settings=ai_settings)

	frappe.throw(_("Unsupported AI provider in AI Sales AI Settings."))


@frappe.whitelist()
def get_ai_provider_profiles() -> dict:
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
	return get_provider_catalog()


def _build_ai_agent_context(company: str | None = None, from_date: str | None = None, to_date: str | None = None) -> dict:
	kpi = get_sales_kpi_summary(company=company, from_date=from_date, to_date=to_date)
	trends = get_monthly_sales_trends(company=kpi["company"], from_date=kpi["from_date"], to_date=kpi["to_date"])
	customer_data = get_customer_analytics(company=kpi["company"], from_date=kpi["from_date"], to_date=kpi["to_date"])
	risk_flags = _build_risk_flags(kpi, trends.get("monthly_revenue") or [])

	return {
		"company": kpi["company"],
		"from_date": kpi["from_date"],
		"to_date": kpi["to_date"],
		"kpi": kpi,
		"trends": trends,
		"top_customers": (customer_data.get("top_customers") or [])[:10],
		"risk_flags": risk_flags,
	}


def _format_ai_rows(rows: list[dict] | None, max_rows: int = 2, max_fields: int = 3) -> str:
	formatted_rows = []
	for row in (rows or [])[:max_rows]:
		parts = []
		for index, (key, value) in enumerate((row or {}).items()):
			if index >= max_fields:
				break
			if value in (None, "", []):
				continue
			parts.append(f"{key}={value}")
		if parts:
			formatted_rows.append("- " + ", ".join(parts))
	return "\n".join(formatted_rows) or "- No data available"


def _build_ai_agent_prompt(message: str, context: dict, include_context: bool, conversation: list[dict] | None = None) -> str:
	parts = []
	if conversation:
		transcript_lines = []
		for entry in conversation[-6:]:
			role = (entry.get("role") or "user").strip().upper()
			text = (entry.get("text") or "").strip()
			if text:
				transcript_lines.append(f"{role}: {text}")
		if transcript_lines:
			transcript_text = "\n".join(transcript_lines)
			parts.append(f"RECENT CONVERSATION:\n{transcript_text}\n")

	parts.append(f"USER QUESTION:\n{message.strip()}\n")
	if include_context:
		kpi = context["kpi"]
		risk_text = "\n".join(
			f"- {risk.get('title')}: {risk.get('detail')}" for risk in (context.get("risk_flags") or [])[:3]
		) or "- No risk flags available"
		revenue_rows = context["trends"].get("monthly_revenue") or []
		revenue_text = "\n".join(
			f"- {row.get('month')}: revenue={row.get('monthly_revenue')}, invoices={row.get('invoice_count')}"
			for row in revenue_rows[-4:]
		) or "- No monthly revenue trend available"
		parts.extend(
			[
				f"COMPANY: {context['company']}",
				f"PERIOD: {context['from_date']} to {context['to_date']}\n",
				(
					"KPI SUMMARY:\n"
					f"- Open Opportunities: {kpi.get('open_opportunities')}\n"
					f"- Pipeline Value: {kpi.get('pipeline_value')}\n"
					f"- Weighted Pipeline Value: {kpi.get('weighted_pipeline_value')}\n"
					f"- Win Rate: {kpi.get('win_rate_percent')}%\n"
					f"- Booked Revenue: {kpi.get('booked_revenue')}\n"
				),
				f"RISK FLAGS:\n{risk_text}\n",
				f"MONTHLY REVENUE TREND:\n{revenue_text}\n",
				f"TOP CUSTOMERS:\n{_format_ai_rows(context['top_customers'])}\n",
			]
		)

	parts.append(
		"RESPONSE RULES:\n"
		"- Use only the supplied ERPNext sales context.\n"
		"- If data is missing, say exactly what is missing.\n"
		"- Give concrete managerial guidance, not generic AI filler.\n"
		"- Prefer short sections and bullets when the answer is operational."
	)
	return "\n".join(parts)


def _user_can_access_session(session_doc) -> bool:
	if not session_doc:
		return False
	user_roles = set(frappe.get_roles(frappe.session.user))
	if "System Manager" in user_roles or "AI Sales Manager" in user_roles:
		return True
	return session_doc.user == frappe.session.user


def _parse_conversation_json(conversation: str | None) -> list[dict]:
	if not conversation:
		return []
	try:
		rows = frappe.parse_json(conversation)
		return rows if isinstance(rows, list) else []
	except Exception:
		try:
			rows = json.loads(conversation)
			return rows if isinstance(rows, list) else []
		except Exception:
			return []


def _create_chat_session_doc(
	title: str,
	company: str | None,
	from_date: str | None,
	to_date: str | None,
	provider: str | None,
	model: str | None,
) -> str:
	doc = frappe.get_doc(
		{
			"doctype": "AI Chat Session",
			"title": (title or "New AI Chat").strip()[:140] or "New AI Chat",
			"status": "Active",
			"user": frappe.session.user,
			"company": company,
			"from_date": from_date,
			"to_date": to_date,
			"provider": provider,
			"model": model,
			"last_activity": now_datetime(),
		}
	)
	doc.insert(ignore_permissions=True)
	return doc.name


def _append_chat_message(
	session_name: str,
	role: str,
	message_text: str,
	provider: str | None = None,
	model: str | None = None,
) -> None:
	doc = frappe.get_doc("AI Chat Session", session_name)
	if not _user_can_access_session(doc):
		frappe.throw(_("Not permitted to access this chat session."), frappe.PermissionError)
	doc.append(
		"messages",
		{
			"role": (role or "user").strip().lower(),
			"message_time": now_datetime(),
			"provider": provider,
			"model": model,
			"message_text": message_text,
		},
	)
	doc.last_activity = now_datetime()
	if provider:
		doc.provider = provider
	if model:
		doc.model = model
	doc.save(ignore_permissions=True)


def _save_chat_exchange(
	session_name: str | None,
	message: str,
	answer: str,
	company: str | None,
	from_date: str | None,
	to_date: str | None,
	provider: str | None,
	model: str | None,
) -> str:
	active_session = session_name
	if active_session:
		doc = frappe.get_doc("AI Chat Session", active_session)
		if not _user_can_access_session(doc):
			frappe.throw(_("Not permitted to access this chat session."), frappe.PermissionError)
	else:
		title = (message or "New AI Chat").strip().split("\n")[0][:140] or "New AI Chat"
		active_session = _create_chat_session_doc(
			title=title,
			company=company,
			from_date=from_date,
			to_date=to_date,
			provider=provider,
			model=model,
		)

	_append_chat_message(active_session, "user", message, provider=provider, model=model)
	_append_chat_message(active_session, "assistant", answer, provider=provider, model=model)
	return active_session


@frappe.whitelist()
def create_ai_chat_session(
	title: str | None = None,
	company: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
) -> dict:
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
	ai_settings = _get_ai_settings()
	name = _create_chat_session_doc(
		title=title or "New AI Chat",
		company=company,
		from_date=from_date,
		to_date=to_date,
		provider=ai_settings.get("provider"),
		model=ai_settings.get("model"),
	)
	return {"session_name": name}


@frappe.whitelist()
def list_ai_chat_sessions(limit: int = 50, status: str | None = None) -> dict:
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
	user_roles = set(frappe.get_roles(frappe.session.user))
	filters = {}
	if "System Manager" not in user_roles and "AI Sales Manager" not in user_roles:
		filters["user"] = frappe.session.user
	if status:
		filters["status"] = status

	rows = frappe.get_all(
		"AI Chat Session",
		filters=filters,
		fields=["name", "title", "company", "from_date", "to_date", "provider", "model", "last_activity", "status"],
		order_by="last_activity desc",
		limit_page_length=max(1, min(cint(limit), 200)),
	)
	return {"sessions": rows}


@frappe.whitelist()
def get_ai_chat_session(session_name: str) -> dict:
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
	if not session_name:
		frappe.throw(_("Session name is required."))

	doc = frappe.get_doc("AI Chat Session", session_name)
	if not _user_can_access_session(doc):
		frappe.throw(_("Not permitted to access this chat session."), frappe.PermissionError)

	messages = []
	for row in doc.messages or []:
		messages.append(
			{
				"role": row.role,
				"text": row.message_text,
				"message_time": row.message_time,
				"provider": row.provider,
				"model": row.model,
			}
		)

	return {
		"session": {
			"name": doc.name,
			"title": doc.title,
			"company": doc.company,
			"from_date": doc.from_date,
			"to_date": doc.to_date,
			"provider": doc.provider,
			"model": doc.model,
			"last_activity": doc.last_activity,
			"status": doc.status,
			"messages": messages,
		}
	}


@frappe.whitelist()
def archive_ai_chat_session(session_name: str) -> dict:
	"""Archive (soft-delete) a chat session. Only owners or managers can archive."""
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
	if not session_name:
		frappe.throw(_("Session name is required."))

	doc = frappe.get_doc("AI Chat Session", session_name)
	if not _user_can_access_session(doc):
		frappe.throw(_("Not permitted to archive this chat session."), frappe.PermissionError)

	doc.status = "Archived"
	doc.save(ignore_permissions=True)
	return {"session_name": session_name, "status": "Archived", "message": "Session archived."}


@frappe.whitelist()
def delete_ai_chat_session(session_name: str) -> dict:
	"""Permanently delete a chat session. Only owners or managers can delete."""
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
	if not session_name:
		frappe.throw(_("Session name is required."))

	doc = frappe.get_doc("AI Chat Session", session_name)
	if not _user_can_access_session(doc):
		frappe.throw(_("Not permitted to delete this chat session."), frappe.PermissionError)

	doc.delete(ignore_permissions=True)
	return {"session_name": session_name, "message": "Session deleted permanently."}


@frappe.whitelist()
def test_ai_provider_connection(
	provider: str | None = None,
	model: str | None = None,
	base_url: str | None = None,
	api_key: str | None = None,
	timeout_seconds: int | None = None,
	max_output_tokens: int | None = None,
	temperature: float | None = None,
) -> dict:
	_require_roles("AI Sales Manager", "Sales Manager")

	ai_settings = _get_ai_settings()
	if provider is not None:
		preset = get_provider_preset(provider)
		ai_settings.update(
			{
				"provider": provider.strip(),
				"transport": preset["transport"],
				"model": (model or "").strip() or preset["model"],
				"base_url": (base_url or "").strip().rstrip("/") or preset["base_url"],
				"api_key": api_key or ai_settings["api_key"],
				"timeout_seconds": cint(timeout_seconds or preset["timeout_seconds"]),
				"max_output_tokens": cint(max_output_tokens or min(preset["max_output_tokens"], 120)),
				"temperature": flt(temperature if temperature is not None else 0.1),
				"system_prompt": DEFAULT_AI_AGENT_INSTRUCTIONS,
			}
		)

	if not ai_settings["base_url"] or not ai_settings["model"]:
		frappe.throw(_("Base URL and Model are required to test the AI provider."))
	if ai_settings.get("transport") == "statistical":
		return {
			"ok": True,
			"provider": ai_settings["provider"],
			"model": ai_settings["model"],
			"base_url": ai_settings["base_url"],
			"preview": "Statistical Engine is ready (offline OLS + rule-based insights).",
		}

	try:
		preview = _call_ai_provider(
			prompt="Reply with exactly one short line that says the connection is working for AI Sales Dashboard.",
			ai_settings=ai_settings,
		)
	except requests.RequestException as exc:
		frappe.log_error(title="AI Provider Connection Test Failed", message=frappe.get_traceback())
		status_code = None
		reason_hint = ""
		if isinstance(exc, requests.HTTPError) and getattr(exc, "response", None) is not None:
			status_code = exc.response.status_code
			if status_code == 401:
				reason_hint = _("Unauthorized (401): API key is invalid, expired, or not permitted.")
			elif status_code == 403:
				reason_hint = _("Forbidden (403): API key lacks required permissions for this model.")
			elif status_code == 404:
				reason_hint = _("Not Found (404): Base URL or model path is incorrect for this provider.")
			elif status_code == 429:
				reason_hint = _("Rate limited (429): quota exceeded or too many requests. Retry later.")
			elif status_code and status_code >= 500:
				reason_hint = _("Provider server error ({0}). Retry shortly.", [status_code])

		if status_code:
			provider_name = ai_settings.get("provider") or "Unknown"
			detail = reason_hint or _("Check Base URL, API key, model, and network access.")
			frappe.throw(_(f"Could not reach AI provider {provider_name}. HTTP {status_code}. {detail}"))

		provider_name = ai_settings.get("provider") or "Unknown"
		frappe.throw(_(f"Could not reach AI provider {provider_name}. Verify Base URL, API key, model, and network access."))
	except Exception:
		frappe.log_error(title="AI Provider Connection Test Failed", message=frappe.get_traceback())
		frappe.throw(_("The AI provider responded with an error. Check model name, credentials, and server logs."))

	return {
		"ok": True,
		"provider": ai_settings["provider"],
		"model": ai_settings["model"],
		"base_url": ai_settings["base_url"],
		"preview": preview,
	}


@frappe.whitelist()
def chat_with_ai_sales_agent(
	message: str,
	company: str | None = None,
	from_date: str | None = None,
	to_date: str | None = None,
	include_context: int | None = 1,
	conversation: str | None = None,
	session_name: str | None = None,
) -> dict:
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
	if not (message or "").strip():
		frappe.throw(_("Please enter a message for the AI sales agent."))

	ai_settings = _get_ai_settings()
	if not ai_settings["enabled"]:
		frappe.throw(_("AI insights are disabled in AI Sales AI Settings."))
	if not ai_settings["model"]:
		frappe.throw(_("Please set Base URL and Model in AI Sales AI Settings."))
	if ai_settings.get("transport") != "statistical" and not ai_settings["base_url"]:
		frappe.throw(_("Please set Base URL and Model in AI Sales AI Settings."))

	context = _build_ai_agent_context(company=company, from_date=from_date, to_date=to_date)
	conversation_rows = _parse_conversation_json(conversation)
	prompt = _build_ai_agent_prompt(
		message=message,
		context=context,
		include_context=bool(cint(include_context)),
		conversation=conversation_rows,
	)
	request_settings = {
		**ai_settings,
		"system_prompt": DEFAULT_AI_AGENT_INSTRUCTIONS,
		"timeout_seconds": min(cint(ai_settings.get("timeout_seconds") or 90), 180),
		"max_output_tokens": min(cint(ai_settings.get("max_output_tokens") or 512), 600),
	}

	# Deterministic guardrail for fact-based KPI queries across all providers.
	direct_answer = _try_direct_query_answer(message, context) if bool(cint(include_context)) else None
	if direct_answer:
		active_session = _save_chat_exchange(
			session_name=session_name,
			message=message,
			answer=direct_answer,
			company=context["company"],
			from_date=context["from_date"],
			to_date=context["to_date"],
			provider="Deterministic KPI Engine",
			model="erpnext-direct-qa-v1",
		)
		return {
			"answer": direct_answer,
			"company": context["company"],
			"from_date": context["from_date"],
			"to_date": context["to_date"],
			"provider": "Deterministic KPI Engine",
			"model": "erpnext-direct-qa-v1",
			"risk_flags": context["risk_flags"],
			"kpi": context["kpi"],
			"forecast": [],
			"fallback_used": False,
			"deterministic_used": True,
			"session_name": active_session,
		}

	if ai_settings.get("transport") == "statistical":
		# Fall back to full statistical summary for analytical questions
		stat_out = _build_statistical_engine_output(context, user_question=message)
		active_session = _save_chat_exchange(
			session_name=session_name,
			message=message,
			answer=stat_out["summary_text"],
			company=context["company"],
			from_date=context["from_date"],
			to_date=context["to_date"],
			provider="Statistical Engine",
			model=stat_out["engine"],
		)
		return {
			"answer": stat_out["summary_text"],
			"company": context["company"],
			"from_date": context["from_date"],
			"to_date": context["to_date"],
			"provider": "Statistical Engine",
			"model": stat_out["engine"],
			"risk_flags": context["risk_flags"],
			"kpi": context["kpi"],
			"forecast": stat_out["forecast"],
			"fallback_used": False,
			"session_name": active_session,
		}

	try:
		answer = _call_ai_provider(prompt=prompt, ai_settings=request_settings)
	except requests.RequestException:
		frappe.log_error(title="AI Sales Agent Provider Error", message=frappe.get_traceback())
		stat_out = _build_statistical_engine_output(context, user_question=message)
		answer = (
			"[Fallback: Statistical Engine]\n\n"
			+ stat_out["summary_text"]
		)
		active_session = _save_chat_exchange(
			session_name=session_name,
			message=message,
			answer=answer,
			company=context["company"],
			from_date=context["from_date"],
			to_date=context["to_date"],
			provider=ai_settings["provider"],
			model=ai_settings["model"],
		)
		return {
			"answer": answer,
			"company": context["company"],
			"from_date": context["from_date"],
			"to_date": context["to_date"],
			"provider": ai_settings["provider"],
			"model": ai_settings["model"],
			"risk_flags": context["risk_flags"],
			"kpi": context["kpi"],
			"forecast": stat_out["forecast"],
			"fallback_used": True,
			"session_name": active_session,
		}
	except Exception:
		frappe.log_error(title="AI Sales Agent Failed", message=frappe.get_traceback())
		frappe.throw(_("Failed to generate AI agent response. Please review AI settings and server logs."))

	active_session = _save_chat_exchange(
		session_name=session_name,
		message=message,
		answer=answer,
		company=context["company"],
		from_date=context["from_date"],
		to_date=context["to_date"],
		provider=ai_settings["provider"],
		model=ai_settings["model"],
	)

	return {
		"answer": answer,
		"company": context["company"],
		"from_date": context["from_date"],
		"to_date": context["to_date"],
		"provider": ai_settings["provider"],
		"model": ai_settings["model"],
		"risk_flags": context["risk_flags"],
		"kpi": context["kpi"],
		"fallback_used": False,
		"session_name": active_session,
	}


@frappe.whitelist()
def get_statistical_engine_summary(company: str | None = None, from_date: str | None = None, to_date: str | None = None) -> dict:
	"""Offline statistical sales insight engine (OLS + rules), no external API calls."""
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
	context = _build_ai_agent_context(company=company, from_date=from_date, to_date=to_date)
	stat_out = _build_statistical_engine_output(context)
	return {
		"company": context["company"],
		"from_date": context["from_date"],
		"to_date": context["to_date"],
		"engine": stat_out["engine"],
		"summary": stat_out["summary_text"],
		"forecast": stat_out["forecast"],
		"kpi": context["kpi"],
		"risk_flags": context["risk_flags"],
	}


@frappe.whitelist()
def get_ai_sales_summary(company: str | None = None, from_date: str | None = None, to_date: str | None = None):
	"""Generate AI summary from KPI metrics for selected period."""
	_can_use_ai_insights()

	ai_settings = _get_ai_settings()
	if not ai_settings["enabled"]:
		frappe.throw(_("AI insights are disabled in AI Sales AI Settings."))
	if not ai_settings["model"]:
		frappe.throw(_("Please set Base URL and Model in AI Sales AI Settings."))
	if ai_settings.get("transport") != "statistical" and not ai_settings["base_url"]:
		frappe.throw(_("Please set Base URL and Model in AI Sales AI Settings."))

	kpi = get_sales_kpi_summary(company=company, from_date=from_date, to_date=to_date)
	pipeline = get_pipeline_breakdown(company=kpi["company"], group_by="status")
	pipeline_rows = pipeline.get("rows") or []
	top_rows = pipeline_rows[:5]

	# Collect extended analytics for comprehensive AI analysis
	territory_data = get_territory_breakdown(company=kpi["company"], from_date=kpi["from_date"], to_date=kpi["to_date"])
	salesperson_data = get_salesperson_breakdown(company=kpi["company"], from_date=kpi["from_date"], to_date=kpi["to_date"])
	item_data = get_item_analytics(company=kpi["company"], from_date=kpi["from_date"], to_date=kpi["to_date"])
	customer_data = get_customer_analytics(company=kpi["company"], from_date=kpi["from_date"], to_date=kpi["to_date"])
	trends_data = get_monthly_sales_trends(company=kpi["company"], from_date=kpi["from_date"], to_date=kpi["to_date"])

	# Build comprehensive prompt with all analytics dimensions
	prompt = (
		"Analyze this comprehensive sales analytics snapshot and provide actionable business insights. "
		"Return exactly three sections with markdown headings: Summary, Risks, Recommended Actions.\n\n"
		f"PERIOD: {kpi['from_date']} to {kpi['to_date']}\n"
		f"COMPANY: {kpi['company']}\n\n"
		f"KPI SUMMARY:\n"
		f"  Open Opportunities: {kpi['open_opportunities']}\n"
		f"  Pipeline Value: ${kpi['pipeline_value']:.2f}\n"
		f"  Weighted Pipeline Value: ${kpi['weighted_pipeline_value']:.2f}\n"
		f"  Win Rate: {kpi['win_rate_percent']:.2f}%\n"
		f"  Booked Revenue: ${kpi['booked_revenue']:.2f}\n\n"
		f"PIPELINE BY STATUS:\n{frappe.as_json(top_rows)}\n\n"
		f"TERRITORY BREAKDOWN (Top 5):\n{frappe.as_json(territory_data['territory_breakdown'])}\n\n"
		f"SALESPERSON BREAKDOWN (Top 5):\n{frappe.as_json(salesperson_data['salesperson_breakdown'])}\n\n"
		f"TOP ITEMS (Top 5):\n{frappe.as_json(item_data['top_items'])}\n\n"
		f"ITEM GROUPS (Top 5):\n{frappe.as_json(item_data['item_groups'])}\n\n"
		f"TOP CUSTOMERS (Top 5):\n{frappe.as_json(customer_data['top_customers'])}\n\n"
		f"CUSTOMER GROUPS (Top 5):\n{frappe.as_json(customer_data['customer_groups'])}\n\n"
		f"MONTHLY REVENUE TREND:\n{frappe.as_json(trends_data['monthly_revenue'])}\n\n"
		f"MONTHLY OPPORTUNITY CREATION:\n{frappe.as_json(trends_data['monthly_opportunities'])}\n"
	)
	if ai_settings.get("transport") == "statistical":
		context = {
			"company": kpi["company"],
			"from_date": kpi["from_date"],
			"to_date": kpi["to_date"],
			"kpi": kpi,
			"trends": trends_data,
			"top_customers": (customer_data.get("top_customers") or [])[:2],
			"risk_flags": _build_risk_flags(kpi, trends_data.get("monthly_revenue") or []),
		}
		stat_out = _build_statistical_engine_output(context)
		return {
			"company": kpi["company"],
			"from_date": kpi["from_date"],
			"to_date": kpi["to_date"],
			"summary": stat_out["summary_text"],
			"provider": "Statistical Engine",
			"model": stat_out["engine"],
			"engine": stat_out["engine"],
			"forecast": stat_out["forecast"],
			"fallback_used": False,
		}

	request_settings = {
		**ai_settings,
		"timeout_seconds": min(cint(ai_settings.get("timeout_seconds") or 90), 90),
		"max_output_tokens": min(cint(ai_settings.get("max_output_tokens") or 280), 280),
	}

	try:
		summary = _call_ai_provider(prompt=prompt, ai_settings=request_settings)
	except requests.RequestException:
		frappe.log_error(
			title="AI Sales Dashboard Provider Error",
			message=frappe.get_traceback(),
		)
		context = {
			"company": kpi["company"],
			"from_date": kpi["from_date"],
			"to_date": kpi["to_date"],
			"kpi": kpi,
			"trends": trends_data,
			"top_customers": (customer_data.get("top_customers") or [])[:2],
			"risk_flags": _build_risk_flags(kpi, trends_data.get("monthly_revenue") or []),
		}
		stat_out = _build_statistical_engine_output(context)
		summary = "[Fallback: Statistical Engine]\n\n" + stat_out["summary_text"]
		return {
			"company": kpi["company"],
			"from_date": kpi["from_date"],
			"to_date": kpi["to_date"],
			"summary": summary,
			"provider": ai_settings["provider"],
			"model": ai_settings["model"],
			"engine": ai_settings["provider"],
			"forecast": stat_out["forecast"],
			"fallback_used": True,
		}
	except Exception:
		frappe.log_error(
			title="AI Sales Dashboard AI Summary Failed",
			message=frappe.get_traceback(),
		)
		frappe.throw(_("Failed to generate AI summary. Please review AI settings and server logs."))

	return {
		"company": kpi["company"],
		"from_date": kpi["from_date"],
		"to_date": kpi["to_date"],
		"summary": summary,
		"provider": ai_settings["provider"],
		"model": ai_settings["model"],
		"fallback_used": False,
	}


@frappe.whitelist()
def sync_ai_sales_workspace_items():
	"""Ensure AI Sales Dashboard workspace has expected shortcuts and links."""
	_require_roles("AI Sales Manager")
	workspace_name = "AI Sales Dashboard"

	# Normalize previously saved page links that used titles instead of page routes.
	page_route_map = {
		"AI Executive Summary": "ai-executive-summary",
		"AI Sales Agent": "ai-sales-agent",
		"AI Chatbot": "ai-chatbot",
	}
	for old_link, new_link in page_route_map.items():
		frappe.db.sql(
			"""
			UPDATE `tabWorkspace Shortcut`
			SET link_to = %s
			WHERE parent = %s
			  AND parenttype = 'Workspace'
			  AND parentfield = 'shortcuts'
			  AND type = 'Page'
			  AND link_to = %s
			""",
			(new_link, workspace_name, old_link),
		)
		frappe.db.sql(
			"""
			UPDATE `tabWorkspace Link`
			SET link_to = %s
			WHERE parent = %s
			  AND parenttype = 'Workspace'
			  AND parentfield = 'links'
			  AND link_type = 'Page'
			  AND link_to = %s
			""",
			(new_link, workspace_name, old_link),
		)

	# Ensure Single DocTypes open in Form view (list view causes reportview/get_count errors).
	frappe.db.sql(
		"""
		UPDATE `tabWorkspace Shortcut`
		SET doc_view = 'Form'
		WHERE parent = %s
		  AND parenttype = 'Workspace'
		  AND parentfield = 'shortcuts'
		  AND type = 'DocType'
		  AND link_to IN ('AI Sales Dashboard Settings', 'AI Sales AI Settings')
		""",
		(workspace_name,),
	)

	# Single DocTypes should not be present in Workspace Link cards.
	# Link cards trigger list/count RPCs that fail for Singles (no tab table exists).
	frappe.db.sql(
		"""
		DELETE FROM `tabWorkspace Link`
		WHERE parent = %s
		  AND parenttype = 'Workspace'
		  AND parentfield = 'links'
		  AND link_type = 'DocType'
		  AND link_to IN ('AI Sales Dashboard Settings', 'AI Sales AI Settings')
		""",
		(workspace_name,),
	)

	# Existing settings shortcuts may still be DocType entries; normalize them to URL shortcuts.
	frappe.db.sql(
		"""
		UPDATE `tabWorkspace Shortcut`
		SET type = 'URL',
			url = '/app/ai-sales-dashboard-settings',
			link_to = NULL,
			doc_view = NULL
		WHERE parent = %s
		  AND parenttype = 'Workspace'
		  AND parentfield = 'shortcuts'
		  AND label = 'AI Sales Dashboard Settings'
		""",
		(workspace_name,),
	)
	frappe.db.sql(
		"""
		UPDATE `tabWorkspace Shortcut`
		SET type = 'URL',
			url = '/app/ai-sales-ai-settings',
			link_to = NULL,
			doc_view = NULL
		WHERE parent = %s
		  AND parenttype = 'Workspace'
		  AND parentfield = 'shortcuts'
		  AND label = 'AI Sales AI Settings'
		""",
		(workspace_name,),
	)

	expected_shortcuts = [
		("Sales KPI Snapshot", "Sales KPI Snapshot", "DocType", "", ""),
		("AI Chat Session", "AI Chat Session", "DocType", "", ""),
		("AI Sales Dashboard Settings", "", "URL", "", "/app/ai-sales-dashboard-settings"),
		("AI Sales AI Settings", "", "URL", "", "/app/ai-sales-ai-settings"),
		("AI Executive Summary", "ai-executive-summary", "Page", "", ""),
		("AI Sales Agent", "ai-sales-agent", "Page", "", ""),
		("AI Chatbot", "ai-chatbot", "Page", "", ""),
		("Pipeline Health Report", "Pipeline Health Report", "Report", "Report", ""),
		("Forecast vs Actual Report", "Forecast vs Actual Report", "Report", "Report", ""),
		("Conversion Funnel Report", "Conversion Funnel Report", "Report", "Report", ""),
		("Sales Analytics", "Sales Analytics", "Report", "Report", ""),
		("Territory-wise Sales", "Territory-wise Sales", "Report", "Report", ""),
		("Sales Person-wise Transaction Summary", "Sales Person-wise Transaction Summary", "Report", "Report", ""),
		("Item-wise Sales History", "Item-wise Sales History", "Report", "Report", ""),
		("Customer Acquisition and Loyalty", "Customer Acquisition and Loyalty", "Report", "Report", ""),
		("Sales Order Trends", "Sales Order Trends", "Report", "Report", ""),
		("Sales Invoice Trends", "Sales Invoice Trends", "Report", "Report", ""),
		("Customer Group-wise Sales", "Customer Group-wise Sales", "Report", "Report", ""),
		("AI Sales KPI Trends Report", "AI Sales KPI Trends Report", "Report", "Report", ""),
		("Item Group-wise Sales", "Item Group-wise Sales", "Report", "Report", ""),
	]

	existing_shortcuts = {
		(row.label, row.type)
		for row in frappe.get_all(
			"Workspace Shortcut",
			filters={"parent": workspace_name, "parenttype": "Workspace", "parentfield": "shortcuts"},
			fields=["label", "type"],
		)
	}
	added_shortcuts = []
	shortcut_idx = (
		frappe.db.sql(
			"""
			SELECT COALESCE(MAX(idx), 0) AS max_idx
			FROM `tabWorkspace Shortcut`
			WHERE parent = %s AND parenttype = 'Workspace' AND parentfield = 'shortcuts'
			""",
			(workspace_name,),
			as_dict=True,
		)[0].max_idx
		or 0
	)
	for label, link_to, row_type, doc_view, shortcut_url in expected_shortcuts:
		if (label, row_type) in existing_shortcuts:
			continue
		shortcut_idx += 1
		doc = frappe.get_doc(
			{
				"doctype": "Workspace Shortcut",
				"parent": workspace_name,
				"parenttype": "Workspace",
				"parentfield": "shortcuts",
				"idx": shortcut_idx,
				"label": label,
				"link_to": link_to or "",
				"url": shortcut_url or "",
				"type": row_type,
				"doc_view": doc_view,
				"stats_filter": "[]",
			}
		)
		doc.db_insert()
		added_shortcuts.append(label)

	expected_links = [
		("Sales KPI Snapshot", "Sales KPI Snapshot", "DocType", 0),
		("AI Chat Session", "AI Chat Session", "DocType", 0),
		("AI Executive Summary", "ai-executive-summary", "Page", 0),
		("AI Sales Agent", "ai-sales-agent", "Page", 0),
		("AI Chatbot", "ai-chatbot", "Page", 0),
		("Pipeline Health Report", "Pipeline Health Report", "Report", 1),
		("Forecast vs Actual Report", "Forecast vs Actual Report", "Report", 1),
		("Conversion Funnel Report", "Conversion Funnel Report", "Report", 1),
		("Sales Analytics", "Sales Analytics", "Report", 1),
		("Territory-wise Sales", "Territory-wise Sales", "Report", 1),
		("Sales Person-wise Transaction Summary", "Sales Person-wise Transaction Summary", "Report", 1),
		("Item-wise Sales History", "Item-wise Sales History", "Report", 1),
		("Customer Acquisition and Loyalty", "Customer Acquisition and Loyalty", "Report", 1),
		("Sales Order Trends", "Sales Order Trends", "Report", 1),
		("Sales Invoice Trends", "Sales Invoice Trends", "Report", 1),
		("Customer Group-wise Sales", "Customer Group-wise Sales", "Report", 1),
		("AI Sales KPI Trends Report", "AI Sales KPI Trends Report", "Report", 1),
		("Item Group-wise Sales", "Item Group-wise Sales", "Report", 1),
	]

	existing_links = {
		(row.link_to, row.link_type)
		for row in frappe.get_all(
			"Workspace Link",
			filters={"parent": workspace_name, "parenttype": "Workspace", "parentfield": "links"},
			fields=["link_to", "link_type"],
		)
		if row.get("link_to")
	}
	added_links = []
	link_idx = (
		frappe.db.sql(
			"""
			SELECT COALESCE(MAX(idx), 0) AS max_idx
			FROM `tabWorkspace Link`
			WHERE parent = %s AND parenttype = 'Workspace' AND parentfield = 'links'
			""",
			(workspace_name,),
			as_dict=True,
		)[0].max_idx
		or 0
	)
	for label, link_to, link_type, is_query_report in expected_links:
		if (link_to, link_type) in existing_links:
			continue
		link_idx += 1
		doc = frappe.get_doc(
			{
				"doctype": "Workspace Link",
				"parent": workspace_name,
				"parenttype": "Workspace",
				"parentfield": "links",
				"idx": link_idx,
				"label": label,
				"link_to": link_to,
				"link_type": link_type,
				"is_query_report": is_query_report,
				"type": "Link",
				"hidden": 0,
				"onboard": 0,
			}
		)
		doc.db_insert()
		added_links.append(label)

	frappe.db.commit()

	return {
		"added_shortcuts": added_shortcuts,
		"added_links": added_links,
		"total_shortcuts": frappe.db.count(
			"Workspace Shortcut",
			{"parent": workspace_name, "parenttype": "Workspace", "parentfield": "shortcuts"},
		),
		"total_links": frappe.db.count(
			"Workspace Link",
			{"parent": workspace_name, "parenttype": "Workspace", "parentfield": "links"},
		),
	}


@frappe.whitelist()
def get_sales_analytics(company: str | None = None, from_date: str | None = None, to_date: str | None = None):
	"""Return comprehensive sales analytics with all breakdowns and time periods."""
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")

	kpi = get_sales_kpi_summary(company=company, from_date=from_date, to_date=to_date)
	company = kpi["company"]
	from_date = kpi["from_date"]
	to_date = kpi["to_date"]

	analytics = {
		"company": company,
		"from_date": from_date,
		"to_date": to_date,
		"kpis": kpi,
	}

	# Time-period trends
	analytics["daily"] = get_daily_sales_trends(company, from_date, to_date)
	analytics["weekly"] = get_weekly_sales_trends(company, from_date, to_date)
	analytics["monthly"] = get_monthly_sales_trends(company, from_date, to_date)
	analytics["quarterly"] = get_quarterly_sales_trends(company, from_date, to_date)
	analytics["yearly"] = get_yearly_sales_trends(company, from_date, to_date)

	# Dimensional breakdowns
	analytics["territory"] = get_territory_breakdown(company, from_date, to_date)
	analytics["salesperson"] = get_salesperson_breakdown(company, from_date, to_date)
	analytics["items"] = get_item_analytics(company, from_date, to_date)
	analytics["customers"] = get_customer_analytics(company, from_date, to_date)
	analytics["partners"] = get_partner_analytics(company, from_date, to_date)

	return analytics


@frappe.whitelist()
def get_daily_sales(company: str | None = None, from_date: str | None = None, to_date: str | None = None):
	"""Get daily sales trends API endpoint."""
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
	kpi = get_sales_kpi_summary(company=company, from_date=from_date, to_date=to_date)
	return get_daily_sales_trends(kpi["company"], kpi["from_date"], kpi["to_date"])


@frappe.whitelist()
def get_weekly_sales(company: str | None = None, from_date: str | None = None, to_date: str | None = None):
	"""Get weekly sales trends API endpoint."""
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
	kpi = get_sales_kpi_summary(company=company, from_date=from_date, to_date=to_date)
	return get_weekly_sales_trends(kpi["company"], kpi["from_date"], kpi["to_date"])


@frappe.whitelist()
def get_quarterly_sales(company: str | None = None, from_date: str | None = None, to_date: str | None = None):
	"""Get quarterly sales trends API endpoint."""
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
	kpi = get_sales_kpi_summary(company=company, from_date=from_date, to_date=to_date)
	return get_quarterly_sales_trends(kpi["company"], kpi["from_date"], kpi["to_date"])


@frappe.whitelist()
def get_yearly_sales(company: str | None = None, from_date: str | None = None, to_date: str | None = None):
	"""Get yearly sales trends API endpoint."""
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
	kpi = get_sales_kpi_summary(company=company, from_date=from_date, to_date=to_date)
	return get_yearly_sales_trends(kpi["company"], kpi["from_date"], kpi["to_date"])


@frappe.whitelist()
def get_partner_sales(company: str | None = None, from_date: str | None = None, to_date: str | None = None):
	"""Get partner-wise sales analytics API endpoint."""
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
	kpi = get_sales_kpi_summary(company=company, from_date=from_date, to_date=to_date)
	return get_partner_analytics(kpi["company"], kpi["from_date"], kpi["to_date"])


@frappe.whitelist()
def get_territory_sales(company: str | None = None, from_date: str | None = None, to_date: str | None = None):
	"""Get territory-wise sales analytics API endpoint."""
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
	kpi = get_sales_kpi_summary(company=company, from_date=from_date, to_date=to_date)
	return get_territory_breakdown(kpi["company"], kpi["from_date"], kpi["to_date"])


@frappe.whitelist()
def get_salesperson_sales(company: str | None = None, from_date: str | None = None, to_date: str | None = None):
	"""Get salesperson-wise sales analytics API endpoint."""
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
	kpi = get_sales_kpi_summary(company=company, from_date=from_date, to_date=to_date)
	return get_salesperson_breakdown(kpi["company"], kpi["from_date"], kpi["to_date"])


@frappe.whitelist()
def get_item_sales(company: str | None = None, from_date: str | None = None, to_date: str | None = None):
	"""Get item and item group wise sales analytics API endpoint."""
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
	kpi = get_sales_kpi_summary(company=company, from_date=from_date, to_date=to_date)
	return get_item_analytics(kpi["company"], kpi["from_date"], kpi["to_date"])


@frappe.whitelist()
def get_customer_sales(company: str | None = None, from_date: str | None = None, to_date: str | None = None):
	"""Get customer and customer group wise sales analytics API endpoint."""
	_require_roles("AI Sales Manager", "AI Sales User", "Sales Manager")
	kpi = get_sales_kpi_summary(company=company, from_date=from_date, to_date=to_date)
	return get_customer_analytics(kpi["company"], kpi["from_date"], kpi["to_date"])
