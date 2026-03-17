async function loadProviderCatalog(frm) {
	if (frm._providerCatalog) {
		return frm._providerCatalog;
	}
	const response = await frappe.call({
		method: "ai_sales_dashboard.api.get_ai_provider_profiles",
	});
	frm._providerCatalog = response.message || {};
	return frm._providerCatalog;
}

function getProviderEntry(catalog, providerLabel) {
	return (catalog?.providers || []).find((entry) => entry.label === providerLabel);
}

function syncProviderOptions(frm, catalog) {
	const labels = (catalog?.providers || []).map((entry) => entry.label).filter(Boolean);
	if (!labels.length) {
		return;
	}
	frm.set_df_property("provider", "options", labels.join("\n"));
	if (!labels.includes(frm.doc.provider || "")) {
		frm.set_value("provider", labels[0]);
	}
	frm.refresh_field("provider");
}

function updateProviderHelpNotes(frm, providerEntry) {
	if (!providerEntry) {
		return;
	}

	const providerLabel = providerEntry.label || __("Selected Provider");
	const freeTierText = providerEntry.free_tier
		? __("Free tier: {0}", [providerEntry.free_tier])
		: "";

	frm.set_df_property(
		"provider",
		"description",
		__("Auto-fills the recommended defaults for this provider. {0}", [freeTierText]).trim()
	);
	frm.set_df_property(
		"model",
		"description",
		__("Recommended {0} model: {1}", [providerLabel, providerEntry.model || __("Set manually")])
	);
	frm.set_df_property(
		"base_url",
		"description",
		__("Recommended {0} Base URL: {1}", [providerLabel, providerEntry.base_url || __("Set manually")])
	);

	const needsKey = !!providerEntry.requires_api_key;
	frm.set_df_property(
		"api_key",
		"description",
		needsKey
			? __("Required for {0}. {1}", [providerLabel, providerEntry.credential_hint || __("Paste your provider API key.")])
			: __("No API key needed for {0}. {1}", [providerLabel, providerEntry.credential_hint || ""])
	);

	frm.refresh_field("provider");
	frm.refresh_field("model");
	frm.refresh_field("base_url");
	frm.refresh_field("api_key");
}

function renderProviderDocumentationLink(frm, providerEntry) {
	const url = providerEntry?.documentation_url || "";
	const freeTierText = providerEntry?.free_tier || "";
	const field = frm.fields_dict.provider_documentation_url;
	if (!field?.$wrapper) {
		return;
	}

	frm.doc.provider_documentation_url = url;

	field.$wrapper.find(".ai-provider-doc-link").remove();

	const descriptionParts = [];
	if (freeTierText) {
		descriptionParts.push(__("Free tier: {0}", [freeTierText]));
	}
	if (url) {
		descriptionParts.push(
			__(
				'<a href="{0}" target="_blank" rel="noopener noreferrer">Open provider docs in new tab</a>',
				[frappe.utils.escape_html(url)]
			)
		);
	}

	frm.set_df_property(
		"provider_documentation_url",
		"description",
		descriptionParts.join("<br>") || __("No documentation link available for this provider.")
	);

	if (url) {
		field.$wrapper.find(".control-input-wrapper").append(`
			<div class="ai-provider-doc-link" style="margin-top:8px;">
				<a class="btn btn-default btn-xs" href="${frappe.utils.escape_html(url)}" target="_blank" rel="noopener noreferrer">
					${__("Open Provider Docs")}
				</a>
			</div>
		`);
	}

	frm.refresh_field("provider_documentation_url");
}

