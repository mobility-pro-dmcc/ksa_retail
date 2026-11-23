export const MONEY_EPSILON = 0.005;

export function round2(value: number): number {
	return Math.round((value + Number.EPSILON) * 100) / 100;
}

const formatter = new Intl.NumberFormat("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Latin digits in both languages (the convention for amounts in KSA retail documents). */
export function formatAmount(value: number): string {
	return formatter.format(round2(Number.isFinite(value) ? value : 0));
}

export function formatQuantity(value: number): string {
	return Number.isInteger(value) ? String(value) : String(round2(value));
}
