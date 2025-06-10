<template>
  <v-card class="mb-4">
    <v-card-title>Drone Status</v-card-title>
    <v-card-text>
      <div class="d-flex justify-space-between mb-2">
        <span>Battery:</span>
        <span class="font-weight-bold">{{ droneBattery }}%</span>
      </div>
      <div class="d-flex justify-space-between mb-2">
        <span>Altitude:</span>
        <span class="font-weight-bold">{{ droneAltitude }}m</span>
      </div>
      <div class="d-flex justify-space-between mb-2">
        <span>Speed:</span>
        <span class="font-weight-bold">{{ droneSpeed }} m/s</span>
      </div>
      <div class="d-flex justify-space-between">
        <span>Connection:</span>
        <span class="font-weight-bold text-success">Strong</span>
      </div>
    </v-card-text>
  </v-card>
</template>

<script>
  export default {
    props: {
      droneBattery: {
        type: Number,
        required: true,
      },
      droneAltitude: {
        type: Number,
        required: true,
      },
      droneSpeed: {
        type: Number,
        required: true,
      },
    },
  }
</script>
