<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { customerApi } from "../../api/endpoints";
import { useI18n } from "../../i18n";
import { useCustomerStore } from "../../stores/customer";
import { useSessionStore } from "../../stores/session";
import { useUiStore } from "../../stores/ui";
import type { FormField } from "../../types";
import AppIcon from "../common/AppIcon.vue";
import ModalDialog from "./ModalDialog.vue";

const emit = defineEmits<{ (event: "close"): void }>();
const session = useSessionStore();
const customer = useCustomerStore();
const ui = useUiStore();
const { t } = useI18n();

const fields = ref<FormField[] | null>(null);
const dialog = ref<InstanceType<typeof ModalDialog> | null>(null);
const values = reactive<Record<string, string | number>>({});
const errors = reactive<Record<string, boolean>>({});
const saving = ref(false);
const WIDE_FIELDS = new Set(["customer_name", "address_line1"]);

onMounted(async () => {
	try {
		fields.value = await customerApi.registrationForm();
		for (const field of fields.value) values[field.fieldname] = field.fieldtype === "Check" ? Number(field.default ?? 0) : field.default ?? "";
		void dialog.value?.focusFirst();
	} catch (error) {
		ui.reportError(error);
		emit("close");
	}
});

const label = (field: FormField) => field.label[session.lang] || field.label.en;
const inputType = (field: FormField) => (field.options === "Phone" ? "tel" : field.options === "Email" ? "email" : "text");

async function save() {
	if (!fields.value || saving.value) return;
	let valid = true;
	for (const field of fields.value) {
		errors[field.fieldname] = Boolean(field.reqd) && field.fieldtype !== "Check" && !String(values[field.fieldname] ?? "").trim();
		valid &&= !errors[field.fieldname];
	}
	if (!valid) return;
	saving.value = true;
	try {
		await customer.register({ ...values });
		emit("close");
	} catch (error) {
		ui.reportError(error);
	} finally {
		saving.value = false;
	}
}
</script>

<template>
	<ModalDialog ref="dialog" :title="t('registerTitle')" :hint="t('registerHint')" wide @close="emit('close')">
		<div v-if="!fields" class="skeleton skeleton--form" />
		<form v-else class="form-grid" novalidate @submit.prevent="save">
			<template v-for="field in fields" :key="field.fieldname">
				<label v-if="field.fieldtype === 'Check'" class="checkbox-field">
					<input v-model="values[field.fieldname]" type="checkbox" :true-value="1" :false-value="0" />
					<span>{{ label(field) }}</span>
				</label>
				<label v-else class="field" :class="{ 'field--wide': WIDE_FIELDS.has(field.fieldname), 'has-error': errors[field.fieldname] }">
					<span class="field__label">{{ label(field) }}<span v-if="field.reqd" class="field__required" aria-hidden="true">*</span></span>
					<select v-if="field.choices" v-model="values[field.fieldname]" class="input" :required="Boolean(field.reqd)">
						<option v-if="!field.reqd" value="" />
						<option v-for="choice in field.choices" :key="choice" :value="choice">{{ choice }}</option>
					</select>
					<input
						v-else
						v-model="values[field.fieldname]"
						class="input"
						:type="inputType(field)"
						:dir="field.options === 'Phone' || field.options === 'Email' ? 'ltr' : undefined"
						:required="Boolean(field.reqd)"
						:data-autofocus="field.fieldname === 'customer_name' ? '' : undefined"
					/>
					<span v-if="errors[field.fieldname]" class="field__error">{{ t("required") }}</span>
				</label>
			</template>
			<button type="submit" hidden />
		</form>
		<template #actions>
			<button type="button" class="button button--primary" :class="{ 'is-busy': saving }" :disabled="!fields || saving" @click="save">
				<AppIcon name="userPlus" />{{ t("saveAndSelect") }}
			</button>
		</template>
	</ModalDialog>
</template>
