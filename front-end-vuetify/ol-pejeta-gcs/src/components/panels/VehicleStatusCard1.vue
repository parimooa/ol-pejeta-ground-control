<template>
  <v-card class="mb-4">
    <v-card-title>Vehicle Status</v-card-title>
    <v-card-text>
      <div class="d-flex justify-space-between mb-2">
        <span>Speed:</span>
        <span class="font-weight-bold">{{ vehicleSpeed }} m/s ({{ vehicleState }})</span>
      </div>
      <div class="d-flex justify-space-between">
        <span>Location:</span>
        <span class="font-weight-bold">{{ vehicleLocation }}</span>
      </div>
    </v-card-text>
  </v-card>
</template>

<script>
  export default {
    props: {
      vehicleSpeed: {
        type: Number,
        required: true,
      },
      vehicleState: {
        type: String,
        required: true,
      },
      vehicleLocation: {
        type: String,
        required: true,
      },
    },
  }
</script>
