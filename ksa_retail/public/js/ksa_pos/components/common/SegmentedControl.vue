<script setup lang="ts">
defineProps<{ modelValue: string; options: { value: string; label: string }[]; label: string }>();
defineEmits<{ (event: "update:modelValue", value: string): void }>();
</script>

<template>
	<div class="segmented" role="radiogroup" :aria-label="label">
		<button
			v-for="option in options"
			:key="option.value"
			type="button"
			role="radio"
			class="segmented__option"
			:aria-checked="option.value === modelValue"
			@click="$emit('update:modelValue', option.value)"
		>
			{{ option.label }}
		</button>
	</div>
</template>
