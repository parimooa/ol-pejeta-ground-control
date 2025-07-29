<template>
  <v-card class="mb-2 rounded-lg mx-auto" elevation="10">
    <v-card-title class="text-h6 text-md-h5 font-weight-bold">
      Vehicle Status
    </v-card-title>

    <v-container fluid>
      <v-row dense>
        <v-col v-for="(item, index) in vehicleStatusDisplay" :key="index" cols="6">
          <v-sheet class="py-2 text-center" color="purple-darken-1" rounded>
            <div class="font-weight-bold text-h5">{{ item.value }}</div>
            <div class="text-caption text-white">{{ item.label }}</div>
          </v-sheet>
        </v-col>
      </v-row>
    </v-container>

    <v-card-subtitle class="text-h6 text-md-h5 font-weight-bold">
      Mission Status
    </v-card-subtitle>

    <v-container fluid>
      <v-row dense>
        <v-col v-for="(item, index) in missionTelemetryDisplay" :key="'mission-' + index" cols="6">
          <v-sheet class="py-2 text-center" color="indigo" rounded>
            <div class="font-weight-bold text-h5">{{ item.value }}</div>
            <div class="text-caption text-white">{{ item.label }}</div>
            <!-- Add progress bar for progress percentage -->
            <v-progress-linear
              v-if="item.showProgress"
              class="mt-1"
              :color="item.progressColor"
              height="4"
              :model-value="item.progressValue"
              rounded
            />
          </v-sheet>
        </v-col>
      </v-row>
    </v-container>

  </v-card>
</template>

<script setup>
  import { computed, reactive, watch } from 'vue'

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
    { value: `${vehicleSpeed.value} m/s`, label: 'Ground Speed' },
    { value: vehicleState.value, label: 'State' },
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
    { deep: true, immediate: true }
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
        value: `${visitedCount} / ${totalWaypoints || 'N/A'}`,
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
        label: 'Distance to WP',
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
