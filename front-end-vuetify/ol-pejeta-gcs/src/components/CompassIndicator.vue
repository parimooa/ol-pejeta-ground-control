<template>
  <div class="compass-container">
    <!-- Compass Toggle Controls -->
    <div class="compass-controls mb-2">
      <v-btn-toggle
        v-model="activeSource"
        color="primary"
        variant="outlined"
        size="x-small"
        mandatory
      >
        <v-btn value="vehicle" :disabled="!isVehicleConnected">
          <v-icon size="small">mdi-car</v-icon>
          <span class="ml-1">Car</span>
        </v-btn>
        <v-btn value="drone" :disabled="!isDroneConnected">
          <v-icon size="small">mdi-quadcopter</v-icon>
          <span class="ml-1">Drone</span>
        </v-btn>
      </v-btn-toggle>
    </div>

    <!-- Main Compass -->
    <div class="compass-wrapper">
      <div class="compass-circle">
        <!-- Fixed compass rose -->
        <div class="compass-rose">
          <!-- Cardinal directions -->
          <div class="direction-marker north">N</div>
          <div class="direction-marker east">E</div>
          <div class="direction-marker south">S</div>
          <div class="direction-marker west">W</div>
          
          <!-- Intercardinal directions -->
          <div class="direction-marker northeast">NE</div>
          <div class="direction-marker southeast">SE</div>
          <div class="direction-marker southwest">SW</div>
          <div class="direction-marker northwest">NW</div>
          
          <!-- Degree markings -->
          <div 
            v-for="degree in degreeMarkings" 
            :key="degree"
            class="degree-mark"
            :style="{ transform: `rotate(${degree}deg)` }"
          >
            <div class="mark-line" :class="{ major: degree % 90 === 0, minor: degree % 30 === 0 && degree % 90 !== 0 }"></div>
          </div>
        </div>

        <!-- Rotating needle -->
        <div 
          class="compass-needle" 
          :style="{ transform: `rotate(${currentHeading}deg)` }"
        >
          <div class="needle-north"></div>
          <div class="needle-south"></div>
        </div>

        <!-- Center dot -->
        <div class="compass-center"></div>
      </div>

      <!-- Heading display -->
      <div class="heading-display">
        <div class="heading-value">{{ currentHeading.toFixed(0) }}°</div>
        <div class="heading-cardinal">{{ cardinalDirection }}</div>
        <div class="heading-source">
          <v-icon size="small" :color="sourceColor">{{ sourceIcon }}</v-icon>
          {{ activeSource.toUpperCase() }}
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, watch } from 'vue'
import { COMPASS_CONSTANTS } from '@/config/constants.js'

const props = defineProps({
  vehicleTelemetryData: {
    type: Object,
    default: null,
  },
  droneTelemetryData: {
    type: Object,
    default: null,
  },
  isVehicleConnected: {
    type: Boolean,
    default: false,
  },
  isDroneConnected: {
    type: Boolean,
    default: false,
  },
})

// Active heading source (vehicle or drone)
const activeSource = ref('vehicle')

// Degree markings for compass (every 10 degrees)
const degreeMarkings = Array.from({ length: 36 }, (_, i) => i * 10)

// Current heading based on selected source
const currentHeading = computed(() => {
  if (activeSource.value === 'vehicle' && props.vehicleTelemetryData?.velocity?.heading !== undefined) {
    return props.vehicleTelemetryData.velocity.heading
  } else if (activeSource.value === 'drone' && props.droneTelemetryData?.velocity?.heading !== undefined) {
    return props.droneTelemetryData.velocity.heading
  }
  return 0 // Default to North if no data
})

// Cardinal direction based on heading
const cardinalDirection = computed(() => {
  const heading = currentHeading.value
  const index = Math.round(heading / COMPASS_CONSTANTS.DEGREE_STEP) % 16
  return COMPASS_CONSTANTS.CARDINAL_DIRECTIONS[index]
})

// Source icon and color
const sourceIcon = computed(() => {
  return activeSource.value === 'vehicle' ? 'mdi-car' : 'mdi-quadcopter'
})

const sourceColor = computed(() => {
  if (activeSource.value === 'vehicle' && props.isVehicleConnected) return 'primary'
  if (activeSource.value === 'drone' && props.isDroneConnected) return 'primary'
  return 'grey'
})

// Auto-switch to available source if current source disconnects
watch([() => props.isVehicleConnected, () => props.isDroneConnected], ([vehicleConnected, droneConnected]) => {
  if (activeSource.value === 'vehicle' && !vehicleConnected && droneConnected) {
    activeSource.value = 'drone'
  } else if (activeSource.value === 'drone' && !droneConnected && vehicleConnected) {
    activeSource.value = 'vehicle'
  }
})

