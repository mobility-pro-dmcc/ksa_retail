<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { dimensionLabel } from "../../domain/dimensions";
import { formatQuantity } from "../../domain/money";
import { quantityInCart } from "../../domain/cart";
import { useI18n } from "../../i18n";
import { useSaleStore } from "../../stores/sale";
import { useSessionStore } from "../../stores/session";
import type { CatalogItem, DimensionValues } from "../../types";
import AppIcon from "../common/AppIcon.vue";
import QuantityStepper from "../common/QuantityStepper.vue";

const LOW_STOCK = 8;
const props = defineProps<{ item: CatalogItem; dims: DimensionValues; tracked: boolean }>();
const sale = useSaleStore();
const session = useSessionStore();
const { t, m } = useI18n();

const label = computed(() => dimensionLabel(props.dims, session.dimensionFields));
const left = computed(() => sale.remaining(props.item, props.item.item_code, props.dims));
const inCart = computed(() => quantityInCart(sale.lines, props.item.item_code, props.dims, session.dimensionFields));
const soldOut = computed(() => left.value <= 0);
const quantity = ref(1);
watch(left, (value) => {
	if (value > 0 && quantity.value > value) quantity.value = Math.floor(value);
});

function add(qty: number) {
	if (qty >= 1) sale.addStock(props.item, props.dims, qty);
	quantity.value = 1;
}
</script>

<template>
	<div class="stock-row" :class="{ 'is-sold-out': soldOut }">
		<bdi class="stock-row__dimension data" :class="{ 'is-empty': !label }">{{ label || "—" }}</bdi>
		<span class="stock-row__level" :class="{ 'is-low': tracked && !soldOut && left <= LOW_STOCK }">
			<template v-if="!tracked">{{ t("notStockTracked") }}</template>
			<template v-else-if="soldOut">{{ t("outOfStock") }}</template>
			<bdi v-else class="data" :title="`${formatQuantity(left)} ${t('pieces')}`">{{ formatQuantity(left) }}</bdi>
		</span>
		<span class="stock-row__picker">
			<button type="button" class="chip-button" :disabled="soldOut" :aria-label="`${t('add')} 1`" @click="add(1)">{{ t("addOne") }}</button>
			<button v-if="tracked" type="button" class="chip-button" :disabled="soldOut" @click="add(left)">{{ t("addAll") }}</button>
			<QuantityStepper
				v-model="quantity"
				:min="1"
				:max="tracked ? Math.max(left, 1) : undefined"
				:disabled="soldOut"
				:label="`${t('quantity')} ${item.item_name} ${label}`"
				@enter="add(quantity)"
			/>
			<button type="button" class="icon-button icon-button--accent" :disabled="soldOut" :aria-label="t('add')" :title="t('add')" @click="add(quantity)">
				<AppIcon name="plus" />
			</button>
		</span>
		<span v-if="inCart" class="stock-row__note"><AppIcon name="check" :size="13" />{{ m.inThisSale(formatQuantity(inCart)) }}</span>
	</div>
</template>
