/** Who is selling, where, and how the screen looks (language, theme, default payment). */
import { defineStore } from "pinia";
import { computed, ref, watchEffect } from "vue";
import { sessionApi } from "../api/endpoints";
import { readBoot } from "../boot";
import type { Lang, PaymentMode, PermissionDoctype, Theme } from "../types";

export const useSessionStore = defineStore("session", () => {
	const boot = readBoot();
	const lang = ref<Lang>(boot.prefs.lang === "ar" ? "ar" : "en");
	const theme = ref<Theme>(boot.prefs.theme === "dark" || boot.prefs.theme === "light" ? boot.prefs.theme : null);
	const paymentModes = ref<PaymentMode[]>(boot.settings.payment_modes);
	const warehouse = ref<string | null>(boot.settings.warehouse);
	const warehouses = boot.settings.warehouses ?? [];

	const media = window.matchMedia("(prefers-color-scheme: dark)");
	const systemDark = ref(media.matches);
	media.addEventListener("change", (event) => (systemDark.value = event.matches));

	const isDark = computed(() => (theme.value ? theme.value === "dark" : systemDark.value));
	const direction = computed(() => (lang.value === "ar" ? "rtl" : "ltr"));
	const dimensionFields = boot.dimensions.map((d) => d.fieldname);
	const defaultMode = computed(() => paymentModes.value.find((m) => m.is_default)?.name ?? paymentModes.value[0]?.name ?? null);

	watchEffect(() => {
		const root = document.documentElement;
		root.lang = lang.value;
		root.dir = direction.value;
		if (theme.value) root.dataset.theme = theme.value;
		else delete root.dataset.theme;
	});

	function can(doctype: PermissionDoctype, permission: "create" | "submit"): boolean {
		return Boolean(boot.perms[doctype]?.[permission]);
	}

	function dimensionLabel(fieldname: string): string {
		const dimension = boot.dimensions.find((d) => d.fieldname === fieldname);
		if (!dimension) return fieldname;
		return lang.value === "ar" && dimension.label_ar ? dimension.label_ar : dimension.label;
	}

	function persist(key: "lang" | "theme" | "mode_of_payment" | "warehouse", value: string): Promise<boolean> {
		return sessionApi.setPreference(key, value);
	}

	function setLang(next: Lang): void {
		lang.value = next;
		void persist("lang", next).catch(() => undefined); // a lost preference is not worth an error
	}

	function setTheme(next: "light" | "dark"): void {
		theme.value = next;
		void persist("theme", next).catch(() => undefined);
	}

	/** Saved on the server first: every stock read and new sale uses it from then on. */
	async function setWarehouse(name: string): Promise<void> {
		await persist("warehouse", name);
		warehouse.value = name;
	}

	async function setDefaultMode(name: string): Promise<void> {
		await persist("mode_of_payment", name);
		paymentModes.value = paymentModes.value
			.map((mode) => ({ ...mode, is_default: mode.name === name }))
			.sort((a, b) => Number(b.is_default) - Number(a.is_default));
	}

	return {
		boot,
		lang,
		theme,
		isDark,
		direction,
		paymentModes,
		warehouse,
		warehouses,
		defaultMode,
		dimensionFields,
		can,
		dimensionLabel,
		setLang,
		setTheme,
		setWarehouse,
		setDefaultMode,
	};
});
