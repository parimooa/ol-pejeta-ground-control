<template>
  <v-card
    class="mb-4"
    :color="surveyButtonEnabled ? 'primary' : 'grey-lighten-2'"
    variant="outlined"
  >
    <v-card-title class="text-subtitle-1 font-weight-bold d-flex align-center">
      <v-icon
        class="mr-2"
        :color="surveyButtonEnabled ? 'primary' : 'grey'"
        :icon="surveyButtonEnabled ? 'mdi-map-search' : 'mdi-map-search-outline'"
      />
      Survey Location
    </v-card-title>
    <v-card-text>
      <div class="text-body-2 text-medium-emphasis mb-3">
        {{ surveyButtonEnabled
          ? `Drone is within ${distance}m of vehicle - survey available`
          : `Move closer (${distance}m away, need ≤5m) to enable survey`
        }}
      </div>

      <!-- Start Survey Button -->
      <v-btn
        v-if="!surveyInProgress"
        block
        :color="surveyButtonEnabled ? 'primary' : 'grey'"
        :disabled="!surveyButtonEnabled || isStartingSurvey"
        :loading="isStartingSurvey"
        size="large"
        variant="outlined"
        @click="showSurveyDialog = true"
      >
        <v-icon class="mr-2">mdi-target</v-icon>
        Survey at This Position
      </v-btn>

      <!-- Pause Survey Button -->
      <v-btn
        v-if="surveyInProgress && !isPaused"
        block
        color="warning"
        size="large"
        variant="flat"
        @click="pauseSurvey"
      >
        <v-icon class="mr-2">mdi-pause</v-icon>
        Pause Survey
      </v-btn>

      <!-- Resume Survey Button -->
      <v-btn
        v-if="surveyInProgress && isPaused"
        block
        color="success"
        size="large"
        variant="flat"
        @click="resumeSurvey"
      >
        <v-icon class="mr-2">mdi-play</v-icon>
        Resume Survey
      </v-btn>

    </v-card-text>

    <!-- Survey Confirmation Dialog -->
    <v-dialog
      v-model="showSurveyDialog"
      max-width="450"
      persistent
    >
      <v-card>
        <v-card-title class="text-h6 font-weight-bold">
          <v-icon class="mr-2" color="primary">mdi-map-search</v-icon>
          Survey Confirmation
        </v-card-title>

        <v-card-text>
          <div class="text-body-1 mb-3">
            Do you want to conduct a lawnmower survey pattern at the current vehicle position?
          </div>
          <v-divider class="my-3" />
          <div class="text-body-2 text-medium-emphasis">
            <v-icon class="mr-1" size="small">mdi-information-outline</v-icon>
            The drone will survey in a lawnmower pattern centered on the vehicle's current location,
            staying within 500m distance. Survey will be abandoned if the vehicle moves 500m from ground vehicle.
          </div>
        </v-card-text>

        <v-card-actions class="px-4 pb-4">
          <v-btn
            color="grey"
            :disabled="isStartingSurvey"
            variant="outlined"
            @click="showSurveyDialog = false"
          >
            Skip
          </v-btn>
          <v-spacer />
          <v-btn
            color="primary"
            :loading="isStartingSurvey"
            variant="flat"
            @click="initiateSurvey"
          >
            Yes, Start Survey
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </v-card>
</template>

<script setup>
  import { ref, onMounted, onUnmounted } from 'vue'

  const props = defineProps({
    surveyButtonEnabled: {
      type: Boolean,
      default: false,
    },
    distance: {
      type: Number,
      default: 0,
    },
  })

  const emit = defineEmits(['initiate-survey'])

  const showSurveyDialog = ref(false)
  const isStartingSurvey = ref(false)
  const surveyInProgress = ref(false)
  const isPaused = ref(false)
  let statusPollInterval = null

  const initiateSurvey = async () => {
    isStartingSurvey.value = true
    showSurveyDialog.value = false

    try {
      await emit('initiate-survey')
      // The polling will handle showing the correct button state
      startStatusPolling()
    } catch (error) {
      console.error('Survey initiation error:', error)
    } finally {
      // Hide the loading spinner
      isStartingSurvey.value = false
    }
  }

  const pauseSurvey = async () => {
    try {
      const response = await fetch('/api/survey/pause', { method: 'POST' })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      // The polling will update the UI to show the "Resume" button
    } catch (error) {
      console.error('Error pausing survey:', error)
    }
  }

  const resumeSurvey = async () => {
    try {
      const response = await fetch('/api/survey/resume', { method: 'POST' })
      if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`)
      // The polling will update the UI to show the "Pause" button
    } catch (error) {
      console.error('Error resuming survey:', error)
    }
  }

  const pollSurveyStatus = async () => {
    try {
      // Check both survey service and coordination service status
      const [surveyResponse, coordinationResponse] = await Promise.all([
        fetch('/api/survey/status'),
        fetch('/api/coordination/status')
      ])

      if (!surveyResponse.ok) {
        console.warn(`Survey status poll failed: ${surveyResponse.status}`)
        return
      }
      if (!coordinationResponse.ok) {
        console.warn(`Coordination status poll failed: ${coordinationResponse.status}`)
        return
      }

      const surveyData = await surveyResponse.json()
      const coordinationData = await coordinationResponse.json()

      // Combine status from both services
      surveyInProgress.value = surveyData.survey_in_progress || coordinationData.surveying
      isPaused.value = surveyData.is_paused || coordinationData.survey_paused

      // If the survey is no longer in progress, stop polling
      if (!surveyInProgress.value) {
        stopStatusPolling()
      }

    } catch (error) {
      console.error('Error fetching survey status:', error)
    }
  }

  const startStatusPolling = () => {
    if (!statusPollInterval) {
      pollSurveyStatus() // Poll immediately on start
      statusPollInterval = setInterval(pollSurveyStatus, 2000) // Then every 2 seconds
    }
  }

  const stopStatusPolling = () => {
    if (statusPollInterval) {
      clearInterval(statusPollInterval)
      statusPollInterval = null
    }
  }

  // When the component is mounted, start polling to check if a survey is already in progress
  onMounted(() => {
    startStatusPolling()
  })

  onUnmounted(() => {
    stopStatusPolling()
  })

</script>

<style scoped>
.v-card {
  transition: all 0.3s ease;
}

.v-card:not(.v-card--disabled) {
  cursor: default;
}
</style>
