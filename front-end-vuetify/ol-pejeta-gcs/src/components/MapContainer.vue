<template>
  <div class="map-container">
    <div ref="mapElement" class="map"/>

    <div class="map-controls">
      <!-- Map Type Toggle -->
      <div class="map-type-toggle pa-2">
        <div class="toggle-wrapper">
          <v-btn-toggle
            v-model="mapType"
            color="primary"
            mandatory
            variant="outlined"
            @update:model-value="switchMapType"
          >
            <v-btn size="small" value="osm">
              <v-icon>mdi-map</v-icon>
              <span class="ml-1">Map</span>
            </v-btn>
            <v-btn size="small" value="satellite">
              <v-icon>mdi-satellite-variant</v-icon>
              <span class="ml-1">Satellite</span>
            </v-btn>
            <v-btn size="small" value="hybrid">
              <v-icon>mdi-layers</v-icon>
              <span class="ml-1">Hybrid</span>
            </v-btn>
          </v-btn-toggle>
        </div>
      </div>

      <!-- Follow Controls -->
      <div class="follow-controls pa-2">
        <div class="toggle-wrapper">
          <v-btn-toggle
            v-model="followVehicle"
            color="purple"
            variant="outlined"
          >
            <v-btn :value="true" size="small">
              <v-icon>mdi-car-connected</v-icon>
              <span class="ml-1">Follow Vehicle</span>
            </v-btn>
          </v-btn-toggle>
        </div>
        <div class="toggle-wrapper ml-2">
          <v-btn-toggle
            v-model="followDrone"
            color="primary"
            variant="outlined"
          >
            <v-btn :value="true" size="small">
              <v-icon>mdi-quadcopter</v-icon>
              <span class="ml-1">Follow Drone</span>
            </v-btn>
          </v-btn-toggle>
        </div>
      </div>

      <div class="coordination-controls pa-2">
        <div class="d-flex gap-2">
          <div class="toggle-wrapper">
            <v-btn
              :disabled="props.isCoordinationActive || coordinationLoading"
              :loading="coordinationLoading && !props.isCoordinationActive"
              color="success"
              size="small"
              variant="outlined"
              @click="startCoordination"
            >
              <v-icon>mdi-play</v-icon>
              <span class="ml-1">Start Coordination</span>
            </v-btn>
          </div>

          <div class="toggle-wrapper">
            <v-btn
              :disabled="!props.isCoordinationActive || coordinationLoading"
              :loading="coordinationLoading && props.isCoordinationActive"
              color="error"
              size="small"
              variant="outlined"
              @click="showStopConfirmation = true"
            >
              <v-icon>mdi-stop</v-icon>
              <span class="ml-1">Stop Coordination</span>
            </v-btn>
          </div>
        </div>
      </div>

      <!-- Stop Coordination Confirmation Dialog -->
      <v-dialog v-model="showStopConfirmation" max-width="400" persistent>
        <v-card>
          <v-card-title class="text-h6 font-weight-bold">
            <v-icon class="mr-2" color="warning">mdi-alert</v-icon>
            Confirm Stop Coordination
          </v-card-title>

          <v-card-text>
            <p class="text-body-1">
              Are you sure you want to stop the coordination service? This will:
            </p>
            <ul class="text-body-2 mt-2">
              <li>Stop autonomous vehicle following</li>
              <li>Disable proximity survey features</li>
              <li>Return control to manual mode</li>
            </ul>
          </v-card-text>

          <v-card-actions class="px-4 pb-4">
            <v-spacer/>
            <v-btn
              :disabled="coordinationLoading"
              color="primary"
              variant="outlined"
              @click="showStopConfirmation = false"
            >
              Cancel
            </v-btn>
            <v-btn
              :loading="coordinationLoading"
              color="error"
              @click="stopCoordination"
            >
              Stop Coordination
            </v-btn>
          </v-card-actions>
        </v-card>
      </v-dialog>


      <!-- Offline Map Controls -->
      <div class="offline-controls pa-2">
        <div class="toggle-wrapper">
          <v-btn
            :color="isDeviceOffline ? 'warning' : 'info'"
            :disabled="isDownloading"
            prepend-icon="mdi-map-marker-path"
            size="small"
            variant="outlined"
            @click="showOfflineDialog = true"
          >
            <v-icon v-if="isDeviceOffline" class="mr-1">mdi-wifi-off</v-icon>
            <span>{{ isDeviceOffline ? 'Offline Maps' : 'Download Maps' }}</span>
          </v-btn>
        </div>
      </div>
    </div>

    <!-- Compass Indicator - Left Side -->
    <div class="compass-indicator">
      <CompassIndicator
        :vehicle-telemetry-data="vehicleTelemetryData"
        :drone-telemetry-data="droneTelemetryData"
        :is-vehicle-connected="isVehicleConnected"
        :is-drone-connected="isDroneConnected"
      />
    </div>

    <!-- Offline Map Dialog -->
    <v-dialog v-model="showOfflineDialog" max-width="600" persistent>
      <v-card>
        <v-card-title class="text-h6 font-weight-bold">
          <v-icon class="mr-2" color="primary">mdi-map-marker-path</v-icon>
          Offline Maps for Ol Pejeta Conservancy
        </v-card-title>

        <v-card-text>
          <div v-if="isDeviceOffline" class="mb-4 pa-2 warning-bg rounded">
            <v-icon class="mr-2" color="warning">mdi-wifi-off</v-icon>
            <span class="font-weight-bold">You are currently offline.</span>
            Using cached map tiles for Ol Pejeta Conservancy.
          </div>

          <p class="text-body-1 mb-4">
            Download map tiles for the Ol Pejeta Conservancy area to use when offline.
            Maps will be centered on the current view position.
          </p>

          <v-slider
            v-model="offlineAreaRadius"
            :disabled="isDownloading"
            :max="10"
            :min="1"
            :step="1"
            hint="Larger radius requires more storage"
            label="Download Area Radius"
            persistent-hint
            thumb-label
          >
            <template #append>
              <span class="text-body-2">{{ offlineAreaRadius }}km</span>
            </template>
          </v-slider>

          <v-divider class="my-4"/>

          <!-- Standard Map -->
          <div class="d-flex align-center justify-space-between mb-4">
            <div>
              <div class="text-subtitle-1 font-weight-bold">
                <v-icon class="mr-1">mdi-map</v-icon>
                Standard Map
              </div>
              <div class="text-caption text-medium-emphasis">
                {{ offlineTileCounts.osm }} tiles stored
              </div>
            </div>

            <div class="d-flex">
              <v-btn
                :disabled="isDownloading || offlineTileCounts.osm === 0"
                class="mr-2"
                color="error"
                size="small"
                variant="outlined"
                @click="clearOfflineMapTiles('osm')"
              >
                <v-icon size="small">mdi-delete</v-icon>
              </v-btn>

              <v-btn
                :disabled="isDownloading && downloadingMapType !== 'osm'"
                :loading="isDownloading && downloadingMapType === 'osm'"
                color="primary"
                size="small"
                @click="downloadOfflineMapTiles('osm')"
              >
                <v-icon class="mr-1" size="small">mdi-download</v-icon>
                Download
              </v-btn>
            </div>
          </div>

          <v-progress-linear
            v-if="isDownloading && downloadingMapType === 'osm'"
            :model-value="downloadProgress.osm.percentage"
            color="primary"
            height="8"
            rounded
            striped
          >
            <template #default>
              {{ downloadProgress.osm.current }} / {{ downloadProgress.osm.total }} tiles
            </template>
          </v-progress-linear>

          <!-- Satellite Map -->
          <div class="d-flex align-center justify-space-between mb-4 mt-4">
            <div>
              <div class="text-subtitle-1 font-weight-bold">
                <v-icon class="mr-1">mdi-satellite-variant</v-icon>
                Satellite Map
              </div>
              <div class="text-caption text-medium-emphasis">
                {{ offlineTileCounts.satellite }} tiles stored
              </div>
            </div>

            <div class="d-flex">
              <v-btn
                :disabled="isDownloading || offlineTileCounts.satellite === 0"
                class="mr-2"
                color="error"
                size="small"
                variant="outlined"
                @click="clearOfflineMapTiles('satellite')"
              >
                <v-icon size="small">mdi-delete</v-icon>
              </v-btn>

              <v-btn
                :disabled="isDownloading && downloadingMapType !== 'satellite'"
                :loading="isDownloading && downloadingMapType === 'satellite'"
                color="primary"
                size="small"
                @click="downloadOfflineMapTiles('satellite')"
              >
                <v-icon class="mr-1" size="small">mdi-download</v-icon>
                Download
              </v-btn>
            </div>
          </div>

          <v-progress-linear
            v-if="isDownloading && downloadingMapType === 'satellite'"
            :model-value="downloadProgress.satellite.percentage"
            color="primary"
            height="8"
            rounded
            striped
          >
            <template #default>
              {{ downloadProgress.satellite.current }} / {{ downloadProgress.satellite.total }} tiles
            </template>
          </v-progress-linear>

          <!-- Hybrid Map -->
          <div class="d-flex align-center justify-space-between mb-4 mt-4">
            <div>
              <div class="text-subtitle-1 font-weight-bold">
                <v-icon class="mr-1">mdi-layers</v-icon>
                Hybrid Map
              </div>
              <div class="text-caption text-medium-emphasis">
                {{ offlineTileCounts.hybrid }} tiles stored
              </div>
            </div>

            <div class="d-flex">
              <v-btn
                :disabled="isDownloading || offlineTileCounts.hybrid === 0"
                class="mr-2"
                color="error"
                size="small"
                variant="outlined"
                @click="clearOfflineMapTiles('hybrid')"
              >
                <v-icon size="small">mdi-delete</v-icon>
              </v-btn>

              <v-btn
                :disabled="isDownloading && downloadingMapType !== 'hybrid'"
                :loading="isDownloading && downloadingMapType === 'hybrid'"
                color="primary"
                size="small"
                @click="downloadOfflineMapTiles('hybrid')"
              >
                <v-icon class="mr-1" size="small">mdi-download</v-icon>
                Download
              </v-btn>
            </div>
          </div>

          <v-progress-linear
            v-if="isDownloading && downloadingMapType === 'hybrid'"
            :model-value="downloadProgress.hybrid.percentage"
            color="primary"
            height="8"
            rounded
            striped
          >
            <template #default>
              {{ downloadProgress.hybrid.current }} / {{ downloadProgress.hybrid.total }} tiles
            </template>
          </v-progress-linear>

          <v-alert
            v-if="isDeviceOffline"
            class="mt-4"
            density="compact"
            type="warning"
            variant="tonal"
          >
            <div class="text-body-2">
              <strong>Note:</strong> You cannot download new map tiles while offline.
              Connect to the internet to download additional map tiles.
            </div>
          </v-alert>
        </v-card-text>

        <v-card-actions class="px-4 pb-4">
          <v-spacer/>
          <v-btn
            :disabled="isDownloading"
            color="primary"
            variant="outlined"
            @click="showOfflineDialog = false"
          >
            Close
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import {computed, onMounted, onUnmounted, ref, watch} from 'vue'
import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import {fromLonLat, toLonLat} from 'ol/proj'
import Feature from 'ol/Feature'
import Point from 'ol/geom/Point'
import LineString from 'ol/geom/LineString'
import Polygon from 'ol/geom/Polygon'
import Circle from 'ol/geom/Circle'
import {Vector as VectorLayer} from 'ol/layer'
import {Vector as VectorSource} from 'ol/source'
import {Circle as CircleStyle, Fill, Icon, Stroke, Style, Text} from 'ol/style'
import * as ol from 'ol/extent'

