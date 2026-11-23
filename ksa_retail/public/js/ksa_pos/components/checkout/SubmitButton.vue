<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "../../i18n";
import { useCustomerStore } from "../../stores/customer";
import { useSaleStore } from "../../stores/sale";
import AppIcon from "../common/AppIcon.vue";

const sale = useSaleStore();
const customer = useCustomerStore();
const { t } = useI18n();

const copy = computed(() => {
	switch (sale.intent) {
		case "items":
			return { label: t("submitItems"), hint: t("submitItemsHint") };
		case "both":
			return { label: t("submitBoth"), hint: t("submitBothHint") };
		case "pay":
			return { label: t("submitPay"), hint: sale.viewingOrder ? t("submitPayOrderHint") : t("submitPayAdvanceHint") };
		case "save":
			return { label: t("submitSave"), hint: t("submitSaveHint") };
		default:
			return { label: t("submitNone"), hint: "" };
	}
});
const disabled = computed(
	() => sale.intent === "none" || !customer.selected || Boolean(sale.busy) || (sale.intent === "save" && !sale.lines.length),
);
</script>

<template>
	<div class="submit-bar">
		<button type="button" class="submit-button" :class="{ 'is-busy': sale.busy === 'submit' }" :disabled="disabled" @click="sale.submit()">
			<AppIcon v-if="sale.intent !== 'none'" name="done" :size="20" />
			<span class="submit-button__label">{{ copy.label }}</span>
			<small v-if="copy.hint" class="submit-button__hint">{{ copy.hint }}</small>
		</button>
	</div>
</template>
