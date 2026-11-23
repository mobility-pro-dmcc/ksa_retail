import { createPinia } from "pinia";
import { createApp } from "vue";
import { configureTransport } from "./api/http";
import { readBoot } from "./boot";
import App from "./components/App.vue";
import { keepSessionSaved, restoreSession } from "./stores/persistence";

export function mount(selector: string): void {
	const boot = readBoot();
	configureTransport(boot.csrf_token);
	const app = createApp(App);
	app.use(createPinia());
	app.config.errorHandler = (error) => console.error("[ksa-pos]", error);
	app.mount(selector);
	void restoreSession().finally(keepSessionSaved);
}
