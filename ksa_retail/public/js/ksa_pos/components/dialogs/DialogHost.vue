<script setup lang="ts">
import { useUiStore } from "../../stores/ui";
import BillSupplierDialog from "./BillSupplierDialog.vue";
import QuantityDialog from "./QuantityDialog.vue";
import RegisterCustomerDialog from "./RegisterCustomerDialog.vue";
import ReturnDialog from "./ReturnDialog.vue";
import SupplierDialog from "./SupplierDialog.vue";

const ui = useUiStore();
</script>

<template>
	<template v-if="ui.dialog">
		<RegisterCustomerDialog v-if="ui.dialog.kind === 'register'" @close="ui.closeDialog()" />
		<QuantityDialog v-else-if="ui.dialog.kind === 'deliver'" mode="deliver" :supplier="ui.dialog.supplier" @close="ui.closeDialog()" />
		<QuantityDialog v-else-if="ui.dialog.kind === 'invoice'" mode="invoice" :supplier="false" @close="ui.closeDialog()" />
		<ReturnDialog v-else-if="ui.dialog.kind === 'return'" @close="ui.closeDialog()" />
		<SupplierDialog v-else-if="ui.dialog.kind === 'supplier'" :deliver="ui.dialog.deliver" @close="ui.closeDialog()" />
		<BillSupplierDialog v-else-if="ui.dialog.kind === 'billSupplier'" @close="ui.closeDialog()" />
	</template>
</template>
