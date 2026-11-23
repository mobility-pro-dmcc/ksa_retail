/**
 * Keeps the screen as it was across page reloads (per user, this browser only):
 * customer, open order (and an edit in progress), tab, filter, searches, cart,
 * discount, payment rows and the pending transaction reference.
 * Storage may be unavailable (private mode, blocked): the app then just starts fresh.
 */
import { watch } from "vue";
import type { CartLine } from "../domain/cart";
import type { PaymentRow } from "../domain/payments";
import { debounce } from "../composables/latest";
import { useCatalogStore } from "./catalog";
import { useCustomerStore } from "./customer";
import { useOrdersStore } from "./orders";
import { useSaleStore, type DiscountState } from "./sale";
import { useSessionStore } from "./session";
import { useUiStore } from "./ui";

const VERSION = 2;
const SAVE_DELAY_MS = 300;

interface Snapshot {
	v: number;
	customer: string | null;
	activeOrder: string | null;
	editing: boolean;
	tab: "orders" | "products";
	filter: "all" | "incomplete";
	itemQuery: string;
	brand: string | null;
	availability?: "all" | "stock";
	lines: CartLine[];
	discount: DiscountState;
	payments: PaymentRow[];
	clientRef: string;
}

function storageKey(): string {
	return `ksa_pos_state:${useSessionStore().boot.user.name}`;
}

function read(): Snapshot | null {
	try {
		const parsed = JSON.parse(localStorage.getItem(storageKey()) ?? "null") as Snapshot | null;
		return parsed && parsed.v === VERSION ? parsed : null;
	} catch {
		return null;
	}
}

function snapshot(): Snapshot {
	const customer = useCustomerStore();
	const orders = useOrdersStore();
	const sale = useSaleStore();
	const catalog = useCatalogStore();
	const ui = useUiStore();
	return {
		v: VERSION,
		customer: customer.selected?.name ?? null,
		activeOrder: orders.active?.name ?? sale.editing,
		editing: Boolean(sale.editing),
		tab: ui.tab,
		filter: orders.filter,
		itemQuery: catalog.query,
		brand: catalog.brand,
		availability: catalog.availability,
		lines: sale.lines,
		discount: sale.discount,
		payments: sale.payments,
		clientRef: sale.clientRef,
	};
}

function write(): void {
	try {
		localStorage.setItem(storageKey(), JSON.stringify(snapshot()));
	} catch {
		/* storage unavailable: nothing to keep */
	}
}

export async function restoreSession(): Promise<void> {
	const saved = read();
	const sale = useSaleStore();
	sale.resetPayments();
	if (!saved) return;

	const ui = useUiStore();
	const orders = useOrdersStore();
	const catalog = useCatalogStore();
	const session = useSessionStore();
	ui.tab = saved.tab === "products" ? "products" : "orders";
	orders.filter = saved.filter === "incomplete" ? "incomplete" : "all";
	catalog.query = typeof saved.itemQuery === "string" ? saved.itemQuery : "";
	catalog.brand = typeof saved.brand === "string" ? saved.brand : null;
	catalog.availability = saved.availability === "stock" ? "stock" : "all";
	sale.lines = Array.isArray(saved.lines) ? saved.lines : [];
	sale.discount = saved.discount?.kind ? saved.discount : { kind: "pct", value: 0 };
	const knownModes = new Set(session.paymentModes.map((mode) => mode.name));
	const payments = Array.isArray(saved.payments) ? saved.payments.filter((row) => knownModes.has(row.mode)) : [];
	if (payments.length) sale.payments = payments;
	if (saved.clientRef) sale.clientRef = saved.clientRef;

	if (saved.customer) {
		await useCustomerStore().select(saved.customer);
		if (saved.activeOrder) {
			await orders.open(saved.activeOrder);
			if (saved.editing && orders.active) sale.editing = orders.active.name;
		}
	}
	if (ui.tab === "products") void catalog.search();
	if (sale.lines.length && !sale.viewingOrder) sale.requestQuote();
}

export function keepSessionSaved(): void {
	const save = debounce(write, SAVE_DELAY_MS);
	watch(snapshot, save, { deep: true });
	window.addEventListener("pagehide", write);
}
