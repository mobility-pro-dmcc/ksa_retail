<script setup lang="ts">
import { inputValue } from "../../composables/events";
import { computed, onMounted, ref } from "vue";
import type { CartLine } from "../../domain/cart";
import { dimensionLabel } from "../../domain/dimensions";
import { useI18n } from "../../i18n";
import { useCatalogStore } from "../../stores/catalog";
import { useSaleStore } from "../../stores/sale";
import { useSessionStore } from "../../stores/session";
import AppIcon from "../common/AppIcon.vue";
import MoneyAmount from "../common/MoneyAmount.vue";
import QuantityStepper from "../common/QuantityStepper.vue";

const props = defineProps<{ line: CartLine; amount: number | null; quotedRate: number | null }>();
const sale = useSaleStore();
const session = useSessionStore();
const catalog = useCatalogStore();
const { t } = useI18n();

const label = computed(() => dimensionLabel(props.line.dims, session.dimensionFields));
const rate = computed(() => props.line.rate ?? props.quotedRate ?? props.line.price);
const choices = ref<Record<string, string[]>>({});
onMounted(async () => {
	if (!props.line.drop_ship) return;
	for (const field of session.dimensionFields) choices.value = { ...choices.value, [field]: await catalog.valuesFor(field) };
});

function onRate(event: Event) {
	const value = (event.target as HTMLInputElement).value;
	sale.setRate(props.line.key, value === "" ? null : Number(value));
}
</script>

<template>
	<div class="cart-line">
		<div class="cart-line__info">
			<span class="cart-line__name">{{ line.item_name }}</span>
			<span class="cart-line__meta">
				<bdi class="data">{{ line.item_code }}</bdi>
				<template v-if="line.drop_ship">
					<select
						v-for="field in session.dimensionFields"
						:key="field"
						class="input input--tiny data"
						:aria-label="session.dimensionLabel(field)"
						:value="line.dims[field] ?? ''"
						@change="sale.setLineDimension(line.key, field, inputValue($event))"
					>
						<option v-for="value in choices[field] ?? [line.dims[field] ?? '']" :key="value" :value="value">{{ value }}</option>
					</select>
					<span class="badge badge--supplier">{{ t("supplierDelivery") }}</span>
				</template>
				<bdi v-else-if="label" class="tag data">{{ label }}</bdi>
			</span>
		</div>
		<span class="cart-line__amount"><MoneyAmount :value="amount ?? line.qty * rate" :currency="false" /></span>
		<div class="cart-line__controls">
			<QuantityStepper
				:model-value="line.qty"
				:min="1"
				lazy
				:label="`${t('quantity')} ${line.item_name}`"
				@update:model-value="(qty) => sale.setQuantity(line.key, qty)"
			/>
			<label class="cart-line__rate">
				<span>{{ t("rate") }}</span>
				<input class="input input--small data" type="number" min="0" step="0.01" :value="rate" @change="onRate" />
			</label>
			<button type="button" class="icon-button icon-button--danger" :aria-label="t('remove')" @click="sale.removeLine(line.key)"><AppIcon name="trash" :size="16" /></button>
		</div>
	</div>
</template>
