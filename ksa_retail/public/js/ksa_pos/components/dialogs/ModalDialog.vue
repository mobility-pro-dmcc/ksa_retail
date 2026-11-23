<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "../../i18n";
import AppIcon from "../common/AppIcon.vue";

defineProps<{ title: string; hint?: string; wide?: boolean }>();
const emit = defineEmits<{ (event: "close"): void }>();
const { t } = useI18n();
const panel = ref<HTMLElement | null>(null);
const previouslyFocused = document.activeElement as HTMLElement | null;
const FOCUSABLE = 'button:not([disabled]), input:not([disabled]), select:not([disabled]), a[href], [tabindex]:not([tabindex="-1"])';

function focusables(): HTMLElement[] {
	return panel.value ? Array.from(panel.value.querySelectorAll<HTMLElement>(FOCUSABLE)) : [];
}

function onKeydown(event: KeyboardEvent) {
	if (event.key === "Escape") {
		event.stopPropagation();
		emit("close");
		return;
	}
	if (event.key !== "Tab") return;
	const items = focusables();
	if (!items.length) return;
	const first = items[0];
	const last = items[items.length - 1];
	if (event.shiftKey && document.activeElement === first) {
		event.preventDefault();
		last.focus();
	} else if (!event.shiftKey && document.activeElement === last) {
		event.preventDefault();
		first.focus();
	}
}

/** First field of the dialog body (or the element marked data-autofocus). Content that
 * loads later (e.g. the registration form) calls `focusFirst` again via the exposed API. */
async function focusFirst() {
	await nextTick();
	const body = panel.value?.querySelector<HTMLElement>(".modal__body");
	const target = body?.querySelector<HTMLElement>("[data-autofocus]") ?? body?.querySelector<HTMLElement>(FOCUSABLE);
	target?.focus();
}

onMounted(focusFirst);
defineExpose({ focusFirst });
onBeforeUnmount(() => previouslyFocused?.focus?.());
</script>

<template>
	<div class="modal-backdrop" @click.self="emit('close')">
		<div ref="panel" class="modal" :class="{ 'modal--wide': wide }" role="dialog" aria-modal="true" :aria-label="title" @keydown="onKeydown">
			<header class="modal__head">
				<div>
					<h2 class="modal__title">{{ title }}</h2>
					<p v-if="hint" class="modal__hint">{{ hint }}</p>
				</div>
				<button type="button" class="icon-button" :aria-label="t('close')" @click="emit('close')"><AppIcon name="close" /></button>
			</header>
			<div class="modal__body"><slot /></div>
			<footer class="modal__foot">
				<button type="button" class="button" @click="emit('close')">{{ t("cancel") }}</button>
				<slot name="actions" />
			</footer>
		</div>
	</div>
</template>
