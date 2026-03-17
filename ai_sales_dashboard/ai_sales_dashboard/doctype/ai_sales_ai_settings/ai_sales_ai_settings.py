from frappe.model.document import Document

from ai_sales_dashboard.ai_providers import AI_PROVIDER_PRESETS, PROVIDER_DOCUMENTATION_URLS


class AISalesAISettings(Document):
	def validate(self):
		active_found = False
		for row in self.saved_providers or []:
			if row.is_active and not active_found:
				active_found = True
			elif row.is_active:
				row.is_active = 0

		provider = (self.provider or "Ollama").strip()
		preset = AI_PROVIDER_PRESETS.get(provider)

		# Set documentation URL based on provider
		self.provider_documentation_url = PROVIDER_DOCUMENTATION_URLS.get(provider, "")

		if not preset:
			return

		provider_changed = self.is_new() or self.has_value_changed("provider")

		if provider_changed:
			self.base_url = preset.get("base_url") or ""
			self.model = preset.get("model") or ""
			self.timeout_seconds = preset.get("timeout_seconds") or 90
			self.max_output_tokens = preset.get("max_output_tokens") or 500
			if not preset.get("requires_api_key", True):
				self.api_key = ""
			return

		if not (self.base_url or "").strip() and preset.get("base_url"):
			self.base_url = preset["base_url"]

		if not (self.model or "").strip() and preset.get("model"):
			self.model = preset["model"]

		if not self.timeout_seconds:
			self.timeout_seconds = preset.get("timeout_seconds") or 90

		if not self.max_output_tokens:
			self.max_output_tokens = preset.get("max_output_tokens") or 500
