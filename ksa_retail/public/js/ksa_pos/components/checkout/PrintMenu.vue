<script setup lang="ts">
import { creationLabel, printUrl, type TimelineEntry } from "../../domain/documents";
import { useI18n } from "../../i18n";
import { useSessionStore } from "../../stores/session";
import AppIcon from "../common/AppIcon.vue";

defineProps<{ entries: TimelineEntry[] }>();
const emit = defineEmits<{ (event: "done"): void }>();
const session = useSessionStore();
const { t, doctype } = useI18n();

function print(entry: TimelineEntry) {
	const format = session.boot.print_formats[entry.doctype] || "Standard";
	window.open(printUrl(entry.doctype, entry.name, format, session.lang), "_blank", "noopener");
	emit("done");
}
</script>

<template>
	<div class="popover op-menu" role="menu">
		<button v-for="entry in entries" :key="entry.doctype + entry.name" type="button" role="menuitem" class="menu-item menu-item--document" @click="print(entry)">
			<AppIcon name="print" />
			<span class="menu-item__text">
				<span>{{ doctype(entry.doctype) }}<span v-if="entry.is_return" class="badge badge--return">{{ t("returnTag") }}</span></span>
				<small><bdi class="data">{{ entry.name }}</bdi> · <bdi class="data">{{ creationLabel(entry) }}</bdi></small>
			</span>
		</button>
	</div>
</template>
