<template>
  <v-card
    :border="instructionCard.border"
    class="mb-4"
    :color="instructionCard.color"
    :variant="instructionCard.variant"
  >
    <v-card-title>Operator Instructions</v-card-title>
    <v-card-text v-html="instructions" />
  </v-card>
</template>

<script>
  export default {
    props: {
      instructions: {
        type: String,
        required: true,
      },
      instructionCard: {
        type: Object,
        required: true,
      },
    },
  }
</script>
