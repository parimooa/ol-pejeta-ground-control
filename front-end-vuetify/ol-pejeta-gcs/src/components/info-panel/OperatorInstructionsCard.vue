<template>
  <v-card
    :border="instructionCard.border"
    class="mb-2 rounded-lg mx-auto"
    :color="instructionCard.color"
    elevation="10"
    :variant="instructionCard.variant"
  >
    <v-card-title>Operator Instructions</v-card-title>
    <v-card-text v-html="instructions" />
  </v-card>
</template>

<script setup>
  const props = defineProps({
    instructions: {
      type: String,
      required: true,
    },
    instructionCard: {
      type: Object,
      required: true,
    },
  })
</script>
