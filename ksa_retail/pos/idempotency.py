"""Duplicate-submission protection for POS actions.

Each action the cashier triggers carries a client-generated reference. While the action
runs, a Redis lock with that reference blocks a second copy (double click, retry while
the first is still running). The result is remembered **only after the database
transaction commits**, so a retry after a failed or rolled-back request runs again
instead of receiving a false success. On rollback the lock is released immediately.
"""

import json

import frappe
from frappe import _

LOCK_SECONDS = 120
RESULT_SECONDS = 24 * 3600


def _keys(client_ref: str) -> tuple[str, str]:
	cache = frappe.cache
	return cache.make_key(f"ksa_pos:txn:{client_ref}"), cache.make_key(f"ksa_pos:txn:{client_ref}:lock")


def run_once(client_ref: str, operation):
	"""Run `operation()` once per client reference and return its (JSON-able) result."""
	cache = frappe.cache  # raw keys: get_value/set_value keep a per-process copy of misses
	result_key, lock_key = _keys(client_ref)

	cached = cache.get(result_key)
	if cached:
		return json.loads(cached)
	if not cache.set(lock_key, 1, nx=True, ex=LOCK_SECONDS):
		frappe.throw(_("This transaction is already being processed. Please wait."), title=_("Duplicate"))

	try:
		result = operation()
	except Exception:
		cache.delete(lock_key)
		raise

	payload = json.dumps(result, default=str)

	def remember():
		cache.set(result_key, payload, ex=RESULT_SECONDS)
		cache.delete(lock_key)

	frappe.db.after_commit.add(remember)
	frappe.db.after_rollback.add(lambda: cache.delete(lock_key))
	return json.loads(payload)  # same shape as a cached replay (dates as strings)
