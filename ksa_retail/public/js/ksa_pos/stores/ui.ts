/** Toasts, the active dialog and the workspace tab. */
import { defineStore } from "pinia";
import { ref } from "vue";
import { ApiError } from "../api/http";
import { messages } from "../i18n/messages";
import { uid } from "../domain/text";
import { useSessionStore } from "./session";

export type ToastTone = "success" | "error";

export interface Toast {
	id: string;
	tone: ToastTone;
	text: string;
	details: string[];
}

export type Dialog =
	| { kind: "register" }
	| { kind: "deliver"; supplier: boolean }
	| { kind: "invoice" }
	| { kind: "return" }
	| { kind: "supplier"; deliver: boolean }
	| { kind: "billSupplier" };

const TOAST_MS: Record<ToastTone, number> = { success: 4500, error: 9000 };

export const useUiStore = defineStore("ui", () => {
	const toasts = ref<Toast[]>([]);
	const dialog = ref<Dialog | null>(null);
	const tab = ref<"orders" | "products">("orders");

	function notify(text: string, tone: ToastTone = "success", details: string[] = []): void {
		const toast = { id: uid(), tone, text, details };
		toasts.value = [...toasts.value.slice(-2), toast];
		setTimeout(() => dismiss(toast.id), TOAST_MS[tone]);
	}

	function dismiss(id: string): void {
		toasts.value = toasts.value.filter((toast) => toast.id !== id);
	}

	/** One place that turns any failure into a message the cashier can act on. */
	function reportError(error: unknown): void {
		const text = messages[useSessionStore().lang];
		if (!(error instanceof ApiError)) {
			console.error("[ksa-pos]", error);
			notify(text.errorServer, "error");
			return;
		}
		if (error.kind === "aborted") return;
		const byKind: Record<string, string> = {
			network: text.errorNetwork,
			server: text.errorServer,
			session: text.errorSession,
			permission: error.message || text.errorPermission,
			not_found: error.message || text.errorNotFound,
			validation: error.message || text.errorServer,
		};
		notify(byKind[error.kind] ?? text.errorServer, "error");
		if (error.kind === "session") setTimeout(() => window.location.assign("/login?redirect-to=/ksa-pos"), 2500);
	}

	function openDialog(next: Dialog): void {
		dialog.value = next;
	}

	function closeDialog(): void {
		dialog.value = null;
	}

	return { toasts, dialog, tab, notify, dismiss, reportError, openDialog, closeDialog };
});
