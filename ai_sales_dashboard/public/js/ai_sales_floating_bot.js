(() => {
	const STYLE_ID = "ai-sales-floating-bot-style";
	const WRAP_ID = "ai-sales-floating-bot";

	function injectStyle() {
		if (document.getElementById(STYLE_ID)) return;
		const style = document.createElement("style");
		style.id = STYLE_ID;
		style.textContent = `
			#${WRAP_ID} {
				position: fixed;
				right: 18px;
				bottom: 18px;
				z-index: 1000;
				font-family: "IBM Plex Sans", "Segoe UI", sans-serif;
			}
			#${WRAP_ID} .ai-sales-bot-btn {
				background: linear-gradient(135deg, #0f3a4e 0%, #1a6685 100%);
				color: #fff;
				border: none;
				border-radius: 999px;
				padding: 10px 14px;
				box-shadow: 0 10px 26px rgba(12, 40, 54, 0.25);
				font-weight: 600;
				cursor: pointer;
			}
			#${WRAP_ID} .ai-sales-bot-panel {
				margin-bottom: 8px;
				width: 300px;
				background: #ffffff;
				border: 1px solid #d8e6ee;
				border-radius: 12px;
				padding: 10px;
				box-shadow: 0 16px 32px rgba(13, 36, 47, 0.2);
				display: none;
			}
			#${WRAP_ID}.open .ai-sales-bot-panel {
				display: block;
			}
			#${WRAP_ID} .ai-sales-bot-panel textarea {
				width: 100%;
				min-height: 80px;
				border: 1px solid #cfdde6;
				border-radius: 8px;
				padding: 8px;
				resize: vertical;
			}
			#${WRAP_ID} .ai-sales-bot-actions {
				display: flex;
				justify-content: space-between;
				gap: 8px;
				margin-top: 8px;
			}
			@media (max-width: 768px) {
				#${WRAP_ID} {
					right: 10px;
					bottom: 10px;
				}
				#${WRAP_ID} .ai-sales-bot-panel {
					width: min(90vw, 320px);
				}
			}
		`;
		document.head.appendChild(style);
	}

	function buildWidget() {
		if (document.getElementById(WRAP_ID)) return;
		const wrap = document.createElement("div");
		wrap.id = WRAP_ID;
		wrap.innerHTML = `
			<div class="ai-sales-bot-panel">
				<div style="font-weight:600;margin-bottom:6px;">AI Sales Bot</div>
				<textarea id="ai-sales-bot-seed" placeholder="Ask about risk, revenue trend, top customers..."></textarea>
				<div class="ai-sales-bot-actions">
					<button class="btn btn-default btn-sm" id="ai-sales-bot-open">Open Chat</button>
					<button class="btn btn-primary btn-sm" id="ai-sales-bot-send">Ask</button>
				</div>
			</div>
			<button class="ai-sales-bot-btn" id="ai-sales-bot-toggle">AI Chat</button>
		`;
		document.body.appendChild(wrap);

		wrap.querySelector("#ai-sales-bot-toggle").addEventListener("click", () => {
			wrap.classList.toggle("open");
		});

		const openChat = () => {
			const seed = (wrap.querySelector("#ai-sales-bot-seed").value || "").trim();
			if (seed) {
				window.localStorage.setItem("ai_sales_dashboard_chat_seed", seed);
			}
			frappe.set_route("ai-chatbot");
		};

		const askQuestion = () => {
			const seed = (wrap.querySelector("#ai-sales-bot-seed").value || "").trim();
			if (!seed) {
				frappe.msgprint("Please ask a question first.");
				return;
			}
			window.localStorage.setItem("ai_sales_dashboard_chat_seed", seed);
			window.localStorage.setItem("ai_sales_dashboard_chat_auto_send", "true");
			frappe.set_route("ai-chatbot");
		};

		wrap.querySelector("#ai-sales-bot-open").addEventListener("click", openChat);
		wrap.querySelector("#ai-sales-bot-send").addEventListener("click", askQuestion);
	}

	function boot() {
		injectStyle();
		buildWidget();
	}

	frappe.after_ajax(() => {
		if (!frappe.session || frappe.session.user === "Guest") return;
		boot();
	});
})();
