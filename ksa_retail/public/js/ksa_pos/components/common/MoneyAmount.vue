<script setup lang="ts">
import { computed } from "vue";
import { formatAmount } from "../../domain/money";
import { useSessionStore } from "../../stores/session";

const props = withDefaults(defineProps<{ value: number; currency?: boolean }>(), { currency: true });
const session = useSessionStore();
const unit = computed(() => {
	const code = session.boot.settings.currency;
	return session.lang === "ar" && code === "SAR" ? "ر.س" : code;
});
</script>

<template>
	<span class="money"><bdi class="data">{{ formatAmount(props.value) }}</bdi><span v-if="currency" class="money__unit">{{ unit }}</span></span>
</template>
