
<template>
  <v-card
    class="mb-2 distance-status-card"
    color="white"
    elevation="8"
    rounded="lg"
  >
    <!-- Compact header -->
    <v-card-title class="px-3 py-2 pb-1">
      <div class="d-flex align-center justify-space-between w-100">
        <div class="d-flex align-center">
          <v-avatar
            :color="statusIndicator.color"
            size="8"
            class="status-pulse me-2"
            :class="statusIndicator.animation"
          >
          </v-avatar>
          <span class="text-title font-weight-bold text-grey-darken-3">Distance Monitoring</span>
        </div>
        <v-chip
          :color="statusChip.color"
          :text-color="statusChip.textColor"
          size="x-small"
          variant="elevated"
          class="font-weight-bold"
        >
          {{ status }}
        </v-chip>
      </div>
    </v-card-title>

    <!-- Compact main content -->
    <v-card-text class="px-3 py-2">
      <div class="text-center">
        <!-- Smaller distance display -->
        <div class="distance-display mb-2">
          <span class="distance-number" :class="distanceTextClass">{{ animatedDistance }}</span>
          <span class="distance-unit text-grey-darken-1">m</span>
        </div>

        <!-- Compact progress indicator -->
        <div class="distance-progress-container mb-2">
          <v-progress-linear
            :model-value="safetyProgress"
            :color="progressColor"
            height="6"
            rounded
            class="mb-1"
          >
          </v-progress-linear>

          <div class="d-flex justify-space-between text-subtitle-2 text-grey-darken-1">
            <span>Safe</span>
            <span class="font-weight-medium">{{ maxSafeDistance }}m</span>
            <span>Critical</span>
          </div>
        </div>

        <!-- Compact status message -->
        <div class="status-message text-subtitle-2 text-grey-darken-2">
          <v-icon :icon="statusAlert.icon" :color="statusAlert.color" size="large" class="me-1"></v-icon>
          {{ compactStatusMessage }}
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>

<script setup>
import { computed, ref, watch, onMounted } from 'vue'
import { DISTANCE_CONSTANTS } from '@/config/constants.js'

const props = defineProps({
  distance: { type: Number, required: true },
  status: { type: String, required: true },
  statusColor: { type: Object, required: true }
})

const animatedDistance = ref(0)
const maxSafeDistance = DISTANCE_CONSTANTS.MAX_SAFE_DISTANCE

// Animate distance changes (simplified)
watch(() => props.distance, (newDistance) => {
  const startDistance = animatedDistance.value
  const duration = 300 // Shorter animation
  const startTime = Date.now()

  const animate = () => {
    const elapsed = Date.now() - startTime
    const progress = Math.min(elapsed / duration, 1)
    const easeOutQuart = 1 - Math.pow(1 - progress, 4)

    animatedDistance.value = Math.round(startDistance + (newDistance - startDistance) * easeOutQuart)

    if (progress < 1) {
      requestAnimationFrame(animate)
    }
  }

  animate()
}, { immediate: true })

// Status indicator
const statusIndicator = computed(() => {
  switch (props.status) {
    case 'SAFE':
      return { color: 'success', animation: 'pulse-slow' }
    case 'WARNING':
      return { color: 'warning', animation: 'pulse-medium' }
    case 'DANGER':
      return { color: 'error', animation: 'pulse-fast' }
    default:
      return { color: 'grey', animation: '' }
  }
})

// Status chip styling with better contrast on white background
const statusChip = computed(() => {
  switch (props.status) {
    case 'SAFE':
      return { color: 'success', textColor: 'white' }
    case 'WARNING':
      return { color: 'orange-darken-2', textColor: 'white' }
    case 'DANGER':
      return { color: 'red-darken-2', textColor: 'white' }
    default:
      return { color: 'grey-darken-2', textColor: 'white' }
  }
})

// Distance text color based on status
const distanceTextClass = computed(() => {
  switch (props.status) {
    case 'SAFE':
      return 'text-success'
    case 'WARNING':
      return 'text-orange-darken-2'
    case 'DANGER':
      return 'text-red-darken-2'
    default:
      return 'text-grey-darken-3'
  }
})

// Safety progress
const safetyProgress = computed(() => {
  if (props.distance >= DISTANCE_CONSTANTS.CRITICAL_THRESHOLD) return 100
  return Math.min((props.distance / maxSafeDistance) * 100, 100)
})

// Progress bar color
const progressColor = computed(() => {
  if (props.distance >= DISTANCE_CONSTANTS.CRITICAL_THRESHOLD) return 'error'
  if (props.distance >= DISTANCE_CONSTANTS.WARNING_THRESHOLD) return 'warning'
  return 'success'
})

// Status alert
const statusAlert = computed(() => {
  switch (props.status) {
    case 'SAFE':
      return { icon: 'mdi-shield-check', color: 'success' }
    case 'WARNING':
      return { icon: 'mdi-alert-triangle', color: 'orange-darken-2' }
    case 'DANGER':
      return { icon: 'mdi-alert-octagon', color: 'red-darken-2' }
    default:
      return { icon: 'mdi-information', color: 'grey' }
  }
})

// Compact status message
const compactStatusMessage = computed(() => {
  switch (props.status) {
    case 'SAFE':
      return 'Operating within safe parameters'
    case 'WARNING':
      return 'Approaching maximum safe distance'
    case 'DANGER':
      return 'Critical distance - immediate attention required'
    default:
      return 'Distance monitoring active'
  }
})

onMounted(() => {
  animatedDistance.value = props.distance
})
</script>

<style scoped>
.distance-status-card {
  position: relative;
  overflow: hidden;
  transition: all 0.2s ease;
  border: 2px solid #f5f5f5;
}

/* Smaller distance display */
.distance-number {
  font-size: 2.5rem;
  font-weight: 800;
  text-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  letter-spacing: -0.02em;
}

.distance-unit {
  font-size: 1.1rem;
  font-weight: 600;
  margin-left: 0.25rem;
}

/* Compact progress container */
.distance-progress-container {
  max-width: 250px;
  margin: 0 auto;
}

/* Status message styling */
.status-message {
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1.2;
}

/* Simplified pulse animation */
.status-pulse {
  position: relative;
}

.pulse-slow::after,
.pulse-medium::after,
.pulse-fast::after {
  content: '';
  position: absolute;
  top: -2px;
  left: -2px;
  right: -2px;
  bottom: -2px;
  border-radius: 50%;
  border: 1px solid currentColor;
  opacity: 0;
}

.pulse-slow::after { animation: pulse 2s infinite; }
.pulse-medium::after { animation: pulse 1s infinite; }
.pulse-fast::after { animation: pulse 0.5s infinite; }

@keyframes pulse {
  0% {
    transform: scale(0.8);
    opacity: 1;
  }
  100% {
    transform: scale(1.8);
    opacity: 0;
  }
}

/* Subtle hover effect with shadow */
.distance-status-card:hover {
  transform: translateY(-1px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15) !important;
}

/* Responsive adjustments */
@media (max-width: 600px) {
  .distance-number {
    font-size: 2rem;
  }

  .distance-unit {
    font-size: 1rem;
  }
}
</style>
