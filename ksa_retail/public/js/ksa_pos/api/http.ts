/** Transport to Frappe whitelisted methods with one error model for the whole app. */

export type ApiErrorKind = "validation" | "permission" | "not_found" | "session" | "network" | "server" | "aborted";

export class ApiError extends Error {
	readonly kind: ApiErrorKind;
	readonly status: number;
	readonly title: string | null;

	constructor(kind: ApiErrorKind, message: string, status = 0, title: string | null = null) {
		super(message);
		this.name = "ApiError";
		this.kind = kind;
		this.status = status;
		this.title = title;
	}
}

interface FrappeResponse<T> {
	message?: T;
	exc?: string;
	exc_type?: string;
	exception?: string;
	_server_messages?: string;
}

export interface CallOptions {
	signal?: AbortSignal;
}

let csrfToken = "";

export function configureTransport(token: string): void {
	csrfToken = token;
}

const PERMISSION_TYPES = new Set(["PermissionError"]);
const NOT_FOUND_TYPES = new Set(["DoesNotExistError"]);
const SESSION_TYPES = new Set(["SessionExpired", "CSRFTokenError", "AuthenticationError", "SessionStopped"]);

export async function call<T>(method: string, args: Record<string, unknown> = {}, options: CallOptions = {}): Promise<T> {
	let response: Response;
	try {
		response = await fetch(`/api/method/${method}`, {
			method: "POST",
			credentials: "same-origin",
			headers: {
				"Content-Type": "application/json",
				Accept: "application/json",
				"X-Frappe-CSRF-Token": csrfToken,
			},
			body: JSON.stringify(args),
			signal: options.signal,
		});
	} catch (error) {
		if (error instanceof DOMException && error.name === "AbortError") {
			throw new ApiError("aborted", "aborted");
		}
		throw new ApiError("network", "");
	}

	let payload: FrappeResponse<T> = {};
	try {
		payload = (await response.json()) as FrappeResponse<T>;
	} catch {
		payload = {};
	}
	if (response.ok && !payload.exc) return payload.message as T;
	throw toApiError(response.status, payload);
}

function toApiError<T>(status: number, payload: FrappeResponse<T>): ApiError {
	const type = payload.exc_type ?? "";
	const { message, title } = serverMessage(payload);
	if (SESSION_TYPES.has(type) || (status === 401 && !message)) return new ApiError("session", message, status, title);
	if (PERMISSION_TYPES.has(type) || status === 403) return new ApiError("permission", message, status, title);
	if (NOT_FOUND_TYPES.has(type) || status === 404) return new ApiError("not_found", message, status, title);
	if (status === 417 || message) return new ApiError("validation", message, status, title);
	// unexpected server error: keep the technical details in the console, not on screen
	if (payload.exc) console.error("[ksa-pos] server error", payload.exc_type, payload.exc);
	return new ApiError("server", "", status, title);
}

function serverMessage<T>(payload: FrappeResponse<T>): { message: string; title: string | null } {
	let title: string | null = null;
	const texts: string[] = [];
	try {
		const raw = JSON.parse(payload._server_messages ?? "[]") as string[];
		for (const entry of raw) {
			try {
				const parsed = JSON.parse(entry) as { message?: string; title?: string };
				if (parsed.message) texts.push(parsed.message);
				if (parsed.title && !title) title = parsed.title;
			} catch {
				texts.push(entry);
			}
		}
	} catch {
		/* ignore malformed messages */
	}
	return { message: texts.map(stripHtml).filter(Boolean).join("\n"), title };
}

function stripHtml(html: string): string {
	const element = document.createElement("div");
	element.innerHTML = html;
	return (element.textContent ?? "").trim();
}
