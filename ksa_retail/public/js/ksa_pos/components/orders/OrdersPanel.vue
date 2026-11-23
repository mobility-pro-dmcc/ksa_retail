<script setup lang="ts">
import { useI18n } from "../../i18n";
import { useOrdersStore } from "../../stores/orders";
import { useSaleStore } from "../../stores/sale";
import EmptyState from "../common/EmptyState.vue";
import OrderCard from "./OrderCard.vue";

const orders = useOrdersStore();
const sale = useSaleStore();
const { t } = useI18n();

function toggle(name: string) {
	if (sale.editing) return; // finish or discard the edit first
	if (orders.active?.name === name) {
		orders.close();
		sale.resetPayments();
		return;
	}
	sale.resetPayments();
	void orders.open(name);
}
</script>

<template>
	<div class="orders-panel">
		<div v-if="orders.cards === null && !orders.failed" class="card-grid">
			<div v-for="n in 4" :key="n" class="skeleton skeleton--order" />
		</div>
		<EmptyState v-else-if="orders.failed && !orders.cards" icon="alert" :title="t('loadFailed')">
			<button type="button" class="button" @click="orders.load()">{{ t("retry") }}</button>
		</EmptyState>
		<EmptyState v-else-if="orders.cards && !orders.cards.length" icon="done" :title="orders.filter === 'incomplete' ? t('noIncomplete') : t('noOrders')" />
		<template v-else-if="orders.cards">
			<div class="card-grid">
				<OrderCard
					v-for="order in orders.cards"
					:key="order.name"
					:order="order"
					:active="orders.active?.name === order.name"
					:loading="orders.opening === order.name"
					@open="toggle(order.name)"
				/>
			</div>
			<button v-if="orders.hasMore" type="button" class="button load-more" :class="{ 'is-busy': orders.loading }" @click="orders.load(true)">
				{{ t("loadMore") }}
			</button>
		</template>
	</div>
</template>
