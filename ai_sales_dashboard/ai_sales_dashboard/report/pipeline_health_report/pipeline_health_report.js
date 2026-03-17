frappe.query_reports["Pipeline Health Report"] = {
	onload(report) {
		report.page.add_inner_button(__("Generate AI Insight"), () => {
			const filters = report.get_values() || {};
			frappe.call({
				method: "ai_sales_dashboard.api.get_ai_sales_summary",
				args: {
					company: filters.company,
					from_date: filters.from_date,
					to_date: filters.to_date,
				},
				freeze: true,
				freeze_message: __("Generating AI insight..."),
				callback: (r) => {
					const summary = r.message?.summary || __("No AI summary returned.");
					const dialog = new frappe.ui.Dialog({
						title: __("AI Sales Insight"),
						fields: [
							{
								fieldname: "insight",
								fieldtype: "HTML",
								options: `<div style=\"max-height:420px;overflow:auto;white-space:pre-wrap;line-height:1.5;\">${frappe.utils.escape_html(summary)}</div>`,
							},
						],
						primary_action_label: __("Close"),
						primary_action() {
							dialog.hide();
						},
					});
					dialog.show();
				},
			});
		});
	},
	filters: [
		{
			fieldname: "company",
			label: __("Company"),
			fieldtype: "Link",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
		},
		{
			fieldname: "from_date",
			label: __("From Date"),
			fieldtype: "Date",
			default: frappe.datetime.add_days(frappe.datetime.get_today(), -90),
			reqd: 1,
		},
		{
			fieldname: "to_date",
			label: __("To Date"),
			fieldtype: "Date",
			default: frappe.datetime.get_today(),
			reqd: 1,
		},
		{
			fieldname: "opportunity_owner",
			label: __("Opportunity Owner"),
			fieldtype: "Link",
			options: "User",
		},
		{
			fieldname: "stale_days",
			label: __("Stale Days"),
			fieldtype: "Int",
			default: 14,
		},
	],
};
