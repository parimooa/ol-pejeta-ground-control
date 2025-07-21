<template>
  <v-app>
    <v-app-bar app class="px-4" color="#1a3a5c">
      <div class="text-h6 font-weight-medium">Ol Pejeta GCS</div>
      <v-spacer />

      <!-- Drone Status and Controls -->
      <div class="d-flex align-center mr-4">
        <v-icon :color="isDroneConnected ? 'success' : 'error'" icon="mdi-quadcopter" class="mr-2" />
        <span class="text-subtitle-2 font-weight-medium" :class="isDroneConnected ? 'text-success' : 'text-error'">
          {{ isDroneConnected ? 'Drone Connected' : 'Drone Disconnected' }}
        </span>
        <v-btn
          v-if="!isDroneConnected"
          class="ml-2"
          color="success"
          density="compact"
          variant="tonal"
          @click="connectVehicle('drone')"
        >
          Connect
        </v-btn>
        <v-btn
          v-if="isDroneConnected"
          class="ml-2"
          color="error"
          density="compact"
          variant="tonal"
          @click="disconnectVehicle('drone')"
        >
          Disconnect
        </v-btn>
      </div>

      <!-- Vehicle Status and Controls -->
      <div class="d-flex align-center mr-4">
        <v-icon :color="isVehicleConnected ? 'success' : 'error'" icon="mdi-car" class="mr-2" />
        <span class="text-subtitle-2 font-weight-medium" :class="isVehicleConnected ? 'text-success' : 'text-error'">
          {{ isVehicleConnected ? 'Vehicle Connected' : 'Vehicle Disconnected' }}
        </span>
        <v-btn
          v-if="!isVehicleConnected"
          class="ml-2"
          color="success"
          density="compact"
          variant="tonal"
          @click="connectVehicle('car')"
        >
          Connect
        </v-btn>
        <v-btn
          v-if="isVehicleConnected"
          class="ml-2"
          color="error"
          density="compact"
          variant="tonal"
          @click="disconnectVehicle('car')"
        >
          Disconnect
        </v-btn>
      </div>

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
      :distance="distance"
      :instruction-card="instructionCard"
      :instructions="instructions"
      :mission-steps="missionSteps"
      :status="status"
      :status-color="statusColor"
      :drone-telemetry-data="droneData"
      :vehicle-telemetry-data="vehicleData"
      :vehicle-location="vehicleLocation"
      :survey-button-enabled="surveyButtonEnabled"
      @initiate-survey="initiateSurvey"
    />

    <v-main>
      <div class="d-flex drone-tracking-container">
        <MapContainer
          class="flex-grow-1"
          :distance="distance"
          :drone-telemetry-data="droneData"
          :is-drone-connected="isDroneConnected"
          :is-coordination-active="isCoordinationActive"
          :is-drone-following="isDroneFollowing"
          :is-vehicle-connected="isVehicleConnected"
          :vehicle-telemetry-data="vehicleData"
          :vehicle-waypoints="vehicleData.mission.mission_waypoints"
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
import { computed, onMounted, onBeforeUnmount, reactive, ref, watch } from 'vue'
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
      total_waypoints: 0,
    },
    heartbeat: {
      timestamp: null,
      flight_mode: null,
      system_status: null,
      armed: null,
      guided_enabled: null,
      custom_mode: null,
      mavlink_version: null,
    },
    vehicle_id: null,
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
      total_waypoints: 0,
      mission_waypoints: {}, // <-- Add this
      visited_waypoints: [],   // <-- Add this
    },
    heartbeat: {
      timestamp: null,
      flight_mode: null,
      system_status: null,
      armed: null,
      guided_enabled: null,
      custom_mode: null,
      mavlink_version: null,
    },
    vehicle_id: null,
  })

// Another app state
const distance = ref(0)
const missionActive = ref(false)
const showSnackbar = ref(false)
const snackbarMessage = ref('')
const snackbarColor = ref('success')

// Waypoint navigation state
const nextWaypointInfo = ref(null)
const waypointReached = ref(false)

