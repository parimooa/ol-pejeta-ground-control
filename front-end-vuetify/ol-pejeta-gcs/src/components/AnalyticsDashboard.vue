<template>
  <v-container class="analytics-container" fluid>
    <!-- Header and Refresh Button -->
    <v-row align="center" class="mb-4">
      <v-col>
        <h1 class="text-h4 font-weight-bold">Analytics Dashboard</h1>
        <p class="text-medium-emphasis">Real-time system performance and mission analysis</p>
      </v-col>
      <v-col class="text-right">
        <v-btn :loading="loading" color="primary" prepend-icon="mdi-refresh" @click="fetchDashboardData">
          Refresh
        </v-btn>
      </v-col>
    </v-row>

    <!-- Loading and Error States -->
    <v-row v-if="loading" class="py-16" justify="center">
      <v-col class="text-center">
        <v-progress-circular color="primary" indeterminate size="64"></v-progress-circular>
        <p class="mt-4 text-medium-emphasis">Loading analytics data...</p>
      </v-col>
    </v-row>

    <v-alert v-if="error" class="mb-4" prominent type="error">
      {{ error }}
    </v-alert>

    <!-- Main Dashboard Content -->
    <div v-if="!loading && !error && dashboardData">
      <!-- KPI Cards -->
      <v-row>
        <v-col cols="12" sm="6" md="3">
          <v-card class="fill-height" elevation="4">
            <v-card-item>
              <template #prepend>
                <v-icon color="primary" icon="mdi-chart-timeline-variant" size="x-large"></v-icon>
              </template>
              <v-card-title class="text-h5 font-weight-bold">
                {{ dashboardData.coordination_stats_24h.total_events || 0 }}
              </v-card-title>
              <v-card-subtitle>Total Events (24h)</v-card-subtitle>
            </v-card-item>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-card class="fill-height" elevation="4">
            <v-card-item>
              <template #prepend>
                <v-icon color="success" icon="mdi-check-decagram-outline" size="x-large"></v-icon>
              </template>
              <v-card-title class="text-h5 font-weight-bold">
                {{ dashboardData.coordination_stats_24h.survey_success_rate || 0 }}%
              </v-card-title>
              <v-card-subtitle>Survey Success (24h)</v-card-subtitle>
            </v-card-item>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-card class="fill-height" elevation="4">
            <v-card-item>
              <template #prepend>
                <v-icon color="info" icon="mdi-timer-sand" size="x-large"></v-icon>
              </template>
              <v-card-title class="text-h5 font-weight-bold">
                {{ dashboardData.coordination_stats_24h.avg_survey_duration_seconds || 0 }}s
              </v-card-title>
              <v-card-subtitle>Avg. Survey Time (24h)</v-card-subtitle>
            </v-card-item>
          </v-card>
        </v-col>
        <v-col cols="12" sm="6" md="3">
          <v-card class="fill-height" elevation="4">
            <v-card-item>
              <template #prepend>
                <v-icon color="purple" icon="mdi-lan" size="x-large"></v-icon>
              </template>
              <v-card-title class="text-h5 font-weight-bold">
                {{ dashboardData.performance_summary_24h.avg_api_response_time_ms || 0 }}ms
              </v-card-title>
              <v-card-subtitle>Avg. API Response (24h)</v-card-subtitle>
            </v-card-item>
          </v-card>
        </v-col>
      </v-row>

      <!-- Charts and Recent Events -->
      <v-row>
        <!-- Event Breakdown Chart -->
        <v-col cols="12" md="6">
          <v-card class="fill-height" elevation="4">
            <v-card-title>Event Breakdown (Last 10)</v-card-title>
            <v-card-text>
              <Bar v-if="chartData.labels.length > 0" :data="chartData" :options="chartOptions" style="height: 300px"/>
              <div v-else class="d-flex align-center justify-center fill-height text-medium-emphasis"
                   style="height: 300px">
                No event data for chart.
              </div>
            </v-card-text>
          </v-card>
        </v-col>

        <!-- Recent Events Timeline -->
        <v-col cols="12" md="6">
          <v-card class="fill-height" elevation="4">
            <v-card-title>Recent Events</v-card-title>
            <v-card-text>
              <v-timeline v-if="dashboardData.recent_events.length > 0" density="compact" side="end">
                <v-timeline-item
                  v-for="event in dashboardData.recent_events"
                  :key="event.timestamp"
                  :dot-color="getEventColor(event.event_type)"
                  fill-dot
                  size="small"
                >
                  <div class="d-flex justify-space-between align-start">
                    <div class="d-flex align-center">
                      <v-icon :color="getEventColor(event.event_type)" class="mr-3">{{ getEventIcon(event.event_type) }}</v-icon>
                      <div>
                        <div class="font-weight-bold">{{ capitalize(event.event_type.replace(/_/g, ' ')) }}</div>
                        <div class="text-caption">{{ formatDateTime(event.timestamp) }}</div>
                      </div>
                    </div>
                    <div class="text-caption text-right ml-4">
                      <div v-if="event.distance">Dist: {{ event.distance.toFixed(1) }}m</div>
                      <div v-if="event.reason" :class="{ 'mt-1': event.distance }">Reason: {{ event.reason }}</div>
                    </div>
                  </div>
                </v-timeline-item>
              </v-timeline>
              <div v-else class="d-flex align-center justify-center fill-height text-medium-emphasis"
                   style="height: 300px">
                No recent events to display.
              </div>
            </v-card-text>
          </v-card>
        </v-col>
      </v-row>
    </div>
  </v-container>
