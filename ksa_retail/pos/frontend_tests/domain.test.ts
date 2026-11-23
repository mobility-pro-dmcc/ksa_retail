import assert from "node:assert/strict";
import { test } from "node:test";
import { addStockQuantity, clampQuantity, quantityInCart, type CartLine } from "../../public/js/ksa_pos/domain/cart";
import { amountDue, orderMoney, quoteMoney, submitIntent } from "../../public/js/ksa_pos/domain/checkout";
import { dimensionKey, dimensionLabel } from "../../public/js/ksa_pos/domain/dimensions";
import { documentTimeline } from "../../public/js/ksa_pos/domain/documents";
import { formatAmount, round2 } from "../../public/js/ksa_pos/domain/money";
import { fillAmount, missingReference, nextMode, paymentTotal, toPaymentInputs, type PaymentRow } from "../../public/js/ksa_pos/domain/payments";
import { remainingQuantity } from "../../public/js/ksa_pos/domain/stock";
import { initials } from "../../public/js/ksa_pos/domain/text";
import type { CatalogItem, OrderDetail, PaymentMode, Totals } from "../../public/js/ksa_pos/types";

const FIELDS = ["production_year", "tire_size"];

const line = (patch: Partial<CartLine> = {}): CartLine => ({
	key: "a",
	item_code: "MIC",
	item_name: "Michelin",
	dims: { production_year: "2024" },
	qty: 2,
	rate: null,
	price: 465,
	drop_ship: false,
	so_detail: null,
	...patch,
});

const item: CatalogItem = {
	item_code: "MIC",
	item_name: "Michelin",
	brand: "Michelin",
	image: null,
	stock_uom: "Unit",
	is_stock_item: 1,
	item_group: "Products",
	rate: 465,
	specs: [],
	stock: [
		{ dims: { production_year: "2024", tire_size: "" }, on_hand: 15, reserved: 0, available: 15 },
		{ dims: { production_year: "2025", tire_size: null }, on_hand: 34, reserved: 4, available: 30 },
	],
};

const totals = (grand: number): Totals => ({
	subtotal: grand,
	discount: 0,
	net_total: grand,
	taxes: [],
	total_taxes: 0,
	grand_total: grand,
	rounded_total: grand,
	lines: [],
});

const order = (patch: Partial<OrderDetail> = {}): OrderDetail => ({
	name: "SO-1",
	customer: "C",
	customer_name: "C",
	date: "2026-11-19",
	status_label: "To Deliver",
	lines: [],
	totals: totals(900),
	total: 900,
	gross_total: 900,
	returns_value: 0,
	paid: 0,
	outstanding: 900,
	refund_due: 0,
	credit: 0,
	status: { payment: "pending", payment_pct: 0, invoice: "pending", invoice_pct: 0, delivery: "pending", delivery_pct: 0 },
	can_deliver: true,
	can_invoice: false,
	can_return: false,
	drop_ship: false,
	edit_block: null,
	supplier_unbilled: false,
	documents: { "Sales Order": [], "Delivery Note": [], "Sales Invoice": [], "Payment Entry": [], "Purchase Order": [], "Purchase Invoice": [] },
	...patch,
});

test("dimension keys treat empty and missing values alike", () => {
	assert.equal(dimensionKey({ production_year: "2025", tire_size: null }, FIELDS), dimensionKey({ production_year: "2025" }, FIELDS));
	assert.equal(dimensionLabel({ production_year: "2025", tire_size: "205/55R16" }, FIELDS), "2025 · 205/55R16");
});

test("adding the same item and year merges lines; another year is a new line", () => {
	const merged = addStockQuantity([line()], line({ key: "b", qty: 1 }), FIELDS, false);
	assert.equal(merged.length, 1);
	assert.equal(merged[0].qty, 3);
	const separate = addStockQuantity([line()], line({ key: "b", dims: { production_year: "2025" } }), FIELDS, false);
	assert.equal(separate.length, 2);
});

test("supplier lines never merge with stock lines and don't use stock", () => {
	const lines = [line({ drop_ship: true, qty: 5 })];
	assert.equal(quantityInCart(lines, "MIC", { production_year: "2024" }, FIELDS), 0);
	assert.equal(addStockQuantity(lines, line({ key: "b" }), FIELDS, false).length, 2);
});

test("remaining quantity per production year, net of the cart", () => {
	const lines = [line({ qty: 10 })];
	assert.equal(remainingQuantity({ item, itemCode: "MIC", dims: { production_year: "2024" }, fields: FIELDS, lines, editingOrder: null }), 5);
	assert.equal(remainingQuantity({ item, itemCode: "MIC", dims: { production_year: "2025" }, fields: FIELDS, lines, editingOrder: null }), 30);
	assert.equal(
		remainingQuantity({ item, itemCode: "MIC", dims: { production_year: "2024" }, fields: FIELDS, lines, editingOrder: null, exceptLineKey: "a" }),
		15,
	);
	assert.equal(remainingQuantity({ item: undefined, itemCode: "X", dims: {}, fields: FIELDS, lines: [], editingOrder: null }), Infinity);
});

