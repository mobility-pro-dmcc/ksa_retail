/** Product search with stock per dimension, plus a cache used for quantity limits. */
import { defineStore } from "pinia";
import { ref, shallowRef } from "vue";
import { catalogApi } from "../api/endpoints";
import { createLatest, debounce } from "../composables/latest";
import type { CatalogItem } from "../types";
import { useUiStore } from "./ui";

const PAGE_SIZE = 24;
const PREFETCH_SIZE = 60;
const SEARCH_DELAY_MS = 250;

export const useCatalogStore = defineStore("catalog", () => {
	const query = ref("");
	const brand = ref<string | null>(null);
	/** "stock": only items with stock in the selected warehouse */
	const availability = ref<"all" | "stock">("all");
	const items = ref<CatalogItem[] | null>(null);
	const brands = ref<string[]>([]);
	const hasMore = ref(false);
	const loading = ref(false);
	const failed = ref(false);
	/** every item seen, by code: stock limits for cart lines even when filtered out */
	const known = shallowRef<Map<string, CatalogItem>>(new Map());
	const request = createLatest();
	const dimensionValues = new Map<string, Promise<string[]>>();

	function remember(list: CatalogItem[]): void {
		const next = new Map(known.value);
		for (const item of list) next.set(item.item_code, item);
		known.value = next;
	}

	async function search(append = false): Promise<void> {
		loading.value = true;
		failed.value = false;
		const start = append && items.value ? items.value.length : 0;
		try {
			const outcome = await request.run((signal) =>
				catalogApi.search({
						query: query.value,
						brand: brand.value,
						start,
						page_length: PAGE_SIZE,
						in_stock: availability.value === "stock" ? 1 : 0,
					}, { signal }),
			);
			if (outcome.superseded) return;
			const result = outcome.value;
			items.value = append && items.value ? [...items.value, ...result.items] : result.items;
			if (result.brands) brands.value = result.brands;
			hasMore.value = result.items.length === PAGE_SIZE;
			remember(result.items);
		} catch (error) {
			failed.value = true;
			useUiStore().reportError(error);
		} finally {
			loading.value = false;
		}
	}
	const searchSoon = debounce(() => void search(), SEARCH_DELAY_MS);

	function setQuery(text: string): void {
		query.value = text;
		searchSoon();
	}

	function setBrand(next: string | null): void {
		brand.value = brand.value === next ? null : next;
		items.value = null;
		void search();
	}

	function setAvailability(next: "all" | "stock"): void {
		if (availability.value === next) return;
		availability.value = next;
		items.value = null;
		void search();
	}

	function item(code: string): CatalogItem | undefined {
		return known.value.get(code);
	}

	/** Fill the cache (used when editing an order: limits for its items). */
	async function prefetch(): Promise<void> {
		try {
			remember((await catalogApi.search({ query: "", brand: null, start: 0, page_length: PREFETCH_SIZE })).items);
		} catch {
			/* limits fall back to the server check */
		}
	}

	function valuesFor(fieldname: string): Promise<string[]> {
		let pending = dimensionValues.get(fieldname);
		if (!pending) {
			pending = catalogApi.dimensionValues(fieldname).catch(() => []);
			dimensionValues.set(fieldname, pending);
		}
		return pending;
	}

	return { query, brand, availability, items, brands, hasMore, loading, failed, setQuery, setBrand, setAvailability, search, item, prefetch, valuesFor };
});
