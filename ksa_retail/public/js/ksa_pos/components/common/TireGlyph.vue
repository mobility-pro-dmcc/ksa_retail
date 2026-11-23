<script setup lang="ts">
withDefaults(defineProps<{ size?: number }>(), { size: 56 });
const spokes = [0, 72, 144, 216, 288];
</script>

<template>
	<svg class="tire-glyph" :width="size" :height="size" viewBox="0 0 64 64" fill="none" stroke="currentColor" aria-hidden="true">
		<circle cx="32" cy="32" r="27" stroke-width="7" />
		<circle cx="32" cy="32" r="27" stroke-width="7" stroke-dasharray="2.5 4.5" class="tire-glyph__tread" />
		<circle cx="32" cy="32" r="14" stroke-width="2" />
		<circle cx="32" cy="32" r="4.5" stroke-width="2" />
		<path v-for="angle in spokes" :key="angle" d="M32 27.5V18.5" stroke-width="2.2" stroke-linecap="round" :transform="`rotate(${angle} 32 32)`" />
	</svg>
</template>
