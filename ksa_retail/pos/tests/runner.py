"""Run the POS test suite against a site without leaving any data behind.

    bench --site <site> execute ksa_retail.pos.tests.runner.run

Everything runs inside one database transaction that is rolled back at the end.
`frappe.db.commit` is replaced for the duration: it only fires the after-commit callbacks
(so commit-dependent behaviour such as duplicate protection is exercised) without
committing. Never run this while the site's data must not be touched by locks: the
transaction holds row locks until it finishes.
"""

import unittest

import frappe

MODULES = ("ksa_retail.pos.tests.test_rules", "ksa_retail.pos.tests.test_scenarios")


def run(modules: str | None = None, verbosity: int = 2) -> dict:
	frappe.set_user("Administrator")
	real_commit = frappe.db.commit
	frappe.db.commit = lambda *args, **kwargs: frappe.db.after_commit.run()
	frappe.flags.mute_emails = True
	frappe.flags.ksa_pos_rollback_run = True
	try:
		names = modules.split(",") if modules else list(MODULES)
		suite = unittest.defaultTestLoader.loadTestsFromNames(names)
		result = unittest.TextTestRunner(verbosity=verbosity).run(suite)
	finally:
		frappe.db.rollback()
		frappe.db.commit = real_commit
		frappe.flags.ksa_pos_rollback_run = False
	summary = {
		"run": result.testsRun,
		"failures": len(result.failures),
		"errors": len(result.errors),
		"ok": result.wasSuccessful(),
	}
	print(summary)
	return summary
