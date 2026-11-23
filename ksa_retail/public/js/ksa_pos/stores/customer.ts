/** The customer being served and the customer search. */
import { defineStore } from "pinia";
import { ref } from "vue";
import { customerApi } from "../api/endpoints";
import { createLatest, debounce } from "../composables/latest";
import { formatAmount } from "../domain/money";
import { messages } from "../i18n/messages";
import type { CustomerHit, CustomerSummary } from "../types";
import { useOrdersStore } from "./orders";
import { useSaleStore } from "./sale";
import { useSessionStore } from "./session";
import { useUiStore } from "./ui";

const SEARCH_DELAY_MS = 220;

export const useCustomerStore = defineStore("customer", () => {
	const query = ref("");
	const results = ref<CustomerHit[] | null>(null);
	const searching = ref(false);
	const selected = ref<CustomerSummary | null>(null);
	const applyingCredit = ref(false);
	const searchRequest = createLatest();
	const selectRequest = createLatest();

	async function search(text: string): Promise<void> {
		searching.value = true;
		try {
			const outcome = await searchRequest.run((signal) => customerApi.search(text, { signal }));
			if (!outcome.superseded) results.value = outcome.value;
		} catch (error) {
			useUiStore().reportError(error);
		} finally {
			searching.value = false;
		}
	}
	const searchSoon = debounce((text: string) => void search(text), SEARCH_DELAY_MS);

	function setQuery(text: string): void {
		query.value = text;
		searchSoon(text);
	}

	async function select(name: string, summary?: CustomerSummary): Promise<void> {
		const orders = useOrdersStore();
		const sale = useSaleStore();
		results.value = null;
		query.value = "";
		if (sale.editing) sale.reset(); // an edit belongs to the previous customer's order
		else sale.leaveOrder();
		orders.reset();
		try {
			if (summary) {
				selectRequest.cancel();
				selected.value = summary;
			} else {
				const outcome = await selectRequest.run((signal) => customerApi.get(name, { signal }));
				if (outcome.superseded) return;
				selected.value = outcome.value;
			}
			await orders.load();
		} catch (error) {
			useUiStore().reportError(error);
		}
	}

	async function refresh(): Promise<void> {
		if (!selected.value) return;
		const outcome = await selectRequest.run((signal) => customerApi.get(selected.value!.name, { signal }));
		if (!outcome.superseded) selected.value = outcome.value;
	}

	function setSummary(summary: CustomerSummary): void {
		if (!selected.value || selected.value.name === summary.name) selected.value = summary;
	}

	async function register(values: Record<string, string | number>): Promise<void> {
		const summary = await customerApi.register(values);
		await select(summary.name, summary);
		useUiStore().notify(messages[useSessionStore().lang].customerCreated(summary.name));
	}

	async function applyCredit(): Promise<void> {
		if (!selected.value || applyingCredit.value) return;
		applyingCredit.value = true;
		try {
			const result = await customerApi.applyCredit(selected.value.name);
			selected.value = result.customer;
			const linked = result.links.reduce((total, link) => total + link.amount, 0);
			useUiStore().notify(messages[useSessionStore().lang].creditLinked(formatAmount(linked)));
			await useOrdersStore().refreshAfterChange();
		} catch (error) {
			useUiStore().reportError(error);
		} finally {
			applyingCredit.value = false;
		}
	}

	return { query, results, searching, selected, applyingCredit, setQuery, search, select, refresh, setSummary, register, applyCredit };
});
