<script setup lang="ts">
import { ref } from "vue";
import { useI18n } from "../../i18n";
import { useSaleStore } from "../../stores/sale";
import { useSessionStore } from "../../stores/session";
import AppIcon from "../common/AppIcon.vue";
import ModalDialog from "./ModalDialog.vue";

const emit = defineEmits<{ (event: "close"): void }>();
const sale = useSaleStore();
const session = useSessionStore();
const { t } = useI18n();
const billNo = ref("");
const invalid = ref(false);

async function confirm() {
	invalid.value = session.boot.bill_no_required && !billNo.value.trim();
	if (invalid.value) return;
	if (await sale.billSupplier(billNo.value.trim() || null)) emit("close");
}
</script>

<template>
	<ModalDialog :title="t('billSupplierTitle')" :hint="t('billSupplierHint')" @close="emit('close')">
		<label class="field" :class="{ 'has-error': invalid }">
			<span class="field__label">{{ t("supplierInvoiceNo") }}<span v-if="session.boot.bill_no_required" class="field__required" aria-hidden="true">*</span></span>
			<input v-model="billNo" class="input" dir="ltr" data-autofocus @keydown.enter="confirm" />
			<span v-if="invalid" class="field__error">{{ t("required") }}</span>
		</label>
		<template #actions>
			<button type="button" class="button button--primary" :class="{ 'is-busy': sale.busy === 'dialog' }" :disabled="Boolean(sale.busy)" @click="confirm">
				<AppIcon name="invoice" />{{ t("confirm") }}
			</button>
		</template>
	</ModalDialog>
</template>
