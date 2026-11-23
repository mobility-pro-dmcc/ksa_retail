/**
 * The sale being built in the checkout: cart, discount, payments, live quote, order
 * editing, and every write action. All write actions share one result handler, and
 * each carries a client reference so the server can drop duplicates (the reference
 * rotates only after a success, so a retry after a failure is deduplicated too).
 */
import { defineStore } from "pinia";
import { computed, ref } from "vue";
import { catalogApi, salesApi } from "../api/endpoints";
import { createLatest, debounce } from "../composables/latest";
import { addStockQuantity, clampQuantity, toSaleLines, type CartLine } from "../domain/cart";
import { amountDue, orderMoney, quoteMoney, submitIntent, type MoneyView } from "../domain/checkout";
import { formatAmount, formatQuantity } from "../domain/money";
import { fillAmount, hasPayment, missingReference, nextMode, paymentTotal, toPaymentInputs, type PaymentRow } from "../domain/payments";
import { remainingQuantity } from "../domain/stock";
import { uid } from "../domain/text";
import { messages } from "../i18n/messages";
import type { CatalogItem, DimensionValues, DiscountInput, LineQuantities, OrderDetail, PaymentInput, Totals, TransactionResult } from "../types";
import { useCatalogStore } from "./catalog";
import { useCustomerStore } from "./customer";
import { useOrdersStore } from "./orders";
import { useSessionStore } from "./session";
import { useUiStore } from "./ui";

const QUOTE_DELAY_MS = 300;

export type Busy = null | "submit" | "deliver" | "invoice" | "dialog";

export interface DiscountState {
	kind: "pct" | "amount";
	value: number;
}

