/** How many units of an item / dimension the cashier may still add (server re-checks). */
import type { CatalogItem, DimensionValues, OrderDetail } from "../types";
import type { CartLine } from "./cart";
import { quantityInCart } from "./cart";
import { sameDimensions } from "./dimensions";

/** Available in the warehouse; Infinity when the item is not stock-tracked or unknown. */
export function bucketAvailable(item: CatalogItem | undefined, dims: DimensionValues, fields: readonly string[]): number {
	if (!item || !item.is_stock_item) return Number.POSITIVE_INFINITY;
	const bucket = item.stock.find((row) => sameDimensions(row.dims, dims, fields));
	return bucket ? bucket.available : 0;
}

/** When editing an order its own undelivered quantity is reserved for it: count it back. */
export function ownReservation(order: OrderDetail | null, itemCode: string, dims: DimensionValues, fields: readonly string[]): number {
	if (!order) return 0;
	return order.lines
		.filter((line) => !line.drop_ship && line.item_code === itemCode && sameDimensions(line.dims, dims, fields))
		.reduce((total, line) => total + line.pending_delivery, 0);
}

export function remainingQuantity(params: {
	item: CatalogItem | undefined;
	itemCode: string;
	dims: DimensionValues;
	fields: readonly string[];
	lines: readonly CartLine[];
	editingOrder: OrderDetail | null;
	exceptLineKey?: string;
}): number {
	const { item, itemCode, dims, fields, lines, editingOrder, exceptLineKey } = params;
	const limit = bucketAvailable(item, dims, fields) + ownReservation(editingOrder, itemCode, dims, fields);
	return limit - quantityInCart(lines, itemCode, dims, fields, exceptLineKey);
}
