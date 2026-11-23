<script setup lang="ts">
import { computed, ref } from "vue";
import { useDismiss } from "../../composables/dismiss";
import { documentTimeline, printUrl } from "../../domain/documents";
import { useI18n } from "../../i18n";
import { useOrdersStore } from "../../stores/orders";
import { useSaleStore } from "../../stores/sale";
import { useSessionStore } from "../../stores/session";
import { useUiStore } from "../../stores/ui";
import type { LinkedDoctype } from "../../types";
import AppIcon from "../common/AppIcon.vue";
import PrintMenu from "./PrintMenu.vue";

const orders = useOrdersStore();
const sale = useSaleStore();
const session = useSessionStore();
const ui = useUiStore();
const { t } = useI18n();

type Menu = "deliver" | "print" | "print-delivery" | "print-invoice" | null;
const menu = ref<Menu>(null);
const root = ref<HTMLElement | null>(null);
useDismiss(root, () => menu.value !== null, () => (menu.value = null));

const order = computed(() => (sale.viewingOrder ? orders.active : null));
const newSaleReady = computed(() => !order.value && !sale.editing && sale.lines.length > 0);
const delivered = computed(() => order.value?.status.delivery === "done");
const invoiced = computed(() => order.value?.status.invoice === "done");
const deliveries = computed(() => (order.value ? documentTimeline(order.value, "Delivery Note") : []));
const invoices = computed(() => (order.value ? documentTimeline(order.value, "Sales Invoice") : []));
const allDocuments = computed(() => (order.value ? documentTimeline(order.value) : []));
const canDeliver = computed(() => session.can("Delivery Note", "submit") && (order.value ? order.value.can_deliver : newSaleReady.value));
const canInvoice = computed(() => session.can("Sales Invoice", "submit") && Boolean(order.value?.can_invoice));
const hasSupplierPending = computed(() => (order.value ? order.value.lines.some((l) => l.drop_ship && l.pending_delivery > 0) : true));
const hasWarehousePending = computed(() => (order.value ? order.value.lines.some((l) => !l.drop_ship && l.pending_delivery > 0) : true));

function toggle(next: Menu) {
	menu.value = menu.value === next ? null : next;
}

function deliver(bySupplier: boolean) {
	menu.value = null;
	if (order.value) ui.openDialog({ kind: "deliver", supplier: bySupplier });
	else sale.deliverNewSale(bySupplier);
}

function invoice() {
	if (order.value) ui.openDialog({ kind: "invoice" });
}

function printSingle(doctypeName: LinkedDoctype) {
	const entry = (doctypeName === "Delivery Note" ? deliveries : invoices).value.at(-1);
	if (!entry) return;
	window.open(printUrl(entry.doctype, entry.name, session.boot.print_formats[entry.doctype] || "Standard", session.lang), "_blank", "noopener");
}
</script>

<template>
	<div ref="root" class="operation-bar">
		<div class="operation-bar__slot">
			<template v-if="delivered && deliveries.length">
				<button v-if="deliveries.length > 1" type="button" class="operation is-delivered" :aria-expanded="menu === 'print-delivery'" @click="toggle('print-delivery')">
					<AppIcon name="print" :size="20" /><span>{{ t("printDeliveryNote") }}</span><AppIcon name="chevron" :size="12" class="operation__caret" />
				</button>
				<button v-else type="button" class="operation is-delivered" @click="printSingle('Delivery Note')">
					<AppIcon name="print" :size="20" /><span>{{ t("printDeliveryNote") }}</span>
				</button>
				<PrintMenu v-if="menu === 'print-delivery'" :entries="deliveries" @done="menu = null" />
			</template>
			<button v-else-if="delivered" type="button" class="operation is-delivered" @click="toggle('print')">
				<AppIcon name="check" :size="20" /><span>{{ t("deliveredState") }}</span>
			</button>
			<template v-else>
				<button
					type="button"
					class="operation"
					:class="{ 'is-busy': sale.busy === 'deliver' }"
					:disabled="!canDeliver || Boolean(sale.busy)"
					:aria-expanded="menu === 'deliver'"
					@click="toggle('deliver')"
				>
					<AppIcon name="truck" :size="20" /><span>{{ t("deliver") }}</span><AppIcon name="chevron" :size="12" class="operation__caret" />
				</button>
				<div v-if="menu === 'deliver'" class="popover op-menu" role="menu">
					<button type="button" role="menuitem" class="menu-item" :disabled="!hasWarehousePending" @click="deliver(false)">
						<AppIcon name="warehouse" />
						<span class="menu-item__text"><span>{{ t("deliverFromWarehouse") }}</span><small>{{ t("deliverFromWarehouseHint") }}</small></span>
					</button>
					<button
						type="button"
						role="menuitem"
						class="menu-item"
						:disabled="!hasSupplierPending || !session.can('Purchase Order', 'submit')"
						@click="deliver(true)"
					>
						<AppIcon name="box" />
						<span class="menu-item__text">
							<span>{{ t("supplierDelivers") }}</span>
							<small>{{ order && !hasSupplierPending ? t("supplierOnlyNewSale") : t("supplierDeliversHint") }}</small>
						</span>
					</button>
				</div>
			</template>
		</div>

		<div class="operation-bar__slot">
			<template v-if="invoiced && invoices.length">
				<button v-if="invoices.length > 1" type="button" class="operation is-invoiced" :aria-expanded="menu === 'print-invoice'" @click="toggle('print-invoice')">
					<AppIcon name="print" :size="20" /><span>{{ t("printInvoice") }}</span><AppIcon name="chevron" :size="12" class="operation__caret" />
				</button>
				<button v-else type="button" class="operation is-invoiced" @click="printSingle('Sales Invoice')">
					<AppIcon name="print" :size="20" /><span>{{ t("printInvoice") }}</span>
				</button>
				<PrintMenu v-if="menu === 'print-invoice'" :entries="invoices" @done="menu = null" />
			</template>
			<button
				v-else
				type="button"
				class="operation"
				:class="{ 'is-busy': sale.busy === 'invoice' }"
				:title="t('invoiceHint')"
				:disabled="!canInvoice || Boolean(sale.busy)"
				@click="invoice"
			>
				<AppIcon name="invoice" :size="20" /><span>{{ t("createInvoice") }}</span>
			</button>
		</div>

		<div class="operation-bar__slot">
			<button type="button" class="operation" :disabled="!order" :aria-expanded="menu === 'print'" @click="toggle('print')">
				<AppIcon name="print" :size="20" /><span>{{ t("print") }}</span><AppIcon name="chevron" :size="12" class="operation__caret" />
			</button>
			<PrintMenu v-if="menu === 'print' && order" class="op-menu--end" :entries="allDocuments" @done="menu = null" />
		</div>
	</div>
</template>
