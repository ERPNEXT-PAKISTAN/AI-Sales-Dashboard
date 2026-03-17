frappe.provide("ai_sales_dashboard");

frappe.pages["ai-executive-summary"].on_page_load = function (wrapper) {
	new AIExecutiveSummaryPage(wrapper);
};

class AIExecutiveSummaryPage {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.charts = {};
		this.chatMessages = [];
		this.currency = frappe.defaults.get_default("currency") || "USD";

		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("AI Executive Summary"),
			single_column: true,
		});

		this.make_filters();
		this.render_layout();
		this.bind_actions();
		this.refreshEngineBadge();
		this.renderChatWelcome();
		this.refresh();
	}

	make_filters() {
		const today = frappe.datetime.get_today();
		const fromDate = frappe.datetime.add_months(today, -3);

		this.companyField = this.page.add_field({
			label: __("Company"),
			fieldtype: "Link",
			fieldname: "company",
			options: "Company",
			default: frappe.defaults.get_user_default("Company"),
			reqd: 1,
			change: () => this.refresh(),
		});

		this.fromDateField = this.page.add_field({
			label: __("From"),
			fieldtype: "Date",
			fieldname: "from_date",
			default: fromDate,
			change: () => this.refresh(),
		});

		this.toDateField = this.page.add_field({
			label: __("To"),
			fieldtype: "Date",
			fieldname: "to_date",
			default: today,
			change: () => this.refresh(),
		});
	}

	render_layout() {
		const styleId = "ai-executive-summary-style";
		if (!document.getElementById(styleId)) {
			$("head").append(`
				<style id="${styleId}">
					.ai-exec-wrap {
						--ink: #12263a;
						--muted: #5a6b7d;
						--line: #dbe3ec;
						--paper: #ffffff;
						--bg-soft: linear-gradient(145deg, #f8f6f1 0%, #edf3fb 65%, #f9fbff 100%);
						--brand: #145f7a;
						--accent: #d99836;
						font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
						color: var(--ink);
						background: var(--bg-soft);
						padding: 18px;
						border-radius: 14px;
					}
					.ai-exec-hero {
						display: flex;
						align-items: flex-start;
						justify-content: space-between;
						gap: 16px;
						padding: 18px;
						border: 1px solid var(--line);
						border-radius: 12px;
						background: var(--paper);
						box-shadow: 0 8px 20px rgba(18, 38, 58, 0.05);
						margin-bottom: 14px;
					}
					.ai-exec-title {
						margin: 0;
						font-family: "IBM Plex Serif", Georgia, serif;
						font-size: 1.4rem;
						font-weight: 600;
					}
					.ai-exec-subtitle {
						margin-top: 6px;
						color: var(--muted);
					}
					.ai-exec-status {
						padding: 6px 10px;
						border-radius: 999px;
						font-size: 12px;
						font-weight: 600;
						background: #e6f4ea;
						color: #1a6e3f;
					}
					.ai-exec-status-stack {
						display: grid;
						gap: 8px;
						justify-items: end;
					}
					.ai-exec-engine {
						padding: 6px 10px;
						border-radius: 999px;
						font-size: 12px;
						font-weight: 600;
						background: #fff6e8;
						border: 1px solid #f4d4a7;
						color: #8b4a00;
					}
					.ai-kpi-grid {
						display: grid;
						grid-template-columns: repeat(4, minmax(0, 1fr));
						gap: 12px;
						margin-bottom: 14px;
					}
					.ai-kpi-card {
						background: var(--paper);
						border: 1px solid var(--line);
						border-radius: 10px;
						padding: 12px 14px;
						min-height: 86px;
						transition: transform 0.2s ease;
					}
					.ai-kpi-card:hover {
						transform: translateY(-2px);
					}
					.ai-kpi-label {
						font-size: 12px;
						color: var(--muted);
						text-transform: uppercase;
						letter-spacing: 0.04em;
					}
					.ai-kpi-value {
						font-family: "IBM Plex Serif", Georgia, serif;
						font-size: 1.4rem;
						margin-top: 6px;
						font-weight: 600;
					}
					.ai-grid-2 {
						display: grid;
						grid-template-columns: 1.35fr 1fr;
						gap: 12px;
					}
					.ai-panel {
						background: var(--paper);
						border: 1px solid var(--line);
						border-radius: 10px;
						padding: 12px;
					}
					.ai-panel h4 {
						font-size: 14px;
						text-transform: uppercase;
						letter-spacing: 0.04em;
						color: var(--muted);
						margin: 0 0 10px;
					}
					.ai-chart-block {
						background: #fbfdff;
						border: 1px solid #e4edf6;
						border-radius: 8px;
						padding: 10px;
						margin-bottom: 10px;
					}
					.ai-risk-list {
						display: grid;
						gap: 8px;
					}
					.ai-risk-item {
						display: flex;
						gap: 10px;
						padding: 9px 10px;
						border-radius: 8px;
						border: 1px solid transparent;
					}
					.ai-risk-dot {
						width: 10px;
						height: 10px;
						border-radius: 50%;
						margin-top: 4px;
					}
					.ai-risk-item.red {
						background: #fff2f2;
						border-color: #ffd9d9;
					}
					.ai-risk-item.red .ai-risk-dot {
						background: #cc2936;
					}
					.ai-risk-item.yellow {
						background: #fff9e8;
						border-color: #fde8b2;
					}
					.ai-risk-item.yellow .ai-risk-dot {
						background: #d99836;
					}
					.ai-risk-item.green {
						background: #edf9f1;
						border-color: #cdeed8;
					}
					.ai-risk-item.green .ai-risk-dot {
						background: #2c8d56;
					}
					.ai-risk-title {
						font-weight: 600;
						font-size: 13px;
					}
					.ai-risk-detail {
						font-size: 12px;
						color: var(--muted);
					}
					.ai-narrative {
						border-radius: 10px;
						padding: 12px;
						background: #132f3c;
						color: #f6f9fc;
						min-height: 180px;
						line-height: 1.5;
						white-space: pre-wrap;
					}
					.ai-brief-head {
						display: flex;
						justify-content: space-between;
						align-items: center;
						gap: 8px;
						margin-bottom: 10px;
						flex-wrap: wrap;
					}
					.ai-brief-meta {
						font-size: 12px;
						color: var(--muted);
					}
					.ai-brief-actions {
						display: flex;
						gap: 8px;
						flex-wrap: wrap;
					}
					.ai-brief-body {
						border-radius: 8px;
						border: 1px solid #e4edf6;
						background: #fbfdff;
						padding: 12px;
						line-height: 1.55;
						white-space: pre-wrap;
						min-height: 110px;
					}
					.ai-exec-chat-shell {
						display: grid;
						gap: 10px;
					}
					.ai-exec-chat-top {
						display: flex;
						justify-content: space-between;
						align-items: center;
						gap: 8px;
					}
					.ai-exec-chat-provider {
						font-size: 12px;
						color: var(--muted);
					}
					.ai-exec-chat-log {
						display: grid;
						gap: 8px;
						max-height: 320px;
						overflow: auto;
						padding-right: 4px;
					}
					.ai-exec-chat-msg {
						padding: 10px 12px;
						border-radius: 10px;
						border: 1px solid var(--line);
						line-height: 1.5;
					}
					.ai-exec-chat-msg.user {
						background: #f7fbfd;
					}
					.ai-exec-chat-msg.assistant {
						background: #112d39;
						color: #f2f8fb;
						border-color: #112d39;
					}
					.ai-exec-chat-role {
						font-size: 11px;
						font-weight: 700;
						text-transform: uppercase;
						letter-spacing: 0.06em;
						margin-bottom: 5px;
					}
					.ai-exec-chat-input {
						width: 100%;
						min-height: 88px;
						border-radius: 10px;
						border: 1px solid var(--line);
						padding: 10px 12px;
						resize: vertical;
						font: inherit;
					}
					.ai-exec-chat-actions {
						display: flex;
						justify-content: space-between;
						gap: 8px;
						flex-wrap: wrap;
					}
					.ai-exec-chat-chips {
						display: flex;
						gap: 6px;
						flex-wrap: wrap;
					}
					.ai-exec-chat-chip {
						padding: 7px 10px;
						border-radius: 999px;
						border: 1px solid #d9e8ef;
						background: #f9fcfe;
						font-size: 12px;
						cursor: pointer;
					}
					.ai-analytics-grid {
						display: grid;
						grid-template-columns: 1fr 1fr;
						gap: 12px;
						margin-top: 12px;
					}
					.ai-indicator-bar {
						display: grid;
						grid-template-columns: repeat(4, minmax(0, 1fr));
						gap: 10px;
						margin-top: 12px;
					}
					.ai-indicator {
						padding: 10px;
						border-radius: 10px;
						border: 1px solid #dfe8f2;
						background: #fbfdff;
					}
					.ai-indicator .label {
						font-size: 11px;
						letter-spacing: 0.05em;
						text-transform: uppercase;
						color: var(--muted);
					}
					.ai-indicator .value {
						font-size: 13px;
						font-weight: 600;
						margin-top: 6px;
					}
					.ai-table-wrap {
						overflow: auto;
						border: 1px solid #e4edf6;
						border-radius: 8px;
						max-height: 260px;
					}
					.ai-table {
						width: 100%;
						border-collapse: collapse;
						font-size: 12px;
					}
					.ai-table th,
					.ai-table td {
						padding: 8px 10px;
						border-bottom: 1px solid #eef3f8;
						text-align: left;
						white-space: nowrap;
					}
					.ai-table thead th {
						position: sticky;
						top: 0;
						background: #f4f9fd;
						z-index: 1;
					}
					.ai-empty {
						padding: 12px;
						color: var(--muted);
						font-size: 12px;
					}
					@media (max-width: 1024px) {
						.ai-kpi-grid {
							grid-template-columns: repeat(2, minmax(0, 1fr));
						}
						.ai-grid-2 {
							grid-template-columns: 1fr;
						}
						.ai-analytics-grid,
						.ai-indicator-bar {
							grid-template-columns: 1fr;
						}
					}
					@media (max-width: 640px) {
						.ai-kpi-grid {
							grid-template-columns: 1fr;
						}
						.ai-exec-wrap {
							padding: 10px;
						}
					}
				</style>
			`);
		}

		this.page.main.html(`
			<div class="ai-exec-wrap">
				<div class="ai-exec-hero">
					<div>
						<h2 class="ai-exec-title">${__("AI Executive Summary")}</h2>
						<div class="ai-exec-subtitle" id="ai-exec-period">${__("Loading period...")}</div>
					</div>
					<div class="ai-exec-status-stack">
						<div class="ai-exec-status" id="ai-exec-health">${__("Health: Pending")}</div>
						<div class="ai-exec-engine" id="ai-exec-engine">${__("Engine: Loading...")}</div>
					</div>
				</div>

				<div class="ai-kpi-grid" id="ai-kpi-grid"></div>

				<div class="ai-grid-2">
					<div class="ai-panel">
						<h4>${__("Trend Analytics")}</h4>
						<div class="ai-chart-block"><div id="ai-chart-revenue"></div></div>
						<div class="ai-chart-block"><div id="ai-chart-pipeline"></div></div>
					</div>

					<div class="ai-panel">
						<h4>${__("Risk Flags")}</h4>
						<div class="ai-risk-list" id="ai-risk-list"></div>
					</div>
				</div>

				<div class="ai-panel" style="margin-top:12px;">
					<h4>${__("One-Click AI Narrative")}</h4>
					<div class="ai-narrative" id="ai-narrative">${__("Click 'Generate AI Narrative' to produce executive insights.")}</div>
				</div>

				<div class="ai-panel" style="margin-top:12px;">
					<h4>${__("AI Management Brief")}</h4>
					<div class="ai-brief-head">
						<div class="ai-brief-meta" id="ai-brief-meta">${__("Provider: - | Model: -")}</div>
						<div class="ai-brief-actions">
							<button class="btn btn-primary btn-sm" id="ai-brief-generate">${__("Generate Brief from Dashboard")}</button>
							<button class="btn btn-default btn-sm" id="ai-brief-to-chat">${__("Send Brief to Chat")}</button>
						</div>
					</div>
					<div class="ai-brief-body" id="ai-brief-body">${__("Use current filters and click Generate Brief to produce management-level insights from ERPNext analytics.")}</div>
				</div>

				<div class="ai-panel" style="margin-top:12px;">
					<h4>${__("Executive Chatbot Agent")}</h4>
					<div class="ai-exec-chat-shell">
						<div class="ai-exec-chat-top">
							<div class="ai-exec-chat-provider" id="ai-exec-chat-provider">${__("Provider: Awaiting response")}</div>
							<button class="btn btn-default btn-xs" id="ai-exec-chat-clear">${__("Clear")}</button>
						</div>
						<div class="ai-exec-chat-log" id="ai-exec-chat-log"></div>
						<textarea class="ai-exec-chat-input" id="ai-exec-chat-input" placeholder="${__("Ask: Explain this month revenue drop, top risks, and 5 actions for the sales team.")}"></textarea>
						<div class="ai-exec-chat-actions">
							<div class="btn-group">
								<button class="btn btn-primary" id="ai-exec-chat-send">${__("Send")}</button>
							</div>
							<div class="ai-exec-chat-chips">
								<button class="ai-exec-chat-chip" data-prompt="${__("Summarize key business risks in plain language.")}">${__("Risk Brief")}</button>
								<button class="ai-exec-chat-chip" data-prompt="${__("Which customers and salespeople need intervention this week?")}">${__("Intervention List")}</button>
								<button class="ai-exec-chat-chip" data-prompt="${__("Give me an executive action plan for the next 7 days.")}">${__("7-Day Plan")}</button>
							</div>
						</div>
					</div>
				</div>

				<div class="ai-panel" style="margin-top:12px;">
					<h4>${__("AI Indicators")}</h4>
					<div class="ai-indicator-bar" id="ai-indicator-bar"></div>
				</div>

				<div class="ai-analytics-grid">
					<div class="ai-panel">
						<h4>${__("Daily Sales Trend")}</h4>
						<div id="ai-chart-daily"></div>
					</div>
					<div class="ai-panel">
						<h4>${__("Weekly Sales Trend")}</h4>
						<div id="ai-chart-weekly"></div>
					</div>
					<div class="ai-panel">
						<h4>${__("Quarterly Comparative")}</h4>
						<div id="ai-chart-quarterly"></div>
					</div>
					<div class="ai-panel">
						<h4>${__("Yearly Comparative")}</h4>
						<div id="ai-chart-yearly"></div>
					</div>
				</div>

				<div class="ai-analytics-grid">
					<div class="ai-panel"><h4>${__("Territory-wise Sales")}</h4><div id="ai-table-territory"></div></div>
					<div class="ai-panel"><h4>${__("Salesperson-wise")}</h4><div id="ai-table-salesperson"></div></div>
					<div class="ai-panel"><h4>${__("Item-wise Sales")}</h4><div id="ai-table-items"></div></div>
					<div class="ai-panel"><h4>${__("Item Group-wise")}</h4><div id="ai-table-item-groups"></div></div>
					<div class="ai-panel"><h4>${__("Customer-wise Sales")}</h4><div id="ai-table-customers"></div></div>
					<div class="ai-panel"><h4>${__("Customer Group-wise")}</h4><div id="ai-table-customer-groups"></div></div>
					<div class="ai-panel"><h4>${__("Partner-wise Sales")}</h4><div id="ai-table-partners"></div></div>
				</div>
			</div>
		`);
	}

	bind_actions() {
		this.page.set_primary_action(__("Refresh"), () => this.refresh(), "refresh");
		this.page.set_secondary_action(__("Generate AI Narrative"), () => this.generateNarrative());

		this.page.main.on("click", "#ai-exec-chat-send", () => this.sendChatMessage());
		this.page.main.on("click", "#ai-exec-chat-clear", () => this.renderChatWelcome());
		this.page.main.on("click", "#ai-brief-generate", () => this.generateManagementBrief());
		this.page.main.on("click", "#ai-brief-to-chat", () => this.pushBriefToChat());
		this.page.main.on("click", ".ai-exec-chat-chip", (event) => {
			const prompt = $(event.currentTarget).attr("data-prompt");
			this.page.main.find("#ai-exec-chat-input").val(prompt);
			this.sendChatMessage();
		});
		this.page.main.on("keydown", "#ai-exec-chat-input", (event) => {
			if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
				event.preventDefault();
				this.sendChatMessage();
			}
		});
	}

	get_args() {
		return {
			company: this.companyField.get_value(),
			from_date: this.fromDateField.get_value(),
			to_date: this.toDateField.get_value(),
		};
	}

	format_currency(value) {
		const rounded = Math.round(flt(value || 0));
		if (typeof format_currency === "function") {
			return format_currency(rounded, this.currency, 0);
		}
		return `${this.currency} ${rounded.toLocaleString()}`;
	}

	format_percent(value) {
		return `${flt(value || 0).toFixed(1)}%`;
	}

	render_kpis(kpis) {
		const cards = [
			{ label: __("Booked Revenue"), value: this.format_currency(kpis.booked_revenue) },
			{ label: __("Pipeline Value"), value: this.format_currency(kpis.pipeline_value) },
			{ label: __("Weighted Pipeline"), value: this.format_currency(kpis.weighted_pipeline_value) },
			{ label: __("Win Rate"), value: this.format_percent(kpis.win_rate_percent) },
			{ label: __("Conversion Rate"), value: this.format_percent(kpis.conversion_rate_percent) },
			{ label: __("Sales Orders"), value: cint(kpis.sales_orders_count || 0) },
			{ label: __("Deliveries"), value: cint(kpis.deliveries_count || 0) },
			{ label: __("Invoices"), value: cint(kpis.invoices_count || 0) },
			{ label: __("Avg Invoice Value"), value: this.format_currency(kpis.avg_invoice_value) },
		];

		const html = cards
			.map(
				(card) => `
					<div class="ai-kpi-card">
						<div class="ai-kpi-label">${frappe.utils.escape_html(card.label)}</div>
						<div class="ai-kpi-value">${frappe.utils.escape_html(String(card.value))}</div>
					</div>
				`
			)
			.join("");

		this.page.main.find("#ai-kpi-grid").html(html);
	}

	render_risks(risks) {
		if (!risks || !risks.length) {
			this.page.main.find("#ai-risk-list").html(`<div class="text-muted">${__("No risk indicators available.")}</div>`);
			this.page.main.find("#ai-exec-health").text(__("Health: Stable"));
			return;
		}

		const hasRed = risks.some((r) => r.level === "red");
		const hasYellow = risks.some((r) => r.level === "yellow");
		const label = hasRed ? __("Health: High Risk") : hasYellow ? __("Health: Watchlist") : __("Health: Healthy");
		this.page.main.find("#ai-exec-health").text(label);

		const html = risks
			.map(
				(risk) => `
					<div class="ai-risk-item ${frappe.utils.escape_html(risk.level || "yellow")}">
						<div class="ai-risk-dot"></div>
						<div>
							<div class="ai-risk-title">${frappe.utils.escape_html(risk.title || "")}</div>
							<div class="ai-risk-detail">${frappe.utils.escape_html(risk.detail || "")}</div>
						</div>
					</div>
				`
			)
			.join("");

		this.page.main.find("#ai-risk-list").html(html);
	}

	render_charts(trends) {
		const revenue = trends.monthly_revenue || [];
		const pipeline = trends.monthly_opportunities || [];

		const revenueLabels = revenue.map((row) => row.month);
		const revenueValues = revenue.map((row) => flt(row.monthly_revenue || 0));
		const invoiceCounts = revenue.map((row) => cint(row.invoice_count || 0));

		const pipelineLabels = pipeline.map((row) => row.month);
		const pipelineValues = pipeline.map((row) => flt(row.month_pipeline_value || 0));
		const createdOpp = pipeline.map((row) => cint(row.created_opportunities || 0));

		if (this.charts.revenue) {
			this.charts.revenue.destroy();
		}
		if (this.charts.pipeline) {
			this.charts.pipeline.destroy();
		}

		this.charts.revenue = new frappe.Chart("#ai-chart-revenue", {
			title: __("Revenue and Invoices by Month"),
			data: {
				labels: revenueLabels,
				datasets: [
					{ name: __("Revenue"), values: revenueValues },
					{ name: __("Invoices"), values: invoiceCounts },
				],
			},
			type: "axis-mixed",
			height: 240,
			colors: ["#145f7a", "#d99836"],
			axisOptions: {
				xAxisMode: "tick",
				xIsSeries: 1,
			},
		});

		this.charts.pipeline = new frappe.Chart("#ai-chart-pipeline", {
			title: __("Pipeline and Opportunity Creation"),
			data: {
				labels: pipelineLabels,
				datasets: [
					{ name: __("Pipeline Value"), values: pipelineValues },
					{ name: __("Created Opportunities"), values: createdOpp },
				],
			},
			type: "axis-mixed",
			height: 240,
			colors: ["#1b8a72", "#9a5a24"],
			axisOptions: {
				xAxisMode: "tick",
				xIsSeries: 1,
			},
		});
	}

	render_comparative_charts(allAnalytics) {
		const daily = ((allAnalytics || {}).daily || {}).daily_revenue || [];
		const weekly = ((allAnalytics || {}).weekly || {}).weekly_revenue || [];
		const quarterly = ((allAnalytics || {}).quarterly || {}).quarterly_revenue || [];
		const yearly = ((allAnalytics || {}).yearly || {}).yearly_revenue || [];

		const destroy = (key) => {
			if (this.charts[key]) {
				this.charts[key].destroy();
			}
		};
		destroy("daily");
		destroy("weekly");
		destroy("quarterly");
		destroy("yearly");

		this.charts.daily = new frappe.Chart("#ai-chart-daily", {
			title: __("Daily Revenue"),
			data: {
				labels: daily.map((d) => d.date),
				datasets: [{ name: __("Revenue"), values: daily.map((d) => flt(d.daily_revenue || 0)) }],
			},
			type: "line",
			height: 220,
			colors: ["#145f7a"],
		});

		this.charts.weekly = new frappe.Chart("#ai-chart-weekly", {
			title: __("Weekly Revenue"),
			data: {
				labels: weekly.map((w) => w.week),
				datasets: [{ name: __("Revenue"), values: weekly.map((w) => flt(w.weekly_revenue || 0)) }],
			},
			type: "bar",
			height: 220,
			colors: ["#d99836"],
		});

		this.charts.quarterly = new frappe.Chart("#ai-chart-quarterly", {
			title: __("Quarterly Revenue"),
			data: {
				labels: quarterly.map((q) => q.quarter_label),
				datasets: [{ name: __("Revenue"), values: quarterly.map((q) => flt(q.quarterly_revenue || 0)) }],
			},
			type: "bar",
			height: 220,
			colors: ["#1b8a72"],
		});

		this.charts.yearly = new frappe.Chart("#ai-chart-yearly", {
			title: __("Yearly Revenue"),
			data: {
				labels: yearly.map((y) => String(y.year)),
				datasets: [{ name: __("Revenue"), values: yearly.map((y) => flt(y.yearly_revenue || 0)) }],
			},
			type: "bar",
			height: 220,
			colors: ["#9a5a24"],
		});
	}

	render_table(containerId, rows, columns) {
		const target = this.page.main.find(containerId);
		if (!rows || !rows.length) {
			target.html(`<div class="ai-empty">${__("No data in selected period.")}</div>`);
			return;
		}

		const header = columns
			.map((col) => `<th>${frappe.utils.escape_html(col.label)}</th>`)
			.join("");
		const body = rows
			.map((row) => {
				const cells = columns
					.map((col) => {
						const raw = row[col.key];
						const value = col.type === "currency"
							? this.format_currency(raw)
							: col.type === "number"
								? cint(raw || 0)
								: (raw || "-");
						return `<td>${frappe.utils.escape_html(String(value))}</td>`;
					})
					.join("");
				return `<tr>${cells}</tr>`;
			})
			.join("");

		target.html(`<div class="ai-table-wrap"><table class="ai-table"><thead><tr>${header}</tr></thead><tbody>${body}</tbody></table></div>`);
	}

	render_indicators(allAnalytics) {
		const territory = (((allAnalytics || {}).territory || {}).territory_breakdown || [])[0] || {};
		const customers = (((allAnalytics || {}).customers || {}).top_customers || [])[0] || {};
		const items = (((allAnalytics || {}).items || {}).top_items || [])[0] || {};
		const salesperson = (((allAnalytics || {}).salesperson || {}).salesperson_breakdown || [])[0] || {};

		const indicators = [
			{ label: __("Top Territory"), value: territory.territory || "-" },
			{ label: __("Top Customer"), value: customers.customer_name || customers.customer || "-" },
			{ label: __("Top Item"), value: items.item_name || items.item_code || "-" },
			{ label: __("Top Salesperson"), value: salesperson.salesperson || "-" },
		];

		const html = indicators
			.map(
				(item) => `<div class="ai-indicator"><div class="label">${frappe.utils.escape_html(item.label)}</div><div class="value">${frappe.utils.escape_html(item.value || "-")}</div></div>`
			)
			.join("");
		this.page.main.find("#ai-indicator-bar").html(html);
	}

	render_report_tables(allAnalytics) {
		const territory = ((allAnalytics || {}).territory || {}).territory_breakdown || [];
		const salesperson = ((allAnalytics || {}).salesperson || {}).salesperson_breakdown || [];
		const items = ((allAnalytics || {}).items || {}).top_items || [];
		const itemGroups = ((allAnalytics || {}).items || {}).item_groups || [];
		const customers = ((allAnalytics || {}).customers || {}).top_customers || [];
		const customerGroups = ((allAnalytics || {}).customers || {}).customer_groups || [];
		const partners = ((allAnalytics || {}).partners || {}).partners || [];

		this.render_table("#ai-table-territory", territory, [
			{ key: "territory", label: __("Territory") },
			{ key: "opportunity_count", label: __("Opportunities"), type: "number" },
			{ key: "pipeline_value", label: __("Pipeline"), type: "currency" },
		]);

		this.render_table("#ai-table-salesperson", salesperson, [
			{ key: "salesperson", label: __("Salesperson") },
			{ key: "opportunity_count", label: __("Opportunities"), type: "number" },
			{ key: "pipeline_value", label: __("Pipeline"), type: "currency" },
		]);

		this.render_table("#ai-table-items", items, [
			{ key: "item_name", label: __("Item") },
			{ key: "total_qty", label: __("Qty"), type: "number" },
			{ key: "total_amount", label: __("Amount"), type: "currency" },
		]);

		this.render_table("#ai-table-item-groups", itemGroups, [
			{ key: "item_group", label: __("Item Group") },
			{ key: "total_qty", label: __("Qty"), type: "number" },
			{ key: "total_amount", label: __("Amount"), type: "currency" },
		]);

		this.render_table("#ai-table-customers", customers, [
			{ key: "customer_name", label: __("Customer") },
			{ key: "invoice_count", label: __("Invoices"), type: "number" },
			{ key: "total_revenue", label: __("Revenue"), type: "currency" },
		]);

		this.render_table("#ai-table-customer-groups", customerGroups, [
			{ key: "customer_group", label: __("Customer Group") },
			{ key: "invoice_count", label: __("Invoices"), type: "number" },
			{ key: "total_revenue", label: __("Revenue"), type: "currency" },
		]);

		this.render_table("#ai-table-partners", partners, [
			{ key: "partner", label: __("Partner") },
			{ key: "invoice_count", label: __("Invoices"), type: "number" },
			{ key: "total_revenue", label: __("Revenue"), type: "currency" },
		]);
	}

	async refresh() {
		const args = this.get_args();
		if (!args.company) {
			return;
		}

		this.refreshEngineBadge();

		this.page.main.find("#ai-exec-period").text(
			`${args.company} | ${frappe.datetime.str_to_user(args.from_date)} ${__("to")} ${frappe.datetime.str_to_user(args.to_date)}`
		);
		this.page.main.find("#ai-exec-health").text(__("Health: Updating..."));

		try {
			const r = await frappe.call({
				method: "ai_sales_dashboard.api.get_ai_executive_summary_data",
				args,
			});
			const analyticsResp = await frappe.call({
				method: "ai_sales_dashboard.api.get_sales_analytics",
				args,
			});
			const payload = r.message || {};
			const allAnalytics = analyticsResp.message || {};
			this.render_kpis(payload.kpis || {});
			this.render_charts(payload.trends || {});
			this.render_risks(payload.risk_flags || []);
			this.render_indicators(allAnalytics);
			this.render_comparative_charts(allAnalytics);
			this.render_report_tables(allAnalytics);
			this.page.main
				.find("#ai-brief-body")
				.text(__("Dashboard data is ready. Click 'Generate Brief from Dashboard' for Groq-powered management insights."));
			this.page.main.find("#ai-brief-meta").text(__("Provider: Awaiting generation | Model: -"));
		} catch (e) {
			frappe.msgprint({
				title: __("Executive Summary Error"),
				indicator: "red",
				message: __("Could not load full analytics dashboard. Check permissions and server logs."),
			});
		}
	}

	async generateManagementBrief() {
		const args = this.get_args();
		if (!args.company) {
			frappe.msgprint(__("Please select a Company first."));
			return;
		}

		this.page.main.find("#ai-brief-body").text(__("Generating management brief from dashboard analytics..."));
		try {
			const r = await frappe.call({
				method: "ai_sales_dashboard.api.get_ai_sales_summary",
				args,
				freeze: true,
				freeze_message: __("Generating AI management brief..."),
			});
			const result = r.message || {};
			this.page.main.find("#ai-brief-body").text(result.summary || __("No brief returned."));
			this.page.main
				.find("#ai-brief-meta")
				.text(__("Provider: {0} | Model: {1}", [result.provider || "-", result.model || "-"]));
		} catch (e) {
			this.page.main.find("#ai-brief-body").text(
				__("Management brief generation failed. Verify AI settings and try again.")
			);
		}
	}

	pushBriefToChat() {
		const brief = (this.page.main.find("#ai-brief-body").text() || "").trim();
		if (!brief || brief.includes("Generating management brief") || brief.includes("Use current filters")) {
			frappe.show_alert({
				message: __("Generate a brief first, then send it to chat."),
				indicator: "orange",
			});
			return;
		}

		const prompt = __(
			"Use this dashboard brief and produce a sharper 7-day execution plan with owners and priorities:\n\n{0}",
			[brief]
		);
		this.page.main.find("#ai-exec-chat-input").val(prompt);
		frappe.show_alert({
			message: __("Brief copied to chat input."),
			indicator: "green",
		});
	}

	async refreshEngineBadge() {
		try {
			const r = await frappe.call({
				method: "ai_sales_dashboard.api.get_ai_engine_status",
			});
			const status = r.message || {};
			this.page.main.find("#ai-exec-engine").text(status.badge_text || __("Engine: Unknown"));
		} catch (e) {
			this.page.main.find("#ai-exec-engine").text(__("Engine: Unknown"));
		}
	}

	renderChatWelcome() {
		this.chatMessages = [
			{
				role: "assistant",
				text: __(
					"Executive assistant ready. Ask about revenue movement, customer risk concentration, forecast direction, and weekly actions."
				),
			},
		];
		this.page.main.find("#ai-exec-chat-provider").text(__("Provider: Awaiting response"));
		this.renderChatTranscript();
		this.page.main.find("#ai-exec-chat-input").val("");
	}

	renderChatTranscript() {
		const log = this.page.main.find("#ai-exec-chat-log");
		log.empty();

		(this.chatMessages || []).forEach((message) => {
			const safeText = frappe.utils.escape_html(message.text || "").replace(/\n/g, "<br>");
			log.append(`
				<div class="ai-exec-chat-msg ${message.role}">
					<div class="ai-exec-chat-role">${message.role === "assistant" ? __("AI Executive Agent") : __("You")}</div>
					<div>${safeText}</div>
				</div>
			`);
		});

		log.scrollTop(log.prop("scrollHeight"));
	}

	async sendChatMessage() {
		const input = this.page.main.find("#ai-exec-chat-input");
		const message = (input.val() || "").trim();
		if (!message) {
			return;
		}

		const args = this.get_args();
		if (!args.company) {
			frappe.msgprint(__("Please select a Company first."));
			return;
		}

		this.chatMessages.push({ role: "user", text: message });
		this.chatMessages.push({ role: "assistant", text: __("Working on it...") });
		this.renderChatTranscript();
		input.val("");

		try {
			const conversation = this.chatMessages
				.filter((entry) => entry.text && entry.text !== __("Working on it..."))
				.map((entry) => ({ role: entry.role, text: entry.text }));

			const r = await frappe.call({
				method: "ai_sales_dashboard.api.chat_with_ai_sales_agent",
				args: {
					message,
					company: args.company,
					from_date: args.from_date,
					to_date: args.to_date,
					include_context: 1,
					conversation: JSON.stringify(conversation),
				},
				freeze: true,
				freeze_message: __("Generating executive AI response..."),
			});

			const result = r.message || {};
			this.chatMessages[this.chatMessages.length - 1] = {
				role: "assistant",
				text: result.answer || __("No answer returned."),
			};
			this.page.main
				.find("#ai-exec-chat-provider")
				.text(__("Provider: {0} | Model: {1}", [result.provider || "-", result.model || "-"]));
			this.renderChatTranscript();
		} catch (e) {
			this.chatMessages[this.chatMessages.length - 1] = {
				role: "assistant",
				text: __("Executive chatbot request failed. Verify AI settings and server logs."),
			};
			this.renderChatTranscript();
		}
	}

	async generateNarrative() {
		const args = this.get_args();
		this.page.main.find("#ai-narrative").text(__("Generating AI narrative..."));

		try {
			const r = await frappe.call({
				method: "ai_sales_dashboard.api.get_ai_sales_summary",
				args,
			});
			const summary = (r.message || {}).summary || __("No summary returned.");
			this.page.main.find("#ai-narrative").text(summary);
		} catch (e) {
			this.page.main.find("#ai-narrative").text(
				__("AI narrative generation failed. Verify AI settings (provider/model/base URL) and try again.")
			);
		}
	}
}
