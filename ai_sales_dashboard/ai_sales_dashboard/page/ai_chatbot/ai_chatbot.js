frappe.provide("ai_sales_dashboard");

frappe.pages["ai-chatbot"].on_page_load = function (wrapper) {
	new AISalesChatbotPage(wrapper);
};

class AISalesChatbotPage {
	constructor(wrapper) {
		this.wrapper = $(wrapper);
		this.messages = [];
		this.currentSession = null;
		this.sessions = [];

		this.page = frappe.ui.make_app_page({
			parent: wrapper,
			title: __("AI Chatbot"),
			single_column: true,
		});

		this.makeFilters();
		this.renderLayout();
		this.bindActions();
		this.refreshEngineBadge();
		this.renderWelcome();
		this.loadSessions();
		this.applySeedPrompt();
	}

	makeFilters() {
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

	renderLayout() {
		const styleId = "ai-chatbot-page-style";
		if (!document.getElementById(styleId)) {
			$("head").append(`
				<style id="${styleId}">
					.ai-chatbot-shell {
						--ink: #132838;
						--muted: #5f7386;
						--line: #d9e4ee;
						--paper: #ffffff;
						--soft: linear-gradient(140deg, #f7f4ed 0%, #eef5fb 55%, #f9fbff 100%);
						padding: 18px;
						border-radius: 14px;
						background: var(--soft);
						font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
					}
					.ai-chatbot-hero {
						display: flex;
						justify-content: space-between;
						gap: 14px;
						padding: 14px;
						border: 1px solid var(--line);
						border-radius: 12px;
						background: var(--paper);
						margin-bottom: 12px;
					}
					.ai-chatbot-title {
						margin: 0;
						font-size: 1.35rem;
						font-family: "IBM Plex Serif", Georgia, serif;
					}
					.ai-chatbot-subtitle {
						margin-top: 5px;
						color: var(--muted);
					}
					.ai-chatbot-pill {
						padding: 7px 11px;
						border-radius: 999px;
						background: #fff6e8;
						border: 1px solid #f4d4a7;
						color: #8b4a00;
						font-size: 12px;
						font-weight: 600;
						align-self: flex-start;
					}
					.ai-chatbot-body {
						display: grid;
						grid-template-columns: 280px 1fr;
						gap: 12px;
					}
					.ai-chatbot-sessions {
						background: var(--paper);
						border: 1px solid var(--line);
						border-radius: 12px;
						padding: 10px;
					}
					.ai-chatbot-sessions-head {
						display: flex;
						justify-content: space-between;
						align-items: center;
						gap: 8px;
						margin-bottom: 8px;
					}
					.ai-chatbot-sessions-list {
						display: grid;
						gap: 6px;
						max-height: 60vh;
						overflow: auto;
					}
					.ai-chatbot-session {
						border: 1px solid var(--line);
						border-radius: 8px;
						padding: 8px;
						cursor: pointer;
						background: #fbfdff;
					}
					.ai-chatbot-session.active {
						border-color: #a3c6dc;
						background: #f0f8fc;
					}
					.ai-chatbot-session-title {
						font-weight: 600;
						font-size: 12px;
					}
					.ai-chatbot-session-meta {
						font-size: 11px;
						color: var(--muted);
						margin-top: 3px;
					}
					.ai-chatbot-main {
						background: var(--paper);
						border: 1px solid var(--line);
						border-radius: 12px;
						padding: 12px;
					}
					.ai-chatbot-log {
						display: grid;
						gap: 8px;
						min-height: 420px;
						max-height: 62vh;
						overflow: auto;
					}
					.ai-chatbot-msg {
						padding: 10px 12px;
						border-radius: 10px;
						border: 1px solid var(--line);
						line-height: 1.5;
					}
					.ai-chatbot-msg.user {
						background: #f7fbfd;
					}
					.ai-chatbot-msg.assistant {
						background: #112d39;
						color: #f2f8fb;
						border-color: #112d39;
					}
					.ai-chatbot-role {
						font-size: 11px;
						font-weight: 700;
						text-transform: uppercase;
						letter-spacing: 0.06em;
						margin-bottom: 5px;
					}
					.ai-chatbot-input {
						width: 100%;
						min-height: 96px;
						border: 1px solid var(--line);
						border-radius: 10px;
						padding: 10px 12px;
						margin-top: 10px;
						resize: vertical;
						font: inherit;
					}
					.ai-chatbot-actions {
						display: flex;
						justify-content: space-between;
						gap: 8px;
						margin-top: 8px;
						flex-wrap: wrap;
					}
					.ai-chatbot-chips {
						display: flex;
						gap: 6px;
						flex-wrap: wrap;
					}
					.ai-chatbot-chip {
						padding: 7px 10px;
						border-radius: 999px;
						border: 1px solid #d9e8ef;
						background: #f9fcfe;
						font-size: 12px;
						cursor: pointer;
					}
					@media (max-width: 1024px) {
						.ai-chatbot-body {
							grid-template-columns: 1fr;
						}
						.ai-chatbot-sessions-list {
							max-height: 220px;
						}
					}
				</style>
			`);
		}

		this.page.main.html(`
			<div class="ai-chatbot-shell">
				<div class="ai-chatbot-hero">
					<div>
						<h2 class="ai-chatbot-title">${__("AI Chatbot")}</h2>
						<div class="ai-chatbot-subtitle">${__("Chat with your ERPNext sales intelligence in real time.")}</div>
					</div>
					<div class="ai-chatbot-pill" id="ai-chatbot-engine">${__("Engine: Loading...")}</div>
				</div>
				<div class="ai-chatbot-body">
					<div class="ai-chatbot-sessions">
						<div class="ai-chatbot-sessions-head">
							<strong>${__("Sessions")}</strong>
							<button class="btn btn-xs btn-default" id="ai-chatbot-new">${__("New")}</button>
						</div>
						<div class="ai-chatbot-sessions-list" id="ai-chatbot-sessions"></div>
					</div>
					<div class="ai-chatbot-main">
						<div class="ai-chatbot-log" id="ai-chatbot-log"></div>
						<textarea class="ai-chatbot-input" id="ai-chatbot-input" placeholder="${__("Ask anything: Explain profit trend, top risky invoices, best customers, what to do this week...")}"></textarea>
						<div class="ai-chatbot-actions">
							<div class="btn-group">
								<button class="btn btn-primary" id="ai-chatbot-send">${__("Send")}</button>
								<button class="btn btn-default" id="ai-chatbot-clear">${__("Clear")}</button>
							</div>
							<div class="ai-chatbot-chips">
								<button class="ai-chatbot-chip" data-prompt="${__("Summarize business risks this month.")}">${__("Risk Summary")}</button>
								<button class="ai-chatbot-chip" data-prompt="${__("Who are top 5 customers by revenue in this period?")}">${__("Top Customers")}</button>
								<button class="ai-chatbot-chip" data-prompt="${__("Predict next month sales and suggest actions.")}">${__("Sales Forecast")}</button>
							</div>
						</div>
					</div>
				</div>
			</div>
		`);
	}

	bindActions() {
		this.page.set_primary_action(__("Send"), () => this.sendMessage());
		this.page.set_secondary_action(__("Open AI Settings"), () => {
			frappe.set_route("Form", "AI Sales AI Settings", "AI Sales AI Settings");
		});

		this.page.main.on("click", "#ai-chatbot-send", () => this.sendMessage());
		this.page.main.on("click", "#ai-chatbot-clear", () => this.clearConversation());
		this.page.main.on("click", "#ai-chatbot-new", () => this.startNewSession());
		this.page.main.on("click", ".ai-chatbot-session", (event) => {
			const name = $(event.currentTarget).attr("data-name");
			if (name && !$(event.target).closest("button").length) {
				this.openSession(name);
			}
		});
		this.page.main.on("click", ".ai-chatbot-archive", (event) => {
			event.stopPropagation();
			const name = $(event.currentTarget).attr("data-name");
			this.archiveSession(name);
		});
		this.page.main.on("click", ".ai-chatbot-delete", (event) => {
			event.stopPropagation();
			const name = $(event.currentTarget).attr("data-name");
			this.deleteSession(name);
		});
		this.page.main.on("click", ".ai-chatbot-chip", (event) => {
			const prompt = $(event.currentTarget).attr("data-prompt");
			this.page.main.find("#ai-chatbot-input").val(prompt);
			this.sendMessage();
		});
		this.page.main.on("keydown", "#ai-chatbot-input", (event) => {
			if (event.key === "Enter" && !event.shiftKey) {
				event.preventDefault();
				this.sendMessage();
			}
		});
	}

	renderWelcome() {
		this.messages = [
			{
				role: "assistant",
				text: __(
					"Hi. I can summarize revenue, risk flags, customer concentration, and next actions. Ask a question to begin."
				),
			},
		];
		this.renderTranscript();
	}

	renderSessions() {
		const wrap = this.page.main.find("#ai-chatbot-sessions");
		if (!wrap.length) return;
		wrap.empty();
		if (!this.sessions.length) {
			wrap.html(`<div class="text-muted small">${__("No saved sessions yet.")}</div>`);
			return;
		}
		this.sessions.forEach((session) => {
			const activeClass = session.name === this.currentSession ? "active" : "";
			const title = frappe.utils.escape_html(session.title || session.name || __("Untitled"));
			const meta = [session.company, session.provider].filter(Boolean).join(" | ");
			wrap.append(`
				<div class="ai-chatbot-session ${activeClass}" data-name="${session.name}">
					<div>
						<div class="ai-chatbot-session-title">${title}</div>
						<div class="ai-chatbot-session-meta">${frappe.utils.escape_html(meta || __("General"))}</div>
					</div>
					<div style="display: flex; gap: 4px; margin-top: 6px;">
						<button class="btn btn-xs btn-default ai-chatbot-archive" title="${__("Archive")}" data-name="${session.name}">
							<i class="fa fa-archive"></i>
						</button>
						<button class="btn btn-xs btn-danger ai-chatbot-delete" title="${__("Delete")}" data-name="${session.name}">
							<i class="fa fa-trash"></i>
						</button>
					</div>
				</div>
			`);
		});
	}

	renderTranscript() {
		const log = this.page.main.find("#ai-chatbot-log");
		log.empty();
		(this.messages || []).forEach((message) => {
			const safeText = frappe.utils.escape_html(message.text || "").replace(/\n/g, "<br>");
			log.append(`
				<div class="ai-chatbot-msg ${message.role}">
					<div class="ai-chatbot-role">${message.role === "assistant" ? __("AI Chatbot") : __("You")}</div>
					<div>${safeText}</div>
				</div>
			`);
		});
		log.scrollTop(log.prop("scrollHeight"));
	}

	async refreshEngineBadge() {
		try {
			const r = await frappe.call({
				method: "ai_sales_dashboard.api.get_ai_engine_status",
			});
			const result = r.message || {};
			const provider = result.provider || "Unknown";
			const mode = result.mode || (result.is_offline ? "Offline" : "Online");
			this.engineProvider = provider;
			this.engineMode = mode;
			this.page.main.find("#ai-chatbot-engine").text(`Engine: ${provider} (${mode})`);
		} catch (e) {
			this.page.main.find("#ai-chatbot-engine").text("Engine: Unknown");
		}
	}

	async loadSessions() {
		try {
			const r = await frappe.call({ method: "ai_sales_dashboard.api.list_ai_chat_sessions" });
			this.sessions = (r.message || {}).sessions || [];
			this.renderSessions();
		} catch (e) {
			this.sessions = [];
			this.renderSessions();
		}
	}

	async openSession(name) {
		try {
			const r = await frappe.call({
				method: "ai_sales_dashboard.api.get_ai_chat_session",
				args: { session_name: name },
			});
			const session = (r.message || {}).session || {};
			this.currentSession = session.name || name;
			if (session.company) this.companyField.set_value(session.company);
			if (session.from_date) this.fromDateField.set_value(session.from_date);
			if (session.to_date) this.toDateField.set_value(session.to_date);
			this.messages = (session.messages || []).map((m) => ({ role: m.role, text: m.text }));
			if (!this.messages.length) {
				this.renderWelcome();
			} else {
				this.renderTranscript();
			}
			this.renderSessions();
		} catch (e) {
			frappe.msgprint(__("Could not load the selected session."));
		}
	}

	async archiveSession(name) {
		if (!frappe.confirm(__("Archive this session? You can restore it later."))) {
			return;
		}
		try {
			await frappe.call({
				method: "ai_sales_dashboard.api.archive_ai_chat_session",
				args: { session_name: name },
				freeze: true,
				freeze_message: __("Archiving..."),
			});
			frappe.show_alert({
				indicator: "green",
				message: __("Session archived successfully."),
			});
			if (this.currentSession === name) {
				this.startNewSession();
			}
			this.loadSessions();
		} catch (e) {
			frappe.msgprint(__("Could not archive the session. Please try again."));
		}
	}

	async deleteSession(name) {
		if (
			!frappe.confirm(
				__(
					"Delete this session permanently? This action cannot be undone and all messages will be lost."
				)
			)
		) {
			return;
		}
		try {
			await frappe.call({
				method: "ai_sales_dashboard.api.delete_ai_chat_session",
				args: { session_name: name },
				freeze: true,
				freeze_message: __("Deleting..."),
			});
			frappe.show_alert({
				indicator: "green",
				message: __("Session deleted successfully."),
			});
			if (this.currentSession === name) {
				this.startNewSession();
			}
			this.loadSessions();
		} catch (e) {
			frappe.msgprint(__("Could not delete the session. Please try again."));
		}
	}

	startNewSession() {
		this.currentSession = null;
		this.renderWelcome();
		this.renderSessions();
		this.page.main.find("#ai-chatbot-input").val("");
	}

	applySeedPrompt() {
		const key = "ai_sales_dashboard_chat_seed";
		const autoSendKey = "ai_sales_dashboard_chat_auto_send";
		const prompt = window.localStorage.getItem(key);
		const autoSend = window.localStorage.getItem(autoSendKey) === "true";

		if (prompt) {
			window.localStorage.removeItem(key);
			window.localStorage.removeItem(autoSendKey);
			this.page.main.find("#ai-chatbot-input").val(prompt);
			if (autoSend) {
				setTimeout(() => this.sendMessage(), 300);
			}
		}
	}

	async sendMessage() {
		const input = this.page.main.find("#ai-chatbot-input");
		const message = (input.val() || "").trim();
		if (!message) {
			return;
		}
		if (!this.companyField.get_value()) {
			frappe.msgprint(__("Please select a Company first."));
			return;
		}

		this.messages.push({ role: "user", text: message });
		this.messages.push({ role: "assistant", text: __("Thinking...") });
		this.renderTranscript();
		input.val("");

		try {
			const conversation = this.messages
				.filter((entry) => entry.text && entry.text !== __("Thinking..."))
				.map((entry) => ({ role: entry.role, text: entry.text }));

			const r = await frappe.call({
				method: "ai_sales_dashboard.api.chat_with_ai_sales_agent",
				args: {
					message,
					company: this.companyField.get_value(),
					from_date: this.fromDateField.get_value(),
					to_date: this.toDateField.get_value(),
					include_context: this.contextField.get_value() ? 1 : 0,
					conversation: JSON.stringify(conversation),
					session_name: this.currentSession,
				},
				freeze: true,
				freeze_message: __("Generating response..."),
			});

			const result = r.message || {};
			if (result.session_name) {
				this.currentSession = result.session_name;
			}
			this.messages[this.messages.length - 1] = {
				role: "assistant",
				text: result.answer || __("No answer returned."),
			};
			this.renderTranscript();
			this.loadSessions();

			// Update engine badge based on actual response
			if (result.provider) {
				const provider = result.provider || this.engineProvider || "Unknown";
				const isOfflineProvider = ["statistical engine", "ollama"].includes((provider || "").toLowerCase());
				const mode = isOfflineProvider ? "Offline" : "Online";
				this.engineProvider = provider;
				this.engineMode = mode;
				this.page.main.find("#ai-chatbot-engine").text(`Engine: ${provider} (${mode})`);
			}
		} catch (e) {
			this.messages[this.messages.length - 1] = {
				role: "assistant",
				text: __("Chatbot request failed. Please verify AI settings and server logs."),
			};
			this.renderTranscript();
		}
	}

	clearConversation() {
		this.startNewSession();
		this.page.main.find("#ai-chatbot-input").val("");
		this.refreshEngineBadge();
	}
}
