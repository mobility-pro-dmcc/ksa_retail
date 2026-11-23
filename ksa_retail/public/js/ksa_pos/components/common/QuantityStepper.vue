<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "../../i18n";
import AppIcon from "./AppIcon.vue";

const props = withDefaults(
	defineProps<{
		modelValue: number;
		min?: number;
		max?: number;
		step?: number;
		label: string;
		disabled?: boolean;
		readonly?: boolean;
		/** commit on change (cart) instead of on every keystroke (pickers, dialogs) */
		lazy?: boolean;
	}>(),
	{ min: 1, max: Number.POSITIVE_INFINITY, step: 1, disabled: false, readonly: false, lazy: false },
);
const emit = defineEmits<{ (event: "update:modelValue", value: number): void; (event: "enter"): void }>();
const { t } = useI18n();

const locked = computed(() => props.disabled || props.readonly);
const atMin = computed(() => props.modelValue <= props.min);
const atMax = computed(() => props.modelValue >= props.max);

function clamp(value: number): number {
	if (!Number.isFinite(value)) return props.min;
	return Math.min(Math.max(value, props.min), props.max);
}

function commit(value: number) {
	emit("update:modelValue", clamp(value));
}

function onInput(event: Event) {
	if (!props.lazy) {
		const raw = (event.target as HTMLInputElement).value;
		if (raw !== "") commit(Number(raw));
	}
}

function onChange(event: Event) {
	const input = event.target as HTMLInputElement;
	const value = clamp(Number(input.value));
	input.value = String(value);
	commit(value);
}

/** Clicking into the box selects the whole number, so typing replaces it. */
function selectAll(event: Event) {
	const input = event.target as HTMLInputElement;
	requestAnimationFrame(() => input.select());
}
</script>

<template>
	<span class="stepper" :class="{ 'is-disabled': disabled }">
		<button type="button" :aria-label="`${t('decrease')} ${label}`" :disabled="locked || atMin" @click="commit(modelValue - step)">
			<AppIcon name="minus" :size="14" />
		</button>
		<input
			class="data"
			type="number"
			inputmode="decimal"
			:min="min"
			:max="Number.isFinite(max) ? max : undefined"
			:step="step"
			:value="modelValue"
			:aria-label="label"
			:disabled="disabled"
			:readonly="readonly"
			@focus="selectAll"
			@mouseup.prevent
			@input="onInput"
			@change="onChange"
			@keydown.enter="emit('enter')"
		/>
		<button type="button" :aria-label="`${t('increase')} ${label}`" :disabled="locked || atMax" @click="commit(modelValue + step)">
			<AppIcon name="plus" :size="14" />
		</button>
	</span>
</template>
