/** Contracts shared with the server (ksa_retail.pos.api.*). */

export type Lang = "en" | "ar";
export type Theme = "light" | "dark" | null;
export type StageState = "done" | "part" | "pending";
export type DimensionValues = Record<string, string | null | undefined>;

export interface PaymentMode {
	name: string;
	type: string | null;
	account: string;
	requires_reference: boolean;
	is_default: boolean;
}

export interface DimensionInfo {
	fieldname: string;
	label: string;
	label_ar: string;
	doctype: string;
	required: boolean;
}

export type PermissionDoctype =
	| "Customer"
	| "Sales Order"
	| "Delivery Note"
	| "Sales Invoice"
	| "Payment Entry"
	| "Purchase Order"
	| "Purchase Invoice";

export type LinkedDoctype = Exclude<PermissionDoctype, "Customer">;

export interface Boot {
	settings: {
		company: string;
		currency: string;
		warehouse: string | null;
		/** warehouses this user may sell from (their permissions) */
		warehouses: string[];
		price_list: string | null;
		payment_modes: PaymentMode[];
	};
	logo: string | null;
	dimensions: DimensionInfo[];
	user: { name: string; full_name: string | null; image: string | null; initials: string };
	prefs: { mode_of_payment: string | null; lang: string | null; theme: string | null };
	desk_url: string;
	bill_no_required: boolean;
	print_formats: Record<LinkedDoctype, string>;
	perms: Record<PermissionDoctype, { create: boolean; submit: boolean }>;
	today: string;
	csrf_token: string;
}

export interface CustomerHit {
	name: string;
	customer_name: string;
	mobile_no: string | null;
	territory: string | null;
	customer_group: string | null;
	image: string | null;
}

export interface CustomerSummary extends CustomerHit {
	has_address: boolean;
	/** positive: the customer owes us */
	balance: number;
	open_invoices: number;
	/** unused money: free payments + credit notes not yet refunded or applied */
	advance: number;
}

export interface FormField {
	fieldname: string;
	fieldtype: string;
	label: { en: string; ar: string };
	reqd: 0 | 1;
	options: string | null;
	default: string | null;
	choices?: string[];
}

export interface StockBucket {
	dims: DimensionValues;
	on_hand: number;
	reserved: number;
	available: number;
}

export interface CatalogItem {
	item_code: string;
	item_name: string;
	brand: string | null;
	image: string | null;
	stock_uom: string;
	is_stock_item: 0 | 1;
	item_group: string;
	rate: number;
	specs: { label: string; value: string }[];
	stock: StockBucket[];
}

export interface ItemSearchResult {
	items: CatalogItem[];
	brands: string[] | null;
}

export interface OrderStatus {
	payment: StageState;
	payment_pct: number;
	invoice: StageState;
	invoice_pct: number;
	delivery: StageState;
	delivery_pct: number;
}

export interface OrderCard {
	name: string;
	date: string;
	status_label: string;
	total: number;
	paid: number;
	outstanding: number;
	refund_due: number;
	status: OrderStatus;
	drop_ship: boolean;
	item_count: number;
	items: { item_code: string; item_name: string; qty: number; dims: string[] }[];
}

export interface OrderLine {
	so_detail: string;
	item_code: string;
	item_name: string;
	qty: number;
	rate: number;
	amount: number;
	delivered_qty: number;
	billed_qty: number;
	returned: number;
	pending_delivery: number;
	pending_billing: number;
	returnable: number;
	drop_ship: 0 | 1;
	supplier: string | null;
	dims: DimensionValues;
}

export interface Totals {
	subtotal: number;
	discount: number;
	net_total: number;
	taxes: { description: string; amount: number }[];
	total_taxes: number;
	grand_total: number;
	rounded_total: number;
	lines: { item_code: string; rate: number; amount: number; price_list_rate: number }[];
}

export interface LinkedDocument {
	name: string;
	creation?: string;
	posting_date?: string;
	is_return?: 0 | 1;
	status?: string;
	bill_no?: string;
}

export interface OrderDetail {
	name: string;
	customer: string;
	customer_name: string;
	date: string;
	status_label: string;
	lines: OrderLine[];
	totals: Totals;
	total: number;
	gross_total: number;
	returns_value: number;
	paid: number;
	outstanding: number;
	refund_due: number;
	credit: number;
	status: OrderStatus;
	can_deliver: boolean;
	can_invoice: boolean;
	can_return: boolean;
	drop_ship: boolean;
	edit_block: string | null;
	supplier_unbilled: boolean;
	documents: Record<LinkedDoctype, LinkedDocument[]>;
}

export interface CreditLink {
	payment: string;
	payment_type: string;
	invoice: string;
	amount: number;
}

export interface TransactionResult {
	documents: { doctype: string; name: string; action: "created" | "cancelled" }[];
	order: OrderDetail | null;
	customer: CustomerSummary;
	credit_links: CreditLink[];
}

/** Request shapes */
export interface SaleLineInput {
	item_code: string;
	qty: number;
	rate: number | null;
	dims: DimensionValues;
	drop_ship: boolean;
	so_detail?: string | null;
}

export interface PaymentInput {
	mode_of_payment: string;
	amount: number;
	reference_no: string | null;
}

export interface DiscountInput {
	type: "pct" | "amount";
	value: number;
}

export type LineQuantities = Record<string, number>;
