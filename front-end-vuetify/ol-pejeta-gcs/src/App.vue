<template>
  <v-app>
    <v-app-bar app class="px-4" color="#1a3a5c">
      <div class="text-h6 font-weight-medium">Ol Pejeta Drone Tracker</div>
      <v-spacer />
      <v-tabs v-model="activeTab" align-tabs="end" color="white">
        <v-tab
          v-for="(item, index) in navItems"
          :key="index"
          class="text-white text-subtitle-1 font-weight-medium"
          :value="index"
        >
          {{ item.label }}
        </v-tab>
      </v-tabs>
    </v-app-bar>

    <InfoPanel
      class="mt-16"
      :distance="distance"
      :instruction-card="instructionCard"
      :instructions="instructions"
      :mission-steps="missionSteps"
      :status="status"
      :status-color="statusColor"
      :telemetry-data="droneData"
      :vehicle-location="vehicleLocation"
      :vehicle-speed="vehicleSpeed"
      :vehicle-state="vehicleState"
    />

    <v-main>
      <div class="d-flex drone-tracking-container">
        <MapContainer
          class="flex-grow-1"
          :distance="distance"
          :drone-telemetry-data="droneData"
          :vehicle-telemetry-data="vehicleData"
          @emergency-stop="emergencyStop"
          @start-mission="startMission"
        />
      </div>
    </v-main>

    <v-snackbar
      v-model="showSnackbar"
      :color="snackbarColor"
      location="top"
      :timeout="4000"
    >
      {{ snackbarMessage }}
    </v-snackbar>

  </v-app>
</template>

