<script setup lang="ts">
import { useI18n } from "../../i18n";
import { useUiStore } from "../../stores/ui";
import AppIcon from "./AppIcon.vue";

const ui = useUiStore();
const { t } = useI18n();
</script>

<template>
	<div class="toast-stack" aria-live="polite">
		<div v-for="toast in ui.toasts" :key="toast.id" class="toast" :class="`toast--${toast.tone}`" :role="toast.tone === 'error' ? 'alert' : 'status'">
			<AppIcon :name="toast.tone === 'error' ? 'alert' : 'done'" :size="18" />
			<div class="toast__body">
				<p class="toast__text">{{ toast.text }}</p>
				<p v-for="detail in toast.details" :key="detail" class="toast__detail"><bdi class="data">{{ detail }}</bdi></p>
			</div>
			<button type="button" class="toast__close" :aria-label="t('close')" @click="ui.dismiss(toast.id)"><AppIcon name="close" :size="14" /></button>
		</div>
	</div>
</template>
