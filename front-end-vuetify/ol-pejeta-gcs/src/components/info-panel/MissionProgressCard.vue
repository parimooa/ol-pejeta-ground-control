<template>
  <v-card class="mb-2 rounded-lg mx-auto" elevation="10">
    <v-card-title>Mission Progress</v-card-title>
    <v-card-text>
      <div v-for="(step, index) in missionSteps" :key="index" class="d-flex align-center mb-3">
        <v-avatar
          class="mr-3 text-white"
          :color="getStepStatusColor(step.status)"
          size="28"
        >
          {{ index + 1 }}
        </v-avatar>
        <div>
          <div>{{ step.text }}</div>
          <div v-if="step.progress" class="text-caption text-grey">
            {{ step.progress }}% complete
          </div>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
  const props = defineProps({
    missionSteps: { // Array of objects with { text, status, progress }
      type: Array,
      required: true,
    },
  })

  const getStepStatusColor = status => {
    switch (status) {
      case 'completed': return 'success'
      case 'current': return 'warning'
      default: return 'grey'
    }
  }
</script>