import droneIcon from '@/assets/drone.png'
import vehicleIcon from '@/assets/car_top_view.png'
import CompassIndicator from '@/components/CompassIndicator.vue'
import {
  API_CONSTANTS,
  TIMING_CONSTANTS,
  SURVEY_CONSTANTS,
  PHYSICAL_CONSTANTS,
  MAP_CONSTANTS
} from '@/config/constants.js'

// Import offline map utilities
import {
  addConnectivityListeners,
  clearTiles,
  countTiles,
  createOfflineOSMSource,
  createOfflineXYZSource,
  downloadMapTiles,
  isOffline,
  removeConnectivityListeners,
} from '@/utils/OfflineMapUtils'

// Import survey file utilities
import {
  findClosestWaypoint,
  loadSurveysFromFiles,
  saveSurveyToFile,
} from '@/utils/SurveyFileUtils'

const props = defineProps({
  distance: {
    type: Number,
    required: true,
  },
  droneTelemetryData: {
    type: Object,
    default: null,
  },
  vehicleTelemetryData: {
    type: Object,
    default: null,
  },
  isDroneConnected: {
    type: Boolean,
    default: false,
  },
  isVehicleConnected: {
    type: Boolean,
    default: false,
  },
  isCoordinationActive: {
    type: Boolean,
    default: false,
  },
  isDroneFollowing: {
    type: Boolean,
    default: false,
  },
  vehicleWaypoints: {
    type: Object,
    default: () => ({}),
  },
  droneMissionWaypoints: {
    type: Array,
    default: () => [],
  },
  surveyComplete: {
    type: Boolean,
    default: false,
  },
  isDroneSurveying: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits([
  'update:current-position',
  'update:drone-position',
  'update:vehicle-position',
  'coordination-status',

])

const mapElement = ref(null)
let map = null

// Map layers
let osmLayer = null
let satelliteLayer = null
let hybridLabelsLayer = null

// Features
let droneFeature = null
let vehicleFeature = null
let safetyRadiusFeature = null
let distanceLineFeature = null
let distanceLabelFeature = null
let vectorSource = null
let vectorLayer = null

// Waypoint layers
let waypointSource = null
let waypointLayer = null
let routeSource = null
let routeLayer = null

// Survey layers
let surveyGridSource = null
let surveyGridLayer = null
let completedSurveySource = null
let completedSurveyLayer = null

// Waypoint state
let hasAutoFittedWaypoints = false

// State variables
const currentPosition = ref({lat: 0.0078, lng: 36.9759})
const dronePosition = ref({x: 0, y: 0})
const vehiclePosition = ref({x: 0, y: 0})
const coordinationLoading = ref(false)

const manualControl = ref(true)
const mapType = ref('osm')
const followVehicle = ref(true)
const followDrone = ref(false)

// Offline map state
const isDeviceOffline = ref(isOffline())
const showOfflineDialog = ref(false)
const downloadProgress = ref({
  osm: {current: 0, total: 0, percentage: 0},
  satellite: {current: 0, total: 0, percentage: 0},
  hybrid: {current: 0, total: 0, percentage: 0},
})
const isDownloading = ref(false)
const downloadingMapType = ref('')
const offlineTileCounts = ref({
  osm: 0,
  satellite: 0,
  hybrid: 0,
})
const offlineAreaRadius = ref(5) // 5km radius by default

// Following system variables
let lastFollowUpdate = 0
const followUpdateThrottle = TIMING_CONSTANTS.FOLLOW_UPDATE_THROTTLE
let isUserInteracting = false

// Helper computed properties
const dronePositionAvailable = computed(() => {
  return props.isDroneConnected &&
    props.droneTelemetryData?.position?.latitude !== null &&
    props.droneTelemetryData?.position?.longitude !== null
})

const vehiclePositionAvailable = computed(() => {
  return props.isVehicleConnected &&
    props.vehicleTelemetryData?.position?.latitude !== null &&
    props.vehicleTelemetryData?.position?.longitude !== null
})

const isManualControlEnabled = computed(() => {
  return manualControl.value && !props.isDroneConnected && !props.isVehicleConnected
})

const showStopConfirmation = ref(false)

const startCoordination = async () => {
  coordinationLoading.value = true

  try {
    const response = await fetch(`${API_CONSTANTS.BASE_URL}/coordination/start`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error(`Failed to start coordination: ${response.status} ${response.statusText}`)
    }

    const data = await response.json()

    if (data.status === 'success') {
      // Emit success event to parent component for snackbar
      emit('coordination-status', {
        type: 'success',
        message: 'Coordination service started successfully',
      })
    } else {
      throw new Error(data.message || 'Failed to start coordination service')
    }

  } catch (error) {
    console.error('Coordination start error:', error)

    // Emit error event to parent component for snackbar
    emit('coordination-status', {
      type: 'error',
      message: `Unable to start coordination: ${error.message.includes('fetch') ? 'Backend service unavailable' : error.message}`,
    })
  } finally {
    coordinationLoading.value = false
  }
}


const stopCoordination = async () => {
  if (coordinationLoading.value) return

  coordinationLoading.value = true
  showStopConfirmation.value = false

  try {
    const response = await fetch(`${API_CONSTANTS.BASE_URL}/coordination/stop`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
    })

    const data = await validateApiResponse(response)
    console.log('Coordination stopped:', data.message)

  } catch (error) {
    console.error('Failed to stop coordination:', error.message)
  } finally {
    coordinationLoading.value = false
  }
}

// Function to fetch drone mission waypoints from REST endpoint
const fetchDroneMissionWaypoints = async (vehicleType = 'drone') => {
  try {
    const response = await fetch(`${API_CONSTANTS.BASE_URL}/vehicles/${vehicleType}/mission/waypoints`, {
      method: 'GET',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error(`Failed to fetch mission waypoints: ${response.statusText}`)
    }

    const data = await response.json()
    console.log(`Fetched ${data.total_waypoints} mission waypoints for ${vehicleType}`)
    return data.mission_waypoints || []
  } catch (error) {
    console.error('Error fetching drone mission waypoints:', error)
    return []
  }
}

// Function to find the closest mission waypoint to vehicle position
const findClosestMissionWaypoint = (missionWaypoints, vehiclePosition) => {
  if (!missionWaypoints || missionWaypoints.length === 0 || !vehiclePosition) {
    return null
  }

  let closestWaypoint = missionWaypoints[0]
  let shortestDistance = calculateDistance(
    vehiclePosition.lat, vehiclePosition.lon,
    closestWaypoint.lat, closestWaypoint.lon
  )

  for (const waypoint of missionWaypoints) {
    const distance = calculateDistance(
      vehiclePosition.lat, vehiclePosition.lon,
      waypoint.lat, waypoint.lon
    )

    if (distance < shortestDistance) {
      shortestDistance = distance
      closestWaypoint = waypoint
    }
  }

  return closestWaypoint.seq || closestWaypoint.id || 1
}

// Haversine distance calculation for mission waypoints
const calculateDistance = (lat1, lon1, lat2, lon2) => {
  const R = PHYSICAL_CONSTANTS.EARTH_RADIUS_METERS
  const toRad = value => (value * Math.PI) / 180

  const dLat = toRad(lat2 - lat1)
  const dLon = toRad(lon2 - lon1)
  const lat1Rad = toRad(lat1)
  const lat2Rad = toRad(lat2)

  const a =
    Math.sin(dLat / 2) * Math.sin(dLat / 2) +
    Math.sin(dLon / 2) * Math.sin(dLon / 2) * Math.cos(lat1Rad) * Math.cos(lat2Rad)
  const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a))
  return R * c
}

