/** The selected customer's orders and the order open in the checkout. */
import { defineStore } from "pinia";
import { ref } from "vue";
import { orderApi } from "../api/endpoints";
import { createLatest } from "../composables/latest";
import type { OrderCard, OrderDetail } from "../types";
import { useCustomerStore } from "./customer";
import { useUiStore } from "./ui";

const PAGE_SIZE = 20;

export const useOrdersStore = defineStore("orders", () => {
	/** null until the first page arrives */
	const cards = ref<OrderCard[] | null>(null);
	const filter = ref<"all" | "incomplete">("all");
	const hasMore = ref(false);
	const loading = ref(false);
	const failed = ref(false);
	const active = ref<OrderDetail | null>(null);
	const opening = ref<string | null>(null);
	const listRequest = createLatest();
	const detailRequest = createLatest();

	async function load(append = false): Promise<void> {
		const customer = useCustomerStore().selected;
		if (!customer) return;
		loading.value = true;
		failed.value = false;
		const start = append && cards.value ? cards.value.length : 0;
		try {
			const outcome = await listRequest.run((signal) =>
				orderApi.list(
					{ customer: customer.name, only_incomplete: filter.value === "incomplete" ? 1 : 0, start, page_length: PAGE_SIZE },
					{ signal },
				),
			);
			if (outcome.superseded) return;
			cards.value = append && cards.value ? [...cards.value, ...outcome.value] : outcome.value;
			hasMore.value = filter.value === "all" && outcome.value.length === PAGE_SIZE;
		} catch (error) {
			failed.value = true;
			useUiStore().reportError(error);
		} finally {
			loading.value = false;
		}
	}

	function setFilter(next: "all" | "incomplete"): void {
		if (filter.value === next) return;
		filter.value = next;
		cards.value = null;
		void load();
	}

	async function open(name: string): Promise<void> {
		opening.value = name;
		try {
			const outcome = await detailRequest.run((signal) => orderApi.get(name, { signal }));
			if (!outcome.superseded) active.value = outcome.value;
		} catch (error) {
			useUiStore().reportError(error);
		} finally {
			if (opening.value === name) opening.value = null;
		}
	}

	function close(): void {
		detailRequest.cancel();
		active.value = null;
	}

	function setActive(order: OrderDetail | null): void {
		detailRequest.cancel();
		active.value = order;
	}

	/** After anything changed money or documents: list + open order. */
	async function refreshAfterChange(): Promise<void> {
		const reloads = [load()];
		if (active.value) reloads.push(open(active.value.name));
		await Promise.all(reloads);
	}

	function reset(): void {
		listRequest.cancel();
		detailRequest.cancel();
		cards.value = null;
		active.value = null;
		hasMore.value = false;
		failed.value = false;
	}

	return { cards, filter, hasMore, loading, failed, active, opening, load, setFilter, open, close, setActive, refreshAfterChange, reset };
});
