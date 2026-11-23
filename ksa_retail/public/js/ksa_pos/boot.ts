import type { Boot } from "./types";

declare global {
	interface Window {
		KSA_POS_BOOT?: Boot;
	}
}

export function readBoot(): Boot {
	const boot = window.KSA_POS_BOOT;
	if (!boot) throw new Error("KSA POS boot data is missing");
	return boot;
}
