<template>
  <v-container class="analytics-container" fluid>
    <!-- Header and Refresh Button -->
    <v-row align="center" class="mb-4">
      <v-col>
        <h1 class="text-h4 font-weight-bold">Analytics Dashboard</h1>
        <p class="text-medium-emphasis">Real-time system performance and mission analysis.</p>
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
          <v-icon color="blue-grey-darken-1" icon="mdi-chart-timeline-variant" size="x-large"></v-icon>
        </template>
        <v-card-title class="text-h5 font-weight-bold">
          {{ dashboardData.coordination_stats_24h?.total_events || 0 }}
        </v-card-title>
        <v-card-subtitle>Total Events (24h)</v-card-subtitle>
      </v-card-item>
    </v-card>
  </v-col>
  <v-col cols="12" sm="6" md="3">
    <v-card class="fill-height" elevation="4">
      <v-card-item>
        <template #prepend>
          <v-icon color="teal" icon="mdi-check-decagram-outline" size="x-large"></v-icon>
        </template>
        <v-card-title class="text-h5 font-weight-bold">
          {{ dashboardData.performance_summary_24h?.mission_success_rate || 0 }}%
        </v-card-title>
        <v-card-subtitle>Mission Success (24h)</v-card-subtitle>
      </v-card-item>
    </v-card>
  </v-col>
</v-row>
  <!-- ... other cards ... -->

      <!-- Detailed Analytics -->
      <v-row>
        <!-- Left Column -->
        <v-col cols="12" md="7">
          <v-row>
            <!-- Mission Effectiveness -->
            <v-col v-if="dashboardData.mission_effectiveness_24h" cols="12">
              <v-card class="fill-height" elevation="4">
                <v-card-title>Mission Effectiveness (24h)</v-card-title>
                <v-card-text v-if="!dashboardData.mission_effectiveness_24h.error">
                  <v-list density="compact">
                    <v-list-item title="Total Missions" :subtitle="dashboardData.mission_effectiveness_24h.overall_stats?.total_missions || 0" />
                    <v-list-item title="Avg. Success Rate" :subtitle="`${dashboardData.mission_effectiveness_24h.overall_stats?.avg_success_rate || 0}%`" />
                    <v-list-item title="Total Area Covered" :subtitle="`${dashboardData.mission_effectiveness_24h.overall_stats?.total_area_covered_m2 || 0} m²`" />
                    <v-list-item title="Avg. Mission Duration" :subtitle="`${dashboardData.mission_effectiveness_24h.efficiency_metrics?.avg_mission_duration_minutes || 0} min`" />
                  </v-list>
                </v-card-text>
                <v-card-text v-else class="text-center text-medium-emphasis pa-4">
                  {{ dashboardData.mission_effectiveness_24h.error }}
                </v-card-text>
              </v-card>
            </v-col>
            <!-- Event Breakdown Chart -->
            <v-col cols="12">
              <v-card class="fill-height" elevation="4">
                <v-card-title>Event Breakdown (Last 10)</v-card-title>
                <v-card-text>
                  <Bar v-if="chartData.labels.length > 0" :data="chartData" :options="chartOptions" style="height: 250px"/>
                  <div v-else class="d-flex align-center justify-center fill-height text-medium-emphasis" style="height: 250px">
                    No event data for chart.
                  </div>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>
        </v-col>

        <!-- Right Column -->
        <v-col cols="12" md="5">
          <v-row>
            <!-- START: New Research Data Card -->
            <v-col cols="12">
              <v-card class="fill-height" elevation="4">
                <v-card-title>
                  <v-icon color="indigo-lighten-1" class="mr-2">mdi-database-eye-outline</v-icon>
                  Research Data Collection
                </v-card-title>
                <v-card-text v-if="dashboardData.enhanced_data_summary">
                  <v-list density="compact">
                    <v-list-item
                      title="Vehicle Telemetry Records"
                      :subtitle="dashboardData.enhanced_data_summary.vehicle_telemetry_records"
                    >
                      <template #prepend>
                        <v-icon color="cyan">mdi-car-wireless</v-icon>
                      </template>
                    </v-list-item>
                    <v-list-item
                      title="Mission Effectiveness Records"
                      :subtitle="dashboardData.enhanced_data_summary.mission_effectiveness_records"
                    >
                      <template #prepend>
                        <v-icon color="green">mdi-bullseye-arrow</v-icon>
                      </template>
                    </v-list-item>
                    <v-list-item
                      title="Safety Events Logged"
                      :subtitle="dashboardData.enhanced_data_summary.safety_events_count"
                    >
                      <template #prepend>
                        <v-icon color="orange">mdi-shield-alert-outline</v-icon>
                      </template>
                    </v-list-item>
                  </v-list>
                </v-card-text>
                <v-card-text v-else class="text-center text-medium-emphasis pa-4">
                  No research data summary available.
                </v-card-text>
              </v-card>
            </v-col>
            <!-- END: New Research Data Card -->

            <!-- System Health -->
            <v-col v-if="dashboardData.system_health_24h" cols="12">
              <v-card class="fill-height" elevation="4">
                <v-card-title>System Health (24h)</v-card-title>
                <v-card-text v-if="!dashboardData.system_health_24h.error">
                  <v-list density="compact">
                    <v-list-item v-for="component in dashboardData.system_health_24h.component_health" :key="component.component">
                      <v-list-item-title>{{ capitalize(component.component.replace('_', ' ')) }}</v-list-item-title>
                      <v-list-item-subtitle>
                        <v-chip :color="getHealthColor(component.latest_status)" size="x-small" class="mr-2">{{ component.latest_status }}</v-chip>
                        <span>{{ component.uptime_percent }}% Uptime</span>
                        <span v-if="component.avg_response_time_ms" class="ml-2">({{ component.avg_response_time_ms }}ms)</span>
                      </v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-card-text>
                 <v-card-text v-else class="text-center text-medium-emphasis pa-4">
                  {{ dashboardData.system_health_24h.error }}
                </v-card-text>
              </v-card>
            </v-col>
            <!-- Safety Events -->
            <v-col v-if="dashboardData.safety_summary_24h?.total_safety_events > 0" cols="12">
               <v-card class="fill-height" elevation="4">
                <v-card-title>
                  <v-icon color="warning" class="mr-2">mdi-alert</v-icon>
                  Safety Events (24h)
                </v-card-title>
                <v-card-text>
                   <v-list density="compact">
                    <v-list-item v-for="(event, i) in dashboardData.safety_summary_24h.recent_events" :key="i">
                       <v-list-item-title>{{ event.description }}</v-list-item-title>
                       <v-list-item-subtitle>
                         <v-chip :color="getEventColor(event.severity)" size="x-small" class="mr-2">{{ event.severity }}</v-chip>
                         <span>{{ formatDateTime(event.timestamp) }}</span>
                       </v-list-item-subtitle>
                    </v-list-item>
                  </v-list>
                </v-card-text>
              </v-card>
            </v-col>
            <!-- Recent Events Timeline -->
            <v-col cols="12">
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
                  <div v-else class="d-flex align-center justify-center fill-height text-medium-emphasis" style="height: 300px">
                    No recent events to display.
                  </div>
                </v-card-text>
              </v-card>
            </v-col>
          </v-row>
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

