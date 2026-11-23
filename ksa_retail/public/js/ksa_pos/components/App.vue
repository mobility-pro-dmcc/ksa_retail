<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRefresh } from "../composables/refresh";
import { useI18n } from "../i18n";
import { useCustomerStore } from "../stores/customer";
import { useOrdersStore } from "../stores/orders";
import { useSaleStore } from "../stores/sale";
import { useSessionStore } from "../stores/session";
import { useUiStore } from "../stores/ui";
import CatalogPanel from "./catalog/CatalogPanel.vue";
import CheckoutPanel from "./checkout/CheckoutPanel.vue";
import AppIcon from "./common/AppIcon.vue";
import ToastStack from "./common/ToastStack.vue";
import CustomerHeader from "./customer/CustomerHeader.vue";
import CustomerSearch from "./customer/CustomerSearch.vue";
import DialogHost from "./dialogs/DialogHost.vue";
import BrandMark from "./layout/BrandMark.vue";
import UserMenu from "./layout/UserMenu.vue";
import WarehousePicker from "./layout/WarehousePicker.vue";
import OrdersPanel from "./orders/OrdersPanel.vue";

const session = useSessionStore();
const customer = useCustomerStore();
const orders = useOrdersStore();
const sale = useSaleStore();
const ui = useUiStore();
const { t } = useI18n();
const search = ref<InstanceType<typeof CustomerSearch> | null>(null);
const { refreshing, refreshAll } = useRefresh();

async function refresh() {
	if (await refreshAll()) ui.notify(t("refreshed"));
}

watch(
	() => ui.tab,
	(tab) => {
		if (tab === "orders" && customer.selected && orders.cards === null) void orders.load();
	},
);

/** Clicking into an amount / rate box selects its value, so typing replaces it. */
function onFocusIn(event: FocusEvent) {
	const target = event.target;
	if (target instanceof HTMLInputElement && target.type === "number" && !target.readOnly) {
		requestAnimationFrame(() => target.select());
	}
}

/** "/" focuses the customer search, like a command bar. */
function onKeydown(event: KeyboardEvent) {
	const target = event.target as HTMLElement;
	const typing = ["INPUT", "SELECT", "TEXTAREA"].includes(target.tagName) || target.isContentEditable;
	if (event.key === "/" && !typing && !ui.dialog) {
		event.preventDefault();
		search.value?.focus();
	}
}

function onBeforeUnload(event: BeforeUnloadEvent) {
	if (sale.busy) {
		event.preventDefault();
		event.returnValue = "";
	}
}

onMounted(() => {
	document.addEventListener("keydown", onKeydown);
	document.addEventListener("focusin", onFocusIn);
	window.addEventListener("beforeunload", onBeforeUnload);
});
onBeforeUnmount(() => {
	document.removeEventListener("keydown", onKeydown);
	document.removeEventListener("focusin", onFocusIn);
	window.removeEventListener("beforeunload", onBeforeUnload);
});
</script>

<template>
	<div class="app-shell">
		<header class="topbar">
			<BrandMark />
			<div class="topbar__search">
				<CustomerSearch ref="search" />
				<button v-if="session.can('Customer', 'create')" type="button" class="button button--accent" @click="ui.openDialog({ kind: 'register' })">
					<AppIcon name="userPlus" /><span>{{ t("registerCustomer") }}</span>
				</button>
			</div>
			<div class="topbar__tools">
				<WarehousePicker />
				<button
					type="button"
					class="topbar__toggle"
					:class="{ 'is-spinning': refreshing }"
					:aria-label="t('refresh')"
					:title="t('refresh')"
					:disabled="refreshing || Boolean(sale.busy)"
					@click="refresh"
				>
					<AppIcon name="refresh" />
				</button>
				<button type="button" class="topbar__toggle" :aria-label="t('language')" @click="session.setLang(session.lang === 'en' ? 'ar' : 'en')">
					{{ t("switchLanguage") }}
				</button>
				<button type="button" class="topbar__toggle" :aria-label="t('theme')" @click="session.setTheme(session.isDark ? 'light' : 'dark')">
					<AppIcon :name="session.isDark ? 'sun' : 'moon'" />
				</button>
				<UserMenu />
			</div>
		</header>

		<main class="workspace">
			<section class="workspace__main">
				<CustomerHeader />
				<nav class="tabs" :aria-label="t('orders')">
					<button type="button" class="tabs__tab" :aria-selected="ui.tab === 'orders'" role="tab" @click="ui.tab = 'orders'">
						{{ t("orders") }}<span v-if="orders.cards" class="count">{{ orders.cards.length }}{{ orders.hasMore ? "+" : "" }}</span>
					</button>
					<button type="button" class="tabs__tab" :aria-selected="ui.tab === 'products'" role="tab" @click="ui.tab = 'products'">
						{{ t("products") }}
					</button>
					<div v-if="ui.tab === 'orders' && customer.selected" class="tabs__tools segmented" role="radiogroup" :aria-label="t('orders')">
						<button type="button" role="radio" class="segmented__option" :aria-checked="orders.filter === 'all'" @click="orders.setFilter('all')">{{ t("filterAll") }}</button>
						<button type="button" role="radio" class="segmented__option" :aria-checked="orders.filter === 'incomplete'" @click="orders.setFilter('incomplete')">
							{{ t("filterIncomplete") }}
						</button>
					</div>
				</nav>
				<div class="workspace__scroll">
					<OrdersPanel v-if="ui.tab === 'orders' && customer.selected" />
					<CatalogPanel v-else-if="ui.tab === 'products'" />
				</div>
			</section>
			<CheckoutPanel />
		</main>

		<DialogHost />
		<ToastStack />
	</div>
</template>
