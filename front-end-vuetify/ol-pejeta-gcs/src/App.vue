<template>
  <v-app>
    <v-app-bar app class="px-4" color="#1a3a5c">
      <div class="text-h6 font-weight-medium">Ol Pejeta GCS</div>
      <v-spacer/>

      <!-- Drone Status and Controls -->
      <div class="d-flex align-center mr-4">
        <v-icon :color="isDroneConnected ? 'success' : 'error'" class="mr-2" icon="mdi-quadcopter"/>
        <span :class="isDroneConnected ? 'text-success' : 'text-error'" class="text-subtitle-2 font-weight-medium">
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
        <v-icon :color="isVehicleConnected ? 'success' : 'error'" class="mr-2" icon="mdi-car"/>
        <span :class="isVehicleConnected ? 'text-success' : 'text-error'" class="text-subtitle-2 font-weight-medium">
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
          :value="index"
          class="text-white text-subtitle-1 font-weight-medium"
        >
          {{ item.label }}
        </v-tab>
      </v-tabs>
    </v-app-bar>


    <InfoPanel
      :distance="distance"
      :drone-telemetry-data="droneData"
      :instruction-card="instructionCard"
      :instructions="instructions"
      :mission-steps="missionSteps"
      :status="status"
      :status-color="statusColor"
      :survey-button-enabled="surveyButtonEnabled"
      :vehicle-location="vehicleLocation"
      :vehicle-telemetry-data="vehicleData"
      @initiate-survey="initiateSurvey"
    />

    <v-main>
      <div class="d-flex drone-tracking-container">
        <MapContainer
          :distance="distance"
          :drone-mission-waypoints="currentMissionWaypoints"
          :drone-telemetry-data="droneData"
          :is-coordination-active="isCoordinationActive"
          :is-drone-connected="isDroneConnected"
          :is-drone-following="isDroneFollowing"
          :is-drone-surveying="isDroneSurveying"
          :is-vehicle-connected="isVehicleConnected"
          :survey-complete="isSurveyComplete"
          :vehicle-telemetry-data="vehicleData"
          :vehicle-waypoints="vehicleData.mission.mission_waypoints"
          class="flex-grow-1"
        />
      </div>
    </v-main>

    <v-snackbar
      v-model="showSnackbar"
      :color="snackbarColor"
      :timeout="4000"
      location="top"
    >
      {{ snackbarMessage }}
    </v-snackbar>

  </v-app>
</template>

<script setup>
import {computed, onBeforeUnmount, onMounted, reactive, ref, watch} from 'vue'
import InfoPanel from './components/InfoPanel.vue'
import MapContainer from './components/MapContainer.vue'

const surveyInProgress = ref(false)

