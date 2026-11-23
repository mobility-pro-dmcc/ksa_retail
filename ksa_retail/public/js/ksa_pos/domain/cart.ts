/** The cart of a new sale or of an order being edited. Pure functions over immutable arrays. */
import type { DimensionValues, SaleLineInput } from "../types";
import { sameDimensions } from "./dimensions";

export interface CartLine {
	key: string;
	item_code: string;
	item_name: string;
	dims: DimensionValues;
	qty: number;
	/** null: use the price list rate */
	rate: number | null;
	/** price list rate, for display until the server quote arrives */
	price: number;
	drop_ship: boolean;
	/** set when the line already exists on the order being edited */
	so_detail: string | null;
}

/** Quantity of an item / dimension already taken by stock lines of the cart. */
export function quantityInCart(
	lines: readonly CartLine[],
	itemCode: string,
	dims: DimensionValues,
	fields: readonly string[],
	exceptKey?: string,
): number {
	return lines
		.filter((line) => !line.drop_ship && line.key !== exceptKey && line.item_code === itemCode && sameDimensions(line.dims, dims, fields))
		.reduce((total, line) => total + line.qty, 0);
}

/**
 * Adds stock quantity: merges into the matching stock line (same item and dimension
 * values). In edit mode the existing order line is reused, so the order keeps its row.
 */
export function addStockQuantity(
	lines: readonly CartLine[],
	incoming: CartLine,
	fields: readonly string[],
	editing: boolean,
): CartLine[] {
	const index = lines.findIndex(
		(line) =>
			!line.drop_ship &&
			line.item_code === incoming.item_code &&
			sameDimensions(line.dims, incoming.dims, fields) &&
			(editing || !line.so_detail),
	);
	if (index === -1) return [...lines, incoming];
	return lines.map((line, i) => (i === index ? { ...line, qty: line.qty + incoming.qty } : line));
}

export function clampQuantity(requested: number, maximum: number): number {
	const whole = Math.floor(Number.isFinite(requested) ? requested : 1);
	return Math.max(1, Math.min(whole, maximum));
}

export function toSaleLines(lines: readonly CartLine[]): SaleLineInput[] {
	return lines.map((line) => ({
		item_code: line.item_code,
		qty: line.qty,
		rate: line.rate,
		dims: line.dims,
		drop_ship: line.drop_ship,
		so_detail: line.so_detail,
	}));
}
