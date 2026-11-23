<script setup lang="ts">
import { onMounted, ref } from "vue";
import { catalogApi } from "../../api/endpoints";
import { createLatest, debounce } from "../../composables/latest";
import { useI18n } from "../../i18n";
import { useSaleStore } from "../../stores/sale";
import { useSessionStore } from "../../stores/session";
import { useUiStore } from "../../stores/ui";
import AppIcon from "../common/AppIcon.vue";
import ModalDialog from "./ModalDialog.vue";

const props = defineProps<{ deliver: boolean }>();
const emit = defineEmits<{ (event: "close"): void }>();
const sale = useSaleStore();
const session = useSessionStore();
const ui = useUiStore();
const { t } = useI18n();

const query = ref("");
const suppliers = ref<{ name: string; supplier_name: string }[] | null>(null);
const chosen = ref<string | null>(null);
const billNo = ref("");
const request = createLatest();

async function load(text: string) {
	try {
		const outcome = await request.run((signal) => catalogApi.suppliers(text, { signal }));
		if (!outcome.superseded) suppliers.value = outcome.value;
	} catch (error) {
		ui.reportError(error);
	}
}
const loadSoon = debounce((text: string) => void load(text), 250);
onMounted(() => void load(""));

async function confirm() {
	if (!chosen.value) return;
	const ok = await sale.createSale(props.deliver, { supplier: chosen.value, bill_no: billNo.value.trim() || null });
	if (ok) emit("close");
}
</script>

<template>
	<ModalDialog :title="t('supplierTitle')" :hint="t('supplierHint')" @close="emit('close')">
		<label class="search-field">
			<AppIcon name="search" />
			<span class="visually-hidden">{{ t("searchSuppliers") }}</span>
			<input
				v-model="query"
				type="search"
				autocomplete="off"
				data-autofocus
				:placeholder="t('searchSuppliers')"
				@input="loadSoon(query)"
			/>
		</label>
		<div class="supplier-list" role="radiogroup" :aria-label="t('searchSuppliers')">
			<div v-if="suppliers === null" class="skeleton skeleton--row" />
			<p v-else-if="!suppliers.length" class="notice">{{ t("noSuppliers") }}</p>
			<button
				v-for="supplier in suppliers ?? []"
				:key="supplier.name"
				type="button"
				role="radio"
				class="supplier-option"
				:aria-checked="chosen === supplier.name"
				@click="chosen = supplier.name"
			>
				<strong>{{ supplier.supplier_name }}</strong><bdi class="data">{{ supplier.name }}</bdi>
			</button>
		</div>
		<label class="field">
			<span class="field__label">{{ t("supplierInvoiceNo") }}</span>
			<input v-model="billNo" class="input" dir="ltr" />
			<span v-if="session.boot.bill_no_required" class="field__help">{{ t("supplierInvoiceLater") }}</span>
		</label>
		<template #actions>
			<button type="button" class="button button--primary" :class="{ 'is-busy': Boolean(sale.busy) }" :disabled="!chosen || Boolean(sale.busy)" @click="confirm">
				<AppIcon name="truck" />{{ t("confirm") }}
			</button>
		</template>
	</ModalDialog>
</template>