// WebSocket connections
const wsConnections = reactive({
  drone: null,
  vehicle: null,
})
const wsReconnectAttempts = ref(0)
const maxReconnectAttempts = 5
const isDroneConnected = ref(false)
const isVehicleConnected = ref(false)
let connectionCheckInterval = null

// Coordination state
const isCoordinationActive = ref(false)
const isDroneFollowing = ref(false)
const surveyButtonEnabled = ref(false)

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

// Function to fetch next waypoint information
const fetchNextWaypointInfo = async () => {
  if (!isVehicleConnected.value) return

  try {
    const response = await fetch('http://localhost:8000/survey/waypoint/next?vehicle_type=car')

    if (!response.ok) {
      console.error('Failed to fetch next waypoint info:', response.statusText)
      return
    }

    const data = await response.json()
    nextWaypointInfo.value = data

    // Update instructions with direction to next waypoint
    if (nextWaypointInfo.value) {
      if (waypointReached.value) {
        instructions.value = `You have reached waypoint ${nextWaypointInfo.value.waypoint_number}. Survey is available at this location.`
      } else {
        // Get current vehicle heading
        const currentHeading = vehicleData.velocity.heading
        const targetBearing = nextWaypointInfo.value.bearing

        // Calculate the relative angle between current heading and target bearing
        let relativeAngle = targetBearing - currentHeading
        // Normalize to -180 to 180 degrees
        if (relativeAngle > 180) relativeAngle -= 360
        if (relativeAngle < -180) relativeAngle += 360

        // Determine turn direction
        let turnDirection = ''
        if (Math.abs(relativeAngle) < 15) {
          turnDirection = 'Continue straight'
        } else if (relativeAngle > 0) {
          turnDirection = `Turn right (${Math.abs(Math.round(relativeAngle))}°)`
        } else {
          turnDirection = `Turn left (${Math.abs(Math.round(relativeAngle))}°)`
        }

        instructions.value = `${turnDirection} to head ${nextWaypointInfo.value.direction} for ${Math.round(nextWaypointInfo.value.distance)}m to reach waypoint ${nextWaypointInfo.value.waypoint_number} of ${nextWaypointInfo.value.total_waypoints}.`

        // Log the instructions for debugging
        console.log('Updated operator instructions:', instructions.value)
      }
    }

    console.log('Next waypoint info:', nextWaypointInfo.value)
  } catch (error) {
    console.error('Error fetching next waypoint info:', error)
  }
}

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

