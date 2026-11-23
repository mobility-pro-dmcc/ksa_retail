<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "../../i18n";
import { useOrdersStore } from "../../stores/orders";
import { useSaleStore } from "../../stores/sale";
import { useSessionStore } from "../../stores/session";
import { useUiStore } from "../../stores/ui";
import AppIcon from "../common/AppIcon.vue";
import EmptyState from "../common/EmptyState.vue";
import CartLineRow from "./CartLineRow.vue";
import DiscountControl from "./DiscountControl.vue";
import LinkedDocuments from "./LinkedDocuments.vue";
import OperationBar from "./OperationBar.vue";
import OrderLineRow from "./OrderLineRow.vue";
import PaymentRows from "./PaymentRows.vue";
import SubmitButton from "./SubmitButton.vue";
import TotalsSummary from "./TotalsSummary.vue";

const sale = useSaleStore();
const orders = useOrdersStore();
const session = useSessionStore();
const ui = useUiStore();
const { t } = useI18n();

const order = computed(() => orders.active);
const title = computed(() => (sale.editing ? t("editingOrder") : order.value ? t("order") : t("newSale")));
const quotedLine = (index: number) => sale.quote?.lines[index] ?? null;
const canReturn = computed(() => Boolean(order.value?.can_return) && session.can("Delivery Note", "submit"));

function closeOrder() {
	if (sale.editing) sale.reset();
	orders.close();
	sale.resetPayments();
}
</script>

<template>
	<aside class="checkout" :aria-label="title">
		<header class="checkout__head">
			<h2 class="checkout__title">{{ title }}</h2>
			<span v-if="order" class="order-pill">
				<bdi class="data">{{ order.name }}</bdi>
				<button type="button" :aria-label="t('closeOrder')" :title="t('closeOrder')" @click="closeOrder"><AppIcon name="close" :size="13" /></button>
			</span>
		</header>

		<div v-if="sale.editing" class="edit-banner">
			<AppIcon name="edit" />
			<span>{{ t("editHint") }}</span>
			<button type="button" class="link-button" @click="sale.cancelEdit()">{{ t("discardChanges") }}</button>
		</div>
		<template v-else>
			<OperationBar />
			<p v-if="!order" class="checkout__hint"><AppIcon name="info" :size="15" />{{ sale.lines.length ? t("hintNewSale") : t("hintEmptySale") }}</p>
		</template>

		<div class="checkout__body">
			<section class="checkout-section" :aria-label="t('items')">
				<header class="section-label">
					<span>{{ t("items") }}</span>
					<span v-if="order && !sale.editing" class="section-label__actions">
						<button v-if="canReturn" type="button" class="link-button link-button--danger" @click="ui.openDialog({ kind: 'return' })">
							<AppIcon name="undo" :size="15" />{{ t("returnItems") }}
						</button>
						<span v-if="order.edit_block" class="badge" :title="order.edit_block">{{ t("locked") }}</span>
						<button v-else type="button" class="link-button" @click="sale.startEdit(order)"><AppIcon name="edit" :size="15" />{{ t("edit") }}</button>
					</span>
					<span v-else class="count">{{ sale.lines.length }}</span>
				</header>
				<div v-if="order && !sale.editing" class="cart-lines">
					<OrderLineRow v-for="line in order.lines" :key="line.so_detail" :line="line" />
				</div>
				<div v-else-if="sale.lines.length" class="cart-lines">
					<CartLineRow
						v-for="(line, index) in sale.lines"
						:key="line.key"
						:line="line"
						:amount="quotedLine(index)?.amount ?? null"
						:quoted-rate="quotedLine(index)?.rate ?? null"
					/>
				</div>
				<EmptyState v-else icon="box" :title="t('emptyCartTitle')" :hint="t('emptyCartHint')">
					<button type="button" class="link-button" @click="ui.tab = 'products'">{{ t("browseProducts") }}<AppIcon name="chevron" :size="14" class="icon--forward" /></button>
				</EmptyState>
			</section>

			<PaymentRows v-if="!sale.editing" />
			<DiscountControl v-if="!order" />
			<TotalsSummary />
			<LinkedDocuments v-if="order && !sale.editing" :order="order" />
		</div>

		<SubmitButton />
	</aside>
</template>
