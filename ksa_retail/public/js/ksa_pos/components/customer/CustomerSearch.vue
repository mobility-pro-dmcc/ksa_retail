<script setup lang="ts">
import { computed, ref } from "vue";
import { useDismiss } from "../../composables/dismiss";
import { initials } from "../../domain/text";
import { useI18n } from "../../i18n";
import { useCustomerStore } from "../../stores/customer";
import AppIcon from "../common/AppIcon.vue";

const customer = useCustomerStore();
const { t } = useI18n();
const root = ref<HTMLElement | null>(null);
const input = ref<HTMLInputElement | null>(null);
const open = ref(false);
const highlighted = ref(0);
useDismiss(root, () => open.value, () => (open.value = false));

const results = computed(() => customer.results ?? []);

function onInput(event: Event) {
	open.value = true;
	highlighted.value = 0;
	customer.setQuery((event.target as HTMLInputElement).value);
}

function onFocus() {
	open.value = true;
	if (customer.results === null) void customer.search(customer.query);
}

function choose(name: string) {
	open.value = false;
	input.value?.blur();
	void customer.select(name);
}

function onKeydown(event: KeyboardEvent) {
	if (!open.value || !results.value.length) return;
	if (event.key === "ArrowDown" || event.key === "ArrowUp") {
		event.preventDefault();
		const step = event.key === "ArrowDown" ? 1 : -1;
		highlighted.value = (highlighted.value + step + results.value.length) % results.value.length;
	} else if (event.key === "Enter") {
		event.preventDefault();
		choose(results.value[highlighted.value].name);
	}
}

defineExpose({ focus: () => input.value?.focus() });
</script>

<template>
	<div ref="root" class="customer-search">
		<label class="search-field search-field--command">
			<AppIcon name="search" />
			<span class="visually-hidden">{{ t("searchCustomers") }}</span>
			<input
				ref="input"
				type="search"
				autocomplete="off"
				role="combobox"
				aria-autocomplete="list"
				aria-controls="customer-results"
				:aria-expanded="open"
				:placeholder="t('searchCustomers')"
				:value="customer.query"
				@input="onInput"
				@focus="onFocus"
				@keydown="onKeydown"
			/>
			<kbd class="search-field__key" aria-hidden="true">/</kbd>
		</label>
		<div v-if="open" id="customer-results" class="popover customer-search__results" role="listbox">
			<p v-if="customer.searching && !results.length" class="customer-search__status">{{ t("searching") }}</p>
			<p v-else-if="!results.length" class="customer-search__status">{{ t("noCustomerMatches") }}</p>
			<button
				v-for="(hit, index) in results"
				:key="hit.name"
				type="button"
				role="option"
				class="customer-hit"
				:aria-selected="index === highlighted"
				@pointerenter="highlighted = index"
				@click="choose(hit.name)"
			>
				<span class="monogram">{{ initials(hit.customer_name) }}</span>
				<span class="customer-hit__main">
					<strong>{{ hit.customer_name }}</strong>
					<span class="customer-hit__meta"><bdi v-if="hit.name !== hit.customer_name" class="code">{{ hit.name }}</bdi><bdi v-if="hit.mobile_no" class="data">{{ hit.mobile_no }}</bdi></span>
				</span>
				<span class="customer-hit__area">{{ hit.territory }}</span>
			</button>
		</div>
	</div>
</template>
