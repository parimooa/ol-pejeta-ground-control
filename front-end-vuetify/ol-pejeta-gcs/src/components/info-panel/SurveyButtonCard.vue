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

      <v-btn
        block
        :color="surveyButtonEnabled ? 'primary' : 'grey'"
        :disabled="!surveyButtonEnabled"
        :loading="surveyInProgress"
        size="large"
        variant="outlined"
        @click="showSurveyDialog = true"
      >
        <v-icon class="mr-2">mdi-target</v-icon>
        {{ surveyInProgress ? 'Survey in Progress...' : 'Survey at This Position' }}
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
            :disabled="surveyInProgress"
            variant="outlined"
            @click="showSurveyDialog = false"
          >
            Skip
          </v-btn>
          <v-spacer />
          <v-btn
            color="primary"
            :loading="surveyInProgress"
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
  import { ref } from 'vue'

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
  const surveyInProgress = ref(false)

  const initiateSurvey = async () => {
    surveyInProgress.value = true
    showSurveyDialog.value = false

    try {
      await emit('initiate-survey')
    } catch (error) {
      console.error('Survey initiation error:', error)
    } finally {
      surveyInProgress.value = false
    }
  }
</script>

<style scoped>
.v-card {
  transition: all 0.3s ease;
}

.v-card:not(.v-card--disabled) {
  cursor: default;
}
</style>
