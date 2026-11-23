<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "../../i18n";
import { useOrdersStore } from "../../stores/orders";
import { useSaleStore } from "../../stores/sale";
import MoneyAmount from "../common/MoneyAmount.vue";

const sale = useSaleStore();
const orders = useOrdersStore();
const { t } = useI18n();
const totals = computed(() => (sale.viewingOrder ? orders.active?.totals ?? null : sale.quote));
const money = computed(() => sale.money);
/** The order's own subtotal / tax lines only add up when its invoices match it (an order
 * made before a tax template existed gets VAT on its invoices instead). */
const showBreakdown = computed(() => !sale.viewingOrder || !orders.active || Math.abs((totals.value?.rounded_total ?? 0) - orders.active.gross_total) < 0.01);
const balanceText = computed(() => {
	const label = money.value?.balanceLabel;
	if (label === "refund_due") return t("refundDue");
	if (label === "credit") return t("customerCredit");
	return t("remaining");
});
</script>

<template>
	<section class="totals" :class="{ 'is-calculating': sale.quoting }" aria-live="polite">
		<p v-if="sale.quoting && !totals" class="totals__status">{{ t("calculating") }}</p>
		<template v-if="totals && money">
			<template v-if="showBreakdown">
				<div class="totals__row"><span>{{ t("subtotal") }}</span><MoneyAmount :value="totals.subtotal" /></div>
				<div v-if="totals.discount > 0" class="totals__row totals__row--saving"><span>{{ t("discount") }}</span><span>−&nbsp;<MoneyAmount :value="totals.discount" /></span></div>
				<div v-for="tax in totals.taxes" :key="tax.description" class="totals__row"><span>{{ tax.description }}</span><MoneyAmount :value="tax.amount" /></div>
			</template>
			<div class="totals__row totals__row--grand" :class="{ 'is-struck': money.returns > 0.005 }"><span>{{ t("grandTotal") }}</span><MoneyAmount :value="money.gross" /></div>
			<template v-if="money.returns > 0.005">
				<div class="totals__row totals__row--saving"><span>{{ t("returns") }}</span><span>−&nbsp;<MoneyAmount :value="money.returns" /></span></div>
				<div class="totals__row totals__row--grand"><span>{{ t("netTotal") }}</span><MoneyAmount :value="money.net" /></div>
			</template>
			<div v-if="money.paidBefore > 0.005" class="totals__row"><span>{{ t("paidBefore") }}</span><MoneyAmount :value="money.paidBefore" /></div>
			<div v-if="!sale.editing" class="totals__row"><span>{{ t("paidNow") }}</span><MoneyAmount :value="money.paidNow" /></div>
			<div class="totals__row totals__row--balance" :class="[`is-${money.balanceLabel}`, { 'is-settled': money.balance < 0.005 }]"><span>{{ balanceText }}</span><MoneyAmount :value="money.balance" /></div>
		</template>
		<div v-else-if="!sale.quoting" class="totals__row"><span>{{ t("paidNow") }}</span><MoneyAmount :value="sale.paidNow" /></div>
	</section>
</template>
