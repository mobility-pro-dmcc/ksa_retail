/** Template helpers: typed access to form events (templates are compiled as plain JS). */
export function inputValue(event: Event): string {
	return (event.target as HTMLInputElement | HTMLSelectElement).value;
}

export function inputNumber(event: Event): number {
	return Number(inputValue(event)) || 0;
}
