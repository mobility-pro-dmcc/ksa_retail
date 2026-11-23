<script setup lang="ts">
import { computed } from "vue";
import { deskUrl, documentTimeline } from "../../domain/documents";
import { useI18n } from "../../i18n";
import { useSessionStore } from "../../stores/session";
import { useUiStore } from "../../stores/ui";
import type { OrderDetail } from "../../types";
import AppIcon from "../common/AppIcon.vue";

const props = defineProps<{ order: OrderDetail }>();
const session = useSessionStore();
const ui = useUiStore();
const { t, doctype } = useI18n();
const entries = computed(() => documentTimeline(props.order));
const kind = (name: string) => name.toLowerCase().replace(/ /g, "-");
</script>

<template>
	<section v-if="entries.length" class="checkout-section" :aria-label="t('linkedDocuments')">
		<header class="section-label">
			<span>{{ t("linkedDocuments") }}</span>
			<button
				v-if="order.supplier_unbilled && session.can('Purchase Invoice', 'submit')"
				type="button"
				class="link-button"
				@click="ui.openDialog({ kind: 'billSupplier' })"
			>
				<AppIcon name="invoice" :size="15" />{{ t("billSupplier") }}
			</button>
		</header>
		<ul class="document-chips">
			<li v-for="entry in entries" :key="entry.doctype + entry.name">
				<a
					class="document-chip"
					:class="[`document-chip--${kind(entry.doctype)}`, { 'is-return': entry.is_return }]"
					:href="deskUrl(session.boot.desk_url, entry.doctype, entry.name)"
					target="_blank"
					rel="noopener"
					:title="doctype(entry.doctype)"
				>
					<span class="document-chip__dot" aria-hidden="true" /><bdi class="data">{{ entry.name }}</bdi>
				</a>
			</li>
		</ul>
	</section>
</template>
