<template>
  <v-card class="mb-2 rounded-lg mx-auto" elevation="10">
    <v-card-title class="d-flex justify-space-between align-center">
      <div class="d-flex align-center">
        <span>Mission Progress</span>
        <v-btn
          :loading="loading"
          class="ml-2"
          icon="mdi-refresh"
          size="x-small"
          variant="text"
          @click="refreshSurveyLogs"
        />
      </div>
      <v-chip v-if="surveyedCount > 0" color="primary" size="small" variant="tonal">
        {{ surveyedCount }} / {{ totalWaypoints }} Surveyed
      </v-chip>
    </v-card-title>

    <v-divider />

    <v-card-text class="pa-0">
      <div ref="scrollContainer" class="timeline-container">
        <v-timeline v-if="timelineItems.length > 0">
          <!-- START: Corrected timeline item implementation -->
          <v-timeline-item
            v-for="(item, index) in timelineItems"
            :key="item.seq"
            :dot-color="item.dotColor"
            fill-dot
            size="small"
          >
            <template #icon>
              <span class="text-white font-weight-bold" style="font-size: 0.7rem;">
                {{ item.seq + 1 }}
              </span>
            </template>
            <!-- END: Corrected timeline item implementation -->

            <div class="d-flex justify-space-between align-center" style="min-height: 24px;">
              <!-- This menu will only appear if the waypoint has been surveyed -->
              <v-menu v-if="item.type === 'surveyed'" open-on-hover :location="index % 2 === 0 ? 'end' : 'start'">
                <template #activator="{ props }">
                  <v-chip
                    v-bind="props"
                    color="primary"
                    class="ml-2"
                    size="small"
                    variant="flat"
                  >
                    Surveyed {{ item.surveyData.survey_count }}x
                  </v-chip>
                </template>
                <v-card class="pa-2" elevation="8" max-width="350">
                  <v-list-item-title class="font-weight-bold mb-2">
                    Survey Details for Waypoint {{ item.seq + 1 }}
                  </v-list-item-title>
                  <v-divider/>
                  <v-list density="compact">
                    <v-list-item
                      v-for="instance in item.surveyData.instances"
                      :key="instance.id"
                      class="px-1"
                    >
                      <template #prepend>
                        <v-icon :color="instance.survey_abandoned ? 'error' : 'success'" size="x-small">
                          {{ instance.survey_abandoned ? 'mdi-alert-circle-outline' : 'mdi-check-circle-outline' }}
                        </v-icon>
                      </template>
                      <div class="text-caption ml-2 d-flex align-center flex-wrap">
                        <span>
                          {{ formatDateTime(instance.completed_at) }}
                          <span v-if="!instance.survey_abandoned && instance.duration_formatted !== 'N/A'">
                            ({{ instance.duration_formatted }})
                          </span>
                        </span>
                        <v-chip
                          v-if="instance.waypoint_count > 0"
                          class="ml-2"
                          color="error"
                          size="x-small"
                          variant="tonal"
                        >
                          {{ instance.waypoint_count }} Waypoints
                        </v-chip>
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

        <div v-if="!loading && timelineItems.length === 0" class="text-center pa-8 text-grey">
          <v-icon class="mb-2" size="48">mdi-map-marker-path</v-icon>
          <div>No mission loaded for the car.</div>
        </div>
      </div>
    </v-card-text>
  </v-card>
</template>



<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { API_CONSTANTS } from '@/config/constants.js'

const props = defineProps({
  carWaypoints: {
    type: Object,
    default: () => ({})
  },
})

const surveyLogs = ref([])
const loading = ref(false)
const page = ref(1)
const limit = 10
const totalLogs = ref(0)
const hasMore = ref(true)
const scrollContainer = ref(null)

const formatDateTime = (isoString) => {
  if (!isoString) return 'N/A'
  try {
    const date = new Date(isoString)
    return date.toLocaleString('en-US', { dateStyle: 'medium', timeStyle: 'short' })
  } catch (e) {
    return 'Invalid Date'
  }
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

// --- START: New Computed Properties for Merging Data ---

// Create a map of survey history for efficient lookups
const surveyHistoryMap = computed(() => {
  const map = {};
  for (const log of surveyLogs.value) {
    map[log.mission_waypoint_id] = log;
  }
  return map;
});

// The main computed property that builds the unified timeline
const timelineItems = computed(() => {
  const allWaypoints = props.carWaypoints;
  if (!allWaypoints || Object.keys(allWaypoints).length === 0) {
    return [];
  }

  return Object.values(allWaypoints)
    .sort((a, b) => a.seq - b.seq)
    .map(wp => {
      const waypointId = wp.seq + 1; // Mission waypoints are 1-indexed in survey logs
      const surveyInfo = surveyHistoryMap.value[waypointId];

      if (surveyInfo) {
        // This waypoint has been surveyed. Use the rich survey data.
        const hasAbandoned = surveyInfo.instances.some(inst => inst.survey_abandoned);
        return {
          ...wp,
          type: 'surveyed',
          surveyData: surveyInfo,
          dotColor: hasAbandoned ? 'error' : 'success'
        };
      } else {

        return {
          ...wp,
          type: 'pending',
          dotColor: 'grey-lighten-1'
        };
      }
    });
});

const totalWaypoints = computed(() => timelineItems.value.length);
const surveyedCount = computed(() => {
  return timelineItems.value.filter(item => item.type === 'surveyed').length;
});

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