<script setup>
  import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
  import InfoPanel from './components/InfoPanel.vue'
  import MapContainer from './components/MapContainer.vue'

  // Navigation state
  const activeTab = ref(0)
  const navItems = ref([
    { label: 'Dashboard' },
    { label: 'History' },
    { label: 'Settings' },
  ])


  // Reactive telemetry data object matching your API structure
  const droneData = reactive({
    position: {
      latitude: null,
      longitude: null,
      altitude_msl: 0,
      relative_altitude: 0,
    },
    velocity: {
      vx: 0,
      vy: 0,
      vz: 0,
      ground_speed: 0,
      heading: 0,
    },
    battery: {
      voltage: 0,
      remaining_percentage: 100,
    },
    mission: {
      current_wp_seq: 0,
      next_wp_seq: 1,
      distance_to_wp: 0,
      progress_percentage: 0,
    },
  })

    const vehicleData = reactive({
    position: {
      latitude: null,
      longitude: null,
      altitude_msl: 0,
      relative_altitude: 0,
    },
    velocity: {
      vx: 0,
      vy: 0,
      vz: 0,
      ground_speed: 0,
      heading: 0,
    },
    battery: {
      voltage: 0,
      remaining_percentage: 100,
    },
    mission: {
      current_wp_seq: 0,
      next_wp_seq: 1,
      distance_to_wp: 0,
      progress_percentage: 0,
    },
  })

  // Other app state
  const distance = ref(0)
  const missionActive = ref(false)
  const showSnackbar = ref(false)
  const snackbarMessage = ref('')
  const snackbarColor = ref('success')

  // WebSocket connection
  // WebSocket connections
  const wsConnections = reactive({
    drone: null,
    vehicle: null,
  })

  const wsConnected = reactive({
    drone: false,
    vehicle: false,
  })


  const wsReconnectAttempts = ref(0)
  const maxReconnectAttempts = 5

  // Vehicle info derived from telemetry data
  const vehicleSpeed = computed(() => {
    // Ground speed from telemetry is in m/s. Default to 0 if not available.
    return vehicleData.velocity.ground_speed.toFixed(2) ?? 0
  })

  const vehicleState = computed(() => {
    // Use a small threshold (e.g., 0.1 m/s) to account for GPS drift or minor fluctuations.
    return (vehicleData.velocity.ground_speed ?? 0) > 0.1 ? 'Moving' : 'Parked'
  })

  const vehicleLocation = ref('Site Ol Pejeta')

  // Instructions and mission steps
  const instructions = ref('Vehicle position is currently safe. Maintain current position during drone operation.')
  const missionSteps = ref([
    { text: 'Drone take-off', status: 'completed' },
    { text: 'Field scanning', status: 'current', progress: 45 },
    { text: 'Data collection at points A, B, C', status: 'pending' },
    { text: 'Return to base', status: 'pending' },
  ])

  // Computed properties
  const status = computed(() => {
    if (distance.value > 500) return 'DANGER'
    if (distance.value > 490) return 'WARNING'
    return 'SAFE'
  })

  const statusColor = computed(() => {
    switch (status.value) {
      case 'DANGER':
        return { dot: 'bg-error', text: 'text-error', bg: 'bg-error-subtle' }
      case 'WARNING':
        return { dot: 'bg-warning', text: 'text-warning', bg: 'bg-warning-subtle' }
      default: // SAFE
        return { dot: 'bg-success', text: 'text-success', bg: 'bg-success-subtle' }
    }
  })

  const instructionCard = computed(() => {
    if (status.value !== 'DANGER') {
      return { color: '', variant: 'flat', border: false }
    } else {
      return { color: 'error-subtle', variant: 'flat', border: 'start' }
    }
  })

  // Function to calculate distance between two GPS coordinates
  const calculateDistance = (lat1, lon1, lat2, lon2) => {
    const R = 6371000 // Earth's radius in meters
    const toRad = value => (value * Math.PI) / 180

    const dLat = toRad(lat2 - lat1)
    const dLon = toRad(lon2 - lon1)
    const lat1Rad = toRad(lat1)
    const lat2Rad = toRad(lat2)

    const a =
      Math.sin(dLat / 2) * Math.sin(dLat / 2) +
      Math.sin(dLon / 2) * Math.sin(dLon / 2) * Math.cos(lat1Rad) * Math.cos(lat2Rad)
    const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
    return R * c
  }

  // Watch for changes in drone or vehicle position to update distance
  watch(
    [() => droneData.position, () => vehicleData.position],
    ([dronePos, vehiclePos]) => {
      if (
        dronePos &&
        dronePos.latitude !== null &&
        dronePos.longitude !== null &&
        vehiclePos &&
        vehiclePos.latitude !== null &&
        vehiclePos.longitude !== null
      ) {
        const newDistance = calculateDistance(
          dronePos.latitude,
          dronePos.longitude,
          vehiclePos.latitude,
          vehiclePos.longitude,
        )
        distance.value = Math.round(newDistance)
      }
    },
    { deep: true },
  )

  // WebSocket connection function
  const connectWebSocket = vehicleType => {
    if (wsConnections[vehicleType] && wsConnections[vehicleType].readyState === WebSocket.OPEN) {
      console.log(`WebSocket for ${vehicleType} already connected`)
      return
    }

    try {
      console.log(`Connecting to ${vehicleType} telemetry WebSocket...`)
      wsConnections[vehicleType] = new WebSocket(`ws://127.0.0.1:8000/vehicles/${vehicleType}/ws`)

      wsConnections[vehicleType].onopen = () => {
        console.log(`WebSocket connection for ${vehicleType} established`)
        wsConnected[vehicleType] = true
        wsReconnectAttempts.value = 0

        snackbarMessage.value = `Connected to ${vehicleType} telemetry`
        snackbarColor.value = 'success'
        showSnackbar.value = true
      }

      wsConnections[vehicleType].onmessage = event => {
        try {
          const data = JSON.parse(event.data)

          // Ignore ping messages
          if (data.type === 'ping') return

          console.log(`Received ${vehicleType} telemetry data:`, data)

          // Update telemetry data object based on vehicle type
          if (vehicleType === 'drone') {
            if (data.position) {
              Object.assign(droneData.position, data.position)
            }
            if (data.velocity) {
              Object.assign(droneData.velocity, data.velocity)
            }
            if (data.battery) {
              Object.assign(droneData.battery, data.battery)
            }
            if (data.mission) {
              Object.assign(droneData.mission, data.mission)
            }
          } else if (vehicleType === 'car') {
            // Handle vehicle telemetry data
            if (data.position) {
              Object.assign(vehicleData.position, data.position)
            }
            if (data.velocity) {
              Object.assign(vehicleData.velocity, data.velocity)
            }
            if (data.battery) {
              Object.assign(vehicleData.battery, data.battery)
            }
            if (data.mission) {
              Object.assign(vehicleData.mission, data.mission)
            }
          }

        } catch (error) {
          console.error(`Error processing ${vehicleType} telemetry message:`, error)
        }
      }

      wsConnections[vehicleType].onclose = event => {
        wsConnected[vehicleType] = false
        console.log(`WebSocket connection for ${vehicleType} closed: ${event.code} ${event.reason}`)

        if (event.code !== 1000 && wsReconnectAttempts.value < maxReconnectAttempts) {
          const delay = Math.min(1000 * Math.pow(2, wsReconnectAttempts.value), 10000)
          wsReconnectAttempts.value++

          console.log(`Attempting to reconnect ${vehicleType} in ${delay}ms`)
          setTimeout(() => connectWebSocket(vehicleType), delay)
        }
      }

      wsConnections[vehicleType].onerror = error => {
        console.error(`WebSocket error for ${vehicleType}:`, error)
      }

    } catch (error) {
      console.error(`Error establishing WebSocket connection for ${vehicleType}:`, error)
      snackbarMessage.value = `Connection error for ${vehicleType}: ${error.message}`
      snackbarColor.value = 'error'
      showSnackbar.value = true
    }
  }

  const disconnectWebSocket = vehicleType => {
    if (
      wsConnections[vehicleType] &&
      [WebSocket.OPEN, WebSocket.CONNECTING].includes(wsConnections[vehicleType].readyState)
    ) {
      console.log(`Closing WebSocket connection for ${vehicleType}`)
      wsConnections[vehicleType].close(1000, `Disconnecting ${vehicleType} by user action`)
      wsConnected[vehicleType] = false
    }
  }


  const startMission = async vehicleType => {
    console.log('Calling start mission'+vehicleType)
    try {
      const response = await fetch(`http://localhost:8000/vehicles/${vehicleType}/connect`, {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || `Failed to connect to ${vehicleType}`)
      }

      // Update initial telemetry data from the connect response for the specific vehicle
      if (vehicleType === 'drone') {
        if (data.position) Object.assign(droneData.position, data.position)
        if (data.velocity) Object.assign(droneData.velocity, data.velocity)
        if (data.battery) Object.assign(droneData.battery, data.battery)
        if (data.mission) Object.assign(droneData.mission, data.mission)
      } else if (vehicleType === 'car') {
        if (data.position) Object.assign(vehicleData.position, data.position)
        if (data.velocity) Object.assign(vehicleData.velocity, data.velocity)
        if (data.battery) Object.assign(vehicleData.battery, data.battery)
        if (data.mission) Object.assign(vehicleData.mission, data.mission)
      }

      snackbarMessage.value = `${vehicleType.charAt(0).toUpperCase() + vehicleType.slice(1)} connected successfully`
      snackbarColor.value = 'success'
      showSnackbar.value = true

      // Connect to the WebSocket for telemetry
      connectWebSocket(vehicleType)

    } catch (error) {
      console.error(`Error connecting to ${vehicleType}:`, error)
      if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
        snackbarMessage.value = 'Connection Refused: Check if the server is running.'
      } else {
        snackbarMessage.value = `Error connecting to ${vehicleType}: ${error.message}`
      }
      snackbarColor.value = 'error'
      showSnackbar.value = true
    }
  }

  const emergencyStop = async () => {
    try {
      const response = await fetch('http://localhost:8000/vehicles/drone/disconnect', {
        method: 'POST',
        headers: {
          'Accept': 'application/json',
          'Content-Type': 'application/json',
        },
      })

      const data = await response.json()

      if (!response.ok) {
        throw new Error(data.detail || 'Failed to disconnect drone')
      }

      missionActive.value = false
      snackbarMessage.value = 'Emergency stop executed successfully'
      snackbarColor.value = 'info'
      showSnackbar.value = true

      disconnectWebSocket()

    } catch (error) {
      console.error('Error executing emergency stop:', error)
      snackbarMessage.value = `Error executing emergency stop: ${error.message}`
      snackbarColor.value = 'error'
      showSnackbar.value = true
      missionActive.value = false
      disconnectWebSocket()
    }
  }

  onBeforeUnmount(() => {
    disconnectWebSocket()
  })
</script>

<style scoped>
.drone-tracking-container {
  width: 100%;
  height: 100%;
}
:deep(.v-card) {
  max-width: 400px !important;
  margin: 0 auto;
}

:deep(.v-navigation-drawer) {
  width: 300px !important;
}

/* Global styles for status dots and text remain here for now */
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