function renderQuickProviderActions(frm) {
	const providerField = frm.fields_dict.provider;
	if (!providerField?.$wrapper) {
		return;
	}

	providerField.$wrapper.find(".ai-provider-quick-actions").remove();

	const actions = $(`
		<div class="ai-provider-quick-actions" style="margin-top:8px; display:flex; gap:8px; flex-wrap:wrap;">
			<button type="button" class="btn btn-default btn-xs" data-provider="Statistical Engine">${__("Apply Statistical Defaults")}</button>
			<button type="button" class="btn btn-default btn-xs" data-provider="Ollama">${__("Apply Ollama Defaults")}</button>
			<button type="button" class="btn btn-default btn-xs" data-provider="Gemini">${__("Apply Gemini Defaults")}</button>
			<button type="button" class="btn btn-default btn-xs" data-provider="Hugging Face">${__("Apply Hugging Face Defaults")}</button>
		</div>
	`);

	actions.on("click", "button[data-provider]", async (event) => {
		event.preventDefault();
		const provider = $(event.currentTarget).attr("data-provider");
		await frm.set_value("provider", provider);
		await applyProviderDefaults(frm, { force: true });
		frappe.show_alert({
			message: __("Applied {0} defaults.", [provider]),
			indicator: "green",
		});
	});

	providerField.$wrapper.append(actions);
}

function getSavedProviderLabels(frm) {
	return (frm.doc.saved_providers || []).map((row) => row.profile_label).filter(Boolean);
}

function renderSavedProviderNotes(frm) {
	const rows = frm.doc.saved_providers || [];
	const active = rows.find((row) => cint(row.is_active));
	const note = rows.length
		? __("Saved profiles: {0}. Active profile: {1}", [rows.length, active?.profile_label || __("None")])
		: __("No saved provider profiles yet. Save the current provider setup to switch between keys without overwriting.");
	frm.set_df_property("saved_providers", "description", note);
	frm.refresh_field("saved_providers");
}

