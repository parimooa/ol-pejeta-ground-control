<template>
  <v-navigation-drawer
    class="info-panel"
    location="right"
    permanent
    width="350"
  >
    <div class="pa-4">
      <StatusCard
        :distance="distance"
        :status="status"
        :status-color="statusColor"
      />

      <DroneStatusCard
        :drone-altitude="droneAltitude"
        :drone-battery="droneBattery"
        :drone-speed="droneSpeed"
      />

      <VehicleStatusCard
        :vehicle-location="vehicleLocation"
        :vehicle-speed="vehicleSpeed"
        :vehicle-state="vehicleState"
      />

      <InstructionsCard
        :instruction-card="instructionCard"
        :instructions="instructions"
      />

      <MissionProgressCard
        :mission-steps="missionSteps"
      />
    </div>
  </v-navigation-drawer>
</template>

<script>
  import StatusCard from './panels/StatusCard.vue'
  import DroneStatusCard from './panels/DroneStatusCard1.vue'
  import VehicleStatusCard from './panels/VehicleStatusCard1.vue'
  import InstructionsCard from './panels/InstructionsCard.vue'
  import MissionProgressCard from './panels/MissionProgressCard.vue'

  export default {
    components: {
      StatusCard,
      DroneStatusCard,
      VehicleStatusCard,
      InstructionsCard,
      MissionProgressCard,
    },

    props: {
      distance: {
        type: Number,
        required: true,
      },
      status: {
        type: String,
        required: true,
      },
      statusColor: {
        type: Object,
        required: true,
      },
      droneBattery: {
        type: Number,
        required: true,
      },
      droneAltitude: {
        type: Number,
        required: true,
      },
      droneSpeed: {
        type: Number,
        required: true,
      },
      vehicleSpeed: {
        type: Number,
        required: true,
      },
      vehicleState: {
        type: String,
        required: true,
      },
      vehicleLocation: {
        type: String,
        required: true,
      },
      instructions: {
        type: String,
        required: true,
      },
      instructionCard: {
        type: Object,
        required: true,
      },
      missionSteps: {
        type: Array,
        required: true,
      },
    },
  }
</script>
