<template>
  <v-navigation-drawer
    class="info-panel"
    app
    location="right"
    permanent
    width="500"
  >

    <div class="pa-1">

      <OperatorInstructionsCard
        :instruction-card="instructionCard"
        :instructions="instructions"
      />
      <VehicleStatusCard
        :vehicle-telemetry-data="vehicleTelemetryData"
        :vehicle-location="vehicleLocation"
      />
      <SurveyButtonCard
        :survey-button-enabled="surveyButtonEnabled"
        :distance="distance"
        @initiate-survey="$emit('initiate-survey')"
      />
      <DistanceStatusCard
        :distance="distance"
        :status="status"
        :status-color="statusColor"
      />

      <DroneStatusCard
        :telemetry-data="droneTelemetryData"
      />


      <MissionProgressCard
        :mission-steps="missionSteps"
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
  missionSteps: {type: Array, required: true},
  surveyButtonEnabled: {type: Boolean, default: false},
})
</script>

<style scoped>
.info-panel {
  box-shadow: -2px 0 5px rgba(0, 0, 0, 0.1);
}
</style>
