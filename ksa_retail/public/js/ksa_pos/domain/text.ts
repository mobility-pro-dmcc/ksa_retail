const COMPANY_WORDS = /^(مؤسسة|شركة)\s+/;

/** Two-letter monogram for people and companies, in Arabic or Latin script. */
export function initials(name: string | null | undefined): string {
	const words = String(name ?? "?")
		.replace(COMPANY_WORDS, "")
		.split(/\s+/)
		.filter(Boolean)
		.slice(0, 2);
	return words.map((word) => word.replace(/^ال/, "").charAt(0)).join("").toUpperCase() || "?";
}

export function uid(): string {
	return typeof crypto !== "undefined" && "randomUUID" in crypto
		? crypto.randomUUID()
		: `${Date.now().toString(36)}${Math.random().toString(36).slice(2)}`;
}
