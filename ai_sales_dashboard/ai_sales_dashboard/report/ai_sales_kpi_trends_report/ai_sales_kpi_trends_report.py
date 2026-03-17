import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate


def execute(filters=None):
	filters = filters or {}
	company = filters.get("company") or frappe.defaults.get_user_default("Company")
	if not company:
		frappe.throw(_("Please select a company for AI Sales KPI Trends Report."))

	period_type = filters.get("period_type") or "Daily"
	to_date = filters.get("to_date") or nowdate()
	from_date = filters.get("from_date") or add_days(getdate(to_date), -90)

	data = frappe.db.sql(
		"""
		SELECT
			snapshot_date,
			company,
			period_type,
			opportunities_created,
			opportunities_converted,
			conversion_rate_percent,
			open_opportunities,
			pipeline_value,
			weighted_pipeline_value,
			booked_revenue,
			sales_orders_count,
			deliveries_count,
			invoices_count,
			avg_invoice_value,
			currency
		FROM `tabSales KPI Snapshot`
		WHERE company = %(company)s
		  AND period_type = %(period_type)s
		  AND snapshot_date BETWEEN %(from_date)s AND %(to_date)s
		ORDER BY snapshot_date ASC
		""",
		{
			"company": company,
			"period_type": period_type,
			"from_date": from_date,
			"to_date": to_date,
		},
		as_dict=True,
	)

	columns = [
		{"label": "Snapshot Date", "fieldname": "snapshot_date", "fieldtype": "Date", "width": 120},
		{"label": "Period", "fieldname": "period_type", "fieldtype": "Data", "width": 90},
		{"label": "Opp Created", "fieldname": "opportunities_created", "fieldtype": "Int", "width": 110},
		{"label": "Opp Converted", "fieldname": "opportunities_converted", "fieldtype": "Int", "width": 120},
		{"label": "Conversion %", "fieldname": "conversion_rate_percent", "fieldtype": "Percent", "width": 110},
		{"label": "Open Opp", "fieldname": "open_opportunities", "fieldtype": "Int", "width": 100},
		{"label": "Pipeline", "fieldname": "pipeline_value", "fieldtype": "Currency", "options": "currency", "width": 130},
		{"label": "Weighted", "fieldname": "weighted_pipeline_value", "fieldtype": "Currency", "options": "currency", "width": 130},
		{"label": "Revenue", "fieldname": "booked_revenue", "fieldtype": "Currency", "options": "currency", "width": 130},
		{"label": "Sales Orders", "fieldname": "sales_orders_count", "fieldtype": "Int", "width": 100},
		{"label": "Deliveries", "fieldname": "deliveries_count", "fieldtype": "Int", "width": 95},
		{"label": "Invoices", "fieldname": "invoices_count", "fieldtype": "Int", "width": 90},
		{"label": "Avg Invoice", "fieldname": "avg_invoice_value", "fieldtype": "Currency", "options": "currency", "width": 120},
		{"label": "Currency", "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "hidden": 1},
	]

	return columns, data