// Function to clear mission waypoints from vehicle after survey completion
const clearDroneMission = async (vehicleType = 'drone') => {
  try {
    const response = await fetch(`${API_CONSTANTS.BASE_URL}/vehicles/${vehicleType}/mission/clear`, {
      method: 'POST',
      headers: {
        'Accept': 'application/json',
        'Content-Type': 'application/json',
      },
    })

    if (!response.ok) {
      throw new Error(`Failed to clear mission: ${response.statusText}`)
    }

    const data = await response.json()
    console.log(`Mission cleared successfully for ${vehicleType}:`, data.message)
    return true
  } catch (error) {
    console.error('Error clearing drone mission:', error)
    return false
  }
}

const validateApiResponse = async response => {
  const data = await response.json()

  if (!response.ok) {
    throw new Error(data.message || 'Request failed')
  }

  if (data.status !== 'success') {
    throw new Error(data.message || 'Operation failed')
  }

  return data
}


// Offline map functions
const updateOfflineTileCounts = async () => {
  try {
    const [osmCount, satelliteCount, hybridCount] = await Promise.all([
      countTiles('osm'),
      countTiles('satellite'),
      countTiles('hybrid'),
    ])

    offlineTileCounts.value = {
      osm: osmCount,
      satellite: satelliteCount,
      hybrid: hybridCount,
    }
  } catch (error) {
    console.error('Error counting offline tiles:', error)
  }
}

