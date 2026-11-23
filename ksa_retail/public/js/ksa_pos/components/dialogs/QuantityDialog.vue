<script setup lang="ts">
import { computed, reactive, ref } from "vue";
import { dimensionLabel } from "../../domain/dimensions";
import { formatQuantity } from "../../domain/money";
import { useI18n } from "../../i18n";
import { useOrdersStore } from "../../stores/orders";
import { useSaleStore } from "../../stores/sale";
import { useSessionStore } from "../../stores/session";
import AppIcon from "../common/AppIcon.vue";
import QuantityStepper from "../common/QuantityStepper.vue";
import ModalDialog from "./ModalDialog.vue";

const props = defineProps<{ mode: "deliver" | "invoice"; supplier: boolean }>();
const emit = defineEmits<{ (event: "close"): void }>();
const orders = useOrdersStore();
const sale = useSaleStore();
const session = useSessionStore();
const { t } = useI18n();

const lines = computed(() =>
	(orders.active?.lines ?? [])
		.map((line) => ({ line, pending: props.mode === "deliver" ? line.pending_delivery : Math.round(line.pending_billing * 1000) / 1000 }))
		.filter(({ line, pending }) => pending > 0.0001 && (props.mode === "invoice" || Boolean(line.drop_ship) === props.supplier)),
);
const quantities = reactive<Record<string, number>>(Object.fromEntries(lines.value.map(({ line, pending }) => [line.so_detail, pending])));
const billNo = ref("");
const showBillNo = computed(() => props.mode === "deliver" && props.supplier);
const working = computed(() => sale.busy !== null);

async function confirm() {
	const chosen = Object.fromEntries(Object.entries(quantities).filter(([, qty]) => Number(qty) > 0));
	if (!Object.keys(chosen).length) return;
	const ok = props.mode === "deliver" ? await sale.deliverOrder(chosen, billNo.value.trim() || null) : await sale.invoiceOrder(chosen);
	if (ok) emit("close");
}
</script>

<template>
	<ModalDialog
		:title="mode === 'deliver' ? (supplier ? t('supplierTitle') : t('deliverTitle')) : t('invoiceTitle')"
		:hint="supplier ? t('supplierHint') : mode === 'invoice' ? t('invoiceHint') : undefined"
		@close="emit('close')"
	>
		<ul class="dialog-lines">
			<li v-for="{ line, pending } in lines" :key="line.so_detail" class="dialog-line">
				<span class="dialog-line__info">
					<strong>{{ line.item_name }}</strong>
					<small>
						<bdi class="data">{{ line.item_code }}</bdi>
						<bdi v-if="dimensionLabel(line.dims, session.dimensionFields)" class="data">{{ dimensionLabel(line.dims, session.dimensionFields) }}</bdi>
						<span>{{ t("pending") }} <bdi class="data">{{ formatQuantity(pending) }}</bdi></span>
					</small>
				</span>
				<QuantityStepper
					v-model="quantities[line.so_detail]"
					:min="0"
					:max="pending"
					:readonly="supplier"
					:label="`${t('quantity')} ${line.item_name}`"
				/>
			</li>
		</ul>
		<label v-if="showBillNo" class="field">
			<span class="field__label">{{ t("supplierInvoiceNo") }}<span v-if="session.boot.bill_no_required" class="field__optional">· {{ t("supplierInvoiceLater") }}</span></span>
			<input v-model="billNo" class="input" dir="ltr" />
		</label>
		<template #actions>
			<button type="button" class="button button--primary" :class="{ 'is-busy': working }" :disabled="working || !lines.length" @click="confirm">
				<AppIcon :name="mode === 'deliver' ? 'truck' : 'invoice'" />{{ t("confirm") }}
			</button>
		</template>
	</ModalDialog>
</template>
