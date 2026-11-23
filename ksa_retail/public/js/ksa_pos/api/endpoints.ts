/** Typed access to every POS endpoint. Nothing else in the app knows method paths. */
import { call, type CallOptions } from "./http";
import type {
	CatalogItem,
	CreditLink,
	CustomerHit,
	CustomerSummary,
	DiscountInput,
	FormField,
	ItemSearchResult,
	LineQuantities,
	OrderCard,
	OrderDetail,
	PaymentInput,
	SaleLineInput,
	Totals,
	TransactionResult,
} from "../types";

const ROOT = "ksa_retail.pos.api";

export const sessionApi = {
	setPreference: (key: "lang" | "theme" | "mode_of_payment" | "warehouse", value: string) =>
		call<boolean>(`${ROOT}.session.set_preference`, { key, value }),
};

export const customerApi = {
	search: (query: string, options?: CallOptions) =>
		call<CustomerHit[]>(`${ROOT}.customers.search_customers`, { query }, options),
	get: (customer: string, options?: CallOptions) =>
		call<CustomerSummary>(`${ROOT}.customers.get_customer`, { customer }, options),
	registrationForm: () => call<FormField[]>(`${ROOT}.customers.get_registration_form`),
	register: (values: Record<string, string | number>) =>
		call<CustomerSummary>(`${ROOT}.customers.register_customer`, { values }),
	applyCredit: (customer: string) =>
		call<{ links: CreditLink[]; customer: CustomerSummary }>(`${ROOT}.customers.apply_customer_credit`, { customer }),
};

export const catalogApi = {
	search: (params: { query: string; brand: string | null; start: number; page_length: number; in_stock?: 0 | 1 }, options?: CallOptions) =>
		call<ItemSearchResult>(`${ROOT}.catalog.search_items`, params, options),
	dimensionValues: (fieldname: string) => call<string[]>(`${ROOT}.catalog.get_dimension_values`, { fieldname }),
	suppliers: (query: string, options?: CallOptions) =>
		call<{ name: string; supplier_name: string }[]>(`${ROOT}.catalog.search_suppliers`, { query }, options),
	quote: (customer: string | null, lines: SaleLineInput[], discount: DiscountInput | null, options?: CallOptions) =>
		call<Totals | null>(`${ROOT}.catalog.quote_sale`, { customer, lines, discount }, options),
};

export const orderApi = {
	list: (params: { customer: string; only_incomplete: 0 | 1; start: number; page_length: number }, options?: CallOptions) =>
		call<OrderCard[]>(`${ROOT}.orders.list_orders`, params, options),
	get: (salesOrder: string, options?: CallOptions) =>
		call<OrderDetail>(`${ROOT}.orders.get_order`, { sales_order: salesOrder }, options),
};

export const salesApi = {
	createSale: (args: {
		client_ref: string;
		customer: string;
		lines: SaleLineInput[];
		discount: DiscountInput | null;
		payments: PaymentInput[];
		deliver: 0 | 1;
		drop_ship: { supplier: string; bill_no: string | null } | null;
	}) => call<TransactionResult>(`${ROOT}.sales.create_sale`, args),
	deliver: (args: {
		client_ref: string;
		sales_order: string;
		quantities: LineQuantities | null;
		bill_no: string | null;
		payments: PaymentInput[];
	}) => call<TransactionResult>(`${ROOT}.sales.deliver_order`, args),
	invoice: (args: { client_ref: string; sales_order: string; quantities: LineQuantities | null; payments: PaymentInput[] }) =>
		call<TransactionResult>(`${ROOT}.sales.invoice_order`, args),
	pay: (args: { client_ref: string; customer: string; sales_order: string | null; payments: PaymentInput[] }) =>
		call<TransactionResult>(`${ROOT}.sales.register_payment`, args),
	updateOrder: (args: { client_ref: string; sales_order: string; lines: SaleLineInput[] }) =>
		call<TransactionResult>(`${ROOT}.sales.update_order`, args),
	returnItems: (args: { client_ref: string; sales_order: string; quantities: LineQuantities; refunds: PaymentInput[] }) =>
		call<TransactionResult>(`${ROOT}.sales.return_items`, args),
	billSupplier: (args: { client_ref: string; sales_order: string; bill_no: string | null }) =>
		call<TransactionResult>(`${ROOT}.sales.bill_supplier`, args),
};

export type { CatalogItem };