const downloadOfflineMapTiles = async type => {
  if (isDownloading.value) return
  isDownloading.value = true
  downloadingMapType.value = type
  downloadProgress.value[type] = {current: 0, total: 0, percentage: 0}

  try {
    const view = map.getView()
    const center = toLonLat(view.getCenter())
    await downloadMapTiles({
      mapType: type,
      center,
      radius: offlineAreaRadius.value,
      progressCallback: (current, total) => {
        downloadProgress.value[type] = {
          current,
          total,
          percentage: Math.round((current / total) * 100),
        }
      },
    })
    await updateOfflineTileCounts()
  } catch (error) {
    console.error(`Error downloading ${type} map tiles:`, error)
  } finally {
    isDownloading.value = false
    downloadingMapType.value = ''
  }
}

const clearOfflineMapTiles = async type => {
  try {
    await clearTiles(type)
    await updateOfflineTileCounts()
  } catch (error) {
    console.error(`Error clearing ${type} map tiles:`, error)
  }
}

const handleOnlineStatus = () => isDeviceOffline.value = false
const handleOfflineStatus = () => isDeviceOffline.value = true

// Map utility functions
const switchMapType = newType => {
  if (!map) return
  osmLayer.setVisible(newType === 'osm')
  satelliteLayer.setVisible(newType === 'satellite' || newType === 'hybrid')
  hybridLabelsLayer.setVisible(newType === 'hybrid')
}

const gpsToMapCoordinates = (lat, lng) => fromLonLat([lng, lat])

// Improved following functions
const centerMapOnVehicle = coordinates => {
  if (!map || !followVehicle.value || isUserInteracting) return
  const now = Date.now()
  if (now - lastFollowUpdate < followUpdateThrottle) return
  lastFollowUpdate = now
  map.getView().setCenter(coordinates)
}

