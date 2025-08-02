<template>
  <v-card class="mb-2 rounded-lg mx-auto" elevation="10">
    <v-card-title class="d-flex justify-space-between align-center">
      <div class="d-flex align-center">
        <span>Mission History</span>
        <v-btn
          :loading="loading"
          class="ml-2"
          icon="mdi-refresh"
          size="x-small"
          variant="text"
          @click="refreshSurveyLogs"
        />
      </div>
      <v-chip v-if="totalLogs > 0" color="primary" size="small" variant="tonal">
        {{ totalLogs }} Waypoints Surveyed
      </v-chip>
    </v-card-title>

    <v-divider />
    <v-card-text class="pa-0">
      <div ref="scrollContainer" class="timeline-container">
        <v-timeline v-if="surveyLogs.length > 0" density="comfortable" align="start">
          <v-timeline-item
            v-for="(log, index) in surveyLogs"
            :key="log.mission_waypoint_id"
            :dot-color="getGroupDotColor(log)"
            fill-dot
            size="x-small"
          >

            <div class="d-flex justify-space-between align-start">
              <div>
                <div class="font-weight-bold">
                  Waypoint {{ log.mission_waypoint_id }}
                </div>
                <div class="text-caption text-medium-emphasis">
                  Last surveyed: {{ formatDateTime(log.last_surveyed_at) }}
                </div>
              </div>
              <v-menu open-on-hover :location="index % 2 === 0 ? 'end' : 'start'">
                <template #activator="{ props }">
                  <v-chip
                    v-bind="props"
                    :color="getSurveyCountColor(log.survey_count)"
                    class="ml-2"
                    size="small"
                    variant="flat"
                  >
                    Surveyed {{ log.survey_count }}x
                  </v-chip>
                </template>
                <v-card class="pa-2" elevation="8" max-width="350">
                  <v-list-item-title class="font-weight-bold mb-2">
                    Survey Details for Waypoint {{ log.mission_waypoint_id }}
                  </v-list-item-title>
                  <v-divider/>
                  <v-list density="compact">
                    <v-list-item
                      v-for="instance in log.instances"
                      :key="instance.id"
                      class="px-1"
                    >
                      <template #prepend>
                        <v-icon :color="instance.scan_abandoned ? 'error' : 'success'" size="x-small">
                          {{ instance.scan_abandoned ? 'mdi-alert-circle-outline' : 'mdi-check-circle-outline' }}
                        </v-icon>
                      </template>
                      <div class="text-caption ml-2">
                        {{ formatDateTime(instance.completed_at) }}
                        <span v-if="!instance.scan_abandoned && instance.duration_formatted !== 'N/A'">
                          ({{ instance.duration_formatted }})
                        </span>
                      </div>
                    </v-list-item>
                  </v-list>
                </v-card>
              </v-menu>
            </div>
          </v-timeline-item>
        </v-timeline>

        <div v-if="loading" class="text-center pa-4">
          <v-progress-circular color="primary" indeterminate size="24"></v-progress-circular>
        </div>

        <div v-if="!loading && surveyLogs.length === 0" class="text-center pa-8 text-grey">
          <v-icon class="mb-2" size="48">mdi-history</v-icon>
          <div>No survey history found.</div>
          <div class="text-caption">Complete a survey to see it here.</div>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template><script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { API_CONSTANTS } from '@/config/constants.js'

const surveyLogs = ref([])
const loading = ref(false)
const page = ref(1)
const limit = 10
const totalLogs = ref(0)
const hasMore = ref(true)
const scrollContainer = ref(null)

const getGroupDotColor = (log) => {
  const hasAbandoned = log.instances.some(instance => instance.scan_abandoned);
  return hasAbandoned ? 'error' : 'primary';
};


const formatDateTime = (isoString) => {
  if (!isoString) return 'N/A'
  try {
    const date = new Date(isoString)
    return date.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })
  } catch (e) {
    return 'Invalid Date'
  }
}

const getSurveyCountColor = (count) => {
  if (count > 5) return 'error'
  if (count > 2) return 'warning'
  return 'success'
}

const loadSurveyLogs = async () => {
  if (loading.value || !hasMore.value) return

  loading.value = true
  try {
    const response = await fetch(`${API_CONSTANTS.BASE_URL}/survey-logs/?page=${page.value}&limit=${limit}`)
    if (!response.ok) throw new Error('Failed to fetch survey history')

    const data = await response.json()
    if (data.logs && data.logs.length > 0) {
      surveyLogs.value.push(...data.logs)
      page.value++
    } else {
      hasMore.value = false
    }
    totalLogs.value = data.total || 0
  } catch (error) {
    console.error('Error loading survey history:', error)
    hasMore.value = false
  } finally {
    loading.value = false
  }
}


const refreshSurveyLogs = async () => {
  if (loading.value) return;
  console.log('Refreshing survey history...');
  // Reset the state to start from the beginning
  surveyLogs.value = [];
  page.value = 1;
  hasMore.value = true;
  totalLogs.value = 0;
  await loadSurveyLogs();
};


const handleScroll = () => {
  const container = scrollContainer.value
  if (container) {
    const isAtBottom = container.scrollTop + container.clientHeight >= container.scrollHeight - 50
    if (isAtBottom) {
      loadSurveyLogs()
    }
  }
}

onMounted(() => {
  loadSurveyLogs() // Initial load
  scrollContainer.value?.addEventListener('scroll', handleScroll)
})

onUnmounted(() => {
  scrollContainer.value?.removeEventListener('scroll', handleScroll)
})
</script>

<style scoped>
.timeline-container {
  height: 400px;
  overflow-y: auto;
  /* Custom scrollbar for better aesthetics */
  &::-webkit-scrollbar {
    width: 6px;
  }
  &::-webkit-scrollbar-track {
    background: rgba(0, 0, 0, 0.05);
  }
  &::-webkit-scrollbar-thumb {
    background: #aaa;
    border-radius: 3px;
  }
  &::-webkit-scrollbar-thumb:hover {
    background: #888;
  }
}
</style>
