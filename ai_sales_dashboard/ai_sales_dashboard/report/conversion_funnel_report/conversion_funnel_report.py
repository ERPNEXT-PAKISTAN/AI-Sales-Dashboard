import frappe
from frappe import _
from frappe.utils import add_days, flt, getdate, nowdate


def _build_date_clause(filters: dict, fieldname: str, values: dict, prefix: str = "") -> str:
	conditions = []
	from_key = f"{prefix}from_date"
	to_key = f"{prefix}to_date"

	if filters.get("from_date"):
		conditions.append(f"DATE({fieldname}) >= %({from_key})s")
		values[from_key] = filters.get("from_date")
	if filters.get("to_date"):
		conditions.append(f"DATE({fieldname}) <= %({to_key})s")
		values[to_key] = filters.get("to_date")

	return " AND ".join(conditions)


def execute(filters=None):
	filters = filters or {}
	company = filters.get("company") or frappe.defaults.get_user_default("Company")
	if not company:
		frappe.throw(_("Please select a company for Conversion Funnel Report."))

	if not filters.get("to_date"):
		filters["to_date"] = nowdate()
	if not filters.get("from_date"):
		filters["from_date"] = add_days(getdate(filters["to_date"]), -90)

	stage_rows = []

	opportunity_values = {"company": company}
	opportunity_conditions = ["op.company = %(company)s"]
	opportunity_date_clause = _build_date_clause(filters, "op.creation", opportunity_values, prefix="op_")
	if opportunity_date_clause:
		opportunity_conditions.append(opportunity_date_clause)

	opportunity_where = " AND ".join(opportunity_conditions)
	open_opp = frappe.db.sql(
		f"""
		SELECT
			COUNT(op.name) AS doc_count,
			SUM(COALESCE(op.opportunity_amount, 0)) AS total_amount
		FROM `tabOpportunity` op
		WHERE {opportunity_where}
		  AND op.status NOT IN ('Lost', 'Converted')
		""",
		opportunity_values,
		as_dict=True,
	)[0]
	stage_rows.append({"stage": "Open Opportunities", **open_opp})

	quotation_values = {"company": company}
	quotation_conditions = ["q.company = %(company)s", "q.docstatus = 1"]
	quotation_date_clause = _build_date_clause(filters, "q.transaction_date", quotation_values, prefix="q_")
	if quotation_date_clause:
		quotation_conditions.append(quotation_date_clause)

	quotation_where = " AND ".join(quotation_conditions)
	quotation = frappe.db.sql(
		f"""
		SELECT
			COUNT(q.name) AS doc_count,
			SUM(COALESCE(q.base_grand_total, 0)) AS total_amount
		FROM `tabQuotation` q
		WHERE {quotation_where}
		""",
		quotation_values,
		as_dict=True,
	)[0]
	stage_rows.append({"stage": "Submitted Quotations", **quotation})

	sales_order_values = {"company": company}
	sales_order_conditions = ["so.company = %(company)s", "so.docstatus = 1"]
	sales_order_date_clause = _build_date_clause(filters, "so.transaction_date", sales_order_values, prefix="so_")
	if sales_order_date_clause:
		sales_order_conditions.append(sales_order_date_clause)

	sales_order_where = " AND ".join(sales_order_conditions)
	sales_order = frappe.db.sql(
		f"""
		SELECT
			COUNT(so.name) AS doc_count,
			SUM(COALESCE(so.base_grand_total, 0)) AS total_amount
		FROM `tabSales Order` so
		WHERE {sales_order_where}
		""",
		sales_order_values,
		as_dict=True,
	)[0]
	stage_rows.append({"stage": "Confirmed Sales Orders", **sales_order})

	sales_invoice_values = {"company": company}
	sales_invoice_conditions = ["si.company = %(company)s", "si.docstatus = 1"]
	sales_invoice_date_clause = _build_date_clause(filters, "si.posting_date", sales_invoice_values, prefix="si_")
	if sales_invoice_date_clause:
		sales_invoice_conditions.append(sales_invoice_date_clause)

	sales_invoice_where = " AND ".join(sales_invoice_conditions)
	sales_invoice = frappe.db.sql(
		f"""
		SELECT
			COUNT(si.name) AS doc_count,
			SUM(COALESCE(si.base_grand_total, 0)) AS total_amount
		FROM `tabSales Invoice` si
		WHERE {sales_invoice_where}
		""",
		sales_invoice_values,
		as_dict=True,
	)[0]
	stage_rows.append({"stage": "Booked Invoices", **sales_invoice})

	data = []
	previous_count = None
	for row in stage_rows:
		doc_count = int(row.get("doc_count") or 0)
		total_amount = flt(row.get("total_amount"))
		if previous_count in (None, 0):
			conversion_percent = 0.0
		else:
			conversion_percent = (doc_count / previous_count) * 100.0

		data.append(
			{
				"stage": row["stage"],
				"doc_count": doc_count,
				"total_amount": total_amount,
				"conversion_percent": round(conversion_percent, 2),
			}
		)
		previous_count = doc_count

	columns = [
		{"label": "Stage", "fieldname": "stage", "fieldtype": "Data", "width": 230},
		{"label": "Documents", "fieldname": "doc_count", "fieldtype": "Int", "width": 130},
		{"label": "Amount", "fieldname": "total_amount", "fieldtype": "Currency", "width": 150},
		{"label": "Stage Conversion %", "fieldname": "conversion_percent", "fieldtype": "Percent", "width": 150},
	]

	return columns, data