const centerMapOnDrone = coordinates => {
  if (!map || !followDrone.value || isUserInteracting) return
  const now = Date.now()
  if (now - lastFollowUpdate < followUpdateThrottle) return
  lastFollowUpdate = now
  map.getView().setCenter(coordinates)
}

// Telemetry update functions
const updateDroneFromTelemetry = () => {
  if (!dronePositionAvailable.value || !droneFeature) return

  const {latitude, longitude} = props.droneTelemetryData.position
  const mapCoords = gpsToMapCoordinates(latitude, longitude)
  dronePosition.value = {x: mapCoords[0], y: mapCoords[1]}

  if (followDrone.value && !isUserInteracting) {
    centerMapOnDrone(mapCoords)
  }
  updateMapFeatures()
  emit('update:drone-position', {lat: latitude, lon: longitude})
}

const updateVehicleFromTelemetry = () => {
  if (!vehiclePositionAvailable.value || !vehicleFeature) return

  const {latitude, longitude} = props.vehicleTelemetryData.position
  const heading = props.vehicleTelemetryData.velocity.heading
  const mapCoords = gpsToMapCoordinates(latitude, longitude)
  vehiclePosition.value = {x: mapCoords[0], y: mapCoords[1]}
  vehicleFeature.getGeometry().setCoordinates(mapCoords)

  if (heading !== undefined && heading !== null) {
    const style = vehicleFeature.getStyle()
    const image = style.getImage()
    // Convert heading (degrees, 0 is North) to rotation in radians
    const rotation = heading * (Math.PI / 180)
    image.setRotation(rotation)
  }

  if (followVehicle.value && !isUserInteracting) {
    centerMapOnVehicle(mapCoords)
  }
  updateMapFeatures()
  emit('update:vehicle-position', {lat: latitude, lon: longitude})
}

const updateMapFeatures = () => {
  if (!map || !vectorSource) return

  droneFeature.getGeometry().setCoordinates([dronePosition.value.x, dronePosition.value.y])
  safetyRadiusFeature.getGeometry().setCenter([vehiclePosition.value.x, vehiclePosition.value.y])
  distanceLineFeature.getGeometry().setCoordinates([
    [dronePosition.value.x, dronePosition.value.y],
    [vehiclePosition.value.x, vehiclePosition.value.y],
  ])

  const midPoint = [
    (dronePosition.value.x + vehiclePosition.value.x) / 2,
    (dronePosition.value.y + vehiclePosition.value.y) / 2,
  ]
  distanceLabelFeature.getGeometry().setCoordinates(midPoint)
  distanceLabelFeature.getStyle().getText().setText(props.distance + 'm')

  vectorSource.changed()
}

// Waypoint functions
const updateWaypointsOnMap = waypointsObj => {
  if (!waypointSource || !routeSource) return

  waypointSource.clear()
  routeSource.clear()

  const waypointsArray = Object.values(waypointsObj).sort((a, b) => a.seq - b.seq)
  if (waypointsArray.length === 0) {
    hasAutoFittedWaypoints = false
    return
  }

  const coordinates = []
  waypointsArray.forEach(waypoint => {
    const coord = fromLonLat([waypoint.lon, waypoint.lat])
    coordinates.push(coord)

    const feature = new Feature({geometry: new Point(coord), waypoint})
    feature.setStyle(new Style({
      image: new CircleStyle({
        radius: 15,
        fill: new Fill({color: '#ff6b35'}),
        stroke: new Stroke({color: 'white', width: 2}),
      }),
      text: new Text({
        text: (waypoint.seq + 1).toString(),
        font: 'bold 12px Arial',
        fill: new Fill({color: 'white'}),
      }),
    }))
    waypointSource.addFeature(feature)
  })

  if (coordinates.length > 1) {
    const routeFeature = new Feature({geometry: new LineString(coordinates)})
    routeFeature.setStyle(new Style({
      stroke: new Stroke({color: '#ff6b35', width: 3, lineDash: [5, 5]}),
    }))
    routeSource.addFeature(routeFeature)

    if (!hasAutoFittedWaypoints) {
      const extent = routeSource.getExtent()
      if (extent && !ol.isEmpty(extent)) {
        map.getView().fit(extent, {padding: [50, 50, 50, 50], duration: TIMING_CONSTANTS.MAP_FIT_DURATION})
        hasAutoFittedWaypoints = true
      }
    }
  }
}

const clearWaypoints = () => {
  if (waypointSource) waypointSource.clear()
  if (routeSource) routeSource.clear()
  hasAutoFittedWaypoints = false
}

// Survey utility functions - Mission Planner style lawnmower pattern
const generateLawnmowerGrid = waypoints => {
  if (!waypoints || waypoints.length < 3) return []

  const sortedWaypoints = [...waypoints].sort((a, b) => a.seq - b.seq)
  const lats = sortedWaypoints.map(wp => wp.lat)
  const lons = sortedWaypoints.map(wp => wp.lon)

  const minLat = Math.min(...lats)
  const maxLat = Math.max(...lats)
  const minLon = Math.min(...lons)
  const maxLon = Math.max(...lons)

  const latRange = maxLat - minLat
  const lonRange = maxLon - minLon

  // Calculate appropriate spacing based on survey area size
  const estimatedAreaSize = Math.max(latRange * 111320, lonRange * 111320 * Math.cos(minLat * Math.PI / 180))
  const spacing = estimatedAreaSize < SURVEY_CONSTANTS.AREA_SIZE_THRESHOLD ? SURVEY_CONSTANTS.GRID_SPACING_SMALL : SURVEY_CONSTANTS.GRID_SPACING_LARGE
  const latSpacing = spacing / 111320 // Convert spacing from meters to degrees

  const gridLines = []
  let currentLat = minLat
  let lineCount = 0

  // Generate horizontal lawnmower pattern lines
  while (currentLat <= maxLat && lineCount < SURVEY_CONSTANTS.MAX_SURVEY_LINES) {
    const lineCoords = [
      fromLonLat([minLon, currentLat]),
      fromLonLat([maxLon, currentLat]),
    ]

    const gridFeature = new Feature({
      geometry: new LineString(lineCoords),
    })

    // Apply style directly to each feature to ensure visibility
    gridFeature.setStyle(new Style({
      stroke: new Stroke({
        color: '#2196F3',
        width: 4,
        lineDash: [10, 5],
      }),
    }))

    gridLines.push(gridFeature)
    currentLat += latSpacing
    lineCount++
  }

  return gridLines
}

