import frappe


def execute(filters=None):
	filters = filters or {}
	conditions = ["si.company = %(company)s", "si.docstatus = 1"]
	values = {"company": filters.get("company")}

	if filters.get("from_date") and filters.get("to_date"):
		conditions.append("si.posting_date BETWEEN %(from_date)s AND %(to_date)s")
		values["from_date"] = filters.get("from_date")
		values["to_date"] = filters.get("to_date")

	if filters.get("item_group"):
		conditions.append("i.item_group = %(item_group)s")
		values["item_group"] = filters.get("item_group")

	where_clause = " AND ".join(conditions)

	data = frappe.db.sql(
		f"""
		SELECT
			COALESCE(i.item_group, 'Not Set') AS item_group,
			COUNT(DISTINCT sii.item_code) AS unique_items,
			SUM(COALESCE(sii.qty, 0)) AS total_qty,
			SUM(COALESCE(sii.base_net_amount, 0)) AS net_amount,
			SUM(COALESCE(sii.base_amount, 0)) AS total_amount
		FROM `tabSales Invoice Item` sii
		LEFT JOIN `tabSales Invoice` si ON sii.parent = si.name
		LEFT JOIN `tabItem` i ON sii.item_code = i.name
		WHERE {where_clause}
		GROUP BY i.item_group
		ORDER BY total_amount DESC
		""",
		values,
		as_dict=True,
	)

	columns = [
		{"label": "Item Group", "fieldname": "item_group", "fieldtype": "Link", "options": "Item Group", "width": 220},
		{"label": "Unique Items", "fieldname": "unique_items", "fieldtype": "Int", "width": 120},
		{"label": "Total Qty", "fieldname": "total_qty", "fieldtype": "Float", "width": 120},
		{"label": "Net Amount", "fieldname": "net_amount", "fieldtype": "Currency", "width": 150},
		{"label": "Total Amount", "fieldname": "total_amount", "fieldtype": "Currency", "width": 160},
	]

	return columns, data
