"""The POS page (/ksa-pos): boots the Vue application with the user's selling context."""

import json

import frappe
from frappe import _
from frappe.utils.jinja_globals import bundled_asset

from ksa_retail.pos.boot import get_boot
from ksa_retail.pos.permissions import has_app_permission

no_cache = 1


def get_context(context):
	if frappe.session.user == "Guest":
		frappe.local.flags.redirect_location = "/login?redirect-to=/ksa-pos"
		raise frappe.Redirect
	if not has_app_permission():
		frappe.throw(_("You are not permitted to use the POS."), frappe.PermissionError)

	boot = get_boot()
	boot["csrf_token"] = frappe.sessions.get_csrf_token()
	lang = boot["prefs"].get("lang") or ("ar" if (frappe.local.lang or "").startswith("ar") else "en")
	boot["prefs"]["lang"] = lang

	context.no_breadcrumbs = 1
	context.pos_lang = lang
	context.pos_dir = "rtl" if lang == "ar" else "ltr"
	context.pos_theme = boot["prefs"].get("theme") or ""
	# JSON inside an inline <script>: neutralise "</" so data can never close the tag
	context.boot_json = json.dumps(boot, default=str).replace("</", "<\\/")
	# the stylesheet handles both directions itself: never Frappe's auto-flipped RTL copy
	context.css_url = bundled_asset("ksa_pos.bundle.css", rtl=False)
	context.js_url = _script_url("ksa_pos.bundle")
	return context


def _script_url(entry: str) -> str:
	"""The asset manifest keys a script by its source name (.ts here, .js in older builds)."""
	assets = frappe.utils.get_assets_json()
	for name in (f"{entry}.ts", f"{entry}.js"):
		if assets.get(name):
			return bundled_asset(name)
	frappe.throw(_("The POS assets are not built. Run: bench build --app ksa_retail"))
