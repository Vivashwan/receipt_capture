app_name = "receipt_capture"
app_title = "Receipt Capture"
app_publisher = "Vivashwan Ghosh"
app_description = "AI receipt capture for ERPNext: OpenCV + Tesseract OCR and a local LLM (Ollama) turn receipt photos into draft Purchase Invoices"
app_email = "vivashwanwork@gmail.com"
app_license = "mit"

# Apps
# ------------------

required_apps = ["erpnext"]

# Each item in the list will be shown as an app in the apps page
# add_to_apps_screen = [
# 	{
# 		"name": "receipt_capture",
# 		"logo": "/assets/receipt_capture/logo.png",
# 		"title": "Receipt Capture",
# 		"route": "/receipt_capture",
# 		"has_permission": "receipt_capture.api.permission.has_app_permission"
# 	}
# ]

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/receipt_capture/css/receipt_capture.css"
# app_include_js = "/assets/receipt_capture/js/receipt_capture.js"

# include js, css files in header of web template
# web_include_css = "/assets/receipt_capture/css/receipt_capture.css"
# web_include_js = "/assets/receipt_capture/js/receipt_capture.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "receipt_capture/public/scss/website"

# include js, css files in header of web form
# webform_include_js = {"doctype": "public/js/doctype.js"}
# webform_include_css = {"doctype": "public/css/doctype.css"}

# include js in page
# page_js = {"page" : "public/js/file.js"}

# include js in doctype views
# doctype_js = {"doctype" : "public/js/doctype.js"}
# doctype_list_js = {"doctype" : "public/js/doctype_list.js"}
# doctype_tree_js = {"doctype" : "public/js/doctype_tree.js"}
# doctype_calendar_js = {"doctype" : "public/js/doctype_calendar.js"}

# Svg Icons
# ------------------
# include app icons in desk
# app_include_icons = "receipt_capture/public/icons.svg"

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
# 	"methods": "receipt_capture.utils.jinja_methods",
# 	"filters": "receipt_capture.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "receipt_capture.install.before_install"
after_install = "receipt_capture.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "receipt_capture.uninstall.before_uninstall"
# after_uninstall = "receipt_capture.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "receipt_capture.utils.before_app_install"
# after_app_install = "receipt_capture.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "receipt_capture.utils.before_app_uninstall"
# after_app_uninstall = "receipt_capture.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "receipt_capture.build.after_build"

# To hook into the build process of other apps
# The list of apps being built is passed as an argument

# after_app_build = "receipt_capture.build.after_app_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "receipt_capture.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["receipt_capture.search.awesomebar_results"]

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

scheduler_events = {
	# Release receipts left in "Processing" by a crashed worker so they can be retried
	"hourly": ["receipt_capture.ai.pipeline.fail_stuck_receipts"],
}

# scheduler_events = {
# 	"all": [
# 		"receipt_capture.tasks.all"
# 	],
# 	"daily": [
# 		"receipt_capture.tasks.daily"
# 	],
# 	"hourly": [
# 		"receipt_capture.tasks.hourly"
# 	],
# 	"weekly": [
# 		"receipt_capture.tasks.weekly"
# 	],
# 	"monthly": [
# 		"receipt_capture.tasks.monthly"
# 	],
# }

# Testing
# -------

before_tests = "receipt_capture.tests_setup.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "receipt_capture.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "receipt_capture.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["receipt_capture.utils.before_request"]
# after_request = ["receipt_capture.utils.after_request"]

# Job Events
# ----------
# before_job = ["receipt_capture.utils.before_job"]
# after_job = ["receipt_capture.utils.after_job"]

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
# 	"receipt_capture.auth.validate"
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
