import type { LinkedDoctype, LinkedDocument, OrderDetail } from "../types";

export interface TimelineEntry extends LinkedDocument {
	doctype: LinkedDoctype;
}

export const LINKED_DOCTYPES: readonly LinkedDoctype[] = [
	"Sales Order",
	"Delivery Note",
	"Sales Invoice",
	"Payment Entry",
	"Purchase Order",
	"Purchase Invoice",
];

/** Every document of an order, oldest first. */
export function documentTimeline(order: OrderDetail, only?: LinkedDoctype): TimelineEntry[] {
	return LINKED_DOCTYPES.filter((doctype) => !only || doctype === only)
		.flatMap((doctype) => (order.documents[doctype] ?? []).map((doc) => ({ ...doc, doctype })))
		.sort((a, b) => String(a.creation ?? "").localeCompare(String(b.creation ?? "")));
}

export function deskUrl(base: string, doctype: string, name: string): string {
	return `${base}/${doctype.toLowerCase().replace(/ /g, "-")}/${encodeURIComponent(name)}`;
}

export function printUrl(doctype: string, name: string, format: string, lang: string): string {
	const query = new URLSearchParams({ doctype, name, format, trigger_print: "1", _lang: lang });
	return `/printview?${query.toString()}`;
}

export function creationLabel(entry: LinkedDocument): string {
	return entry.creation ? String(entry.creation).slice(0, 16).replace("T", " ") : entry.posting_date ?? "";
}
