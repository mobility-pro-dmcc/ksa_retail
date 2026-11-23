"""Customer money: receipts, refunds and linking unused credit to open invoices.

Where a receipt goes, in order:
  1. the selected order's unpaid invoices,
  2. the selected order itself (advance on the not-yet-invoiced part),
  3. the customer's other unpaid invoices (oldest due first),
  4. the customer's other open orders (oldest first, as advance);
anything left stays as unallocated customer credit.
"""

from dataclasses import dataclass

import frappe
from frappe import _
from frappe.utils import flt, getdate, nowdate

from ksa_retail.pos import order_summary
from ksa_retail.pos.context import get_context, payment_mode
from ksa_retail.pos.inputs import PaymentLine

MONEY_EPSILON = 0.005


@dataclass
class Target:
	doctype: str
	name: str
	open_amount: float


def plan_allocation(amount: float, targets: list[Target]) -> tuple[list[tuple[Target, float]], float]:
	"""Split `amount` over `targets` in order. Mutates each target's open amount, so the
	same target list can be used for several payment rows. Returns (allocations, left over)."""
	allocations = []
	left = flt(amount, 2)
	for target in targets:
		if left <= MONEY_EPSILON:
			break
		if target.open_amount <= MONEY_EPSILON:
			continue
		share = min(left, target.open_amount)
		allocations.append((target, share))
		target.open_amount -= share
		left -= share
	return allocations, max(left, 0.0)


# --------------------------------------------------------------------------- targets
def order_targets(order_name: str | None) -> list[Target]:
	if not order_name:
		return []
	order = frappe.get_doc("Sales Order", order_name)
	targets = [
		Target("Sales Invoice", inv.name, flt(inv.outstanding_amount))
		for inv in order_summary.invoices_for_orders([order_name])
		if not inv.is_return and flt(inv.outstanding_amount) > MONEY_EPSILON
	]
	open_amount = order_summary.open_amounts([order]).get(order_name, 0.0)
	if open_amount > MONEY_EPSILON:
		targets.append(Target("Sales Order", order_name, open_amount))
	return targets


def customer_open_invoices(customer: str, company: str, exclude=()) -> list[Target]:
	return [
		Target("Sales Invoice", row.name, flt(row.outstanding_amount))
		for row in frappe.get_all(
			"Sales Invoice",
			filters={
				"customer": customer,
				"company": company,
				"docstatus": 1,
				"is_return": 0,
				"outstanding_amount": [">", MONEY_EPSILON],
			},
			fields=["name", "outstanding_amount"],
			order_by="due_date asc, posting_date asc, creation asc",
		)
		if row.name not in exclude
	]


def customer_open_orders(customer: str, company: str, exclude=()) -> list[Target]:
	orders = frappe.get_all(
		"Sales Order",
		filters={
			"customer": customer,
			"company": company,
			"docstatus": 1,
			"per_billed": ["<", 99.99],
			"status": ["not in", list(order_summary.INACTIVE_STATUSES)],
		},
		fields=order_summary.ORDER_FIELDS,
		order_by="transaction_date asc, creation asc",
	)
	orders = [o for o in orders if o.name not in exclude]
	amounts = order_summary.open_amounts(orders)
	return [
		Target("Sales Order", o.name, amounts[o.name])
		for o in orders
		if amounts.get(o.name, 0) > MONEY_EPSILON
	]


def allocation_targets(customer: str, order_name: str | None) -> list[Target]:
	company = get_context().company
	targets = order_targets(order_name)
	targets += customer_open_invoices(customer, company, exclude={t.name for t in targets})
	targets += customer_open_orders(customer, company, exclude={t.name for t in targets})
	return targets


# --------------------------------------------------------------------------- receipts
def receive(
	customer: str, order_name: str | None, payments: list[PaymentLine], client_ref: str
) -> list[tuple]:
	"""One Payment Entry per payment method, allocated over the targets above."""
	from erpnext.accounts.party import get_party_account

	company = get_context().company
	receivable = get_party_account("Customer", customer, company)
	targets = allocation_targets(customer, order_name)
	created = []
	for payment in payments:
		mode = payment_mode(payment.mode_of_payment)
		if mode["requires_reference"] and not payment.reference_no:
			frappe.throw(_("Enter the reference / transaction no. for {0}.").format(payment.mode_of_payment))
		entry = _new_payment_entry("Receive", customer, payment, mode, client_ref)
		entry.paid_from, entry.paid_to = receivable, mode["account"]
		entry.reference_no = payment.reference_no or f"POS-{client_ref[:12]}"
		if order_name:
			entry.remarks = _("Payment for {0} via KSA Retail POS").format(order_name)
		allocations, _left_over = plan_allocation(payment.amount, targets)
		for target, amount in allocations:
			entry.append(
				"references",
				{
					"reference_doctype": target.doctype,
					"reference_name": target.name,
					"allocated_amount": amount,
				},
			)
		created.append(_submit_payment_entry(entry))
	return created


