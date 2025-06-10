<template>
  <v-navigation-drawer
    class="info-panel"
    location="right"
    permanent
    width="350"
  >

    <div class="pa-1">
      <DistanceStatusCard
        :distance="distance"
        :status="status"
        :status-color="statusColor"
      />

      <DroneStatusCard
        :telemetry-data="telemetryData"
      />

      <VehicleStatusCard
        :vehicle-location="vehicleLocation"
        :vehicle-speed="vehicleSpeed"
        :vehicle-state="vehicleState"
      />

      <OperatorInstructionsCard
        :instruction-card="instructionCard"
        :instructions="instructions"
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
  import OperatorInstructionsCard from './info-panel/OperatorInstructionsCard.vue'
  import MissionProgressCard from './info-panel/MissionProgressCard.vue'


  const props = defineProps({
    telemetryData: {
      type: Object,
      required: true,
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
    distance: { type: Number, required: true },
    status: { type: String, required: true },
    statusColor: { type: Object, required: true },
    vehicleSpeed: { type: Number, required: true },
    vehicleState: { type: String, required: true },
    vehicleLocation: { type: String, required: true },
    instructions: { type: String, required: true },
    instructionCard: { type: Object, required: true },
    missionSteps: { type: Array, required: true },
  })
</script>

<style scoped>
.info-panel {
  box-shadow: -2px 0 5px rgba(0, 0, 0, 0.1);
}
</style>
