import frappe
from frappe import _
from frappe.utils import add_days, getdate, nowdate


def execute(filters=None):
	filters = filters or {}
	company = filters.get("company") or frappe.defaults.get_user_default("Company")
	if not company:
		frappe.throw(_("Please select a company for Forecast vs Actual Report."))

	to_date = filters.get("to_date") or nowdate()
	from_date = filters.get("from_date") or add_days(getdate(to_date), -30)

	data = frappe.db.sql(
		"""
		SELECT
			snapshot_date,
			company,
			COALESCE(pipeline_value, 0) AS pipeline_value,
			COALESCE(weighted_pipeline_value, 0) AS forecast_value,
			COALESCE(booked_revenue, 0) AS actual_revenue,
			(COALESCE(booked_revenue, 0) - COALESCE(weighted_pipeline_value, 0)) AS variance,
			CASE
				WHEN COALESCE(weighted_pipeline_value, 0) > 0
				THEN (COALESCE(booked_revenue, 0) / COALESCE(weighted_pipeline_value, 0)) * 100
				ELSE 0
			END AS attainment_percent,
			currency
		FROM `tabSales KPI Snapshot`
		WHERE company = %(company)s
		  AND snapshot_date BETWEEN %(from_date)s AND %(to_date)s
		ORDER BY snapshot_date ASC
		""",
		{"company": company, "from_date": from_date, "to_date": to_date},
		as_dict=True,
	)

	columns = [
		{"label": "Snapshot Date", "fieldname": "snapshot_date", "fieldtype": "Date", "width": 120},
		{"label": "Company", "fieldname": "company", "fieldtype": "Link", "options": "Company", "width": 180},
		{"label": "Pipeline Value", "fieldname": "pipeline_value", "fieldtype": "Currency", "options": "currency", "width": 150},
		{"label": "Forecast Value", "fieldname": "forecast_value", "fieldtype": "Currency", "options": "currency", "width": 150},
		{"label": "Actual Revenue", "fieldname": "actual_revenue", "fieldtype": "Currency", "options": "currency", "width": 150},
		{"label": "Variance", "fieldname": "variance", "fieldtype": "Currency", "options": "currency", "width": 140},
		{"label": "Attainment %", "fieldname": "attainment_percent", "fieldtype": "Percent", "width": 120},
		{"label": "Currency", "fieldname": "currency", "fieldtype": "Link", "options": "Currency", "hidden": 1},
	]

	return columns, data
