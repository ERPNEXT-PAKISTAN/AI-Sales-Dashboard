import frappe


def execute(filters=None):
	filters = filters or {}
	conditions = ["si.company = %(company)s", "si.docstatus = 1"]
	values = {"company": filters.get("company")}

	if filters.get("from_date") and filters.get("to_date"):
		conditions.append("si.posting_date BETWEEN %(from_date)s AND %(to_date)s")
		values["from_date"] = filters.get("from_date")
		values["to_date"] = filters.get("to_date")

	if filters.get("customer_group"):
		conditions.append("c.customer_group = %(customer_group)s")
		values["customer_group"] = filters.get("customer_group")

	where_clause = " AND ".join(conditions)

	data = frappe.db.sql(
		f"""
		SELECT
			COALESCE(c.customer_group, 'Not Set') AS customer_group,
			COUNT(DISTINCT si.customer) AS customers,
			COUNT(si.name) AS invoice_count,
			SUM(COALESCE(si.base_net_total, 0)) AS net_amount,
			SUM(COALESCE(si.base_grand_total, 0)) AS grand_total,
			AVG(COALESCE(si.base_grand_total, 0)) AS avg_invoice_value
		FROM `tabSales Invoice` si
		LEFT JOIN `tabCustomer` c ON si.customer = c.name
		WHERE {where_clause}
		GROUP BY c.customer_group
		ORDER BY grand_total DESC
		""",
		values,
		as_dict=True,
	)

	columns = [
		{"label": "Customer Group", "fieldname": "customer_group", "fieldtype": "Link", "options": "Customer Group", "width": 200},
		{"label": "Customers", "fieldname": "customers", "fieldtype": "Int", "width": 110},
		{"label": "Invoices", "fieldname": "invoice_count", "fieldtype": "Int", "width": 110},
		{"label": "Net Amount", "fieldname": "net_amount", "fieldtype": "Currency", "width": 150},
		{"label": "Grand Total", "fieldname": "grand_total", "fieldtype": "Currency", "width": 160},
		{"label": "Avg Invoice Value", "fieldname": "avg_invoice_value", "fieldtype": "Currency", "width": 150},
	]

	return columns, data