// Set initial source to first available
if (props.isDroneConnected && !props.isVehicleConnected) {
  activeSource.value = 'drone'
}
</script>

<style scoped>
.compass-container {
  background-color: rgba(255, 255, 255, 0.75);
  border-radius: 8px;
  padding: 8px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.15);
  min-width: 140px;
}

.compass-controls {
  display: flex;
  justify-content: center;
}

.compass-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.compass-circle {
  position: relative;
  width: 90px;
  height: 90px;
  border-radius: 50%;
  background: linear-gradient(135deg, rgba(245, 245, 245, 0.9) 0%, rgba(232, 232, 232, 0.9) 100%);
  border: 1px solid rgba(221, 221, 221, 0.8);
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.08);
}

.compass-rose {
  position: absolute;
  width: 100%;
  height: 100%;
}

.direction-marker {
  position: absolute;
  font-size: 11px;
  font-weight: bold;
  color: #333;
  transform-origin: center;
}

.direction-marker.north {
  top: 3px;
  left: 50%;
  transform: translateX(-50%);
  color: #e74c3c;
  font-size: 12px;
}

.direction-marker.east {
  right: 6px;
  top: 50%;
  transform: translateY(-50%);
}

.direction-marker.south {
  bottom: 3px;
  left: 50%;
  transform: translateX(-50%);
}

.direction-marker.west {
  left: 6px;
  top: 50%;
  transform: translateY(-50%);
}

.direction-marker.northeast {
  top: 8px;
  right: 8px;
  font-size: 8px;
}

.direction-marker.southeast {
  bottom: 8px;
  right: 8px;
  font-size: 8px;
}

.direction-marker.southwest {
  bottom: 8px;
  left: 8px;
  font-size: 8px;
}

.direction-marker.northwest {
  top: 8px;
  left: 8px;
  font-size: 8px;
}

.degree-mark {
  position: absolute;
  width: 100%;
  height: 100%;
  top: 0;
  left: 0;
}

.mark-line {
  position: absolute;
  top: 2px;
  left: 50%;
  transform: translateX(-50%);
  background-color: #666;
}

.mark-line.major {
  width: 1px;
  height: 8px;
  background-color: #333;
}

.mark-line.minor {
  width: 1px;
  height: 5px;
  background-color: #666;
}

.mark-line:not(.major):not(.minor) {
  width: 1px;
  height: 3px;
  background-color: #999;
}

.compass-needle {
  position: absolute;
  width: 100%;
  height: 100%;
  top: 0;
  left: 0;
  transition: transform 300ms ease-out;
  z-index: 2;
}

.needle-north {
  position: absolute;
  top: 6px;
  left: 50%;
  width: 0;
  height: 0;
  border-left: 4px solid transparent;
  border-right: 4px solid transparent;
  border-bottom: 30px solid #e74c3c;
  transform: translateX(-50%);
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.3));
}

.needle-south {
  position: absolute;
  bottom: 6px;
  left: 50%;
  width: 0;
  height: 0;
  border-left: 3px solid transparent;
  border-right: 3px solid transparent;
  border-top: 30px solid #34495e;
  transform: translateX(-50%);
  filter: drop-shadow(0 1px 2px rgba(0, 0, 0, 0.3));
}

.compass-center {
  position: absolute;
  top: 50%;
  left: 50%;
  width: 6px;
  height: 6px;
  background-color: #2c3e50;
  border-radius: 50%;
  transform: translate(-50%, -50%);
  z-index: 3;
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}

.heading-display {
  text-align: center;
  min-height: 45px;
}

.heading-value {
  font-size: 14px;
  font-weight: bold;
  color: #2c3e50;
  margin-bottom: 1px;
}

.heading-cardinal {
  font-size: 10px;
  color: #7f8c8d;
  margin-bottom: 2px;
}

.heading-source {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 2px;
  font-size: 9px;
  color: #95a5a6;
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

/* Responsive adjustments */
@media (max-width: 768px) {
  .compass-container {
    min-width: 120px;
    padding: 6px;
  }
  
  .compass-circle {
    width: 75px;
    height: 75px;
  }
  
  .direction-marker.north {
    font-size: 10px;
  }
  
  .heading-value {
    font-size: 12px;
  }
  
  .needle-north {
    border-left: 3px solid transparent;
    border-right: 3px solid transparent;
    border-bottom: 22px solid #e74c3c;
  }
  
  .needle-south {
    border-left: 2px solid transparent;
    border-right: 2px solid transparent;
    border-top: 22px solid #34495e;
  }
}
</style>