</template>

<script setup>
import { onMounted, ref, computed } from 'vue';
import { API_CONSTANTS } from '@/config/constants.js';
import { Bar } from 'vue-chartjs';
import { Chart as ChartJS, Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale } from 'chart.js';

ChartJS.register(Title, Tooltip, Legend, BarElement, CategoryScale, LinearScale);

const dashboardData = ref(null);
const loading = ref(false);
const error = ref(null);

const fetchDashboardData = async () => {
  loading.value = true;
  error.value = null;
  try {
    const response = await fetch(`${API_CONSTANTS.BASE_URL}/analytics/dashboard-data`);
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({ detail: response.statusText }));
      throw new Error(errorData.detail || 'Failed to fetch analytics data.');
    }
    dashboardData.value = await response.json();
  } catch (e) {
    console.error('Error fetching dashboard data:', e);
    error.value = e.message;
  } finally {
    loading.value = false;
  }
};

const formatDateTime = (isoString) => {
  if (!isoString) return 'N/A';
  return new Date(isoString).toLocaleString('en-GB', {
    dateStyle: 'medium',
    timeStyle: 'short',
    hour12: false,
  });
};

const getEventColor = (eventType) => {
  if (eventType.includes('complete')) return 'success';
  if (eventType.includes('start')) return 'primary';
  if (eventType.includes('abandon')) return 'warning';
  if (eventType.includes('fault')) return 'error';
  if (eventType.includes('stop')) return 'orange';
  return 'grey';
};

const getEventIcon = (eventType) => {
  if (eventType.includes('complete')) return 'mdi-check-circle-outline';
  if (eventType.includes('start')) return 'mdi-play-circle-outline';
  if (eventType.includes('abandon')) return 'mdi-alert-circle-outline';
  if (eventType.includes('stop')) return 'mdi-stop-circle-outline';
  if (eventType.includes('fault')) return 'mdi-close-circle-outline';
  return 'mdi-information-outline';
};

const capitalize = (value) => {
  if (!value) return '';
  value = value.toString();
  return value.charAt(0).toUpperCase() + value.slice(1);
};

// --- Chart Logic ---
const chartData = computed(() => {
  const data = {
    labels: [],
    datasets: [
      {
        label: 'Event Count',
        backgroundColor: [],
        data: [],
      },
    ],
  };

  if (dashboardData.value?.recent_events) {
    const eventCounts = {};
    for (const event of dashboardData.value.recent_events) {
      const type = capitalize(event.event_type.replace(/_/g, ' '));
      eventCounts[type] = (eventCounts[type] || 0) + 1;
    }

    for (const [label, count] of Object.entries(eventCounts)) {
      data.labels.push(label);
      data.datasets[0].data.push(count);
      data.datasets[0].backgroundColor.push(getEventColor(label.toLowerCase()));
    }
  }
  return data;
});

const chartOptions = {
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: {
      display: false,
    },
  },
  scales: {
    y: {
      beginAtZero: true,
      ticks: {
        stepSize: 1,
      },
    },
  },
};
// --- End Chart Logic ---

onMounted(() => {
  fetchDashboardData();
});
</script>

<style scoped>
.fill-height {
  height: 100%;
}

.analytics-container {
  height: 100%;
  overflow-y: auto;
  padding: 24px;
}
</style>