// Function to check connection status based on last heartbeat
const checkConnectionStatus = () => {
  const now = Date.now()
  const CONNECTION_TIMEOUT = 5000 // 5 seconds

  // Check drone
  const droneHeartbeat = droneData.heartbeat?.timestamp
  if (droneHeartbeat) {
    const lastHeartbeatMs = droneHeartbeat * 1000 // Convert seconds to ms
    isDroneConnected.value = (now - lastHeartbeatMs) < CONNECTION_TIMEOUT
  } else {
    isDroneConnected.value = false
  }

  // Check vehicle
  const vehicleHeartbeat = vehicleData.heartbeat?.timestamp
  if (vehicleHeartbeat) {
    const lastHeartbeatMs = vehicleHeartbeat * 1000
    isVehicleConnected.value = (now - lastHeartbeatMs) < CONNECTION_TIMEOUT
  } else {
    isVehicleConnected.value = false
  }
}
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

          // Handle new coordination events
          if (data.type === 'coordination_event') {
            console.log(`Received coordination event:`, data.event)
            switch (data.event) {
              case 'coordination_active':
                isCoordinationActive.value = true
                snackbarMessage.value = 'Coordination Mode Activated.'
                snackbarColor.value = 'info'
                showSnackbar.value = true
                break
              case 'following_triggered':
                isDroneFollowing.value = true
                snackbarMessage.value = 'SAFETY: Drone is now following the car!'
                snackbarColor.value = 'warning'
                showSnackbar.value = true
                break
              case 'following_stopped':
                isDroneFollowing.value = false
                break
              case 'coordination_stopped':
                isCoordinationActive.value = false
                isDroneFollowing.value = false
                snackbarMessage.value = 'Coordination Mode Deactivated.'
                snackbarColor.value = 'info'
                showSnackbar.value = true
                break
              case 'coordination_fault':
                snackbarMessage.value = `Coordination Fault: ${data.reason}`
                snackbarColor.value = 'error'
                showSnackbar.value = true
                // Do not change isCoordinationActive or isDroneFollowing, as the service is still running
                break
              case 'survey_button_state_changed':
                surveyButtonEnabled.value = data.enabled
                console.log(`Survey button ${data.enabled ? 'enabled' : 'disabled'} at distance ${data.distance}m`)
                break
              case 'survey_abandoned':
                snackbarMessage.value = `Survey abandoned: ${data.reason}`
                snackbarColor.value = 'warning'
                showSnackbar.value = true
                break
              case 'survey_completed':
                snackbarMessage.value = 'Survey mission completed successfully! 🎉'
                snackbarColor.value = 'success'
                showSnackbar.value = true
                break
            }
            return; // Stop processing since this wasn't a telemetry message
          }

          console.log(`Received ${vehicleType} telemetry data:`, data)

          // Update a telemetry data object based on a vehicle type
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
            if (data.heartbeat) {
              // To prevent flickering, we only update the timestamp if the new one is valid.
              // Otherwise, we keep the last known good timestamp.
              const newHeartbeatData = { ...data.heartbeat };
              if (newHeartbeatData.timestamp === null && droneData.heartbeat.timestamp !== null) {
                // If the incoming packet has no heartbeat, reuse the last one we saw.
                newHeartbeatData.timestamp = droneData.heartbeat.timestamp;
              }
              Object.assign(droneData.heartbeat, newHeartbeatData)
            }
            if (data.vehicle_id) droneData.vehicle_id = data.vehicle_id
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
            if (data.heartbeat) {
              const newHeartbeatData = { ...data.heartbeat };
              if (newHeartbeatData.timestamp === null && vehicleData.heartbeat.timestamp !== null) {
                // If the incoming packet has no heartbeat, reuse the last one we saw.
                newHeartbeatData.timestamp = vehicleData.heartbeat.timestamp;
              }
              Object.assign(vehicleData.heartbeat, newHeartbeatData)
            }
            if (data.vehicle_id) vehicleData.vehicle_id = data.vehicle_id
          }

        } catch (error) {
          console.error(`Error processing ${vehicleType} telemetry message:`, error)
        }
      }

      wsConnections[vehicleType].onclose = event => {
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
  }
}
  // const startMission = async vehicleType => {
  //   console.log('Connecting to '+vehicleType)
  //   try {
  //     const response = await fetch(`http://localhost:8000/vehicles/${vehicleType}/connect`, {
  //       method: 'POST',
  //       headers: {
  //         'Accept': 'application/json',
  //         'Content-Type': 'application/json',
  //       },
  //     })
  //
  //     const data = await response.json()
  //
  //     if (!response.ok) {
  //       throw new Error(data.detail || `Failed to connect to ${vehicleType}`)
  //     }
  //
  //     // Update initial telemetry data from the connected response for the specific vehicle
  //     if (vehicleType === 'drone') {
  //       if (data.position) Object.assign(droneData.position, data.position)
  //       if (data.velocity) Object.assign(droneData.velocity, data.velocity)
  //       if (data.battery) Object.assign(droneData.battery, data.battery)
  //       if (data.mission) Object.assign(droneData.mission, data.mission)
  //       if (data.heartbeat) Object.assign(droneData.heartbeat, data.heartbeat)
  //     } else if (vehicleType === 'car') {
  //       if (data.position) Object.assign(vehicleData.position, data.position)
  //       if (data.velocity) Object.assign(vehicleData.velocity, data.velocity)
  //       if (data.battery) Object.assign(vehicleData.battery, data.battery)
  //       if (data.mission) Object.assign(vehicleData.mission, data.mission)
  //       if (data.heartbeat) Object.assign(vehicleData.heartbeat, data.heartbeat)
  //     }
  //
  //     snackbarMessage.value = `${vehicleType.charAt(0).toUpperCase() + vehicleType.slice(1)} connected successfully`
  //     snackbarColor.value = 'success'
  //     showSnackbar.value = true
  //
  //     // Connect to the WebSocket for telemetry
  //     connectWebSocket(vehicleType)
  //
  //   } catch (error) {
  //     console.error(`Error connecting to ${vehicleType}:`, error)
  //     if (error instanceof TypeError && error.message.includes('Failed to fetch')) {
  //       snackbarMessage.value = 'Connection Refused: Check if the server is running.'
  //     } else {
  //       snackbarMessage.value = `Error connecting to ${vehicleType}: ${error.message}`
  //     }
  //     snackbarColor.value = 'error'
  //     showSnackbar.value = true
  //   }
  // }
  // const emergencyStop = async () => {
  //   try {
  //     const response = await fetch('http://localhost:8000/vehicles/drone/disconnect', {
  //       method: 'POST',
  //       headers: {
  //         'Accept': 'application/json',
  //         'Content-Type': 'application/json',
  //       },
  //     })
  //
  //     const data = await response.json()
  //
  //     if (!response.ok) {
  //       throw new Error(data.detail || 'Failed to disconnect drone')
  //     }
  //
  //     missionActive.value = false
  //     snackbarMessage.value = 'Disconnected successfully'
  //     snackbarColor.value = 'info'
  //     showSnackbar.value = true
  //
  //     disconnectWebSocket()
  //
  //   } catch (error) {
  //     console.error('Error executing emergency stop:', error)
  //     snackbarMessage.value = `Error executing emergency stop: ${error.message}`
  //     snackbarColor.value = 'error'
  //     showSnackbar.value = true
  //     missionActive.value = false
  //     disconnectWebSocket()
  //   }
  // }
