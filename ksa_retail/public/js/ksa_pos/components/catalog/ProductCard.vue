<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "../../i18n";
import { useSaleStore } from "../../stores/sale";
import { useSessionStore } from "../../stores/session";
import type { CatalogItem } from "../../types";
import AppIcon from "../common/AppIcon.vue";
import MoneyAmount from "../common/MoneyAmount.vue";
import TireGlyph from "../common/TireGlyph.vue";
import StockRow from "./StockRow.vue";

const props = defineProps<{ item: CatalogItem }>();
const sale = useSaleStore();
const session = useSessionStore();
const { t } = useI18n();

const tracked = computed(() => Boolean(props.item.is_stock_item));
/** the first spec (tyre size on this site) is the product's headline */
const headline = computed(() => props.item.specs[0]?.value ?? null);
const rows = computed(() => (tracked.value && props.item.stock.length ? props.item.stock.map((bucket) => bucket.dims) : [{}]));
const dimensionTitle = computed(() => session.dimensionFields.map((field) => session.dimensionLabel(field)).join(" · "));
</script>

<template>
	<article class="product-card">
		<header class="product-card__head">
			<span class="product-card__media">
				<img v-if="item.image" :src="item.image" alt="" loading="lazy" />
				<TireGlyph v-else />
			</span>
			<span class="product-card__identity">
				<span v-if="item.brand" class="product-card__brand">{{ item.brand }}</span>
				<bdi v-if="headline" class="product-card__size data">{{ headline }}</bdi>
				<span class="product-card__name">{{ item.item_name }}</span>
				<span class="product-card__specs">
					<bdi class="data">{{ item.item_code }}</bdi>
					<bdi v-for="spec in item.specs.slice(1)" :key="spec.label" class="spec" :title="spec.label">{{ spec.value }}</bdi>
				</span>
			</span>
		</header>
		<div class="product-card__price">
			<MoneyAmount :value="item.rate" />
			<small>{{ t("priceListRate") }}</small>
		</div>
		<div class="product-card__stock">
			<div class="product-card__stock-head">
				<span>{{ dimensionTitle }}</span>
				<span>{{ t("available") }}</span>
			</div>
			<StockRow v-for="(dims, index) in rows" :key="index" :item="item" :dims="dims" :tracked="tracked" />
		</div>
		<footer v-if="session.can('Purchase Order', 'submit') && !sale.editing" class="product-card__footer">
			<button type="button" class="link-button" @click="sale.addFromSupplier(item)"><AppIcon name="truck" :size="15" />{{ t("orderFromSupplier") }}</button>
		</footer>
	</article>
</template>
