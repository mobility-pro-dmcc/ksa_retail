<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "../../i18n";
import type { Messages } from "../../i18n/messages";
import type { OrderStatus, StageState } from "../../types";
import AppIcon from "../common/AppIcon.vue";

const props = defineProps<{ status: OrderStatus }>();
const { t } = useI18n();

type Label = keyof Messages & `stage${string}`;
const LABELS: Record<"payment" | "invoice" | "delivery", Record<StageState, Label>> = {
	payment: { done: "stagePaid", part: "stagePartlyPaid", pending: "stageUnpaid" },
	invoice: { done: "stageInvoiced", part: "stagePartlyInvoiced", pending: "stageNotInvoiced" },
	delivery: { done: "stageDelivered", part: "stagePartlyDelivered", pending: "stageNotDelivered" },
};

const stages = computed(() =>
	(["payment", "invoice", "delivery"] as const).map((stage) => {
		const state = props.status[stage];
		const percent = props.status[`${stage}_pct`];
		return { stage, state, percent, label: t(LABELS[stage][state]) };
	}),
);
</script>

<template>
	<ol class="status-track">
		<li
			v-for="item in stages"
			:key="item.stage"
			class="status-track__stage"
			:class="[`status-track__stage--${item.stage}`, `is-${item.state}`]"
			:style="item.state === 'part' ? { '--progress': `${Math.round(item.percent)}%` } : undefined"
		>
			<AppIcon :name="item.state === 'done' ? 'check' : 'clock'" :size="13" />
			<span>{{ item.label }}</span>
		</li>
	</ol>
</template>