function addSavedProviderButtons(frm) {
	frm.add_custom_button(__("Save Current Provider"), () => {
		const dialog = new frappe.ui.Dialog({
			title: __("Save Current Provider"),
			fields: [
				{
					label: __("Profile Label"),
					fieldname: "profile_label",
					fieldtype: "Data",
					default: `${frm.doc.provider || __("Provider")} - ${frm.doc.model || __("Default Model")}`,
					reqd: 1,
				},
				{
					label: __("Overwrite if exists"),
					fieldname: "overwrite",
					fieldtype: "Check",
					default: 1,
				},
			],
			primary_action_label: __("Save"),
			async primary_action(values) {
				await frappe.call({
					method: "ai_sales_dashboard.api.save_current_ai_provider_profile",
					args: values,
					freeze: true,
					freeze_message: __("Saving provider profile..."),
				});
				dialog.hide();
				await frm.reload_doc();
				frappe.show_alert({
					message: __("Saved provider profile: {0}", [values.profile_label]),
					indicator: "green",
				});
			},
		});
		dialog.show();
	}, __("Saved Providers"));

	frm.add_custom_button(__("Load Saved Provider"), () => {
		const options = getSavedProviderLabels(frm);
		if (!options.length) {
			frappe.msgprint(__("No saved provider profiles found."));
			return;
		}

		const dialog = new frappe.ui.Dialog({
			title: __("Load Saved Provider"),
			fields: [
				{
					label: __("Saved Profile"),
					fieldname: "profile_label",
					fieldtype: "Select",
					options: options.join("\n"),
					reqd: 1,
				},
			],
			primary_action_label: __("Load"),
			async primary_action(values) {
				await frappe.call({
					method: "ai_sales_dashboard.api.load_saved_ai_provider",
					args: values,
					freeze: true,
					freeze_message: __("Loading saved provider..."),
				});
				dialog.hide();
				await frm.reload_doc();
				frappe.show_alert({
					message: __("Loaded provider profile: {0}", [values.profile_label]),
					indicator: "green",
				});
			},
		});
		dialog.show();
	}, __("Saved Providers"));

	frm.add_custom_button(__("Delete Saved Provider"), () => {
		const options = getSavedProviderLabels(frm);
		if (!options.length) {
			frappe.msgprint(__("No saved provider profiles found."));
			return;
		}

		const dialog = new frappe.ui.Dialog({
			title: __("Delete Saved Provider"),
			fields: [
				{
					label: __("Saved Profile"),
					fieldname: "profile_label",
					fieldtype: "Select",
					options: options.join("\n"),
					reqd: 1,
				},
			],
			primary_action_label: __("Delete"),
			async primary_action(values) {
				await frappe.call({
					method: "ai_sales_dashboard.api.delete_saved_ai_provider",
					args: values,
					freeze: true,
					freeze_message: __("Deleting saved provider..."),
				});
				dialog.hide();
				await frm.reload_doc();
				frappe.show_alert({
					message: __("Deleted provider profile: {0}", [values.profile_label]),
					indicator: "orange",
				});
			},
		});
		dialog.show();
	}, __("Saved Providers"));

	frm.add_custom_button(__("Test Saved Providers"), async () => {
		frappe.show_alert({ message: __("Testing all saved provider profiles..."), indicator: "blue" });
		const r = await frappe.call({
			method: "ai_sales_dashboard.api.test_saved_ai_provider_profiles",
			freeze: true,
			freeze_message: __("Running provider checks..."),
		});
		const payload = r.message || {};
		const rows = payload.results || [];
		const table = rows.length
			? `
				<table class="table table-bordered" style="margin-top:8px; font-size:12px;">
					<thead>
						<tr>
							<th>${__("Profile")}</th>
							<th>${__("Provider")}</th>
							<th>${__("Model")}</th>
							<th>${__("Status")}</th>
							<th>${__("Detail")}</th>
						</tr>
					</thead>
					<tbody>
						${rows
							.map((row) => {
								const status = row.ok ? "OK" : "FAILED";
								const detail = row.ok ? row.preview || "Connection verified" : row.error || "Unknown error";
								return `<tr>
									<td>${frappe.utils.escape_html(row.profile_label || "-")}</td>
									<td>${frappe.utils.escape_html(row.provider || "-")}</td>
									<td>${frappe.utils.escape_html(row.model || "-")}</td>
									<td><b>${frappe.utils.escape_html(status)}</b></td>
									<td>${frappe.utils.escape_html(detail)}</td>
								</tr>`;
							})
							.join("")}
					</tbody>
				</table>
			`
			: `<div class="text-muted">${__("No saved profiles found.")}</div>`;

		frappe.msgprint({
			title: __("Saved Provider Health Report"),
			indicator: payload.failed_count ? "orange" : "green",
			message: `
				<div>
					<b>${__("Checked")}</b>: ${payload.checked || 0} &nbsp;|&nbsp;
					<b>${__("OK")}</b>: ${payload.ok_count || 0} &nbsp;|&nbsp;
					<b>${__("Failed")}</b>: ${payload.failed_count || 0}
					${table}
				</div>
			`,
		});
	}, __("Saved Providers"));
}

async function applyProviderDefaults(frm, { force } = { force: false }) {
	const provider = (frm.doc.provider || "").trim();
	if (!provider) {
		return;
	}

	const catalog = await loadProviderCatalog(frm);
	const providerEntry = getProviderEntry(catalog, provider);
	if (!providerEntry) {
		return;
	}

	updateProviderHelpNotes(frm, providerEntry);
	renderProviderDocumentationLink(frm, providerEntry);

	if (force || !frm.doc.base_url) {
		await frm.set_value("base_url", providerEntry.base_url || "");
	}
	if (force || !frm.doc.model) {
		await frm.set_value("model", providerEntry.model || "");
	}
	if (force || !frm.doc.timeout_seconds) {
		await frm.set_value("timeout_seconds", providerEntry.timeout_seconds || 90);
	}
	if (force || !frm.doc.max_output_tokens) {
		await frm.set_value("max_output_tokens", providerEntry.max_output_tokens || 500);
	}

	const needsKey = !!providerEntry.requires_api_key;
	frm.set_df_property("api_key", "hidden", !needsKey);
	frm.set_df_property(
		"api_key",
		"description",
		needsKey
			? __(
				"Required for {0}. {1}",
				[provider, providerEntry.credential_hint || __("Paste your provider API key.")]
			)
			: __("No API key needed for {0}. {1}", [provider, providerEntry.credential_hint || ""])
	);

	if (!needsKey && frm.doc.api_key) {
		await frm.set_value("api_key", "");
	}

	frm.refresh_field("api_key");
}

