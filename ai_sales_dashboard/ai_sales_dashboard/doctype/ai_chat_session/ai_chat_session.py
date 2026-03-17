import frappe
from frappe.model.document import Document
from frappe.utils import now_datetime


class AIChatSession(Document):
	def validate(self):
		if not self.user:
			self.user = frappe.session.user
		if not self.title:
			self.title = "New AI Chat"
		self.last_activity = now_datetime()
