<script setup lang="ts">
import { ref } from "vue";
import { useDismiss } from "../../composables/dismiss";
import { useI18n } from "../../i18n";
import { useCatalogStore } from "../../stores/catalog";
import { useSaleStore } from "../../stores/sale";
import { useSessionStore } from "../../stores/session";
import { useUiStore } from "../../stores/ui";
import AppIcon from "../common/AppIcon.vue";

const session = useSessionStore();
const catalog = useCatalogStore();
const sale = useSaleStore();
const ui = useUiStore();
const { t, m } = useI18n();
const open = ref(false);
const switching = ref(false);
const root = ref<HTMLElement | null>(null);
useDismiss(root, () => open.value, () => (open.value = false));

async function choose(name: string) {
	open.value = false;
	if (name === session.warehouse || switching.value) return;
	switching.value = true;
	try {
		await session.setWarehouse(name);
		// stock and the cart's stock check now refer to the new warehouse
		if (catalog.items !== null) await catalog.search();
		if (sale.lines.length) sale.requestQuote();
		ui.notify(m.value.warehouseChanged(name));
	} catch (error) {
		ui.reportError(error);
	} finally {
		switching.value = false;
	}
}
</script>

<template>
	<div v-if="session.warehouse" ref="root" class="warehouse-picker">
		<button
			v-if="session.warehouses.length > 1"
			type="button"
			class="topbar__warehouse topbar__warehouse--button"
			:class="{ 'is-busy': switching }"
			:title="t('changeWarehouse')"
			aria-haspopup="listbox"
			:aria-expanded="open"
			:disabled="Boolean(sale.busy) || switching"
			@click="open = !open"
		>
			<AppIcon name="warehouse" :size="15" /><bdi>{{ session.warehouse }}</bdi><AppIcon name="chevron" :size="12" />
		</button>
		<span v-else class="topbar__warehouse" :title="t('warehouse')"><AppIcon name="warehouse" :size="15" /><bdi>{{ session.warehouse }}</bdi></span>
		<div v-if="open" class="popover warehouse-picker__menu" role="listbox" :aria-label="t('changeWarehouse')">
			<p class="warehouse-picker__title">{{ t("changeWarehouse") }}</p>
			<button
				v-for="name in session.warehouses"
				:key="name"
				type="button"
				role="option"
				class="menu-item"
				:aria-selected="name === session.warehouse"
				@click="choose(name)"
			>
				<AppIcon :name="name === session.warehouse ? 'check' : 'warehouse'" :size="16" /><bdi>{{ name }}</bdi>
			</button>
		</div>
	</div>
</template>
