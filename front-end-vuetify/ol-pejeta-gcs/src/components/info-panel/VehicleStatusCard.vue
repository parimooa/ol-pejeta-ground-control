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
<!--            <v-progress-linear-->
<!--              v-if="item.showProgress"-->
<!--              class="mt-1"-->
<!--              :color="item.progressColor"-->
<!--              height="4"-->
<!--              :model-value="item.progressValue"-->
<!--              rounded-->
<!--            />-->
          </v-sheet>
        </v-col>
      </v-row>
    </v-container>

  </v-card>
</template>

<script setup>
  import { computed } from 'vue'

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
    { value: props.vehicleTelemetryData?.battery?.remaining_percentage != null ? `${props.vehicleTelemetryData.battery.remaining_percentage}%` : 'N/A', label: 'Battery' },
    { value: props.vehicleLocation, label: 'Location' },
  ])
const nextWaypointDisplay = computed(() => {
    const mission = props.vehicleTelemetryData.mission
    if (!mission) return 'N/A'

    // If progress is 100% or more, the mission is complete.
    if (mission.progress_percentage >= 100) {
      return 'Done'
    }

    // Otherwise, show the next waypoint sequence or N/A if not available.
    return mission.next_wp_seq ?? 'N/A'
  })
  const missionTelemetryDisplay = computed(() => {
    const mission = props.vehicleTelemetryData?.mission

    return [
      {
        // Use 'N/A' for null values
        value: `${nextWaypointDisplay.value - 1 ?? 'N/A'} / ${mission?.total_waypoints ?? 'N/A'}`,
        label: 'Waypoints',
        showProgress: false,
      },
      {
        value: nextWaypointDisplay.value,
        label: 'Next WP',
        showProgress: false,
      },
      {
        // Use 'N/A' for null values
        value: mission?.distance_to_wp != null ? `${mission.distance_to_wp.toFixed(0)}m` : 'N/A',
        label: 'Distance to WP',
        showProgress: false,
      },
      {
        // Use 'N/A' for null values
        value: mission?.progress_percentage != null ? `${mission.progress_percentage}%` : 'N/A',
        label: 'Progress',
        showProgress: true,
        progressValue: mission?.progress_percentage ?? 0,
        progressColor: 'blue',
      },
    ]
  })
</script>
