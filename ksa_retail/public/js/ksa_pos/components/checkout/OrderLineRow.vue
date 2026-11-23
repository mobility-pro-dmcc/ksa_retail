<script setup lang="ts">
import { computed } from "vue";
import { dimensionLabel } from "../../domain/dimensions";
import { formatQuantity } from "../../domain/money";
import { useI18n } from "../../i18n";
import { useSessionStore } from "../../stores/session";
import type { OrderLine } from "../../types";
import MoneyAmount from "../common/MoneyAmount.vue";

const props = defineProps<{ line: OrderLine }>();
const session = useSessionStore();
const { t } = useI18n();
const label = computed(() => dimensionLabel(props.line.dims, session.dimensionFields));
</script>

<template>
	<div class="cart-line cart-line--readonly">
		<div class="cart-line__info">
			<span class="cart-line__name">{{ line.item_name }}</span>
			<span class="cart-line__meta">
				<bdi class="data">{{ line.item_code }}</bdi>
				<bdi v-if="label" class="tag data">{{ label }}</bdi>
				<span v-if="line.drop_ship" class="badge badge--supplier">{{ t("supplierDelivery") }}</span>
			</span>
		</div>
		<span class="cart-line__amount"><MoneyAmount :value="line.amount" :currency="false" /></span>
		<div class="cart-line__progress">
			<bdi class="data">{{ formatQuantity(line.qty) }} × <MoneyAmount :value="line.rate" :currency="false" /></bdi>
			<span class="progress-chips">
				<span class="progress-chip progress-chip--delivered">{{ t("deliveredQty") }} <bdi class="data">{{ formatQuantity(line.delivered_qty) }}</bdi></span>
				<span class="progress-chip progress-chip--invoiced">{{ t("invoicedQty") }} <bdi class="data">{{ formatQuantity(line.billed_qty) }}</bdi></span>
				<span v-if="line.returned > 0" class="progress-chip progress-chip--returned">{{ t("returnedQty") }} <bdi class="data">{{ formatQuantity(line.returned) }}</bdi></span>
			</span>
		</div>
	</div>
</template>