const saveSurveyedArea = async (waypoints, vehicleId) => {
  try {
    const timestamp = new Date()
    const surveyId = `survey_${vehicleId || 'unknown'}_${timestamp.getTime()}`

    // Get current vehicle position for closest waypoint calculation
    const vehiclePosition = props.vehicleTelemetryData?.position
    const closestWaypointNum = vehiclePosition
      ? findClosestWaypoint(waypoints, vehiclePosition)
      : 1

    // Fetch mission waypoints to determine mission_waypoint_id
    const missionWaypoints = await fetchDroneMissionWaypoints('drone')
    const missionWaypointId = findClosestMissionWaypoint(missionWaypoints, vehiclePosition) || closestWaypointNum
    const surveyData = {
      id: surveyId,
      waypoints: waypoints.map(wp => ({lat: wp.lat, lon: wp.lon, seq: wp.seq})),
      vehicleId: String(vehicleId) || 'unknown',
      completedAt: timestamp.toISOString(),
      siteName,
      closestWaypoint: closestWaypointNum,
      mission_waypoint_id: missionWaypointId,
    }

    // Save to JSON file
    try {
      await saveSurveyToFile(surveyData, filename)
      console.log(`Survey saved to file: ${filename}`)
    } catch (fileError) {
      console.error('Failed to save survey file:', fileError)
      throw fileError
    }

  } catch (error) {
    console.error('Error saving survey area:', error)
  }
}


const displaySurveyGrid = waypoints => {
  if (!surveyGridSource || !waypoints || waypoints.length < 3) return

  surveyGridSource.clear()
  const gridFeatures = generateLawnmowerGrid(waypoints)

  if (gridFeatures.length > 0) {
    surveyGridSource.addFeatures(gridFeatures)
  }
}

const displayCompletedSurvey = waypoints => {
  if (!completedSurveySource || !waypoints || waypoints.length < 3) return

  // Filter out invalid waypoints
  const validWaypoints = waypoints.filter(wp =>
    wp && wp.lat != null && wp.lon != null &&
    !isNaN(wp.lat) && !isNaN(wp.lon) &&
    Math.abs(wp.lat) <= 90 && Math.abs(wp.lon) <= 180 &&
    wp.seq !== 0  // Exclude home position since it causes polygon to start with the actual home
  )

  if (validWaypoints.length < 3) {
    console.warn('Not enough valid waypoints to form survey polygon (excluding home position)')
    return
  }

  // Sort waypoints by sequence if available
  const sortedWaypoints = validWaypoints.sort((a, b) => (a.seq || 0) - (b.seq || 0));

  // Create boundary coordinates for polygon (rectangular boundary)
  const lats = sortedWaypoints.map(wp => wp.lat);
  const lons = sortedWaypoints.map(wp => wp.lon);

  const minLat = Math.min(...lats);
  const maxLat = Math.max(...lats);
  const minLon = Math.min(...lons);
  const maxLon = Math.max(...lons);

  const boundaryPoints = [
    [minLon, minLat],
    [maxLon, minLat],
    [maxLon, maxLat],
    [minLon, maxLat],
    [minLon, minLat]  // Close the polygon
  ];

  // Convert boundary coordinates to map projection
  const boundaryCoords = boundaryPoints.map(coord => fromLonLat(coord));

  // Create the survey polygon feature
  const surveyPolygon = new Feature({
    geometry: new Polygon([boundaryCoords]),
    type: 'survey_boundary'
  });

  // Create flight path connecting waypoints in sequence
  const waypointCoords = sortedWaypoints.map(wp => {
    const coord = fromLonLat([wp.lon, wp.lat]);
    if (!isFinite(coord[0]) || !isFinite(coord[1])) {
      console.warn(`Invalid coordinate conversion for waypoint: ${wp.lat}, ${wp.lon}`);
      return null;
    }
    return coord;
  }).filter(coord => coord !== null);

  if (waypointCoords.length >= 2) {
    const flightPath = new Feature({
      geometry: new LineString(waypointCoords),
      type: 'flight_path'
    });
    completedSurveySource.addFeature(flightPath);
  }

  // Create individual waypoint features
  const waypointFeatures = sortedWaypoints.map((wp, index) => {
    const coord = fromLonLat([wp.lon, wp.lat]);

    if (!isFinite(coord[0]) || !isFinite(coord[1])) {
      return null;
    }

    return new Feature({
      geometry: new Point(coord),
      type: 'waypoint',
      sequence: wp.seq || index,
      altitude: wp.alt || 0,
      name: `Waypoint ${wp.seq || index}`,
      lat: wp.lat,
      lon: wp.lon
    });
  }).filter(feature => feature !== null);

  // Add all features to the source
  completedSurveySource.addFeature(surveyPolygon);

  if (waypointFeatures.length > 0) {
    completedSurveySource.addFeatures(waypointFeatures);
  }

}

