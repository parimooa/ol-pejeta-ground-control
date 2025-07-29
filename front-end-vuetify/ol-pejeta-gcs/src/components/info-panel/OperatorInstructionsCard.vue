<template>
  <v-card
    :border="instructionCard.border"
    class="mb-2 rounded-lg mx-auto"
    :color="instructionCard.color"
    elevation="10"
    :variant="instructionCard.variant"
  >
    <v-card-title>Operator Instructions</v-card-title>
    <v-card-text class="text-center pa-4">
      <v-chip
        class="instructions-chip"
        :color="getChipColor()"
        label
        size="x-large"
        variant="elevated"
      >
        <span class="instructions-text" v-html="instructions" />
      </v-chip>
    </v-card-text>
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

  // Function to determine chip color based on instruction content
  const getChipColor = () => {
    const instruction = props.instructions.toLowerCase()

    if (instruction.includes('danger') || instruction.includes('🚨')) {
      return 'error'
    } else if (instruction.includes('warning') || instruction.includes('⚠️')) {
      return 'warning'
    } else if (instruction.includes('survey in progress') || instruction.includes('🚁')) {
      return 'purple'
    } else if (instruction.includes('waypoint reached') || instruction.includes('✅') || instruction.includes('🎯')) {
      return 'success'
    } else if (instruction.includes('turn') || instruction.includes('drive') || instruction.includes('move')) {
      return 'primary'
    } else {
      return 'info'
    }
  }
</script>

<style scoped>
.instructions-chip {
  min-height: 80px !important;
  width: 100%;
  white-space: normal !important;
  padding: 20px 24px !important;
  border-radius: 12px !important;
}

.instructions-text {
  font-size: 1.0rem !important;
  font-weight: 500 !important;
  line-height: 1.5 !important;
  text-align: center;
  display: block;
  width: 100%;
  letter-spacing: 0.6px !important;
}
</style>