const connectVehicle = async vehicleType => {
  console.log(`Connecting to ${vehicleType}...`)
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

const disconnectVehicle = async vehicleType => {
  console.log(`Disconnecting ${vehicleType}...`)
  try {
    const response = await fetch(`http://localhost:8000/vehicles/${vehicleType}/disconnect`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
    })

    const data = await response.json()

    if (!response.ok) {
      throw new Error(data.detail || `Failed to disconnect ${vehicleType}`)
    }

    snackbarMessage.value = `${vehicleType.charAt(0).toUpperCase() + vehicleType.slice(1)} disconnected successfully`
    snackbarColor.value = 'info'
    showSnackbar.value = true

    disconnectWebSocket(vehicleType)

  } catch (error) {
    console.error(`Error disconnecting ${vehicleType}:`, error)
    snackbarMessage.value = `Error disconnecting ${vehicleType}: ${error.message}`
    snackbarColor.value = 'error'
    showSnackbar.value = true
    // Still attempt to close the websocket on error
    disconnectWebSocket(vehicleType)
  }
}
const initiateSurvey = async () => {
  try {
    const response = await fetch('http://localhost:8000/coordination/initiate-proximity-survey', {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
    })

    const data = await response.json()

    if (!response.ok) {
      throw new Error(data.message || 'Failed to initiate survey')
    }

    snackbarMessage.value = 'Proximity survey initiated successfully'
    snackbarColor.value = 'success'
    showSnackbar.value = true

  } catch (error) {
    console.error('Error initiating survey:', error)
    snackbarMessage.value = `Error initiating survey: ${error.message}`
    snackbarColor.value = 'error'
    showSnackbar.value = true
  }
}

onBeforeUnmount(() => {
  if (connectionCheckInterval) {
    clearInterval(connectionCheckInterval)
  }
  disconnectWebSocket('drone')
  disconnectWebSocket('car')
})
onMounted(() => {
  // Start checking connection status periodically
  connectionCheckInterval = setInterval(checkConnectionStatus, 1000)

  // --- START OF CHANGE ---
  // Automatically connect to WebSockets on application startup
  console.log('Application mounted. Automatically connecting WebSockets...')
  connectWebSocket('drone')
  connectWebSocket('car')
  // --- END OF CHANGE ---
})
</script>

<style scoped>
.drone-tracking-container {
  width: 100%;
  height: 100%;
}
:deep(.v-card) {
  margin: 0 auto;
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
