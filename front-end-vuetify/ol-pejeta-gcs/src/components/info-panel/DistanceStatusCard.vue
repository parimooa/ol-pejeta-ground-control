<template>
  <v-card class="mb-2 rounded-lg mx-auto" :color="statusColor.bg" elevation="10" variant="flat">
    <v-card-title class="d-flex align-center">
      <div class="status-dot mr-3" :class="statusColor.dot" />
      <span class="text-md-h5 font-weight-bold">Distance Monitoring</span>
    </v-card-title>
    <v-card-text>
      <div class="d-flex justify-space-between mb-2">
        <span>Current Distance:</span>
        <span class="font-weight-bold">{{ distance }}m</span>
      </div>
      <div class="d-flex justify-space-between mb-2">
        <span>Minimum Safe Distance:</span>
        <span class="font-weight-bold">100m</span>
      </div>
      <div class="d-flex justify-space-between">
        <span>Status:</span>
        <span class="font-weight-bold" :class="statusColor.text">
          {{ status }}
        </span>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
  const props = defineProps({
    distance: {
      type: Number,
      required: true,
    },
    status: {
      type: String,
      required: true,
    },
    statusColor: {
      type: Object,
      required: true,
    },
  })
</script>

<style scoped>
/* Status dot and color classes are assumed to be global or imported from a shared stylesheet */
</style>
