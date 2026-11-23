<script setup lang="ts">
import { inputNumber } from "../../composables/events";
import { useI18n } from "../../i18n";
import { useSaleStore } from "../../stores/sale";
import { useSessionStore } from "../../stores/session";
import SegmentedControl from "../common/SegmentedControl.vue";

const sale = useSaleStore();
const session = useSessionStore();
const { t } = useI18n();
</script>

<template>
	<section class="checkout-section" :aria-label="t('discount')">
		<header class="section-label"><span>{{ t("discount") }}</span></header>
		<div class="discount-control">
			<SegmentedControl
				:model-value="sale.discount.kind"
				:label="t('discount')"
				:options="[
					{ value: 'pct', label: '%' },
					{ value: 'amount', label: session.lang === 'ar' && session.boot.settings.currency === 'SAR' ? 'ر.س' : session.boot.settings.currency },
				]"
				@update:model-value="(kind) => sale.setDiscount({ kind: kind === 'amount' ? 'amount' : 'pct' })"
			/>
			<input
				class="input input--amount data"
				type="number"
				min="0"
				step="0.01"
				placeholder="0"
				:aria-label="t('discount')"
				:value="sale.discount.value || ''"
				@input="sale.setDiscount({ value: inputNumber($event) })"
			/>
		</div>
	</section>
</template>
