<script setup lang="ts">
import { inputNumber, inputValue } from "../../composables/events";
import { useI18n } from "../../i18n";
import { useSaleStore } from "../../stores/sale";
import { useSessionStore } from "../../stores/session";
import AppIcon from "../common/AppIcon.vue";

const sale = useSaleStore();
const session = useSessionStore();
const { t } = useI18n();
const modeOf = (name: string) => session.paymentModes.find((mode) => mode.name === name);
</script>

<template>
	<section class="checkout-section" :aria-label="t('payment')">
		<header class="section-label"><span>{{ t("payment") }}</span></header>
		<p v-if="!session.paymentModes.length" class="notice">{{ t("noPaymentModes") }}</p>
		<div v-for="(row, index) in sale.payments" :key="row.id" class="payment-row">
			<select class="input" :aria-label="t('payment')" :value="row.mode" @change="sale.updatePayment(row.id, { mode: inputValue($event) })">
				<option v-for="mode in session.paymentModes" :key="mode.name" :value="mode.name">{{ mode.name }}</option>
			</select>
			<input
				class="input input--amount data"
				type="number"
				min="0"
				step="0.01"
				placeholder="0.00"
				:aria-label="`${t('amount')} ${row.mode}`"
				:value="row.amount || ''"
				@input="sale.updatePayment(row.id, { amount: inputNumber($event) })"
			/>
			<button v-if="index > 0" type="button" class="icon-button" :aria-label="t('remove')" @click="sale.removePaymentRow(row.id)"><AppIcon name="close" :size="15" /></button>
			<span v-else class="payment-row__spacer" />
			<input
				v-if="modeOf(row.mode)?.requires_reference"
				class="input payment-row__reference"
				:placeholder="t('referenceNo')"
				:aria-label="t('referenceNo')"
				:value="row.reference"
				@input="sale.updatePayment(row.id, { reference: inputValue($event) })"
			/>
			<span class="payment-row__account">
				<span>{{ t("account") }}:</span><bdi class="code">{{ modeOf(row.mode)?.account }}</bdi>
				<span v-if="modeOf(row.mode)?.is_default" class="payment-row__default">· {{ t("yourDefault") }}</span>
			</span>
		</div>
		<div v-if="session.paymentModes.length" class="checkout-section__actions">
			<button type="button" class="link-button" @click="sale.addPaymentRow()"><AppIcon name="plus" :size="15" />{{ t("addPaymentMethod") }}</button>
			<button type="button" class="link-button link-button--muted" @click="sale.fillRemaining()">{{ t("fillRemaining") }}</button>
		</div>
	</section>
</template>