// Navigation state
const activeTab = ref(0)
const navItems = ref([
  {label: 'Dashboard'},
  {label: 'History'},
  {label: 'Settings'},
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
    mission_waypoints: {},
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
    mission_waypoints: {}, // <--
    visited_waypoints: [],   // <--
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
const surveyState = reactive({
  isComplete: false,
  completedWaypoints: []
})
const instructionType = ref('info')
const surveyInitiated = ref(false)


// Add computed property for survey completion
const isSurveyComplete = computed(() => surveyState.isComplete)

// Add computed property for drone surveying state
const isDroneSurveying = computed(() => {
  return surveyInProgress.value
})

// Get current mission waypoints from drone telemetry
const currentMissionWaypoints = computed(() => {
  const waypoints = droneData.mission.mission_waypoints || {}
  const mappedWaypoints = Object.values(waypoints).map(wp => ({
    lat: wp.lat,
    lon: wp.lon,
    seq: wp.seq
  }))


  return mappedWaypoints
})

// Vehicle info derived from telemetry data
const vehicleLocation = ref('Site Ol Pejeta')

// Instructions and mission steps
const instructions = ref('Vehicle position is currently safe. Maintain current position during drone operation.')
const missionSteps = ref([
  {text: 'Drone take-off', status: 'completed'},
  {text: 'Field scanning', status: 'current', progress: 45},
  {text: 'Data collection at points A, B, C', status: 'pending'},
  {text: 'Return to base', status: 'pending'},
])

// Helper functions for navigation instructions
const calculateBearing = (lat1, lon1, lat2, lon2) => {
  const dLon = (lon2 - lon1) * Math.PI / 180
  const lat1Rad = lat1 * Math.PI / 180
  const lat2Rad = lat2 * Math.PI / 180

  const y = Math.sin(dLon) * Math.cos(lat2Rad)
  const x = Math.cos(lat1Rad) * Math.sin(lat2Rad) - Math.sin(lat1Rad) * Math.cos(lat2Rad) * Math.cos(dLon)

  const bearing = Math.atan2(y, x) * 180 / Math.PI
  return (bearing + 360) % 360
}

const bearingToCompass = (bearing) => {
  const directions = ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW']
  const index = Math.round(bearing / 22.5) % 16
  return directions[index]
}

const bearingToDirection = (bearing) => {
  const directions = [
    'North', 'North-Northeast', 'Northeast', 'East-Northeast',
    'East', 'East-Southeast', 'Southeast', 'South-Southeast',
    'South', 'South-Southwest', 'Southwest', 'West-Southwest',
    'West', 'West-Northwest', 'Northwest', 'North-Northwest'
  ]
  const index = Math.round(bearing / 22.5) % 16
  return directions[index]
}

const getRelativeDirection = (currentHeading, targetBearing) => {
  let relativeAngle = targetBearing - currentHeading
  if (relativeAngle > 180) relativeAngle -= 360
  if (relativeAngle < -180) relativeAngle += 360
  return relativeAngle
}

const getDroneOperationalContext = () => {
  const droneStatus = droneData.heartbeat
  if (!droneStatus) return 'unknown'

  const {armed, custom_mode, system_status} = droneStatus
  const groundSpeed = droneData.velocity.ground_speed || 0

  if (!armed) return 'idle'
  if (armed && custom_mode === 3 && groundSpeed > 1) return 'mission_active' // AUTO mode with movement
  if (armed && custom_mode === 4) return 'guided' // GUIDED mode
  if (armed && system_status === 3) return 'armed_ready'

  return 'active'
}

// Enhanced function to update operator instructions based on car/vehicle telemetry
const updateOperatorInstructions = () => {
  if (!isVehicleConnected.value) {
    instructions.value = '⚠️ VEHICLE NOT CONNECTED: Please connect the ground vehicle to receive mission instructions.'
    instructionType.value = 'warning'
    return // Exit early, as no other instructions are relevant.
  }

  const droneContext = getDroneOperationalContext()
  const vehicleHeading = vehicleData.velocity.heading
  const vehicleSpeed = vehicleData.velocity.ground_speed || 0
  const vehiclePos = vehicleData.position
  const droneSpeed = droneData.velocity.ground_speed || 0

  const missionData = vehicleData.mission
  const currentWaypoint = missionData.current_wp_seq || 0
  const totalWaypoints = missionData.total_waypoints || 0
  const missionWaypoints = missionData.mission_waypoints || {}

  let instruction = 'Standby for mission instructions.'
  instructionType.value = 'info' // Default type

  // Check if survey was just initiated (highest priority)
  if (surveyInitiated.value && !isDroneSurveying.value) {
    instruction = '🚁 SURVEY INITIATED: Drone is preparing to start survey mission. Maintain current position and avoid sudden movements.'
    instructionType.value = 'survey'
    instructions.value = instruction
    return // Exit early for survey initiation message
  }

  // Check if drone is surveying - this takes priority over other instructions
  if (isDroneSurveying.value && vehicleSpeed < 0.5 && !isDroneFollowing.value) {
    instruction = '🚁 SURVEY IN PROGRESS: Drone is actively surveying. Maintain current position and avoid sudden movements.'
    instructionType.value = 'survey'
    instructions.value = instruction
    return // Exit early to prioritise survey message
  }

  // Check if drone is in follow mode (not surveying, following is true, drone moving, vehicle parked)
  if (!isDroneSurveying.value && isDroneFollowing.value && droneSpeed > 1 && vehicleSpeed < 0.5) {
    instruction = '🤖 DRONE FOLLOWING: Drone is in follow mode and tracking ground vehicle. Vehicle is parked - drone maintaining position.'
    instructionType.value = 'info'
    instructions.value = instruction
    return // Exit early for follow mode message
  }

  // Rest of the function remains the same...
  if (totalWaypoints > 0 && missionWaypoints && Object.keys(missionWaypoints).length > 0) {
    let targetWaypointSeq = currentWaypoint
    const visitedWaypoints = missionData.visited_waypoints || []

    if (visitedWaypoints.includes(currentWaypoint)) {
      const sortedWaypoints = Object.keys(missionWaypoints).map(Number).sort((a, b) => a - b)
      for (const seq of sortedWaypoints) {
        if (!visitedWaypoints.includes(seq)) {
          targetWaypointSeq = seq
          break
        }
      }
    }

    const targetWaypoint = missionWaypoints[targetWaypointSeq]

    if (targetWaypoint && vehiclePos.latitude && vehiclePos.longitude) {
      const wpDistance = calculateDistance(
        vehiclePos.latitude, vehiclePos.longitude,
        targetWaypoint.lat, targetWaypoint.lon
      )
      const bearing = calculateBearing(
        vehiclePos.latitude, vehiclePos.longitude,
        targetWaypoint.lat, targetWaypoint.lon
      )
      const waypointNumber = targetWaypointSeq + 1

      if (wpDistance <= 5 && !isDroneSurveying.value && !surveyInitiated.value) {
        instruction = `🎯 WAYPOINT REACHED: You've arrived at waypoint ${waypointNumber}/${totalWaypoints}. Survey operation available here.`
        instructionType.value = 'success'
        waypointReached.value = true
      } else {
        waypointReached.value = false
        const targetDirection = bearingToDirection(bearing)
        const compassDirection = bearingToCompass(bearing)

        if (vehicleHeading !== null && vehicleHeading !== undefined) {
          const relativeAngle = getRelativeDirection(vehicleHeading, bearing)
          let turnInstruction = ''
          if (Math.abs(relativeAngle) < 15) {
            turnInstruction = '➡️ Continue straight'
          } else if (relativeAngle > 0) {
            turnInstruction = relativeAngle > 45 ? `🔄 Turn sharp right (${Math.round(relativeAngle)}°)` : `↗️ Turn right (${Math.round(relativeAngle)}°)`
          } else {
            turnInstruction = relativeAngle < -45 ? `🔄 Turn sharp left (${Math.abs(Math.round(relativeAngle))}°)` : `↖️ Turn left (${Math.abs(Math.round(relativeAngle))}°)`
          }
          let speedGuidance = vehicleSpeed > 5 ? ' - SLOW DOWN' : (vehicleSpeed < 0.5 ? ' - START MOVING' : '')
          instruction = `${turnInstruction} to head ${compassDirection} for ${Math.round(wpDistance)}m to waypoint ${waypointNumber}/${totalWaypoints}${speedGuidance}.`
        } else {
          instruction = `🧭 Drive ${compassDirection} (${targetDirection.toLowerCase()}) for ${Math.round(wpDistance)}m to reach waypoint ${waypointNumber}/${totalWaypoints}.`
        }
        instructionType.value = 'action'
      }
    }
  }
  //
  // if (droneContext === 'mission_active') {
  //   if (isCoordinationActive.value) {
  if (490 > distance.value > 400) {
    instruction = '⚠️ MOVE TOWARDS DRONE: Drive closer to drone position for coordination. Check drone location on map.'
    instructionType.value = 'warning'
  } else if (distance.value > 500) {
    instruction = '🚨 CRITICAL: MOVE CLOSER TO DRONE - Distance exceeds 500m safety limit. Drive towards drone position immediately!'
    instructionType.value = 'error'
    instructions.value = instruction
    return

  } else if (vehicleSpeed > 2 && !waypointReached.value) {
    instruction = '🛑 SLOW DOWN: Approaching waypoint. Drone may start survey here. Reduce speed.'
    instructionType.value = 'action'
  } else if (waypointReached.value && !surveyInitiated.value) {
    instruction = '✅ MAINTAIN POSITION: You are at the survey waypoint. Keep vehicle stationary while drone surveys.'
    instructionType.value = 'success'
  }
  //   }
  // }

  instructions.value = instruction
}
const armCarOnConnect = async () => {
  console.log('WebSocket for car is open. Sending arm command...')
  try {
    const response = await fetch('http://localhost:8000/vehicles/car/arm', {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
    })

    const data = await response.json()

    if (!response.ok) {
      throw new Error(data.detail || 'Failed to send arm command')
    }

    snackbarMessage.value = 'Car arm command sent successfully.'
    snackbarColor.value = 'info'
    showSnackbar.value = true

  } catch (error) {
    console.error('Error sending arm command to car on connect:', error)
    snackbarMessage.value = `Arming Failed: ${error.message}`
    snackbarColor.value = 'error'
    showSnackbar.value = true
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
      return {dot: 'bg-error', text: 'text-error', bg: 'bg-error-subtle'}
    case 'WARNING':
      return {dot: 'bg-warning', text: 'text-warning', bg: 'bg-warning-subtle'}
    default: // SAFE
      return {dot: 'bg-success', text: 'text-success', bg: 'bg-success-subtle'}
  }
})
const instructionCard = computed(() => {
  if (status.value !== 'DANGER') {
    return {color: '', variant: 'flat', border: false}
  } else {
    return {color: 'error-subtle', variant: 'flat', border: 'start'}
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
// Watch for changes in drone or vehicle position to update distance and instructions
watch(
  [() => droneData.position, () => vehicleData.position, () => vehicleData.velocity, () => droneData.heartbeat, () => isCoordinationActive.value,
    () => isDroneFollowing.value,
    () => isDroneSurveying.value,
    () => isVehicleConnected.value
  ],
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
      // Update instructions when position, velocity, or drone status changes
      updateOperatorInstructions()
      fetchCoordinationStatus()
    }
  },
  {deep: true},
)


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
              surveyState.isComplete = true
              surveyState.completedWaypoints = currentMissionWaypoints.value

              snackbarMessage.value = 'Survey mission completed successfully! 🎉'
              snackbarColor.value = 'success'
              showSnackbar.value = true

              // Clear mission waypoints after survey completion with a small delay
              setTimeout(() => {
                console.log('Clearing mission waypoints after survey completion')
                droneData.mission.mission_waypoints = {}
                droneData.mission.total_waypoints = 0
                droneData.mission.current_wp_seq = 0
                droneData.mission.next_wp_seq = 0
                surveyState.isComplete = false // Reset for next survey
              }, 3000) // 3 second delay to allow map to save the completed area
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
            const newHeartbeatData = {...data.heartbeat};
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
            const newHeartbeatData = {...data.heartbeat};
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
    if (vehicleType === 'car') {
      armCarOnConnect()
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
  if (!surveyButtonEnabled.value) {
    console.log('Survey button not enabled')
    return
  }

  try {
    // Immediately set survey initiation state for UI feedback
    surveyInitiated.value = true

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

    console.log('Survey initiated successfully:', data.message)

    // The backend will send WebSocket events to update the actual survey state
    // Don't set surveyInProgress here - let the WebSocket event handle it

    snackbarMessage.value = 'Survey mission initiated successfully!'
    snackbarColor.value = 'success'
    showSnackbar.value = true

  } catch (error) {
    console.error('Failed to initiate survey:', error)

    // Reset survey state on error
    surveyInitiated.value = false

    snackbarMessage.value = `Survey initiation failed: ${error.message}`
    snackbarColor.value = 'error'
    showSnackbar.value = true
  }
}
// fetch coordination status
const fetchCoordinationStatus = async () => {
  try {
    const response = await fetch('http://localhost:8000/coordination/status')
    const data = await response.json()

    console.log('Coordination status on load:', data)

    // Update state based on backend status
    isCoordinationActive.value = data.active
    isDroneFollowing.value = data.following
    surveyInProgress.value = data.surveying
    surveyButtonEnabled.value = data.survey_button_enabled

    // If survey is in progress, clear the initiation flag
    if (data.surveying) {
      surveyInitiated.value = false
    }

    console.log('Frontend state updated:', {
      isCoordinationActive: isCoordinationActive.value,
      isDroneFollowing: isDroneFollowing.value,
      surveyInProgress: surveyInProgress.value,
      surveyButtonEnabled: surveyButtonEnabled.value
    })

  } catch (error) {
    console.error('Failed to fetch coordination status:', error)
  }
}

// Update your onMounted function
onMounted(async () => {
  console.log('App mounted, setting up connections...')

  // Fetch coordination status first
  await fetchCoordinationStatus()

  // Then setup WebSocket connections
  connectWebSocket('drone')
  connectWebSocket('vehicle')

  // Setup connection check interval
  connectionCheckInterval = setInterval(checkConnectionStatus, 5000)

  // Initial instruction update
  updateOperatorInstructions()
})


onBeforeUnmount(() => {
  if (connectionCheckInterval) {
    clearInterval(connectionCheckInterval)
  }
  disconnectWebSocket('drone')
  disconnectWebSocket('car')
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
