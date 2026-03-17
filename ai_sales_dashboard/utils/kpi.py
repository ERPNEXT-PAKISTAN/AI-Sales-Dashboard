import frappe
from frappe.utils import add_days, cint, flt, getdate, nowdate


def _get_period_days(default: int = 90) -> int:
	return cint(frappe.db.get_single_value("AI Sales Dashboard Settings", "analysis_period_days") or default)


def _get_company_currency(company: str) -> str | None:
	return frappe.db.get_value("Company", company, "default_currency")


def _compute_kpis(company: str, from_date: str, to_date: str) -> dict:
	opp_filters = {"company": company, "creation": ["between", [from_date, to_date]]}

	open_opportunities = frappe.db.count(
		"Opportunity",
		filters={**opp_filters, "status": ["not in", ["Lost", "Converted"]]},
	)

	pipeline_rows = frappe.get_all(
		"Opportunity",
		filters={**opp_filters, "status": ["not in", ["Lost", "Converted"]]},
		fields=["opportunity_amount", "probability"],
	)
	pipeline_value = 0.0
	weighted_pipeline_value = 0.0
	for row in pipeline_rows:
		amount = flt(row.opportunity_amount)
		probability = flt(row.probability)
		pipeline_value += amount
		weighted_pipeline_value += amount * (probability / 100.0)

	total_created = frappe.db.count("Opportunity", filters=opp_filters) or 0
	total_converted = frappe.db.count(
		"Opportunity",
		filters={**opp_filters, "status": ["in", ["Converted", "Quotation"]]},
	)
	win_rate_percent = (flt(total_converted) / total_created * 100.0) if total_created else 0.0
	conversion_rate_percent = win_rate_percent

	revenue_rows = frappe.get_all(
		"Sales Invoice",
		filters={
			"company": company,
			"posting_date": ["between", [from_date, to_date]],
			"docstatus": 1,
		},
		fields=["base_grand_total"],
	)
	booked_revenue = sum(flt(row.base_grand_total) for row in revenue_rows)
	invoices_count = len(revenue_rows)
	avg_invoice_value = (booked_revenue / invoices_count) if invoices_count else 0.0

	sales_orders_count = frappe.db.count(
		"Sales Order",
		filters={
			"company": company,
			"transaction_date": ["between", [from_date, to_date]],
			"docstatus": 1,
		},
	)

	deliveries_count = frappe.db.count(
		"Delivery Note",
		filters={
			"company": company,
			"posting_date": ["between", [from_date, to_date]],
			"docstatus": 1,
		},
	)

	return {
		"opportunities_created": total_created,
		"opportunities_converted": total_converted,
		"conversion_rate_percent": round(conversion_rate_percent, 2),
		"open_opportunities": open_opportunities,
		"pipeline_value": pipeline_value,
		"weighted_pipeline_value": weighted_pipeline_value,
		"win_rate_percent": round(win_rate_percent, 2),
		"booked_revenue": booked_revenue,
		"sales_orders_count": sales_orders_count,
		"deliveries_count": deliveries_count,
		"invoices_count": invoices_count,
		"avg_invoice_value": avg_invoice_value,
	}


def create_snapshot_for_company(
	company: str,
	snapshot_date: str | None = None,
	period_type: str = "Daily",
	period_days: int | None = None,
) -> str:
	"""Create or update one Sales KPI Snapshot row for a company/date."""
	if not company:
		frappe.throw("Company is required to create Sales KPI Snapshot.")

	if not frappe.db.exists("Company", company):
		frappe.throw(f"Company not found: {company}")

	snapshot_date = snapshot_date or nowdate()
	period_days = period_days or _get_period_days(default=90)
	from_date = str(add_days(getdate(snapshot_date), -cint(period_days)))

	kpi = _compute_kpis(company=company, from_date=from_date, to_date=snapshot_date)
	currency = _get_company_currency(company)

	existing_name = frappe.db.exists(
		"Sales KPI Snapshot",
		{
			"snapshot_date": snapshot_date,
			"company": company,
			"period_type": period_type,
		},
	)

	if existing_name:
		doc = frappe.get_doc("Sales KPI Snapshot", existing_name)
	else:
		doc = frappe.new_doc("Sales KPI Snapshot")
		doc.snapshot_date = snapshot_date
		doc.company = company
		doc.period_type = period_type

	doc.open_opportunities = kpi["open_opportunities"]
	doc.opportunities_created = kpi["opportunities_created"]
	doc.opportunities_converted = kpi["opportunities_converted"]
	doc.conversion_rate_percent = kpi["conversion_rate_percent"]
	doc.pipeline_value = kpi["pipeline_value"]
	doc.weighted_pipeline_value = kpi["weighted_pipeline_value"]
	doc.win_rate_percent = kpi["win_rate_percent"]
	doc.booked_revenue = kpi["booked_revenue"]
	doc.sales_orders_count = kpi["sales_orders_count"]
	doc.deliveries_count = kpi["deliveries_count"]
	doc.invoices_count = kpi["invoices_count"]
	doc.avg_invoice_value = kpi["avg_invoice_value"]
	doc.currency = currency
	doc.data_source_note = f"Computed from Opportunity/Sales Invoice for {from_date} to {snapshot_date}"

	if existing_name:
		doc.save(ignore_permissions=True)
	else:
		doc.insert(ignore_permissions=True)

	return doc.name


def create_daily_snapshots() -> list[str]:
	"""Scheduled daily job from hooks.py."""
	snapshot_date = nowdate()
	companies: list[str] = []

	settings_company = frappe.db.get_single_value("AI Sales Dashboard Settings", "company")
	if settings_company:
		companies = [settings_company]
	else:
		companies = frappe.get_all("Company", filters={"is_group": 0}, pluck="name")

	created_or_updated: list[str] = []
	for company in companies:
		try:
			name = create_snapshot_for_company(company=company, snapshot_date=snapshot_date, period_type="Daily")
			created_or_updated.append(name)
		except Exception:
			frappe.log_error(title=f"AI Sales Dashboard Snapshot Failed: {company}", message=frappe.get_traceback())

	return created_or_updated
