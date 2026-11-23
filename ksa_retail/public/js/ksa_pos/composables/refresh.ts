/**
 * Reload what the screen shows from the server (customer balances, orders, the open order,
 * product stock, cart totals) without reloading the page: the cart, payments and an edit in
 * progress are kept.
 */
import { ref } from "vue";
import { useCatalogStore } from "../stores/catalog";
import { useCustomerStore } from "../stores/customer";
import { useOrdersStore } from "../stores/orders";
import { useSaleStore } from "../stores/sale";
import { useUiStore } from "../stores/ui";

const refreshing = ref(false);

export function useRefresh() {
	async function refreshAll(): Promise<boolean> {
		if (refreshing.value) return false;
		refreshing.value = true;
		const customer = useCustomerStore();
		const orders = useOrdersStore();
		const catalog = useCatalogStore();
		const sale = useSaleStore();
		try {
			const work: Promise<unknown>[] = [];
			if (customer.selected) work.push(customer.refresh(), orders.load());
			if (orders.active) work.push(orders.open(orders.active.name));
			if (catalog.items !== null) work.push(catalog.search());
			await Promise.all(work);
			if (sale.lines.length && !sale.viewingOrder) sale.requestQuote();
			return true;
		} catch (error) {
			useUiStore().reportError(error);
			return false;
		} finally {
			refreshing.value = false;
		}
	}
	return { refreshing, refreshAll };
}
