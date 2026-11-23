"""Pure business rules (no database access)."""

import unittest

import frappe

from ksa_retail.pos import dimensions, inputs, order_summary
from ksa_retail.pos.payments import Target, plan_allocation


def progress(qty, dn_out=0.0, dn_ret=0.0, si_out=0.0, si_ret=0.0):
	return order_summary.finish_line_progress(
		frappe._dict(qty=qty, dn_out=dn_out, dn_ret=dn_ret, si_out=si_out, si_ret=si_ret)
	)


class TestAllocation(unittest.TestCase):
	def test_fills_targets_in_order(self):
		targets = [Target("Sales Invoice", "SI-1", 100), Target("Sales Order", "SO-1", 300)]
		allocations, left = plan_allocation(250, targets)
		self.assertEqual([(t.name, a) for t, a in allocations], [("SI-1", 100), ("SO-1", 150)])
		self.assertEqual(left, 0)
		self.assertEqual(targets[1].open_amount, 150)

	def test_leftover_stays_as_credit(self):
		allocations, left = plan_allocation(500, [Target("Sales Invoice", "SI-1", 120)])
		self.assertEqual([a for _t, a in allocations], [120])
		self.assertAlmostEqual(left, 380)

	def test_shared_targets_across_payment_rows(self):
		targets = [Target("Sales Invoice", "SI-1", 100)]
		plan_allocation(60, targets)
		allocations, left = plan_allocation(60, targets)
		self.assertEqual([a for _t, a in allocations], [40])
		self.assertAlmostEqual(left, 20)

	def test_skips_settled_targets(self):
		allocations, _left = plan_allocation(
			10, [Target("Sales Invoice", "SI-0", 0), Target("Sales Invoice", "SI-1", 5)]
		)
		self.assertEqual([t.name for t, _a in allocations], ["SI-1"])


class TestStatus(unittest.TestCase):
	def test_stages(self):
		status = order_summary.derive_status(total=1000, paid=400, per_billed=0, per_delivered=100)
		self.assertEqual(
			(status["payment"], status["invoice"], status["delivery"]), ("part", "pending", "done")
		)
		self.assertEqual(status["payment_pct"], 40)

	def test_paid_within_a_cent_is_done(self):
		self.assertEqual(order_summary.derive_status(100, 99.995, 100, 100)["payment"], "done")

	def test_complete(self):
		self.assertTrue(order_summary.is_complete(order_summary.derive_status(10, 10, 100, 100)))
		self.assertFalse(order_summary.is_complete(order_summary.derive_status(10, 10, 99, 100)))


class TestLineProgress(unittest.TestCase):
	def test_only_delivered_quantity_is_billable(self):
		line = progress(qty=5, dn_out=2)
		self.assertEqual((line.pending_delivery, line.pending_billing), (3, 2))

	def test_returned_quantity_is_no_longer_pending(self):
		line = progress(qty=4, dn_out=4, dn_ret=1)
		self.assertEqual((line.effective, line.pending_delivery, line.pending_billing), (3, 0, 3))

	def test_returnable_is_what_the_customer_still_has(self):
		line = progress(qty=4, dn_out=4, si_out=4, dn_ret=1, si_ret=1)
		self.assertEqual(line.returnable, 3)

	def test_percentages_ignore_returns(self):
		lines = [progress(qty=4, dn_out=4, dn_ret=1, si_out=3), progress(qty=2, dn_out=2, si_out=2)]
		delivered, invoiced = order_summary.order_percentages(lines)
		self.assertEqual((round(delivered), round(invoiced)), (100, 100))

	def test_fully_returned_order_counts_as_complete(self):
		self.assertEqual(
			order_summary.order_percentages([progress(qty=2, dn_out=2, dn_ret=2)]), (100.0, 100.0)
		)


class TestInputs(unittest.TestCase):
	def test_rejects_non_positive_quantity(self):
		with self.assertRaises(frappe.ValidationError):
			inputs.sale_lines([{"item_code": "X", "qty": 0}], set())

	def test_rejects_negative_rate(self):
		with self.assertRaises(frappe.ValidationError):
			inputs.sale_lines([{"item_code": "X", "qty": 1, "rate": -5}], set())

	def test_drops_unknown_dimensions(self):
		line = inputs.sale_lines(
			[{"item_code": "X", "qty": 1, "dims": {"production_year": "2025", "evil": "1"}}],
			{"production_year"},
		)[0]
		self.assertEqual(line.dims, {"production_year": "2025"})

	def test_empty_payment_rows_are_ignored(self):
		rows = inputs.payment_lines(
			[{"mode_of_payment": "Cash", "amount": 0}, {"mode_of_payment": "Cash", "amount": "12.346"}]
		)
		self.assertEqual([(r.mode_of_payment, r.amount) for r in rows], [("Cash", 12.35)])

	def test_percentage_discount_capped(self):
		with self.assertRaises(frappe.ValidationError):
			inputs.discount({"type": "pct", "value": 120})

	def test_rejects_non_numbers(self):
		with self.assertRaises(frappe.ValidationError):
			inputs.line_quantities({"x": "abc"})

	def test_dimension_key_normalises_empty_values(self):
		self.assertEqual(dimensions.key([None, "2025", ""]), ("", "2025", ""))
