app_name = "ksa_retail"
app_title = "Ksa Retail"
app_publisher = "MobilityPro"
app_description = "customizations for retail"
app_email = "info@mobilityp.com"
app_license = "mit"

# Apps
# ------------------

# required_apps = []

# Each item in the list will be shown as an app in the apps page
add_to_apps_screen = [
	{
		"name": "ksa_retail",
		"logo": "/assets/ksa_retail/images/pos-mark.svg",
		"title": "KSA Retail POS",
		"route": "/ksa-pos",
		"has_permission": "ksa_retail.pos.permissions.has_app_permission",
	}
]

website_route_rules = [{"from_route": "/ksa-pos", "to_route": "ksa_pos"}]

doc_events = {
	"Sales Invoice": {"before_validate": "ksa_retail.pos.doc_events.sales_invoice_before_validate"},
	"Purchase Invoice": {"before_validate": "ksa_retail.pos.doc_events.purchase_invoice_before_validate"},
	# a new / changed Inventory Dimension gets its field on Sales Order lines too
	"Inventory Dimension": {"on_update": "ksa_retail.setup.install.on_inventory_dimension_update"},
}

# POS custom fields come from patches/v1_0/add_pos_custom_fields.py.
# Patches are skipped on a fresh install, so create them there too.
after_install = "ksa_retail.setup.install.after_install"

# Includes in <head>
# ------------------

# include js, css files in header of desk.html
# app_include_css = "/assets/ksa_retail/css/ksa_retail.css"
# app_include_js = "/assets/ksa_retail/js/ksa_retail.js"

# include js, css files in header of web template
# web_include_css = "/assets/ksa_retail/css/ksa_retail.css"
# web_include_js = "/assets/ksa_retail/js/ksa_retail.js"

# include custom scss in every website theme (without file extension ".scss")
# website_theme_scss = "ksa_retail/public/scss/website"

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
# app_include_icons = "ksa_retail/public/icons.svg"

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
# 	"methods": "ksa_retail.utils.jinja_methods",
# 	"filters": "ksa_retail.utils.jinja_filters"
# }

# Installation
# ------------

# before_install = "ksa_retail.install.before_install"
# after_install = "ksa_retail.install.after_install"

# Uninstallation
# ------------

# before_uninstall = "ksa_retail.uninstall.before_uninstall"
# after_uninstall = "ksa_retail.uninstall.after_uninstall"

# Integration Setup
# ------------------
# To set up dependencies/integrations with other apps
# Name of the app being installed is passed as an argument

# before_app_install = "ksa_retail.utils.before_app_install"
# after_app_install = "ksa_retail.utils.after_app_install"

# Integration Cleanup
# -------------------
# To clean up dependencies/integrations with other apps
# Name of the app being uninstalled is passed as an argument

# before_app_uninstall = "ksa_retail.utils.before_app_uninstall"
# after_app_uninstall = "ksa_retail.utils.after_app_uninstall"

# Build
# ------------------
# To hook into the build process

# after_build = "ksa_retail.build.after_build"

# To hook into the build process of other apps
# The list of apps being built is passed as an argument

# after_app_build = "ksa_retail.build.after_app_build"

# Desk Notifications
# ------------------
# See frappe.core.notifications.get_notification_config

# notification_config = "ksa_retail.notifications.get_notification_config"

# Awesome Bar
# -----------
# Extra search results: list of dicts with label, description, route, index.
# route: ["List", "ToDo"], "/desk/docs/some/page", or "https://example.com"
# awesomebar_search = ["ksa_retail.search.awesomebar_results"]

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
# 		"ksa_retail.tasks.all"
# 	],
# 	"daily": [
# 		"ksa_retail.tasks.daily"
# 	],
# 	"hourly": [
# 		"ksa_retail.tasks.hourly"
# 	],
# 	"weekly": [
# 		"ksa_retail.tasks.weekly"
# 	],
# 	"monthly": [
# 		"ksa_retail.tasks.monthly"
# 	],
# }

# Testing
# -------

# before_tests = "ksa_retail.install.before_tests"

# Overriding Methods
# ------------------------------
#
# override_whitelisted_methods = {
# 	"frappe.desk.doctype.event.event.get_events": "ksa_retail.event.get_events"
# }
#
# each overriding function accepts a `data` argument;
# generated from the base implementation of the doctype dashboard,
# along with any modifications made in other Frappe apps
# override_doctype_dashboards = {
# 	"Task": "ksa_retail.task.get_dashboard_data"
# }

# exempt linked doctypes from being automatically cancelled
#
# auto_cancel_exempted_doctypes = ["Auto Repeat"]

# Ignore links to specified DocTypes when deleting documents
# -----------------------------------------------------------

# ignore_links_on_delete = ["Communication", "ToDo"]

# Request Events
# ----------------
# before_request = ["ksa_retail.utils.before_request"]
# after_request = ["ksa_retail.utils.after_request"]

# Job Events
# ----------
# before_job = ["ksa_retail.utils.before_job"]
# after_job = ["ksa_retail.utils.after_job"]

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
# 	"ksa_retail.auth.validate"
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

# --- mobility_customizations: customization installer (auto-generated) ---
# Applies customizations/install and customizations/updates without needing mobility_customizations.
# Keep this block at the end of the file.
def _add_customization_installer_hook(name, method):
	value = globals().get(name) or []
	value = [value] if isinstance(value, str) else list(value)
	if method not in value:
		value.append(method)
	globals()[name] = value


_add_customization_installer_hook("after_install", "ksa_retail.customizations.installer.after_install")
_add_customization_installer_hook("after_migrate", "ksa_retail.customizations.installer.after_migrate")
# --- end mobility_customizations customization installer ---
