<script setup lang="ts">
import { ICONS, type IconName } from "./icons";

withDefaults(defineProps<{ name: IconName; size?: number; directional?: boolean }>(), { size: 18, directional: false });
</script>

<template>
	<svg
		class="icon"
		:class="{ 'icon--directional': directional }"
		:width="size"
		:height="size"
		viewBox="0 0 24 24"
		fill="none"
		stroke="currentColor"
		stroke-width="1.9"
		stroke-linecap="round"
		stroke-linejoin="round"
		aria-hidden="true"
		focusable="false"
		v-html="ICONS[name]"
	/>
</template>