def refund(
	customer: str, credit_notes: list[str], refunds: list[PaymentLine], client_ref: str
) -> list[tuple]:
	"""Pay money back: against the new credit notes first, the rest as unallocated."""
	from erpnext.accounts.party import get_party_account

	receivable = get_party_account("Customer", customer, get_context().company)
	targets = []
	for name in credit_notes:
		outstanding = flt(frappe.db.get_value("Sales Invoice", name, "outstanding_amount"))
		if outstanding < -MONEY_EPSILON:
			targets.append(Target("Sales Invoice", name, -outstanding))

	created = []
	for payment in refunds:
		mode = payment_mode(payment.mode_of_payment)
		if mode["requires_reference"] and not payment.reference_no:
			frappe.throw(_("Enter the reference / transaction no. for {0}.").format(payment.mode_of_payment))
		entry = _new_payment_entry("Pay", customer, payment, mode, client_ref)
		entry.paid_from, entry.paid_to = mode["account"], receivable
		entry.reference_no = payment.reference_no or f"POS-R-{client_ref[:10]}"
		allocations, _left_over = plan_allocation(payment.amount, targets)
		for target, amount in allocations:
			entry.append(
				"references",
				{
					"reference_doctype": target.doctype,
					"reference_name": target.name,
					"allocated_amount": -amount,
				},
			)
		created.append(_submit_payment_entry(entry))
	return created


def _new_payment_entry(payment_type: str, customer: str, payment: PaymentLine, mode: dict, client_ref: str):
	entry = frappe.new_doc("Payment Entry")
	entry.update(
		{
			"payment_type": payment_type,
			"company": get_context().company,
			"posting_date": nowdate(),
			"mode_of_payment": payment.mode_of_payment,
			"party_type": "Customer",
			"party": customer,
			"paid_amount": payment.amount,
			"received_amount": payment.amount,
			"source_exchange_rate": 1,
			"target_exchange_rate": 1,
			"reference_date": nowdate(),
			"ksa_pos_ref": client_ref,
		}
	)
	return entry


def _submit_payment_entry(entry) -> tuple:
	entry.setup_party_account_field()
	entry.set_missing_values()
	if hasattr(entry, "set_missing_ref_details"):
		entry.set_missing_ref_details()
	entry.set_amounts()
	entry.insert()
	entry.submit()
	return ("Payment Entry", entry.name)


# --------------------------------------------------------------------------- credit
def apply_credit(customer: str) -> list[dict]:
	"""Link the customer's unused money (unallocated payments, credit notes) to their oldest
	unpaid invoices with ERPNext's Payment Reconciliation. Money paid against an order is
	left for that order's own invoices."""
	from erpnext.accounts.party import get_party_account

	company = get_context().company
	reconciliation = frappe.new_doc("Payment Reconciliation")
	reconciliation.update(
		{
			"company": company,
			"party_type": "Customer",
			"party": customer,
			"receivable_payable_account": get_party_account("Customer", customer, company),
		}
	)
	reconciliation.get_unreconciled_entries()

	payments = _free_money(reconciliation.get("payments") or [])
	invoices = sorted(
		(
			frappe._dict(i.as_dict())
			for i in reconciliation.get("invoices") or []
			if flt(i.outstanding_amount) > MONEY_EPSILON
		),
		key=lambda i: (getdate(i.invoice_date), i.invoice_number),
	)
	if not payments or not invoices:
		return []

	targets = [Target("Sales Invoice", inv.invoice_number, flt(inv.outstanding_amount)) for inv in invoices]
	by_number = {inv.invoice_number: inv for inv in invoices}
	pairs = []
	for payment in payments:
		payment.unreconciled_amount = flt(payment.amount)
		allocations, _left_over = plan_allocation(payment.amount, targets)
		pairs += [(payment, by_number[target.name], amount) for target, amount in allocations]
	if not pairs:
		return []

	gain_loss_account = frappe.get_cached_value("Company", company, "exchange_gain_loss_account")
	reconciliation.set("allocation", [])
	for payment, invoice, amount in pairs:
		row = reconciliation.get_allocated_entry(payment, invoice, amount)
		row.difference_amount = 0
		row.difference_account = gain_loss_account
		row.exchange_rate = flt(invoice.get("exchange_rate")) or 1
		reconciliation.append("allocation", row)
	reconciliation.reconcile_allocations()
	return [
		{
			"payment": p.reference_name,
			"payment_type": p.reference_type,
			"invoice": inv.invoice_number,
			"amount": amount,
		}
		for p, inv, amount in pairs
	]


def _free_money(rows) -> list[frappe._dict]:
	"""Unreconciled payments that are not tied to an order or invoice."""
	free_amounts = {}
	entries = [
		r.reference_name for r in rows if r.reference_type == "Payment Entry" and not r.get("reference_row")
	]
	if entries:
		free_amounts = dict(
			frappe.get_all(
				"Payment Entry",
				filters={"name": ["in", entries]},
				fields=["name", "unallocated_amount"],
				as_list=True,
			)
		)
	payments = []
	for row in rows:
		row = frappe._dict(row.as_dict())
		if row.get("reference_row"):
			continue
		if row.reference_type == "Payment Entry":
			free = flt(free_amounts.get(row.reference_name))
			if free <= MONEY_EPSILON:
				continue
			row.amount = min(flt(row.amount), free)
		payments.append(row)
	return payments


def apply_credit_safely(customer: str) -> list[dict]:
	"""After a POS action: best effort, never undoes the action if reconciliation fails."""
	if not frappe.has_permission("Payment Entry", "write"):
		return []
	frappe.db.savepoint("ksa_pos_credit")
	try:
		return apply_credit(customer)
	except Exception:
		frappe.db.rollback(save_point="ksa_pos_credit")
		frappe.log_error(title="KSA POS: apply customer credit")
		return []
