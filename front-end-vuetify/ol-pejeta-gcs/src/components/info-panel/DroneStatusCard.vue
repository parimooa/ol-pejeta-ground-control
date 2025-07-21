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
          </v-sheet>
        </v-col>
      </v-row>
    </v-container>

    <v-card-subtitle class="text-h6 text-md-h5 font-weight-bold">
     Drone Status
    </v-card-subtitle>

    <v-container fluid>
      <v-row dense>
        <v-col cols="12">
          <v-sheet class="py-2 text-center" :color="operationalStatusColor" rounded>
            <div class="font-weight-bold text-h5">{{ operationalStatus }}</div>
            <div class="text-caption text-white">Current Operation</div>
          </v-sheet>
        </v-col>
      </v-row>
    </v-container>

    <v-card-subtitle class="text-h6 text-md-h5 font-weight-bold">
     Survey Status
    </v-card-subtitle>


<v-container fluid>
  <v-row dense>
    <v-col
      v-for="(item, index) in missionTelemetryDisplay"
      :key="'mission-' + index"
      cols="6"
    >
      <v-card
        class="text-center"
        color="indigo"
        rounded
        elevation="2"
      >
        <v-card-text class="py-2">
          <div class="font-weight-bold text-h5 text-white">{{ item.value }}</div>
          <div class="text-caption text-white">{{ item.label }}</div>

        </v-card-text>
      </v-card>
    </v-col>
  </v-row>
</v-container>


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
        heartbeat: {
          timestamp: null,
          flight_mode: null,
          system_status: null,
          armed: null,
          guided_enabled: null,
          custom_mode: null,
          mavlink_version: null,
          operational_status: 'Idle',
        },
      }),
    },
  })



  const batteryProgressColor = computed(() => {
    const percentage = props.telemetryData.battery.remaining_percentage
    if (percentage < 20) return 'red'
    if (percentage >= 30 && percentage <= 40) return 'orange'
    return 'green'
  })

 // Computed properties for display data with progress bars
  const droneTelemetryDisplay = computed(() => [
    {
      // Use optional chaining and provide a default value if altitude_msl is null or undefined
      value: `${props.telemetryData?.position?.altitude_msl ?? 'N/A'}m`,
      label: 'Altitude MSL',
      showProgress: false,
    },
    {
      // Use optional chaining and provide a default value before calling toFixed
      value: `${props.telemetryData?.velocity?.ground_speed?.toFixed(1) ?? 'N/A'} m/s`,
      label: 'Ground Speed',
      showProgress: false,
    },
    {
      // Use optional chaining and provide a default value for remaining_percentage
      value: `${props.telemetryData?.battery?.remaining_percentage ?? 'N/A'}%`,
      label: 'Battery',
      showProgress: true,
      // Provide a default value for progressValue as well
      progressValue: props.telemetryData?.battery?.remaining_percentage ?? 0,
      progressColor: batteryProgressColor.value,
    },
    {
      // Use optional chaining and provide a default value before calling toFixed
      value: `${props.telemetryData?.velocity?.heading?.toFixed(0) ?? 'N/A'}°`,
      label: 'Heading',
      showProgress: false,
    },
  ])


const missionTelemetryDisplay = computed(() => {
  const current = props.telemetryData?.mission?.current_wp_seq || 0
  const total = props.telemetryData?.mission?.total_waypoints || 0
  const percentage = total > 0 ? Math.round((current / total) * 100) : 0

  return [
    {
      value: `${current}/${total}`,
      label: 'Current WP',
      showProgress: false,
    },
    {
      value: props.telemetryData?.mission?.next_wp_seq ?? 'N/A',
      label: 'Next WP',
      showProgress: false,
    },
    {
      value: `${props.telemetryData?.mission?.distance_to_wp?.toFixed(0) ?? 'N/A'}m`,
      label: 'Distance to WP',
      showProgress: false,
    },
    {
      value: `${percentage}%`,
      label: 'Progress',
      showProgress: true,
      progressValue: percentage,
      progressColor: 'blue',
    },
  ]
})

const operationalStatus = computed(() => {
  const heartbeat = props.telemetryData?.heartbeat

  if (!heartbeat) {
    return 'No Data'
  }

  const {
    armed,
    operational_status,
    system_status,
    custom_mode,
    flight_mode,
    guided_enabled
  } = heartbeat

  // System status values (MAV_STATE enum):
  // 0: UNINIT, 1: BOOT, 2: CALIBRATING, 3: STANDBY, 4: ACTIVE, 5: CRITICAL, 6: EMERGENCY, 7: POWEROFF

  // Determine actual operational state
  let actualStatus = 'Unknown'

  if (!armed) {
    actualStatus = 'Idle'
  } else if (armed && system_status === 3) {
    // Armed but in standby
    actualStatus = 'Armed'
  } else if (armed && system_status === 4) {
    // Armed and active - need to check flight mode for more specific status
    if (custom_mode === 3 && props.telemetryData.velocity.ground_speed >1) {
      // Auto mode - likely executing mission
      actualStatus = 'Executing Mission'
    } else if (custom_mode === 4) {
      // Guided mode
      actualStatus = guided_enabled ? 'Guided Flight' : 'Armed'
    } else if (custom_mode === 22) {
      // Takeoff mode (ArduCopter)
      actualStatus = 'Taking Off'
    } else if (custom_mode === 16) {
      // Survey/Auto mission modes
      actualStatus = 'Surveying'
    } else {
      actualStatus = 'Active Flight'
    }
  } else if (system_status === 5) {
    actualStatus = 'Critical'
  } else if (system_status === 6) {
    actualStatus = 'Emergency'
  }

  console.log('Drone telemetry analysis:', {
    armed,
    system_status,
    custom_mode,
    flight_mode,
    original_status: operational_status,
    determined_status: actualStatus
  })

  return actualStatus
})

  const operationalStatusColor = computed(() => {
    const status = operationalStatus.value.toLowerCase()

    if (status.includes('failed') || status.includes('error')) {
      return 'error'
    } else if (status.includes('executing') || status.includes('survey')) {
      return 'success'
    } else if (status.includes('preparing') || status.includes('uploading') || status.includes('starting')) {
      return 'info'
    } else if (status.includes('abandoned') || status.includes('timed out')) {
      return 'warning'
    } else {
      return 'blue-grey'
    }
  })

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
