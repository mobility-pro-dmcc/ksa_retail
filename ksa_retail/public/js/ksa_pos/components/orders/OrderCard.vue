<script setup lang="ts">
import { formatQuantity } from "../../domain/money";
import { useI18n } from "../../i18n";
import type { OrderCard } from "../../types";
import MoneyAmount from "../common/MoneyAmount.vue";
import StatusTrack from "./StatusTrack.vue";

defineProps<{ order: OrderCard; active: boolean; loading: boolean }>();
defineEmits<{ (event: "open"): void }>();
const { t, m } = useI18n();
</script>

<template>
	<button type="button" class="order-card" :class="{ 'is-active': active, 'is-busy': loading }" :aria-pressed="active" @click="$emit('open')">
		<StatusTrack :status="order.status" />
		<span class="order-card__head">
			<bdi class="order-card__number data">{{ order.name }}</bdi>
			<span v-if="order.drop_ship" class="badge badge--supplier">{{ t("supplierDelivery") }}</span>
			<bdi class="order-card__date data">{{ order.date }}</bdi>
		</span>
		<ul class="order-card__items">
			<li v-for="(item, index) in order.items" :key="index">
				<bdi class="order-card__qty data">{{ formatQuantity(item.qty) }}×</bdi>
				<span class="order-card__item-name">{{ item.item_name }}</span>
				<bdi v-if="item.dims.length" class="order-card__dims data">{{ item.dims.join(" · ") }}</bdi>
			</li>
			<li v-if="order.item_count > order.items.length" class="order-card__more">{{ m.moreItems(order.item_count - order.items.length) }}</li>
		</ul>
		<span class="order-card__money">
			<span><small>{{ t("total") }}</small><MoneyAmount :value="order.total" :currency="false" /></span>
			<span><small>{{ t("paid") }}</small><MoneyAmount :value="order.paid" :currency="false" /></span>
			<span v-if="order.refund_due > 0.005" class="is-refund"><small>{{ t("refundDue") }}</small><MoneyAmount :value="order.refund_due" :currency="false" /></span>
			<span v-else :class="order.outstanding > 0.005 ? 'is-due' : 'is-settled'"><small>{{ t("outstanding") }}</small><MoneyAmount :value="order.outstanding" :currency="false" /></span>
		</span>
	</button>
</template>
