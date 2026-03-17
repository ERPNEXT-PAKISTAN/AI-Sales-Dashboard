app_name = "ai_sales_dashboard"
app_title = "AI Sales Dashboard"
app_publisher = "Your Company"
app_description = "Sales intelligence and KPI dashboard app for ERPNext"
app_email = "dev@yourcompany.com"
app_license = "mit"

required_apps = ["erpnext"]

add_to_apps_screen = [
	{
		"name": "ai_sales_dashboard",
		"logo": "/assets/ai_sales_dashboard/logo.png",
		"title": "AI Sales Dashboard",
		"route": "/app/ai-sales-dashboard",
		"has_permission": "ai_sales_dashboard.api.has_app_access",
	}
]

fixtures = [
	{"dt": "Workspace", "filters": [["name", "=", "AI Sales Dashboard"]]},
	{"dt": "Page", "filters": [["module", "=", "AI Sales Dashboard"]]},
	{"dt": "Report", "filters": [["module", "=", "AI Sales Dashboard"]]},
	{"dt": "Dashboard Chart", "filters": [["module", "=", "AI Sales Dashboard"]]},
	{"dt": "Number Card", "filters": [["module", "=", "AI Sales Dashboard"]]},
	{"dt": "DocType", "filters": [["name", "=", "AI Sales AI Settings"]]},
	{"dt": "Role", "filters": [["name", "in", ["AI Sales Manager", "AI Sales User"]]]},
]

scheduler_events = {
	"daily": [
		"ai_sales_dashboard.utils.kpi.create_daily_snapshots",
	]
}

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "ai_sales_dashboard",
# 		"logo": "/assets/ai_sales_dashboard/logo.png",
# 		"title": "AI Sales Dashboard",
# 		"route": "/ai_sales_dashboard",
# 		"has_permission": "ai_sales_dashboard.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
app_include_js = "/assets/ai_sales_dashboard/js/ai_sales_floating_bot.js"

# include js, css files in header of web template
# web_include_css = "/assets/ai_sales_dashboard/css/ai_sales_dashboard.css"
# web_include_js = "/assets/ai_sales_dashboard/js/ai_sales_dashboard.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "ai_sales_dashboard/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
doctype_js = {
	"AI Sales AI Settings": "public/js/ai_sales_ai_settings.js",
}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "ai_sales_dashboard/public/icons.svg"

# Home Pages
# ----------

# application home page (will override Website Settings)
# home_page = "login"

# website user home page (by Role)
# role_home_page = {
# 	"Role": "home_page"
# }

# Generators
# ----------

# automatically create page for each record of this doctype
# website_generators = ["Web Page"]

# Jinja
# ----------

# add methods and filters to jinja environment
# jinja = {
# 	"methods": "ai_sales_dashboard.utils.jinja_methods",
# 	"filters": "ai_sales_dashboard.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "ai_sales_dashboard.install.before_install"
# after_install = "ai_sales_dashboard.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "ai_sales_dashboard.uninstall.before_uninstall"
# after_uninstall = "ai_sales_dashboard.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "ai_sales_dashboard.utils.before_app_install"
# after_app_install = "ai_sales_dashboard.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "ai_sales_dashboard.utils.before_app_uninstall"
# after_app_uninstall = "ai_sales_dashboard.utils.after_app_uninstall"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "ai_sales_dashboard.notifications.get_notification_config"

# Permissions
# -----------
# Permissions evaluated in scripted ways

# permission_query_conditions = {
# 	"Event": "frappe.desk.doctype.event.event.get_permission_query_conditions",
# }
#
# has_permission = {
# 	"Event": "frappe.desk.doctype.event.event.has_permission",
# }

# DocType Class
# ---------------
# Override standard doctype classes

# override_doctype_class = {
# 	"ToDo": "custom_app.overrides.CustomToDo"
# }

# Document Events
# ---------------
# Hook on document methods and events

# doc_events = {
# 	"*": {
# 		"on_update": "method",
# 		"on_cancel": "method",
# 		"on_trash": "method"
# 	}
# }

# Scheduled Tasks
# ---------------

# scheduler_events = {
# 	"all": [
# 		"ai_sales_dashboard.tasks.all"
# 	],
# 	"daily": [
# 		"ai_sales_dashboard.tasks.daily"
# 	],
# 	"hourly": [
# 		"ai_sales_dashboard.tasks.hourly"
# 	],
# 	"weekly": [
# 		"ai_sales_dashboard.tasks.weekly"
# 	],
# 	"monthly": [
# 		"ai_sales_dashboard.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "ai_sales_dashboard.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "ai_sales_dashboard.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "ai_sales_dashboard.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["ai_sales_dashboard.utils.before_request"]
# after_request = ["ai_sales_dashboard.utils.after_request"]

# Job Events
# ----------
# before_job = ["ai_sales_dashboard.utils.before_job"]
# after_job = ["ai_sales_dashboard.utils.after_job"]

# User Data Protection
# --------------------

# user_data_fields = [
# 	{
# 		"doctype": "{doctype_1}",
# 		"filter_by": "{filter_by}",
# 		"redact_fields": ["{field_1}", "{field_2}"],
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_2}",
# 		"filter_by": "{filter_by}",
# 		"partial": 1,
# 	},
# 	{
# 		"doctype": "{doctype_3}",
# 		"strict": False,
# 	},
# 	{
# 		"doctype": "{doctype_4}"
# 	}
# ]

# Authentication and authorization
# --------------------------------

# auth_hooks = [
# 	"ai_sales_dashboard.auth.validate"
# ]

# Automatically update python controller files with type annotations for this app.
# export_python_type_annotations = True

# default_log_clearing_doctypes = {
# 	"Logging DocType Name": 30  # days to retain logs
# }

# Translation
# ------------
# List of apps whose translatable strings should be excluded from this app's translations.
# ignore_translatable_strings_from = []

