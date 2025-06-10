<template>
  <v-card class="mb-2 rounded-lg mx-auto" elevation="10">
    <v-card-title class="text-h6 text-md-h5 font-weight-bold">
      Telemetry Data
    </v-card-title>

    <v-card-subtitle class="text-h6 text-md-h5 font-weight-bold">
      Drone
    </v-card-subtitle>

    <v-container fluid>
      <v-row dense>
        <v-col
          v-for="(item, index) in droneTelemetryDisplay"
          :key="'drone-' + index"
          cols="6"
        >
          <v-sheet class="py-2 text-center" color="blue-grey" rounded>
            <div class="font-weight-bold text-h5">{{ item.value }}</div>
            <div class="text-caption text-white">{{ item.label }}</div>
            <!-- Progress bar for battery -->
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

    <v-card-subtitle class="text-h6 text-md-h5 font-weight-bold">
      Mission Status
    </v-card-subtitle>

    <v-container fluid>
      <v-row dense>
        <v-col
          v-for="(item, index) in missionTelemetryDisplay"
          :key="'mission-' + index"
          cols="6"
        >
          <v-sheet class="py-2 text-center" color="indigo" rounded>
            <div class="font-weight-bold text-h5">{{ item.value }}</div>
            <div class="text-caption text-white">{{ item.label }}</div>
            <!-- Progress bar for mission progress -->
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

    <!--    <v-card-text>-->
    <!--      <div class="d-flex justify-space-between mb-2">-->
    <!--        <span>Battery:</span>-->
    <!--        <div class="d-flex align-center">-->
    <!--          <span class="font-weight-bold mr-2" :class="batteryTextClass">-->
    <!--            {{ telemetryData.battery.remaining_percentage }}%-->
    <!--            ({{ telemetryData.battery.voltage.toFixed(1) }}V)-->
    <!--          </span>-->
    <!--          &lt;!&ndash; Battery status indicator &ndash;&gt;-->
    <!--          <v-chip-->
    <!--            :color="batteryChipColor"-->
    <!--            size="small"-->
    <!--            variant="flat"-->
    <!--          >-->
    <!--            {{ batteryStatus }}-->
    <!--          </v-chip>-->
    <!--        </div>-->
    <!--      </div>-->

    <!--      <div class="d-flex justify-space-between mb-2">-->
    <!--        <span>Altitude:</span>-->
    <!--        <span class="font-weight-bold">-->
    <!--          {{ telemetryData.position.altitude_msl }}m MSL-->
    <!--        </span>-->
    <!--      </div>-->

    <!--      <div class="d-flex justify-space-between mb-2">-->
    <!--        <span>Ground Speed:</span>-->
    <!--        <span class="font-weight-bold">-->
    <!--          {{ telemetryData.velocity.ground_speed.toFixed(1) }} m/s-->
    <!--        </span>-->
    <!--      </div>-->

    <!--      <div class="d-flex justify-space-between mb-2">-->
    <!--        <span>Heading:</span>-->
    <!--        <span class="font-weight-bold">-->
    <!--          {{ telemetryData.velocity.heading.toFixed(0) }}°-->
    <!--        </span>-->
    <!--      </div>-->

    <!--      <div class="d-flex justify-space-between">-->
    <!--        <span>GPS Position:</span>-->
    <!--        <span class="font-weight-bold text-success">-->
    <!--          {{ gpsStatus }}-->
    <!--        </span>-->
    <!--      </div>-->
    <!--    </v-card-text>-->
  </v-card>
</template>

<script setup>
  import { computed } from 'vue'

  const props = defineProps({
    telemetryData: {
      type: Object,
      required: false,
      default: () => ({
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
      }),
    },
  })

  // Battery color and status logic
  // const batteryTextClass = computed(() => {
  //   const percentage = props.telemetryData.battery.remaining_percentage
  //   if (percentage < 20) return 'text-red'
  //   if (percentage >= 70 && percentage <= 80) return 'text-orange'
  //   return 'text-green'
  // })
  //
  // const batteryChipColor = computed(() => {
  //   const percentage = props.telemetryData.battery.remaining_percentage
  //   if (percentage < 20) return 'red'
  //   if (percentage >= 70 && percentage <= 80) return 'orange'
  //   return 'green'
  // })
  //
  // const batteryStatus = computed(() => {
  //   const percentage = props.telemetryData.battery.remaining_percentage
  //   if (percentage < 20) return 'LOW'
  //   if (percentage >= 70 && percentage <= 80) return 'MEDIUM'
  //   return 'GOOD'
  // })

  const batteryProgressColor = computed(() => {
    const percentage = props.telemetryData.battery.remaining_percentage
    if (percentage < 20) return 'red'
    if (percentage >= 30 && percentage <= 40) return 'orange'
    return 'green'
  })

  // Computed properties for display data with progress bars
  const droneTelemetryDisplay = computed(() => [
    {
      value: `${props.telemetryData.position.altitude_msl}m`,
      label: 'Altitude MSL',
      showProgress: false,
    },
    {
      value: `${props.telemetryData.velocity.ground_speed.toFixed(1)} m/s`,
      label: 'Ground Speed',
      showProgress: false,
    },
    {
      value: `${props.telemetryData.battery.remaining_percentage}%`,
      label: 'Battery',
      showProgress: true,
      progressValue: props.telemetryData.battery.remaining_percentage,
      progressColor: batteryProgressColor.value,
    },
    {
      value: `${props.telemetryData.velocity.heading.toFixed(0)}°`,
      label: 'Heading',
      showProgress: false,
    },
  ])

  const missionTelemetryDisplay = computed(() => [
    {
      value: props.telemetryData.mission.current_wp_seq,
      label: 'Current WP',
      showProgress: false,
    },
    {
      value: props.telemetryData.mission.next_wp_seq,
      label: 'Next WP',
      showProgress: false,
    },
    {
      value: `${props.telemetryData.mission.distance_to_wp.toFixed(0)}m`,
      label: 'Distance to WP',
      showProgress: false,
    },
    {
      value: `${props.telemetryData.mission.progress_percentage}%`,
      label: 'Progress',
      showProgress: true,
      progressValue: props.telemetryData.mission.progress_percentage,
      progressColor: 'blue',
    },
  ])

  const gpsStatus = computed(() => {
    const { latitude, longitude } = props.telemetryData.position
    return (latitude && longitude) ? 'Connected' : 'No Fix'
  })
</script>

<style scoped>
.text-red {
  color: #f44336 !important;
}

.text-orange {
  color: #ff9800 !important;
}

.text-green {
  color: #4caf50 !important;
}
</style>