frappe.ui.form.on("AI Sales AI Settings", {
	async refresh(frm) {
		const catalog = await loadProviderCatalog(frm);
		syncProviderOptions(frm, catalog);
		renderQuickProviderActions(frm);
		renderSavedProviderNotes(frm);
		await applyProviderDefaults(frm, { force: false });

		frm.add_custom_button(__("Apply Provider Preset"), async () => {
			const catalog = await loadProviderCatalog(frm);
			const profiles = catalog?.profiles || [];
			if (!profiles.length) {
				frappe.msgprint(__("No AI provider presets are available."));
				return;
			}

			const dialog = new frappe.ui.Dialog({
				title: __("Apply Provider Preset"),
				fields: [
					{
						label: __("Preset"),
						fieldname: "profile_key",
						fieldtype: "Select",
						options: profiles.map((profile) => profile.key).join("\n"),
						reqd: 1,
					},
				],
				primary_action_label: __("Apply"),
				primary_action(values) {
					const profile = profiles.find((entry) => entry.key === values.profile_key);
					if (!profile) {
						return;
					}

					frm.set_value("provider", profile.provider);
					frm.set_value("base_url", profile.base_url);
					frm.set_value("model", profile.model);
					frm.set_value("timeout_seconds", profile.timeout_seconds);
					frm.set_value("max_output_tokens", profile.max_output_tokens);
					frm.set_value("temperature", profile.temperature);
					applyProviderDefaults(frm, { force: true });
					dialog.hide();
					frappe.show_alert({
						message: __("Applied preset: {0}", [profile.label]),
						indicator: "green",
					});
					if (profile.notes) {
						frappe.msgprint({
							title: __("Preset Notes"),
							message: profile.notes,
							indicator: "blue",
						});
					}
				},
			});

			dialog.show();
		});

		frm.add_custom_button(__("Test Connection"), async () => {
			if (frm.is_dirty()) {
				frappe.msgprint(__("Save the settings first so the latest provider values and API key are used for the test."));
				return;
			}

			if (!frm.doc.provider || !frm.doc.model || !frm.doc.base_url) {
				frappe.msgprint(__("Set Provider, Base URL, and Model before testing."));
				return;
			}

			frappe.show_alert({ message: __("Testing AI provider connection..."), indicator: "blue" });
			const response = await frappe.call({
				method: "ai_sales_dashboard.api.test_ai_provider_connection",
				args: {
					provider: frm.doc.provider,
					model: frm.doc.model,
					base_url: frm.doc.base_url,
					timeout_seconds: frm.doc.timeout_seconds,
					max_output_tokens: frm.doc.max_output_tokens,
					temperature: frm.doc.temperature,
				},
				freeze: true,
				freeze_message: __("Contacting AI provider..."),
			});

			const result = response.message || {};
			frappe.msgprint({
				title: __("Connection Successful"),
				indicator: "green",
				message: __("Provider: {0}<br>Model: {1}<br><br><b>Preview</b><br>{2}", [
					frappe.utils.escape_html(result.provider || frm.doc.provider),
					frappe.utils.escape_html(result.model || frm.doc.model),
					frappe.utils.escape_html(result.preview || ""),
				]),
			});
		});

		frm.add_custom_button(__("Open AI Sales Agent"), () => {
			frappe.set_route("app", "ai-sales-agent");
		});

		addSavedProviderButtons(frm);
	},

	async provider(frm) {
		await applyProviderDefaults(frm, { force: true });
		frappe.show_alert({
			message: __("Applied defaults for {0}. Enter only the required credentials.", [frm.doc.provider || "Provider"]),
			indicator: "blue",
		});
	},
});