// START: New helper function for robust number formatting
const formatDistanceKm = (meters) => {
  if (meters === null || typeof meters === 'undefined') {
    return '0.0';
  }
  return (meters / 1000).toFixed(1);
};
// END: New helper function

const eventColorMap = {
  complete: 'teal',
  start: 'blue',
  abandon: 'amber-darken-2',
  stop: 'orange-darken-2',
  fault: 'red-darken-2',
  follow: 'deep-purple-lighten-1',
  coordination: 'cyan-darken-1',
  // For safety events
  critical: 'red-darken-4',
  high: 'red-darken-1',
  medium: 'orange-darken-1',
  low: 'amber',
  // For health status
  online: 'success',
  offline: 'grey',
  error: 'error',
  default: 'grey-darken-1'
};

const getEventColor = (eventType) => {
  const lowerType = eventType.toLowerCase();
  for (const key in eventColorMap) {
    if (lowerType.includes(key)) {
      return eventColorMap[key];
    }
  }
  return eventColorMap.default;
};

const getHealthColor = (status) => {
  const lowerStatus = status.toLowerCase();
  return eventColorMap[lowerStatus] || eventColorMap.default;
}

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
        borderRadius: 4,
      },
    ],
  };

  if (dashboardData.value?.recent_events) {
    const eventCounts = {};
    const recentEvents = [...dashboardData.value.recent_events].reverse();
    for (const event of recentEvents) {
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
