import frappe


def execute(filters=None):
	filters = filters or {}
	conditions = ["op.company = %(company)s"]
	values = {"company": filters.get("company")}

	if filters.get("from_date") and filters.get("to_date"):
		conditions.append("DATE(op.creation) BETWEEN %(from_date)s AND %(to_date)s")
		values["from_date"] = filters.get("from_date")
		values["to_date"] = filters.get("to_date")

	if filters.get("opportunity_owner"):
		conditions.append("op.opportunity_owner = %(opportunity_owner)s")
		values["opportunity_owner"] = filters.get("opportunity_owner")

	stale_days = int(filters.get("stale_days") or 14)
	values["stale_days"] = stale_days

	where_clause = " AND ".join(conditions)

	data = frappe.db.sql(
		f"""
		SELECT
			op.name AS opportunity,
			op.party_name AS party_name,
			op.opportunity_owner AS opportunity_owner,
			op.status AS status,
			op.expected_closing AS expected_closing,
			COALESCE(op.opportunity_amount, 0) AS opportunity_amount,
			COALESCE(op.probability, 0) AS probability,
			COALESCE(op.opportunity_amount, 0) * COALESCE(op.probability, 0) / 100 AS weighted_amount,
			DATEDIFF(CURDATE(), DATE(op.creation)) AS age_days,
			CASE WHEN DATEDIFF(CURDATE(), DATE(op.creation)) > %(stale_days)s THEN 'Yes' ELSE 'No' END AS stale_flag
		FROM `tabOpportunity` op
		WHERE {where_clause}
		ORDER BY op.modified DESC
		""",
		values,
		as_dict=True,
	)

	columns = [
		{"label": "Opportunity", "fieldname": "opportunity", "fieldtype": "Link", "options": "Opportunity", "width": 170},
		{"label": "Party", "fieldname": "party_name", "fieldtype": "Data", "width": 160},
		{"label": "Owner", "fieldname": "opportunity_owner", "fieldtype": "Link", "options": "User", "width": 160},
		{"label": "Status", "fieldname": "status", "fieldtype": "Data", "width": 120},
		{"label": "Expected Closing", "fieldname": "expected_closing", "fieldtype": "Date", "width": 120},
		{"label": "Amount", "fieldname": "opportunity_amount", "fieldtype": "Currency", "width": 140},
		{"label": "Probability %", "fieldname": "probability", "fieldtype": "Percent", "width": 110},
		{"label": "Weighted Amount", "fieldname": "weighted_amount", "fieldtype": "Currency", "width": 150},
		{"label": "Age (Days)", "fieldname": "age_days", "fieldtype": "Int", "width": 110},
		{"label": "Stale", "fieldname": "stale_flag", "fieldtype": "Data", "width": 80},
	]

	return columns, data
