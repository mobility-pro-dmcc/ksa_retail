<script setup lang="ts">
import AppIcon from "./AppIcon.vue";
import type { IconName } from "./icons";

defineProps<{ icon: IconName; title: string; hint?: string }>();
</script>

<template>
	<div class="empty-state">
		<span class="empty-state__icon"><AppIcon :name="icon" :size="22" /></span>
		<p class="empty-state__title">{{ title }}</p>
		<p v-if="hint" class="empty-state__hint">{{ hint }}</p>
		<slot />
	</div>
</template>
