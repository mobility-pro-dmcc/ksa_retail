<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { dimensionLabel } from "../../domain/dimensions";
import { formatQuantity } from "../../domain/money";
import { missingReference, nextMode, toPaymentInputs, type PaymentRow } from "../../domain/payments";
import { uid } from "../../domain/text";
import { useI18n } from "../../i18n";
import { useOrdersStore } from "../../stores/orders";
import { useSaleStore } from "../../stores/sale";
import { useSessionStore } from "../../stores/session";
import { useUiStore } from "../../stores/ui";
import AppIcon from "../common/AppIcon.vue";
import QuantityStepper from "../common/QuantityStepper.vue";
import ModalDialog from "./ModalDialog.vue";

const emit = defineEmits<{ (event: "close"): void }>();
const orders = useOrdersStore();
const sale = useSaleStore();
const session = useSessionStore();
const ui = useUiStore();
const { t, m } = useI18n();

const lines = computed(() => (orders.active?.lines ?? []).filter((line) => line.returnable > 0));
const quantities = reactive<Record<string, number>>(Object.fromEntries(lines.value.map((line) => [line.so_detail, 0])));
const refunds = ref<PaymentRow[]>([]);
const modeOf = (name: string) => session.paymentModes.find((mode) => mode.name === name);

function addRefund() {
	const mode = nextMode(refunds.value, session.paymentModes);
	if (mode) refunds.value = [...refunds.value, { id: uid(), mode, amount: 0, reference: "" }];
}

async function confirm() {
	const chosen = Object.fromEntries(Object.entries(quantities).filter(([, qty]) => Number(qty) > 0));
	if (!Object.keys(chosen).length) return;
	const missing = missingReference(refunds.value, session.paymentModes);
	if (missing) {
		ui.notify(m.value.referenceRequired(missing.mode), "error");
		return;
	}
	if (await sale.returnItems(chosen, toPaymentInputs(refunds.value))) emit("close");
}
</script>

<template>
	<ModalDialog :title="t('returnTitle')" :hint="t('returnHint')" @close="emit('close')">
		<ul class="dialog-lines">
			<li v-for="line in lines" :key="line.so_detail" class="dialog-line">
				<span class="dialog-line__info">
					<strong>{{ line.item_name }}</strong>
					<small>
						<bdi class="data">{{ line.item_code }}</bdi>
						<bdi v-if="dimensionLabel(line.dims, session.dimensionFields)" class="data">{{ dimensionLabel(line.dims, session.dimensionFields) }}</bdi>
						<span>{{ t("returnable") }} <bdi class="data">{{ formatQuantity(line.returnable) }}</bdi></span>
					</small>
				</span>
				<QuantityStepper
					v-model="quantities[line.so_detail]"
					:min="0"
					:max="line.returnable"
					:label="`${t('quantity')} ${line.item_name}`"
				/>
			</li>
		</ul>
		<section class="checkout-section">
			<header class="section-label"><span>{{ t("refundNow") }}</span></header>
			<div v-for="row in refunds" :key="row.id" class="payment-row">
				<select v-model="row.mode" class="input" :aria-label="t('payment')">
					<option v-for="mode in session.paymentModes" :key="mode.name" :value="mode.name">{{ mode.name }}</option>
				</select>
				<input v-model.number="row.amount" class="input input--amount data" type="number" min="0" step="0.01" placeholder="0.00" :aria-label="t('amount')" />
				<button type="button" class="icon-button" :aria-label="t('remove')" @click="refunds = refunds.filter((r) => r.id !== row.id)"><AppIcon name="close" :size="15" /></button>
				<input v-if="modeOf(row.mode)?.requires_reference" v-model="row.reference" class="input payment-row__reference" :placeholder="t('referenceNo')" />
			</div>
			<button type="button" class="link-button" @click="addRefund"><AppIcon name="plus" :size="15" />{{ t("addRefund") }}</button>
		</section>
		<template #actions>
			<button type="button" class="button button--danger" :class="{ 'is-busy': sale.busy === 'dialog' }" :disabled="Boolean(sale.busy)" @click="confirm">
				<AppIcon name="undo" />{{ t("createReturn") }}
			</button>
		</template>
	</ModalDialog>
</template>
