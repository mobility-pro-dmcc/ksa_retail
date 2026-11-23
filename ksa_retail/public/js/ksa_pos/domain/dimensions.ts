import type { DimensionValues } from "../types";

/** Stable key of dimension values; empty and missing values compare equal. */
export function dimensionKey(values: DimensionValues | undefined, fields: readonly string[]): string {
	return fields.map((field) => values?.[field] ?? "").join("|");
}

export function dimensionLabel(values: DimensionValues | undefined, fields: readonly string[]): string {
	return fields
		.map((field) => values?.[field])
		.filter((value): value is string => Boolean(value))
		.join(" · ");
}

export function sameDimensions(a: DimensionValues | undefined, b: DimensionValues | undefined, fields: readonly string[]): boolean {
	return dimensionKey(a, fields) === dimensionKey(b, fields);
}
