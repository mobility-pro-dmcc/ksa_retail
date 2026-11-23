<script setup lang="ts">
import { ref } from "vue";
import { useDismiss } from "../../composables/dismiss";
import { useI18n } from "../../i18n";
import { useSessionStore } from "../../stores/session";
import { useUiStore } from "../../stores/ui";
import AppIcon from "../common/AppIcon.vue";
import SegmentedControl from "../common/SegmentedControl.vue";

const session = useSessionStore();
const ui = useUiStore();
const { t } = useI18n();
const open = ref(false);
const root = ref<HTMLElement | null>(null);
useDismiss(root, () => open.value, () => (open.value = false));

async function changeDefaultMode(event: Event) {
	try {
		await session.setDefaultMode((event.target as HTMLSelectElement).value);
		ui.notify(t("saved"));
	} catch (error) {
		ui.reportError(error);
	}
}

async function logout() {
	await fetch("/api/method/logout", { method: "POST", headers: { "X-Frappe-CSRF-Token": session.boot.csrf_token } }).catch(() => undefined);
	window.location.assign("/login");
}
</script>

<template>
	<div ref="root" class="user-menu">
		<button type="button" class="avatar" :aria-expanded="open" aria-haspopup="menu" :title="session.boot.user.full_name ?? ''" @click="open = !open">
			<img v-if="session.boot.user.image" :src="session.boot.user.image" alt="" />
			<span v-else>{{ session.boot.user.initials }}</span>
		</button>
		<div v-if="open" class="popover user-menu__panel" role="menu">
			<div class="user-menu__who">
				<strong>{{ session.boot.user.full_name || session.boot.user.name }}</strong>
				<span class="data">{{ session.boot.user.name }}</span>
			</div>
			<label class="user-menu__row">
				<span><AppIcon name="card" />{{ t("defaultPayment") }}</span>
				<select class="input input--small" :value="session.defaultMode ?? ''" @change="changeDefaultMode">
					<option v-for="mode in session.paymentModes" :key="mode.name" :value="mode.name">{{ mode.name }}</option>
				</select>
			</label>
			<div class="user-menu__row">
				<span><AppIcon name="globe" />{{ t("language") }}</span>
				<SegmentedControl
					:model-value="session.lang"
					:label="t('language')"
					:options="[
						{ value: 'ar', label: 'عربي' },
						{ value: 'en', label: 'EN' },
					]"
					@update:model-value="(value) => session.setLang(value === 'ar' ? 'ar' : 'en')"
				/>
			</div>
			<div class="user-menu__row">
				<span><AppIcon :name="session.isDark ? 'moon' : 'sun'" />{{ t("theme") }}</span>
				<SegmentedControl
					:model-value="session.isDark ? 'dark' : 'light'"
					:label="t('theme')"
					:options="[
						{ value: 'light', label: t('light') },
						{ value: 'dark', label: t('dark') },
					]"
					@update:model-value="(value) => session.setTheme(value === 'dark' ? 'dark' : 'light')"
				/>
			</div>
			<a class="menu-item" :href="session.boot.desk_url" target="_blank" rel="noopener"><AppIcon name="desk" />{{ t("openDesk") }}</a>
			<button type="button" class="menu-item menu-item--danger" @click="logout"><AppIcon name="logout" directional />{{ t("logout") }}</button>
		</div>
	</div>
</template>
