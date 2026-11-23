<script setup lang="ts">
import { computed } from "vue";
import { initials } from "../../domain/text";
import { useI18n } from "../../i18n";
import { useCustomerStore } from "../../stores/customer";
import { useSessionStore } from "../../stores/session";
import AppIcon from "../common/AppIcon.vue";
import MoneyAmount from "../common/MoneyAmount.vue";

const customerStore = useCustomerStore();
const session = useSessionStore();
const { t } = useI18n();
const customer = computed(() => customerStore.selected);
const canApplyCredit = computed(
	() => Boolean(customer.value) && customer.value!.advance > 0.005 && customer.value!.open_invoices > 0.005 && session.can("Payment Entry", "submit"),
);
</script>

<template>
	<section v-if="customer" class="customer-header" :aria-label="customer.customer_name">
		<span class="monogram monogram--large">{{ initials(customer.customer_name) }}</span>
		<div class="customer-header__identity">
			<h1 class="customer-header__name">{{ customer.customer_name }}</h1>
			<p class="customer-header__meta">
				<bdi v-if="customer.name !== customer.customer_name" class="code">{{ customer.name }}</bdi>
				<bdi v-if="customer.mobile_no" class="data">{{ customer.mobile_no }}</bdi>
				<span v-if="customer.territory">{{ customer.territory }}</span>
				<span v-if="!customer.has_address" class="badge badge--warning"><AppIcon name="alert" :size="14" />{{ t("noAddress") }}</span>
			</p>
		</div>
		<dl class="customer-header__figures">
			<!-- the customer's account balance as ERPNext's ledger has it (net) -->
			<div class="figure" :class="{ 'figure--due': customer.balance > 0.005 }">
				<dt>{{ t("outstanding") }}</dt>
				<dd><MoneyAmount :value="Math.max(customer.balance, 0)" /></dd>
			</div>
			<div class="figure" :class="{ 'figure--credit': customer.balance < -0.005 }">
				<dt>{{ t("credit") }}</dt>
				<dd><MoneyAmount :value="Math.max(-customer.balance, 0)" /></dd>
			</div>
		</dl>
		<button
			v-if="canApplyCredit"
			type="button"
			class="button button--quiet customer-header__credit"
			:class="{ 'is-busy': customerStore.applyingCredit }"
			:disabled="customerStore.applyingCredit"
			@click="customerStore.applyCredit()"
		>
			<AppIcon name="link" />{{ t("applyCredit") }}
		</button>
	</section>
	<section v-else class="customer-header customer-header--empty">
		<span class="customer-header__prompt-icon"><AppIcon name="search" :size="22" /></span>
		<div>
			<h1 class="customer-header__name">{{ t("chooseCustomerTitle") }}</h1>
			<p class="customer-header__meta">{{ t("chooseCustomerHint") }}</p>
		</div>
	</section>
</template>
