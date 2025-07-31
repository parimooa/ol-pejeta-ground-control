<template>
  <v-card class="mb-2 rounded-lg vehicle-status-card" elevation="8">
    <!-- Compact header -->
    <v-card-title class="px-3 py-2 d-flex align-center justify-space-between">
      <div class="d-flex align-center">
        <v-icon class="me-2" color="purple-lighten-1" icon="mdi-car" size="small"></v-icon>
        <span class="text-subtitle-1 font-weight-bold">Ground Vehicle Status</span>
      </div>

    </v-card-title>
    <!-- Compact main status -->
    <v-card-text class="px-3 py-2">
      <v-row dense>
        <v-col v-for="(item, index) in vehicleStatusDisplay" :key="index" cols="6">
          <v-sheet class="py-2 px-2 text-center status-chip" color="purple-darken-1" rounded>
            <div class="font-weight-bold text-subtitle-1">{{ item.value }}</div>
            <div class="text-caption text-white">{{ item.label }}</div>
          </v-sheet>
        </v-col>
      </v-row>
    </v-card-text>

    <!-- Expandable mission details -->
    <v-card-actions>
      <v-btn
        color="deep-purple-accent-3"
        text="Mission Waypoints Details"
      ></v-btn>
      <v-spacer></v-spacer>
      <v-btn
        :icon="show ? 'mdi-chevron-up' : 'mdi-chevron-down'"
        @click="show = !show"
      ></v-btn>
    </v-card-actions>
    <v-expand-transition>
      <div v-show="show">
        <v-divider class="mx-3"></v-divider>
        <v-card-text class="px-3 py-2">
          <div class="text-subtitle-2 font-weight-bold mb-2 text-indigo">Mission Status</div>
          <v-row dense>
            <v-col v-for="(item, index) in missionTelemetryDisplay" :key="'mission-' + index" cols="6">
              <v-sheet class="py-2 px-2 text-center mission-chip" color="indigo" rounded>
                <div class="font-weight-bold text-subtitle-2">{{ item.value }}</div>
                <div class="text-caption text-white">{{ item.label }}</div>

              </v-sheet>
            </v-col>
          </v-row>
        </v-card-text>
      </div>
    </v-expand-transition>
  </v-card>
</template>

<script setup>
import {computed, reactive, ref, watch} from 'vue'

const show = ref(false)
const props = defineProps({
  vehicleTelemetryData: {
    type: Object,
    required: true,
  },
  vehicleLocation: {
    type: String,
    required: true,
  },
})

// Local state for tracking visited waypoints
const localMissionState = reactive({
  visitedWaypoints: new Set(),
  totalWaypoints: 0,
  lastCheckedWaypoint: null,
})

// Vehicle info derived from telemetry data
const vehicleSpeed = computed(() => {
  return props.vehicleTelemetryData?.velocity?.ground_speed?.toFixed(1) ?? '0.0'
})

const vehicleState = computed(() => {
  return (props.vehicleTelemetryData?.velocity?.ground_speed ?? 0) > 0.1 ? 'Moving' : 'Parked'
})

const vehicleStatusDisplay = computed(() => [
  {value: `${vehicleSpeed.value} m/s`, label: 'Speed'},
  {value: vehicleState.value, label: 'State'},
])

// Watch for waypoint arrivals and update local state
watch(
  () => props.vehicleTelemetryData?.mission,
  (newMission, oldMission) => {
    if (!newMission) return

    // Update total waypoints
    if (newMission.total_waypoints !== localMissionState.totalWaypoints) {
      localMissionState.totalWaypoints = newMission.total_waypoints || 0
    }

    // Sync visited waypoints from backend
    if (newMission.visited_waypoints && Array.isArray(newMission.visited_waypoints)) {
      // Clear and repopulate the Set with backend data
      localMissionState.visitedWaypoints.clear()
      newMission.visited_waypoints.forEach(wp => {
        localMissionState.visitedWaypoints.add(wp)
      })
    }

    // Check if we've arrived at a new waypoint
    const currentWP = newMission.current_wp_seq
    const distanceToWP = newMission.distance_to_wp || 0
    const ARRIVAL_THRESHOLD = 5 // meters

    if (currentWP !== null && currentWP !== localMissionState.lastCheckedWaypoint) {
      // Check if we're close enough to the current waypoint to mark it as visited
      if (distanceToWP <= ARRIVAL_THRESHOLD && !localMissionState.visitedWaypoints.has(currentWP)) {
        console.log(`🎯 Waypoint ${currentWP + 1} reached! Distance: ${distanceToWP.toFixed(1)}m`)
        localMissionState.visitedWaypoints.add(currentWP)
      }
      localMissionState.lastCheckedWaypoint = currentWP
    }
  },
  {deep: true, immediate: true}
)

// Calculate progress percentage based on visited waypoints
const progressPercentage = computed(() => {
  if (localMissionState.totalWaypoints === 0) return 0

  const visitedCount = localMissionState.visitedWaypoints.size
  const progress = Math.round((visitedCount / localMissionState.totalWaypoints) * 100)

  // Cap at 100%
  return Math.min(progress, 100)
})

const nextWaypointDisplay = computed(() => {
  const mission = props.vehicleTelemetryData?.mission
  if (!mission) return 'N/A'

  // If progress is 100%, the mission is complete
  if (progressPercentage.value >= 100) {
    return 'Complete'
  }

  // Show next waypoint (1-indexed for display)
  return mission.next_wp_seq !== null ? mission.next_wp_seq + 1 : 'N/A'
})

const missionTelemetryDisplay = computed(() => {
  const mission = props.vehicleTelemetryData?.mission
  const visitedCount = localMissionState.visitedWaypoints.size
  const totalWaypoints = localMissionState.totalWaypoints

  return [
    {
      value: `${visitedCount}/${totalWaypoints || 0}`,
      label: 'Waypoints',
      showProgress: false,
    },
    {
      value: nextWaypointDisplay.value,
      label: 'Next WP',
      showProgress: false,
    },
    {
      value: mission?.distance_to_wp != null ? `${mission.distance_to_wp.toFixed(0)}m` : 'N/A',
      label: 'Distance',
      showProgress: false,
    },
    {
      value: `${progressPercentage.value}%`,
      label: 'Progress',
      showProgress: true,
      progressValue: progressPercentage.value,
      progressColor: progressPercentage.value >= 100 ? 'success' : 'primary',
    },
  ]
})
</script>

<style scoped>
.vehicle-status-card {
  transition: all 0.2s ease;
}

.vehicle-status-card:hover {
  transform: translateY(-1px);
}

.status-chip,
.mission-chip {
  transition: all 0.2s ease;
}

.status-chip:hover,
.mission-chip:hover {
  transform: scale(1.02);
}
</style>
