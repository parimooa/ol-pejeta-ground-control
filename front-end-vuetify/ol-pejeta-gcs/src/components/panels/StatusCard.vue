<template>
  <v-card class="mb-4" :color="statusColor.bg" variant="flat">
    <v-card-item>
      <template #prepend>
        <div class="status-dot" :class="statusColor.dot" />
      </template>
      <v-card-title>Distance Status</v-card-title>
    </v-card-item>
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

<script>
  export default {
    props: {
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
    },
  }
</script>

<style scoped>
.status-dot {
  width: 14px;
  height: 14px;
  border-radius: 50%;
}

.bg-success {
  background-color: #2ecc71 !important;
}

.bg-warning {
  background-color: #f39c12 !important;
}

.bg-error {
  background-color: #e74c3c !important;
}

.text-success {
  color: #2ecc71 !important;
}

.text-warning {
  color: #f39c12 !important;
}

.text-error {
  color: #e74c3c !important;
}
</style>
