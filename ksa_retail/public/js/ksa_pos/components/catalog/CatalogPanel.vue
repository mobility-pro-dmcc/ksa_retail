<script setup lang="ts">
import { inputValue } from "../../composables/events";
import { onMounted } from "vue";
import { useI18n } from "../../i18n";
import { useCatalogStore } from "../../stores/catalog";
import AppIcon from "../common/AppIcon.vue";
import EmptyState from "../common/EmptyState.vue";
import SegmentedControl from "../common/SegmentedControl.vue";
import ProductCard from "./ProductCard.vue";

const catalog = useCatalogStore();
const { t } = useI18n();
const VISIBLE_BRANDS = 10;

function onAvailability(value: string) {
	catalog.setAvailability(value === "stock" ? "stock" : "all");
}

onMounted(() => {
	if (catalog.items === null) void catalog.search();
});
</script>

<template>
	<div class="catalog-panel">
		<div class="catalog-panel__tools">
			<label class="search-field">
				<AppIcon name="search" />
				<span class="visually-hidden">{{ t("searchItems") }}</span>
				<input type="search" autocomplete="off" :placeholder="t('searchItems')" :value="catalog.query" @input="catalog.setQuery(inputValue($event))" />
			</label>
			<SegmentedControl
				:model-value="catalog.availability"
				:label="t('stockFilter')"
				:options="[
					{ value: 'stock', label: t('inStockOnly') },
					{ value: 'all', label: t('allItems') },
				]"
				@update:model-value="onAvailability"
			/>
			<div class="chip-row" role="group" :aria-label="t('allBrands')">
				<button
					v-for="brand in catalog.brands.slice(0, VISIBLE_BRANDS)"
					:key="brand"
					type="button"
					class="filter-chip"
					:aria-pressed="catalog.brand === brand"
					@click="catalog.setBrand(brand)"
				>
					{{ brand }}
				</button>
			</div>
		</div>
		<div v-if="catalog.items === null && !catalog.failed" class="card-grid card-grid--products">
			<div v-for="n in 6" :key="n" class="skeleton skeleton--product" />
		</div>
		<EmptyState v-else-if="catalog.failed && !catalog.items" icon="alert" :title="t('loadFailed')">
			<button type="button" class="button" @click="catalog.search()">{{ t("retry") }}</button>
		</EmptyState>
		<EmptyState v-else-if="catalog.items && !catalog.items.length" icon="search" :title="catalog.availability === 'stock' ? t('noStockedItems') : t('noItems')" />
		<template v-else-if="catalog.items">
			<div class="card-grid card-grid--products" :class="{ 'is-refreshing': catalog.loading }">
				<ProductCard v-for="item in catalog.items" :key="item.item_code" :item="item" />
			</div>
			<button v-if="catalog.hasMore" type="button" class="button load-more" :class="{ 'is-busy': catalog.loading }" @click="catalog.search(true)">
				{{ t("loadMore") }}
			</button>
		</template>
	</div>
</template>
