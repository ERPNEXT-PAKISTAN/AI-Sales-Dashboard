frappe.provide("ai_sales_dashboard");

frappe.pages["ai-sales-agent"].on_page_load = function (wrapper) {
	new AISalesAgentPage(wrapper);
};

class AISalesAgentPage {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.messages = [];

		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("AI Sales Agent"),
			single_column: true,
		});

		this.make_filters();
		this.render_layout();
		this.bind_actions();
		this.refreshEngineBadge();
		this.renderWelcome();
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
		});

		this.fromDateField = this.page.add_field({
			label: __("From"),
			fieldtype: "Date",
			fieldname: "from_date",
			default: fromDate,
		});

		this.toDateField = this.page.add_field({
			label: __("To"),
			fieldtype: "Date",
			fieldname: "to_date",
			default: today,
		});

		this.contextField = this.page.add_field({
			label: __("Use Live Sales Context"),
			fieldtype: "Check",
			fieldname: "include_context",
			default: 1,
		});
	}

	render_layout() {
		const styleId = "ai-sales-agent-style";
		if (!document.getElementById(styleId)) {
			$("head").append(`
				<style id="${styleId}">
					.ai-agent-shell {
						--ink: #142433;
						--muted: #627488;
						--line: #d8e3ec;
						--paper: #ffffff;
						--brand: #0d6a7c;
						--accent: #d27f2c;
						--soft: linear-gradient(135deg, #f7f4ec 0%, #edf5fb 60%, #f9fbff 100%);
						padding: 18px;
						border-radius: 16px;
						background: var(--soft);
						font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
					}
					.ai-agent-hero {
						display: flex;
						justify-content: space-between;
						gap: 16px;
						padding: 18px;
						background: var(--paper);
						border: 1px solid var(--line);
						border-radius: 14px;
						box-shadow: 0 10px 22px rgba(20, 36, 51, 0.05);
						margin-bottom: 14px;
					}
					.ai-agent-title {
						margin: 0;
						font-family: "IBM Plex Serif", Georgia, serif;
						font-size: 1.45rem;
						font-weight: 600;
					}
					.ai-agent-subtitle {
						margin-top: 6px;
						color: var(--muted);
						max-width: 720px;
					}
					.ai-agent-pill {
						padding: 8px 12px;
						border-radius: 999px;
						background: #eef8fb;
						color: var(--brand);
						font-weight: 600;
						align-self: flex-start;
					}
					.ai-agent-status-stack {
						display: grid;
						gap: 8px;
						justify-items: end;
					}
					.ai-agent-engine-badge {
						padding: 7px 11px;
						border-radius: 999px;
						background: #fff6e8;
						border: 1px solid #f4d4a7;
						color: #8b4a00;
						font-size: 12px;
						font-weight: 600;
					}
					.ai-agent-body {
						display: grid;
						grid-template-columns: 1.4fr 0.8fr;
						gap: 14px;
					}
					.ai-agent-panel {
						background: var(--paper);
						border: 1px solid var(--line);
						border-radius: 14px;
						padding: 14px;
					}
					.ai-agent-panel h4 {
						margin: 0 0 10px;
						font-size: 12px;
						letter-spacing: 0.06em;
						text-transform: uppercase;
						color: var(--muted);
					}
					.ai-agent-transcript {
						display: grid;
						gap: 10px;
						min-height: 460px;
						max-height: 60vh;
						overflow: auto;
						padding-right: 4px;
					}
					.ai-agent-message {
						padding: 12px 14px;
						border-radius: 12px;
						border: 1px solid var(--line);
						line-height: 1.55;
						white-space: normal;
					}
					.ai-agent-message.user {
						background: #f7fbfd;
						border-color: #d5e7ee;
					}
					.ai-agent-message.assistant {
						background: #112d39;
						border-color: #112d39;
						color: #f3f8fb;
					}
					.ai-agent-role {
						font-size: 11px;
						font-weight: 700;
						letter-spacing: 0.06em;
						text-transform: uppercase;
						margin-bottom: 6px;
					}
					.ai-agent-composer textarea {
						width: 100%;
						min-height: 112px;
						border-radius: 12px;
						border: 1px solid var(--line);
						padding: 12px 14px;
						resize: vertical;
						font: inherit;
					}
					.ai-agent-actions {
						display: flex;
						justify-content: space-between;
						gap: 10px;
						margin-top: 10px;
					}
					.ai-agent-actions .btn-group {
						display: flex;
						gap: 8px;
						flex-wrap: wrap;
					}
					.ai-agent-chip-list {
						display: flex;
						gap: 8px;
						flex-wrap: wrap;
					}
					.ai-agent-chip {
						padding: 8px 10px;
						border-radius: 999px;
						border: 1px solid #d9e8ef;
						background: #f9fcfe;
						font-size: 12px;
						cursor: pointer;
					}
					.ai-agent-meta {
						display: grid;
						gap: 10px;
					}
					.ai-agent-stat {
						padding: 12px;
						border: 1px solid var(--line);
						border-radius: 12px;
						background: #fbfdff;
					}
					.ai-agent-stat-label {
						font-size: 11px;
						letter-spacing: 0.06em;
						text-transform: uppercase;
						color: var(--muted);
					}
					.ai-agent-stat-value {
						font-family: "IBM Plex Serif", Georgia, serif;
						font-size: 1.2rem;
						margin-top: 4px;
					}
					.ai-agent-risk {
						padding: 10px 12px;
						border-radius: 10px;
						font-size: 12px;
					}
					.ai-agent-risk.red {
						background: #fff1f2;
						color: #b42318;
					}
					.ai-agent-risk.yellow {
						background: #fff8e6;
						color: #a15c00;
					}
					.ai-agent-risk.green {
						background: #edf9f1;
						color: #1f7a45;
					}
					@media (max-width: 980px) {
						.ai-agent-body {
							grid-template-columns: 1fr;
						}
					}
				</style>
			`);
		}

		this.page.main.html(`
			<div class="ai-agent-shell">
				<div class="ai-agent-hero">
					<div>
						<h2 class="ai-agent-title">${__("AI Sales Agent")}</h2>
						<div class="ai-agent-subtitle">${__("Ask questions about pipeline risk, revenue momentum, customers, salespeople, and next actions. The agent uses the same AI provider settings as your executive narrative.")}</div>
					</div>
					<div class="ai-agent-status-stack">
						<div class="ai-agent-pill" id="ai-agent-provider">${__("Awaiting provider")}</div>
						<div class="ai-agent-engine-badge" id="ai-agent-engine-badge">${__("Engine: Loading...")}</div>
					</div>
				</div>
				<div class="ai-agent-body">
					<div class="ai-agent-panel">
						<h4>${__("Conversation")}</h4>
						<div class="ai-agent-transcript" id="ai-agent-transcript"></div>
						<div class="ai-agent-composer">
							<textarea id="ai-agent-input" placeholder="${__("Ask: Which customers are driving concentration risk? Where is revenue slipping? What should my sales team do this week?")}"></textarea>
							<div class="ai-agent-actions">
								<div class="btn-group">
									<button class="btn btn-primary" id="ai-agent-send">${__("Send")}</button>
									<button class="btn btn-default" id="ai-agent-clear">${__("Clear")}</button>
								</div>
								<div class="ai-agent-chip-list">
									<button class="ai-agent-chip" data-prompt="${__("Summarize the biggest revenue and pipeline risks for this period.")}">${__("Risk Summary")}</button>
									<button class="ai-agent-chip" data-prompt="${__("Which customers and salespeople need immediate attention?")}">${__("Who Needs Attention")}</button>
									<button class="ai-agent-chip" data-prompt="${__("Give me 5 concrete actions for this sales team this week.")}">${__("Weekly Actions")}</button>
								</div>
							</div>
						</div>
					</div>
					<div class="ai-agent-panel">
						<h4>${__("Live Context")}</h4>
						<div class="ai-agent-meta" id="ai-agent-meta">
							<div class="ai-agent-stat">
								<div class="ai-agent-stat-label">${__("Company")}</div>
								<div class="ai-agent-stat-value" id="ai-agent-company">-</div>
							</div>
							<div class="ai-agent-stat">
								<div class="ai-agent-stat-label">${__("Booked Revenue")}</div>
								<div class="ai-agent-stat-value" id="ai-agent-revenue">-</div>
							</div>
							<div class="ai-agent-stat">
								<div class="ai-agent-stat-label">${__("Win Rate")}</div>
								<div class="ai-agent-stat-value" id="ai-agent-winrate">-</div>
							</div>
							<div id="ai-agent-risks"></div>
						</div>
					</div>
				</div>
			</div>
		`);
	}

	bind_actions() {
		this.page.set_primary_action(__("Send"), () => this.sendMessage());
		this.page.set_secondary_action(__("Open AI Settings"), () => {
			frappe.set_route("Form", "AI Sales AI Settings", "AI Sales AI Settings");
		});

		this.page.main.on("click", "#ai-agent-send", () => this.sendMessage());
		this.page.main.on("click", "#ai-agent-clear", () => this.clearConversation());
		this.page.main.on("click", ".ai-agent-chip", (event) => {
			const prompt = $(event.currentTarget).attr("data-prompt");
			this.page.main.find("#ai-agent-input").val(prompt);
			this.sendMessage();
		});
		this.page.main.on("keydown", "#ai-agent-input", (event) => {
			if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
				event.preventDefault();
				this.sendMessage();
			}
		});
	}

	renderWelcome() {
		this.messages = [
			{
				role: "assistant",
				text: __("Ask for a revenue summary, risk diagnosis, customer concentration view, or a concrete action plan. Use Ctrl+Enter to send."),
			},
		];
		this.renderTranscript();
	}

	renderTranscript() {
		const transcript = this.page.main.find("#ai-agent-transcript");
		transcript.empty();

		(this.messages || []).forEach((message) => {
			const safeText = frappe.utils.escape_html(message.text || "").replace(/\n/g, "<br>");
			transcript.append(`
				<div class="ai-agent-message ${message.role}">
					<div class="ai-agent-role">${message.role === "assistant" ? __("AI Sales Agent") : __("You")}</div>
					<div>${safeText}</div>
				</div>
			`);
		});

		transcript.scrollTop(transcript.prop("scrollHeight"));
	}

	renderSidebar(result) {
		this.page.main.find("#ai-agent-provider").text(`${result.provider || "-"} • ${result.model || "-"}`);
		const mode = (result.provider || "").toLowerCase().includes("statistical") || (result.provider || "").toLowerCase().includes("ollama")
			? __("Offline")
			: __("Online");
		this.page.main
			.find("#ai-agent-engine-badge")
			.text(__("Engine: {0} ({1})", [result.provider || "Unknown", mode]));
		this.page.main.find("#ai-agent-company").text(result.company || "-");
		this.page.main.find("#ai-agent-revenue").text(this.formatCurrency(result.kpi?.booked_revenue || 0));
		this.page.main.find("#ai-agent-winrate").text(`${frappe.format(result.kpi?.win_rate_percent || 0, { fieldtype: "Percent" })}`);

		const risks = this.page.main.find("#ai-agent-risks");
		risks.empty();
		(result.risk_flags || []).forEach((risk) => {
			risks.append(`
				<div class="ai-agent-risk ${risk.level || "yellow"}">
					<strong>${frappe.utils.escape_html(risk.title || "")}</strong><br>
					${frappe.utils.escape_html(risk.detail || "")}
				</div>
			`);
		});
	}

	async sendMessage() {
		const input = this.page.main.find("#ai-agent-input");
		const message = (input.val() || "").trim();
		if (!message) {
			return;
		}

		this.messages.push({ role: "user", text: message });
		this.messages.push({ role: "assistant", text: __("Working on it...") });
		this.renderTranscript();
		input.val("");

		try {
			const conversation = this.messages
				.filter((entry) => entry.text && entry.text !== __("Working on it..."))
				.map((entry) => ({ role: entry.role, text: entry.text }));

			const response = await frappe.call({
				method: "ai_sales_dashboard.api.chat_with_ai_sales_agent",
				args: {
					message,
					company: this.companyField.get_value(),
					from_date: this.fromDateField.get_value(),
					to_date: this.toDateField.get_value(),
					include_context: this.contextField.get_value() ? 1 : 0,
					conversation: JSON.stringify(conversation),
				},
				freeze: true,
				freeze_message: __("Generating AI sales answer..."),
			});

			const result = response.message || {};
			this.messages[this.messages.length - 1] = {
				role: "assistant",
				text: result.answer || __("No answer returned."),
			};
			this.renderTranscript();
			this.renderSidebar(result);
		} catch (error) {
			this.messages[this.messages.length - 1] = {
				role: "assistant",
				text: __("The AI sales agent request failed. Review provider settings, model access, and server logs."),
			};
			this.renderTranscript();
		}
	}

	clearConversation() {
		this.renderWelcome();
		this.page.main.find("#ai-agent-input").val("");
		this.page.main.find("#ai-agent-provider").text(__("Awaiting provider"));
		this.refreshEngineBadge();
		this.page.main.find("#ai-agent-company").text("-");
		this.page.main.find("#ai-agent-revenue").text("-");
		this.page.main.find("#ai-agent-winrate").text("-");
		this.page.main.find("#ai-agent-risks").empty();
	}

	async refreshEngineBadge() {
		try {
			const r = await frappe.call({
				method: "ai_sales_dashboard.api.get_ai_engine_status",
			});
			const status = r.message || {};
			this.page.main.find("#ai-agent-engine-badge").text(status.badge_text || __("Engine: Unknown"));
		} catch (e) {
			this.page.main.find("#ai-agent-engine-badge").text(__("Engine: Unknown"));
		}
	}

	formatCurrency(value) {
		return format_currency(value || 0, frappe.defaults.get_default("currency") || "USD");
	}
}