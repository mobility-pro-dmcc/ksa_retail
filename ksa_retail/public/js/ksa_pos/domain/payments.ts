import type { PaymentInput, PaymentMode } from "../types";
import { round2 } from "./money";

export interface PaymentRow {
	id: string;
	mode: string;
	amount: number;
	reference: string;
}

export function paymentTotal(rows: readonly PaymentRow[]): number {
	return round2(rows.reduce((total, row) => total + (Number(row.amount) || 0), 0));
}

export function hasPayment(rows: readonly PaymentRow[]): boolean {
	return rows.some((row) => Number(row.amount) > 0);
}

export function toPaymentInputs(rows: readonly PaymentRow[]): PaymentInput[] {
	return rows
		.filter((row) => Number(row.amount) > 0)
		.map((row) => ({ mode_of_payment: row.mode, amount: round2(Number(row.amount)), reference_no: row.reference.trim() || null }));
}

/** Amount that makes the given row settle `due`, given the other rows. */
export function fillAmount(rows: readonly PaymentRow[], rowId: string, due: number): number {
	const others = rows.filter((row) => row.id !== rowId).reduce((total, row) => total + (Number(row.amount) || 0), 0);
	return Math.max(0, round2(due - others));
}

/** The next mode to offer when a row is added: the first one not used yet. */
export function nextMode(rows: readonly PaymentRow[], modes: readonly PaymentMode[]): string | null {
	const used = new Set(rows.map((row) => row.mode));
	return (modes.find((mode) => !used.has(mode.name)) ?? modes[0])?.name ?? null;
}

export function missingReference(rows: readonly PaymentRow[], modes: readonly PaymentMode[]): PaymentRow | undefined {
	return rows.find(
		(row) => Number(row.amount) > 0 && !row.reference.trim() && modes.find((mode) => mode.name === row.mode)?.requires_reference,
	);
}