export const useSaleStore = defineStore("sale", () => {
	const session = useSessionStore();
	const lines = ref<CartLine[]>([]);
	const discount = ref<DiscountState>({ kind: "pct", value: 0 });
	const payments = ref<PaymentRow[]>([]);
	const quote = ref<Totals | null>(null);
	const quoting = ref(false);
	/** name of the order being edited, if any */
	const editing = ref<string | null>(null);
	const clientRef = ref(uid());
	const busy = ref<Busy>(null);
	const quoteRequest = createLatest();

	const orders = useOrdersStore();
	const text = computed(() => messages[session.lang]);
	const viewingOrder = computed(() => Boolean(orders.active) && !editing.value);
	const editingOrder = computed<OrderDetail | null>(() => (editing.value ? orders.active : null));
	const paidNow = computed(() => (editing.value ? 0 : paymentTotal(payments.value)));
	const intent = computed(() =>
		submitIntent({ editing: Boolean(editing.value), viewingOrder: viewingOrder.value, hasItems: lines.value.length > 0, hasPayment: hasPayment(payments.value) }),
	);
	const money = computed<MoneyView | null>(() => {
		if (viewingOrder.value && orders.active) return orderMoney(orders.active, paidNow.value);
		return quote.value ? quoteMoney(quote.value, paidNow.value, editingOrder.value) : null;
	});
	const hasSupplierLines = computed(() => lines.value.some((line) => line.drop_ship));

	// ------------------------------------------------------------------ payments
	function resetPayments(): void {
		const mode = session.defaultMode;
		payments.value = mode ? [{ id: uid(), mode, amount: 0, reference: "" }] : [];
	}

	function addPaymentRow(): void {
		const mode = nextMode(payments.value, session.paymentModes);
		if (mode) payments.value = [...payments.value, { id: uid(), mode, amount: 0, reference: "" }];
	}

	function updatePayment(id: string, patch: Partial<Omit<PaymentRow, "id">>): void {
		payments.value = payments.value.map((row) => (row.id === id ? { ...row, ...patch } : row));
	}

	function removePaymentRow(id: string): void {
		payments.value = payments.value.filter((row) => row.id !== id);
	}

	function fillRemaining(): void {
		const last = payments.value[payments.value.length - 1];
		if (!last) return;
		const due = amountDue(viewingOrder.value ? orders.active : null, quote.value);
		updatePayment(last.id, { amount: fillAmount(payments.value, last.id, due) });
	}

	// ------------------------------------------------------------------ cart
	function remaining(item: CatalogItem | undefined, itemCode: string, dims: DimensionValues, exceptLineKey?: string): number {
		return remainingQuantity({
			item,
			itemCode,
			dims,
			fields: session.dimensionFields,
			lines: lines.value,
			editingOrder: editingOrder.value,
			exceptLineKey,
		});
	}

	/** Adding products while an order is open (not being edited) starts a new sale. */
	function leaveOrder(): void {
		if (viewingOrder.value) {
			orders.close();
			resetPayments();
		}
	}

	function addStock(item: CatalogItem, dims: DimensionValues, requested: number): void {
		const left = remaining(item, item.item_code, dims);
		const qty = Math.min(Math.floor(requested), left);
		if (requested > left) useUiStore().notify(text.value.maxAvailable(formatQuantity(Math.max(left, 0))), "error");
		if (qty < 1) return;
		leaveOrder();
		const line: CartLine = {
			key: uid(),
			item_code: item.item_code,
			item_name: item.item_name,
			dims: { ...dims },
			qty,
			rate: null,
			price: item.rate,
			drop_ship: false,
			so_detail: null,
		};
		lines.value = addStockQuantity(lines.value, line, session.dimensionFields, Boolean(editing.value));
		requestQuote();
	}

	async function addFromSupplier(item: CatalogItem): Promise<void> {
		leaveOrder();
		const catalog = useCatalogStore();
		const dims: DimensionValues = {};
		for (const field of session.dimensionFields) dims[field] = (await catalog.valuesFor(field))[0] ?? "";
		lines.value = [
			...lines.value,
			{ key: uid(), item_code: item.item_code, item_name: item.item_name, dims, qty: 1, rate: null, price: item.rate, drop_ship: true, so_detail: null },
		];
		requestQuote();
	}

	function setQuantity(key: string, requested: number): void {
		const line = lines.value.find((l) => l.key === key);
		if (!line) return;
		const maximum = line.drop_ship
			? Number.POSITIVE_INFINITY
			: remaining(useCatalogStore().item(line.item_code), line.item_code, line.dims, key);
		if (requested > maximum) useUiStore().notify(text.value.maxAvailable(formatQuantity(maximum)), "error");
		const qty = clampQuantity(requested, maximum);
		lines.value = lines.value.map((l) => (l.key === key ? { ...l, qty } : l));
		requestQuote();
	}

	function setRate(key: string, rate: number | null): void {
		lines.value = lines.value.map((l) => (l.key === key ? { ...l, rate: rate === null ? null : Math.max(0, rate) } : l));
		requestQuote();
	}

	function setLineDimension(key: string, field: string, value: string): void {
		lines.value = lines.value.map((l) => (l.key === key ? { ...l, dims: { ...l.dims, [field]: value } } : l));
	}

	function removeLine(key: string): void {
		lines.value = lines.value.filter((l) => l.key !== key);
		requestQuote();
	}

	function setDiscount(next: Partial<DiscountState>): void {
		discount.value = { ...discount.value, ...next };
		requestQuote();
	}

	// ------------------------------------------------------------------ quote
	function discountInput(): DiscountInput | null {
		if (editing.value || !(discount.value.value > 0)) return null;
		return { type: discount.value.kind, value: discount.value.value };
	}

	async function refreshQuote(): Promise<void> {
		if (!lines.value.length || viewingOrder.value) {
			quoteRequest.cancel();
			quote.value = null;
			quoting.value = false;
			return;
		}
		quoting.value = true;
		try {
			const customer = useCustomerStore().selected?.name ?? null;
			const outcome = await quoteRequest.run((signal) => catalogApi.quote(customer, toSaleLines(lines.value), discountInput(), { signal }));
			if (outcome.superseded) return;
			quote.value = outcome.value;
		} catch (error) {
			quote.value = null;
			useUiStore().reportError(error);
		}
		quoting.value = false;
	}
	const quoteSoon = debounce(() => void refreshQuote(), QUOTE_DELAY_MS);

	function requestQuote(): void {
		quoting.value = lines.value.length > 0;
		quoteSoon();
	}

	// ------------------------------------------------------------------ editing
	function startEdit(order: OrderDetail): void {
		editing.value = order.name;
		lines.value = order.lines.map((line) => ({
			key: uid(),
			item_code: line.item_code,
			item_name: line.item_name,
			dims: { ...line.dims },
			qty: line.qty,
			rate: line.rate,
			price: line.rate,
			drop_ship: Boolean(line.drop_ship),
			so_detail: line.so_detail,
		}));
		useUiStore().tab = "products";
		void useCatalogStore().prefetch();
		requestQuote();
	}

	function cancelEdit(): void {
		const name = editing.value;
		reset();
		if (name) void orders.open(name);
	}

	function reset(): void {
		quoteSoon.cancel();
		quoteRequest.cancel();
		lines.value = [];
		discount.value = { kind: "pct", value: 0 };
		quote.value = null;
		quoting.value = false;
		editing.value = null;
		clientRef.value = uid();
		resetPayments();
	}

	// ------------------------------------------------------------------ write actions
	function paymentInputs(): PaymentInput[] | null {
		const missing = missingReference(payments.value, session.paymentModes);
		if (missing) {
			useUiStore().notify(text.value.referenceRequired(missing.mode), "error");
			return null;
		}
		return editing.value ? [] : toPaymentInputs(payments.value);
	}

	async function run(kind: Exclude<Busy, null>, action: () => Promise<TransactionResult>): Promise<boolean> {
		if (busy.value) return false;
		busy.value = kind;
		try {
			applyResult(await action());
			return true;
		} catch (error) {
			useUiStore().reportError(error);
			return false;
		} finally {
			busy.value = null;
		}
	}

	function applyResult(result: TransactionResult): void {
		const ui = useUiStore();
		useCustomerStore().setSummary(result.customer);
		const staysOnProducts = ui.tab === "products" && !result.order;
		reset();
		orders.setActive(result.order);
		ui.tab = staysOnProducts ? "products" : "orders";
		void orders.load();
		if (useCatalogStore().items) void useCatalogStore().search();

		const details = result.documents.map((doc) => (doc.action === "cancelled" ? `${doc.name} · ${text.value.cancelled}` : doc.name));
		const linked = result.credit_links.reduce((total, link) => total + link.amount, 0);
		if (linked > 0.005) details.push(text.value.creditLinked(formatAmount(linked)));
		ui.notify(text.value.done, "success", details);
	}

	function customerName(): string | null {
		const customer = useCustomerStore().selected;
		if (!customer) useUiStore().notify(text.value.chooseCustomerTitle, "error");
		return customer?.name ?? null;
	}

	/** Main button. Supplier-delivered lines first need the supplier (dialog). */
	async function submit(): Promise<void> {
		if (intent.value === "none") return;
		if ((intent.value === "items" || intent.value === "both") && hasSupplierLines.value) {
			useUiStore().openDialog({ kind: "supplier", deliver: false });
			return;
		}
		if (intent.value === "save") {
			const order = editing.value;
			if (!order) return;
			await run("submit", () => salesApi.updateOrder({ client_ref: clientRef.value, sales_order: order, lines: toSaleLines(lines.value) }));
			return;
		}
		if (intent.value === "pay") {
			const customer = customerName();
			const paid = paymentInputs();
			if (!customer || !paid) return;
			await run("submit", () => salesApi.pay({ client_ref: clientRef.value, customer, sales_order: orders.active?.name ?? null, payments: paid }));
			return;
		}
		await createSale(false, null);
	}

	async function createSale(deliver: boolean, dropShip: { supplier: string; bill_no: string | null } | null): Promise<boolean> {
		const customer = customerName();
		const paid = paymentInputs();
		if (!customer || !paid) return false;
		return run(deliver ? "deliver" : "submit", () =>
			salesApi.createSale({
				client_ref: clientRef.value,
				customer,
				lines: toSaleLines(lines.value),
				discount: discountInput(),
				payments: paid,
				deliver: deliver ? 1 : 0,
				drop_ship: dropShip,
			}),
		);
	}

	/** Deliver on a new sale: supplier lines (or the supplier option) go through the dialog. */
	function deliverNewSale(bySupplier: boolean): void {
		if (bySupplier || hasSupplierLines.value) {
			useUiStore().openDialog({ kind: "supplier", deliver: true });
			return;
		}
		void createSale(true, null);
	}

	async function deliverOrder(quantities: LineQuantities | null, billNo: string | null): Promise<boolean> {
		const order = orders.active;
		const paid = paymentInputs();
		if (!order || !paid) return false;
		return run("deliver", () =>
			salesApi.deliver({ client_ref: clientRef.value, sales_order: order.name, quantities, bill_no: billNo, payments: paid }),
		);
	}

	async function invoiceOrder(quantities: LineQuantities | null): Promise<boolean> {
		const order = orders.active;
		const paid = paymentInputs();
		if (!order || !paid) return false;
		return run("invoice", () => salesApi.invoice({ client_ref: clientRef.value, sales_order: order.name, quantities, payments: paid }));
	}

	async function returnItems(quantities: LineQuantities, refunds: PaymentInput[]): Promise<boolean> {
		const order = orders.active;
		if (!order) return false;
		return run("dialog", () => salesApi.returnItems({ client_ref: clientRef.value, sales_order: order.name, quantities, refunds }));
	}

	async function billSupplier(billNo: string | null): Promise<boolean> {
		const order = orders.active;
		if (!order) return false;
		return run("dialog", () => salesApi.billSupplier({ client_ref: clientRef.value, sales_order: order.name, bill_no: billNo }));
	}

	return {
		lines,
		discount,
		payments,
		quote,
		quoting,
		editing,
		clientRef,
		busy,
		viewingOrder,
		editingOrder,
		paidNow,
		intent,
		money,
		hasSupplierLines,
		resetPayments,
		addPaymentRow,
		updatePayment,
		removePaymentRow,
		fillRemaining,
		remaining,
		leaveOrder,
		addStock,
		addFromSupplier,
		setQuantity,
		setRate,
		setLineDimension,
		removeLine,
		setDiscount,
		requestQuote,
		startEdit,
		cancelEdit,
		reset,
		submit,
		createSale,
		deliverNewSale,
		deliverOrder,
		invoiceOrder,
		returnItems,
		billSupplier,
	};
});