const loadExistingSurveys = async () => {
  try {
    // Load surveys from file system only
    const fileSurveys = await loadSurveysFromFiles()

    if (fileSurveys.length > 0) {
      console.log(`Loaded ${fileSurveys.length} surveys from files`)
      fileSurveys.forEach(survey => {
        if (survey.waypoints) {
          displayCompletedSurvey(survey.waypoints)
        }
      })
    } else {
      console.log('No survey files found')
    }
  } catch (error) {
    console.error('Error loading existing surveys:', error)
  }
}


const initializeFeatures = () => {
  // Create vector source for all dynamic features
  vectorSource = new VectorSource()

  // Create drone feature
  droneFeature = new Feature({
    geometry: new Point([0, 0]),
  })
  droneFeature.setStyle(new Style({
    image: new Icon({
      src: droneIcon,
      scale: 0.1,
      anchor: [0.5, 0.5],
      anchorXUnits: 'fraction',
      anchorYUnits: 'fraction',
    }),
  }))

  // Create vehicle feature
  vehicleFeature = new Feature({
    geometry: new Point([0, 0]),
  })
  vehicleFeature.setStyle(new Style({
    image: new Icon({
      src: vehicleIcon,
      scale: 0.1,
      anchor: [0.5, 0.5],
      anchorXUnits: 'fraction',
      anchorYUnits: 'fraction',
      rotateWithView: false, // Set to false to control rotation programmatically
    }),
    text: new Text({
      text: 'VEHICLE',
      font: '12px Arial',
      fill: new Fill({color: '#000'}),
      stroke: new Stroke({color: '#fff', width: 2}),
      offsetY: -35,
    }),
  }))

  // Create safety radius feature
  safetyRadiusFeature = new Feature({
    geometry: new Circle([0, 0], SURVEY_CONSTANTS.DEFAULT_CIRCLE_RADIUS), // Radius in map units
  })
  safetyRadiusFeature.setStyle(new Style({
    stroke: new Stroke({
      color: 'rgba(230, 126, 34, 0.7)',
      width: 2,
      lineDash: [5, 5],
    }),
    fill: new Fill({
      color: 'rgba(230, 126, 34, 0.1)',
    }),
  }))

  // Create distance line feature
  distanceLineFeature = new Feature({
    geometry: new LineString([[0, 0], [0, 0]]),
  })
  distanceLineFeature.setStyle(new Style({
    stroke: new Stroke({
      color: 'rgba(142, 68, 173, 0.7)',
      width: 2,
    }),
  }))

  // Create distance label feature
  distanceLabelFeature = new Feature({
    geometry: new Point([0, 0]),
  })
  distanceLabelFeature.setStyle(new Style({
    text: new Text({
      text: '0m',
      fill: new Fill({color: 'white'}),
      stroke: new Stroke({color: 'rgba(142, 68, 173, 0.8)', width: 5}),
      font: '12px sans-serif',
      padding: [3, 5, 3, 5],
    }),
  }))

  vectorSource.addFeatures([
    droneFeature,
    vehicleFeature,
    safetyRadiusFeature,
    distanceLineFeature,
    distanceLabelFeature,
  ])
}

const initMap = () => {
  initializeFeatures()

  // Create base layers with offline capability
  osmLayer = new TileLayer({
    source: createOfflineOSMSource(),
    visible: true,
  })

  satelliteLayer = new TileLayer({
    source: createOfflineXYZSource({
      url: 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
      mapType: 'satellite',
      maxZoom: 20,
    }),
    visible: false,
  })

  hybridLabelsLayer = new TileLayer({
    source: createOfflineXYZSource({
      url: 'https://mt1.google.com/vt/lyrs=h&x={x}&y={y}&z={z}',
      mapType: 'hybrid',
      maxZoom: 20,
    }),
    visible: false,
  })

  // Create main vector layer for vehicles and indicators
  vectorLayer = new VectorLayer({
    source: vectorSource,
    zIndex: 15,
  })

  // Create waypoint sources and layers
  waypointSource = new VectorSource()
  waypointLayer = new VectorLayer({
    source: waypointSource,
    zIndex: 10,
  })

  routeSource = new VectorSource()
  routeLayer = new VectorLayer({
    source: routeSource,
    zIndex: 5,
  })

  // Create survey sources and layers
  surveyGridSource = new VectorSource()
  surveyGridLayer = new VectorLayer({
    source: surveyGridSource,
    zIndex: 20, // High z-index to ensure visibility above other layers
  })

  completedSurveySource = new VectorSource()
  completedSurveyLayer = new VectorLayer({
    source: completedSurveySource,
    style: new Style({
      fill: new Fill({
        color: 'rgba(76, 175, 80, 0.3)',
      }),
      stroke: new Stroke({
        color: '#4CAF50',
        width: 2,
      }),
    }),
    zIndex: 2,
  })

  // Initialize map
  map = new Map({
    target: mapElement.value,
    layers: [
      osmLayer,
      satelliteLayer,
      hybridLabelsLayer,
      completedSurveyLayer,
      routeLayer,
      vectorLayer,
      surveyGridLayer, // Move survey grid layer to render above other features
      waypointLayer,
    ],
    view: new View({
      center: fromLonLat([36.9759, 0.0078]), // Ol Pejeta coordinates
      zoom: 17,
    }),
  })

  // Map interaction handlers
  map.on('pointerdown', () => {
    isUserInteracting = true
    followVehicle.value = false
    followDrone.value = false
  })

  map.on('pointerup', () => {
    setTimeout(() => {
      isUserInteracting = false
    }, TIMING_CONSTANTS.STARTUP_DELAY)
  })

  map.on('movestart', evt => {
    if (evt.frameState && evt.frameState.viewHints[0] > 0) {
      isUserInteracting = true
      followVehicle.value = false
      followDrone.value = false
    }
  })

  map.on('moveend', () => {
    setTimeout(() => {
      isUserInteracting = false
    }, TIMING_CONSTANTS.MAP_FIT_DURATION)
  })
}


