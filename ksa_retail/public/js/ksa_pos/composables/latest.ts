/** Latest-request-wins: starting a new request aborts the previous one and its result is dropped. */
export interface LatestRunner {
	run<T>(task: (signal: AbortSignal) => Promise<T>): Promise<{ superseded: true } | { superseded: false; value: T }>;
	cancel(): void;
}

export function createLatest(): LatestRunner {
	let controller: AbortController | null = null;
	let ticket = 0;
	return {
		async run(task) {
			controller?.abort();
			const own = new AbortController();
			controller = own;
			const mine = ++ticket;
			try {
				const value = await task(own.signal);
				return mine === ticket ? { superseded: false, value } : { superseded: true };
			} catch (error) {
				if (mine !== ticket || own.signal.aborted) return { superseded: true };
				throw error;
			}
		},
		cancel() {
			ticket++;
			controller?.abort();
			controller = null;
		},
	};
}

export function debounce<A extends unknown[]>(fn: (...args: A) => void, wait: number): ((...args: A) => void) & { cancel(): void } {
	let timer: ReturnType<typeof setTimeout> | undefined;
	const debounced = (...args: A) => {
		clearTimeout(timer);
		timer = setTimeout(() => fn(...args), wait);
	};
	debounced.cancel = () => clearTimeout(timer);
	return debounced;
}
