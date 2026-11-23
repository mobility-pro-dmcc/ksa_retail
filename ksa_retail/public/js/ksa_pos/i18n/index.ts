import { computed } from "vue";
import { useSessionStore } from "../stores/session";
import type { LinkedDoctype } from "../types";
import { messages, type Messages } from "./messages";

type TextKey = { [K in keyof Messages]: Messages[K] extends string ? K : never }[keyof Messages];

const DOCTYPE_KEYS: Record<LinkedDoctype, TextKey> = {
	"Sales Order": "doctypeSalesOrder",
	"Delivery Note": "doctypeDeliveryNote",
	"Sales Invoice": "doctypeSalesInvoice",
	"Payment Entry": "doctypePaymentEntry",
	"Purchase Order": "doctypePurchaseOrder",
	"Purchase Invoice": "doctypePurchaseInvoice",
};

/** `m` gives the active catalogue (functions included); `t` reads plain text keys. */
export function useI18n() {
	const session = useSessionStore();
	const m = computed<Messages>(() => messages[session.lang]);
	const t = (key: TextKey): string => m.value[key] as string;
	const doctype = (name: LinkedDoctype): string => t(DOCTYPE_KEYS[name]);
	return { m, t, doctype };
}
