<template>
  <v-navigation-drawer
    app
    class="info-panel"
    location="right"
    permanent
    width="500"
  >

    <div class="pa-1">

      <OperatorInstructionsCard
        :instruction-card="instructionCard"
        :instructions="instructions"
      />
      <DistanceStatusCard
        :distance="distance"
        :status="status"
        :status-color="statusColor"
      />

      <SurveyButtonCard
        :distance="distance"
        :survey-button-enabled="surveyButtonEnabled"
        @initiate-survey="$emit('initiate-survey')"
      />
      <DroneStatusCard
        :telemetry-data="droneTelemetryData"
        :survey-in-progress="surveyInProgress"
        :survey-paused="surveyPaused"
      />
      <VehicleStatusCard
        :vehicle-location="vehicleLocation"
        :vehicle-telemetry-data="vehicleTelemetryData"
      />
      <!-- Pass the new props to the MissionProgressCard -->
      <MissionProgressCard
        :carWaypoints="carMissionWaypoints"
      />
    </div>
  </v-navigation-drawer>
</template>

<script setup>
import DistanceStatusCard from './info-panel/DistanceStatusCard.vue'
import DroneStatusCard from './info-panel/DroneStatusCard.vue'
import VehicleStatusCard from './info-panel/VehicleStatusCard.vue'
import SurveyButtonCard from './info-panel/SurveyButtonCard.vue'
import OperatorInstructionsCard from './info-panel/OperatorInstructionsCard.vue'
import MissionProgressCard from './info-panel/MissionProgressCard.vue'


const props = defineProps({
  droneTelemetryData: {
    type: Object,
    required: true,
  },
  vehicleTelemetryData: {
    type: Object,
    required: true,
  },
  distance: {type: Number, required: true},
  status: {type: String, required: true},
  statusColor: {type: Object, required: true},
  vehicleLocation: {type: String, required: true},
  instructions: {type: String, required: true},
  instructionCard: {type: Object, required: true},
  surveyButtonEnabled: {type: Boolean, default: false},
  // Add new props to accept car mission data
  carMissionWaypoints: {
    type: Object,
    default: () => ({})
  },
  // Add survey state props
  surveyInProgress: {
    type: Boolean,
    default: false
  },
  surveyPaused: {
    type: Boolean,
    default: false
  },

})
</script>

<style scoped>
.info-panel {
  box-shadow: -2px 0 5px rgba(0, 0, 0, 0.1);
}
</style>
