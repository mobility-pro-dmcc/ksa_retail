"""Request payload parsing.

Endpoints receive JSON from the browser. Everything is validated here into plain,
typed values before any business code runs; nothing downstream reads raw input.
Amounts and quantities from the client are *requests* (what the cashier asked for):
prices, totals and stock are always recomputed on the server.
"""

import json
import math
from dataclasses import dataclass, field

import frappe
from frappe import _
from frappe.utils import cstr, flt

MAX_LINES = 200
MAX_TEXT = 140


def parse_json(value, expected=(dict, list), default=None):
	if value in (None, ""):
		return default
	if isinstance(value, str):
		try:
			value = json.loads(value)
		except ValueError:
			frappe.throw(_("Invalid request data."))
	if not isinstance(value, expected):
		frappe.throw(_("Invalid request data."))
	return value


def text(value, label: str, required: bool = False, max_length: int = MAX_TEXT) -> str | None:
	value = cstr(value).strip() if value is not None else ""
	if not value:
		if required:
			frappe.throw(_("{0} is required.").format(_(label)))
		return None
	if len(value) > max_length:
		frappe.throw(_("{0} is too long.").format(_(label)))
	return value


def number(value, label: str, minimum: float | None = 0.0, allow_zero: bool = True) -> float:
	try:
		result = float(value)
	except (TypeError, ValueError):
		frappe.throw(_("{0} must be a number.").format(_(label)))
	if not math.isfinite(result):
		frappe.throw(_("{0} must be a number.").format(_(label)))
	if minimum is not None and result < minimum:
		frappe.throw(_("{0} cannot be negative.").format(_(label)))
	if not allow_zero and result == 0:
		frappe.throw(_("{0} must be greater than zero.").format(_(label)))
	return result


@dataclass
class SaleLine:
	item_code: str
	qty: float
	rate: float | None = None
	dims: dict = field(default_factory=dict)
	drop_ship: bool = False
	so_detail: str | None = None


@dataclass
class PaymentLine:
	mode_of_payment: str
	amount: float
	reference_no: str | None = None


@dataclass
class Discount:
	kind: str  # "pct" | "amount"
	value: float


@dataclass
class DropShip:
	supplier: str | None
	bill_no: str | None


def sale_lines(raw, dimension_fields: set[str]) -> list[SaleLine]:
	rows = parse_json(raw, expected=list, default=[])
	if len(rows) > MAX_LINES:
		frappe.throw(_("Too many lines in one sale."))
	lines = []
	for row in rows:
		if not isinstance(row, dict):
			frappe.throw(_("Invalid request data."))
		item_code = text(row.get("item_code"), "Item", required=True)
		qty = number(row.get("qty"), _("Quantity for {0}").format(item_code), allow_zero=False)
		rate = row.get("rate")
		rate = None if rate in (None, "") else number(rate, _("Rate for {0}").format(item_code))
		raw_dims = row.get("dims") or {}
		if not isinstance(raw_dims, dict):
			frappe.throw(_("Invalid request data."))
		dims = {k: cstr(v) for k, v in raw_dims.items() if k in dimension_fields and v not in (None, "")}
		lines.append(
			SaleLine(
				item_code=item_code,
				qty=qty,
				rate=rate,
				dims=dims,
				drop_ship=bool(row.get("drop_ship")),
				so_detail=text(row.get("so_detail"), "Line"),
			)
		)
	return lines


def payment_lines(raw) -> list[PaymentLine]:
	"""Rows with no amount are ignored (an empty payment row in the UI)."""
	rows = parse_json(raw, expected=list, default=[])
	payments = []
	for row in rows:
		if not isinstance(row, dict):
			frappe.throw(_("Invalid request data."))
		amount = flt(number(row.get("amount") or 0, "Amount"), 2)
		if amount <= 0:
			continue
		payments.append(
			PaymentLine(
				mode_of_payment=text(row.get("mode_of_payment"), "Mode of Payment", required=True),
				amount=amount,
				reference_no=text(row.get("reference_no"), "Reference No"),
			)
		)
	return payments


def discount(raw) -> Discount | None:
	data = parse_json(raw, expected=dict, default=None)
	if not data:
		return None
	value = number(data.get("value") or 0, "Discount")
	if value <= 0:
		return None
	kind = "amount" if data.get("type") == "amount" else "pct"
	if kind == "pct" and value > 100:
		frappe.throw(_("Discount cannot exceed 100%."))
	return Discount(kind=kind, value=value)


def line_quantities(raw) -> dict[str, float]:
	"""{Sales Order line: qty} for partial deliveries / invoices / returns."""
	data = parse_json(raw, expected=dict, default={})
	result = {}
	for key, qty in data.items():
		qty = number(qty, "Quantity")
		if qty > 0:
			result[cstr(key)] = qty
	return result


def drop_ship(raw) -> DropShip | None:
	data = parse_json(raw, expected=dict, default=None)
	if not data:
		return None
	return DropShip(
		supplier=text(data.get("supplier"), "Supplier"), bill_no=text(data.get("bill_no"), "Bill No")
	)


def client_ref(value) -> str:
	return text(value, "Transaction reference", required=True, max_length=80)
