<script setup lang="ts">
import { useI18n } from "../../i18n";
import { useSessionStore } from "../../stores/session";

const session = useSessionStore();
const { t } = useI18n();
const stars: [number, number, number][] = [
	[24, 20, 3.4],
	[35, 17, 2.6],
	[42, 25, 3],
	[30, 29, 4],
	[21, 34, 2.4],
	[39, 37, 2.8],
	[31, 45, 2.2],
];
const star = ([x, y, r]: [number, number, number]) =>
	`M${x} ${y - r * 1.6}L${x + r * 0.45} ${y - r * 0.45}L${x + r * 1.6} ${y}L${x + r * 0.45} ${y + r * 0.45}L${x} ${y + r * 1.6}L${x - r * 0.45} ${y + r * 0.45}L${x - r * 1.6} ${y}L${x - r * 0.45} ${y - r * 0.45}Z`;
</script>

<template>
	<div class="brand">
		<span class="brand__halo" aria-hidden="true" />
		<img v-if="session.boot.logo" class="brand__logo" :src="session.boot.logo" :alt="session.boot.settings.company" />
		<svg v-else class="brand__mark" viewBox="0 0 64 64" aria-hidden="true">
			<rect x="2" y="2" width="60" height="60" rx="16" class="brand__mark-plate" />
			<circle cx="32" cy="32" r="22" fill="none" class="brand__mark-orbit" />
			<path v-for="(s, i) in stars" :key="i" :d="star(s)" class="brand__mark-star" />
		</svg>
		<span class="brand__text">
			<strong class="brand__name">{{ session.boot.settings.company }}</strong>
			<span class="brand__tag">{{ t("appTag") }}</span>
		</span>
	</div>
</template>
