/** What the checkout shows and what its main button does. */
import type { OrderDetail, Totals } from "../types";
import { MONEY_EPSILON, round2 } from "./money";

export type SubmitIntent = "none" | "items" | "both" | "pay" | "save";

export function submitIntent(state: { editing: boolean; viewingOrder: boolean; hasItems: boolean; hasPayment: boolean }): SubmitIntent {
	if (state.editing) return "save";
	const newItems = !state.viewingOrder && state.hasItems;
	if (newItems && state.hasPayment) return "both";
	if (newItems) return "items";
	if (state.hasPayment) return "pay";
	return "none";
}

export type BalanceLabel = "remaining" | "credit" | "refund_due";

export interface MoneyView {
	gross: number;
	returns: number;
	net: number;
	paidBefore: number;
	paidNow: number;
	balance: number;
	balanceLabel: BalanceLabel;
}

function view(gross: number, returns: number, net: number, paidBefore: number, paidNow: number, refundDue: number): MoneyView {
	const balance = round2(net - paidBefore - paidNow);
	let balanceLabel: BalanceLabel = "remaining";
	if (balance < -MONEY_EPSILON) balanceLabel = refundDue > MONEY_EPSILON && paidNow < MONEY_EPSILON ? "refund_due" : "credit";
	return { gross, returns, net, paidBefore, paidNow, balance: Math.abs(balance), balanceLabel };
}

/** New sale (or an order being edited): ERPNext's quote is the authority. */
export function quoteMoney(totals: Totals, paidNow: number, editingOrder: OrderDetail | null): MoneyView {
	const grand = totals.rounded_total || totals.grand_total;
	const paidBefore = editingOrder ? editingOrder.paid + editingOrder.refund_due : 0;
	return view(grand, 0, grand, paidBefore, paidNow, editingOrder?.refund_due ?? 0);
}

/** An existing order: returns reduce the total; overpayment shows as refund due.
 * The server builds these from the invoices, so VAT added on an invoice is included. */
export function orderMoney(order: OrderDetail, paidNow: number): MoneyView {
	return view(order.gross_total, order.returns_value, order.total, order.paid + order.refund_due, paidNow, order.refund_due);
}

/** Amount still to collect, used by "Fill remaining". */
export function amountDue(order: OrderDetail | null, totals: Totals | null): number {
	if (order) return order.outstanding;
	return totals ? totals.rounded_total || totals.grand_total : 0;
}
