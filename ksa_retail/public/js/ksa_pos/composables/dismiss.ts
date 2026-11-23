import { onBeforeUnmount, onMounted, type Ref } from "vue";

/** Close a popover on outside click or Escape. */
export function useDismiss(root: Ref<HTMLElement | null>, isOpen: () => boolean, close: () => void): void {
	const onPointer = (event: PointerEvent) => {
		if (isOpen() && root.value && !root.value.contains(event.target as Node)) close();
	};
	const onKey = (event: KeyboardEvent) => {
		if (isOpen() && event.key === "Escape") {
			event.stopPropagation();
			close();
		}
	};
	onMounted(() => {
		document.addEventListener("pointerdown", onPointer);
		document.addEventListener("keydown", onKey);
	});
	onBeforeUnmount(() => {
		document.removeEventListener("pointerdown", onPointer);
		document.removeEventListener("keydown", onKey);
	});
}