// Watchers
watch(() => props.droneTelemetryData, updateDroneFromTelemetry, {deep: true})
watch(() => props.vehicleTelemetryData, updateVehicleFromTelemetry, {deep: true})
watch(() => props.distance, updateMapFeatures)
watch(() => props.isDroneFollowing, () => vectorSource?.changed())
watch(() => props.vehicleWaypoints, waypoints => {
  if (waypoints && Object.keys(waypoints).length > 0) {
    updateWaypointsOnMap(waypoints)
  } else {
    clearWaypoints()
  }
}, {deep: true})
watch(followVehicle, isFollowing => {
  // `isFollowing` will be `true` when the button is activated.
  if (isFollowing) {
    // When 'Follow Vehicle' is turned on, turn 'Follow Drone' off.
    followDrone.value = false;

    // Also, center the map on the vehicle as before.
    if (vehiclePositionAvailable.value) {
      centerMapOnVehicle(
        gpsToMapCoordinates(
          props.vehicleTelemetryData.position.latitude,
          props.vehicleTelemetryData.position.longitude
        )
      );
    }
  }
});

watch(followDrone, isFollowing => {
  // `isFollowing` will be `true` when the button is activated.
  if (isFollowing) {
    // When 'Follow Drone' is turned on, turn 'Follow Vehicle' off.
    followVehicle.value = false;

    // Also, center the map on the drone as before.
    if (dronePositionAvailable.value) {
      centerMapOnDrone(
        gpsToMapCoordinates(
          props.droneTelemetryData.position.latitude,
          props.droneTelemetryData.position.longitude
        )
      );
    }
  }
});


// Survey grid management - show grid when waypoints exist, hide when cleared
watch(() => props.droneMissionWaypoints, waypoints => {
  if (waypoints && waypoints.length > 2) {
    displaySurveyGrid(waypoints);
  } else if (surveyGridSource) {
    surveyGridSource.clear();
  }
}, {deep: true, immediate: true});

// Survey completion handler - save completed survey, show as green polygon, and clear mission
watch(() => props.surveyComplete, async (isComplete, wasComplete) => {
  if (isComplete && !wasComplete && props.droneMissionWaypoints.length > 2) {
    const waypoints = props.droneMissionWaypoints;
    const droneId = props.droneTelemetryData?.vehicle_id || 'unknown';

    try {
      // Display completed survey as green polygon
      displayCompletedSurvey(waypoints);

      // Clear the survey grid
      if (surveyGridSource) {
        surveyGridSource.clear();
      }

      // Clear the mission from the drone to remove blue dotted lines
      const missionCleared = await clearDroneMission('drone');
      if (missionCleared) {
        console.log('Survey completed and mission cleared successfully');
      } else {
        console.warn('Survey completed but failed to clear mission');
      }
    } catch (error) {
      console.error('Error during survey completion:', error);
    }
  }
});

onMounted(() => {
  initMap()
  updateOfflineTileCounts()
  addConnectivityListeners(handleOnlineStatus, handleOfflineStatus)
  setTimeout(loadExistingSurveys, TIMING_CONSTANTS.STARTUP_DELAY)
})

onUnmounted(() => {
  if (map) {
    map.setTarget(null)
    map = null
  }
  removeConnectivityListeners(handleOnlineStatus, handleOfflineStatus)
})
</script>

<style scoped>
.map-container {
  position: relative;
  height: 100%;
  width: 100%;
}

.map {
  width: 100%;
  height: 100%;
}

.map-controls {
  position: absolute;
  width: 100%;
  top: 0;
  left: 0;
  /*
    START: Key Fix
    1. Use the --v-layout-top variable (provided by v-app-bar) to add dynamic top padding.
       A fallback of 64px is included for safety.
    2. Set pointer-events to none so that clicks pass through the empty parts of this container to the map below.
  */
  padding: calc(var(--v-layout-top, 64px) + 16px) 16px 16px;
  z-index: 1;
  pointer-events: none;
}

/*
  Make the direct children of the controls container (the control groups themselves) clickable again.
  This allows clicks on buttons but not on the space between them.
*/
.map-controls > div {
  pointer-events: auto;
}
/* END: Key Fix */


.toggle-wrapper {
  background-color: rgba(255, 255, 255, 0.95);
  border-radius: 8px;
  padding: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  backdrop-filter: blur(10px);
}

.map-type-toggle,
.coordination-controls,
.follow-controls,
.offline-controls {
  display: inline-flex;
  margin-right: 8px;
  margin-bottom: 10px;
  gap: 8px;
  vertical-align: top;
}

.warning-bg {
  background-color: rgba(255, 193, 7, 0.15);
  border: 1px solid rgba(255, 193, 7, 0.3);
}

/* Compass Indicator Positioning */
.compass-indicator {
  position: absolute;
  left: 16px;
  top: calc(var(--v-layout-top, 64px) + 120px);
  z-index: 2;
  pointer-events: auto;
}

/* Responsive compass positioning */
@media (max-width: 768px) {
  .compass-indicator {
    left: 12px;
    top: calc(var(--v-layout-top, 64px) + 100px);
  }
}

@media (max-width: 480px) {
  .compass-indicator {
    left: 8px;
    top: calc(var(--v-layout-top, 64px) + 80px);
  }
}
</style>