test("an order being edited gets its own reservation back", () => {
	const editing = order({
		lines: [
			{
				so_detail: "r1", item_code: "MIC", item_name: "Michelin", qty: 4, rate: 465, amount: 1860, delivered_qty: 1, billed_qty: 0,
				returned: 0, pending_delivery: 3, pending_billing: 1, returnable: 1, drop_ship: 0, supplier: null, dims: { production_year: "2024" },
			},
		],
	});
	assert.equal(remainingQuantity({ item, itemCode: "MIC", dims: { production_year: "2024" }, fields: FIELDS, lines: [], editingOrder: editing }), 18);
});

test("quantity clamps to 1..maximum", () => {
	assert.equal(clampQuantity(0, 10), 1);
	assert.equal(clampQuantity(12.7, 10), 10);
	assert.equal(clampQuantity(Number.NaN, 10), 1);
});

test("payments: totals, inputs, fill remaining, next mode, references", () => {
	const rows: PaymentRow[] = [
		{ id: "1", mode: "Cash", amount: 1000, reference: "" },
		{ id: "2", mode: "Wire Transfer", amount: 0, reference: "" },
	];
	const modes: PaymentMode[] = [
		{ name: "Cash", type: "Cash", account: "Cash - MA", requires_reference: false, is_default: true },
		{ name: "Wire Transfer", type: "Bank", account: "Bank - MA", requires_reference: true, is_default: false },
	];
	assert.equal(paymentTotal(rows), 1000);
	assert.deepEqual(toPaymentInputs(rows), [{ mode_of_payment: "Cash", amount: 1000, reference_no: null }]);
	assert.equal(fillAmount(rows, "2", 1697.4), 697.4);
	assert.equal(fillAmount(rows, "2", 500), 0);
	assert.equal(nextMode(rows.slice(0, 1), modes), "Wire Transfer");
	assert.equal(missingReference([{ id: "3", mode: "Wire Transfer", amount: 5, reference: " " }], modes)?.id, "3");
	assert.equal(missingReference([{ id: "3", mode: "Wire Transfer", amount: 0, reference: "" }], modes), undefined);
});

test("main button intent follows what the cashier entered", () => {
	assert.equal(submitIntent({ editing: false, viewingOrder: false, hasItems: false, hasPayment: false }), "none");
	assert.equal(submitIntent({ editing: false, viewingOrder: false, hasItems: true, hasPayment: false }), "items");
	assert.equal(submitIntent({ editing: false, viewingOrder: false, hasItems: true, hasPayment: true }), "both");
	assert.equal(submitIntent({ editing: false, viewingOrder: true, hasItems: true, hasPayment: true }), "pay");
	assert.equal(submitIntent({ editing: true, viewingOrder: false, hasItems: true, hasPayment: true }), "save");
});

test("order money: returns reduce the total; overpayment is a refund due", () => {
	const returned = order({ total: 0, gross_total: 943, returns_value: 943, paid: 0, refund_due: 700, outstanding: 0, totals: totals(943) });
	const view = orderMoney(returned, 0);
	assert.equal(view.net, 0);
	assert.equal(view.paidBefore, 700);
	assert.equal(view.balance, 700);
	assert.equal(view.balanceLabel, "refund_due");
	const paying = orderMoney(order({ paid: 500, outstanding: 400 }), 400);
	assert.equal(paying.balance, 0);
	assert.equal(paying.balanceLabel, "remaining");
	assert.equal(amountDue(order({ outstanding: 100 }), null), 100);
});

test("new sale money: paying more than the total becomes customer credit", () => {
	const view = quoteMoney(totals(1697.4), 2000, null);
	assert.equal(view.balanceLabel, "credit");
	assert.equal(round2(view.balance), 302.6);
	assert.equal(amountDue(null, totals(1697.4)), 1697.4);
});

test("documents timeline is ordered by creation across document types", () => {
	const timeline = documentTimeline(
		order({
			documents: {
				"Sales Order": [{ name: "SO-1", creation: "2026-11-19 09:00:00" }],
				"Delivery Note": [{ name: "DN-2", creation: "2026-11-19 10:40:00" }, { name: "DN-1", creation: "2026-11-19 09:30:00" }],
				"Sales Invoice": [{ name: "SI-1", creation: "2026-11-19 10:00:00" }],
				"Payment Entry": [],
				"Purchase Order": [],
				"Purchase Invoice": [],
			},
		}),
	);
	assert.deepEqual(timeline.map((entry) => entry.name), ["SO-1", "DN-1", "SI-1", "DN-2"]);
	assert.deepEqual(documentTimeline(order({ documents: { ...order().documents, "Delivery Note": [{ name: "DN-9" }] } }), "Delivery Note").map((e) => e.name), ["DN-9"]);
});

test("formatting and monograms", () => {
	assert.equal(formatAmount(1697.4), "1,697.40");
	assert.equal(initials("مؤسسة الحربي لقطع الغيار"), "حل");
	assert.equal(initials("Faisal Al-Otaibi"), "FA");
});
