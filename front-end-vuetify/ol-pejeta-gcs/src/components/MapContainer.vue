
<template>
  <div class="map-container">
    <div ref="mapElement" class="map" />

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
            <v-btn size="small" :value="true">
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
            <v-btn size="small" :value="true">
              <v-icon>mdi-quadcopter</v-icon>
              <span class="ml-1">Follow Drone</span>
            </v-btn>
          </v-btn-toggle>
        </div>
      </div>

      <!-- Coordination Controls -->
   <div class="coordination-controls pa-2">
        <div class="toggle-wrapper">
          <v-btn
            :loading="coordinationLoading"
            :color="props.isCoordinationActive ? 'red' : 'green'"
            variant="outlined"
            size="small"
            :prepend-icon="props.isCoordinationActive ? 'mdi-sync-off' : 'mdi-sync'"
            @click="toggleCoordination"
          >
            {{ props.isCoordinationActive ? 'Coordination Off' : 'Coordination On' }}
          </v-btn>
        </div>
      </div>


      <!-- Offline Map Controls -->
      <div class="offline-controls pa-2">
        <div class="toggle-wrapper">
          <v-btn
            @click="showOfflineDialog = true"
            size="small"
            :color="isDeviceOffline ? 'warning' : 'info'"
            variant="outlined"
            prepend-icon="mdi-map-marker-path"
            :disabled="isDownloading"
          >
            <v-icon v-if="isDeviceOffline" class="mr-1">mdi-wifi-off</v-icon>
            <span>{{ isDeviceOffline ? 'Offline Maps' : 'Download Maps' }}</span>
          </v-btn>
        </div>
      </div>
    </div>

    <!-- Offline Map Dialog -->
    <v-dialog v-model="showOfflineDialog" max-width="600" persistent>
      <v-card>
        <v-card-title class="text-h6 font-weight-bold">
          <v-icon color="primary" class="mr-2">mdi-map-marker-path</v-icon>
          Offline Maps for Ol Pejeta Conservancy
        </v-card-title>

        <v-card-text>
          <div v-if="isDeviceOffline" class="mb-4 pa-2 warning-bg rounded">
            <v-icon color="warning" class="mr-2">mdi-wifi-off</v-icon>
            <span class="font-weight-bold">You are currently offline.</span>
            Using cached map tiles for Ol Pejeta Conservancy.
          </div>

          <p class="text-body-1 mb-4">
            Download map tiles for the Ol Pejeta Conservancy area to use when offline.
            Maps will be centered on the current view position.
          </p>

          <v-slider
            v-model="offlineAreaRadius"
            :min="1"
            :max="10"
            :step="1"
            label="Download Area Radius"
            hint="Larger radius requires more storage"
            persistent-hint
            thumb-label
            :disabled="isDownloading"
          >
            <template v-slot:append>
              <span class="text-body-2">{{ offlineAreaRadius }}km</span>
            </template>
          </v-slider>

          <v-divider class="my-4"></v-divider>

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
                size="small"
                color="error"
                variant="outlined"
                class="mr-2"
                @click="clearOfflineMapTiles('osm')"
                :disabled="isDownloading || offlineTileCounts.osm === 0"
              >
                <v-icon size="small">mdi-delete</v-icon>
              </v-btn>

              <v-btn
                size="small"
                color="primary"
                :loading="isDownloading && downloadingMapType === 'osm'"
                :disabled="isDownloading && downloadingMapType !== 'osm'"
                @click="downloadOfflineMapTiles('osm')"
              >
                <v-icon size="small" class="mr-1">mdi-download</v-icon>
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
            <template v-slot:default>
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
                size="small"
                color="error"
                variant="outlined"
                class="mr-2"
                @click="clearOfflineMapTiles('satellite')"
                :disabled="isDownloading || offlineTileCounts.satellite === 0"
              >
                <v-icon size="small">mdi-delete</v-icon>
              </v-btn>

              <v-btn
                size="small"
                color="primary"
                :loading="isDownloading && downloadingMapType === 'satellite'"
                :disabled="isDownloading && downloadingMapType !== 'satellite'"
                @click="downloadOfflineMapTiles('satellite')"
              >
                <v-icon size="small" class="mr-1">mdi-download</v-icon>
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
            <template v-slot:default>
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
                size="small"
                color="error"
                variant="outlined"
                class="mr-2"
                @click="clearOfflineMapTiles('hybrid')"
                :disabled="isDownloading || offlineTileCounts.hybrid === 0"
              >
                <v-icon size="small">mdi-delete</v-icon>
              </v-btn>

              <v-btn
                size="small"
                color="primary"
                :loading="isDownloading && downloadingMapType === 'hybrid'"
                :disabled="isDownloading && downloadingMapType !== 'hybrid'"
                @click="downloadOfflineMapTiles('hybrid')"
              >
                <v-icon size="small" class="mr-1">mdi-download</v-icon>
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
            <template v-slot:default>
              {{ downloadProgress.hybrid.current }} / {{ downloadProgress.hybrid.total }} tiles
            </template>
          </v-progress-linear>

          <v-alert
            v-if="isDeviceOffline"
            type="warning"
            variant="tonal"
            class="mt-4"
            density="compact"
          >
            <div class="text-body-2">
              <strong>Note:</strong> You cannot download new map tiles while offline.
              Connect to the internet to download additional map tiles.
            </div>
          </v-alert>
        </v-card-text>

        <v-card-actions class="px-4 pb-4">
          <v-spacer></v-spacer>
          <v-btn
            color="primary"
            variant="outlined"
            @click="showOfflineDialog = false"
            :disabled="isDownloading"
          >
            Close
          </v-btn>
        </v-card-actions>
      </v-card>
    </v-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import { fromLonLat, toLonLat } from 'ol/proj'
import Feature from 'ol/Feature'
import Point from 'ol/geom/Point'
import LineString from 'ol/geom/LineString'
import Polygon from 'ol/geom/Polygon'
import Circle from 'ol/geom/Circle'
import { Vector as VectorLayer } from 'ol/layer'
import { Vector as VectorSource } from 'ol/source'
import { Circle as CircleStyle, Fill, Icon, Stroke, Style, Text } from 'ol/style'
import * as ol from 'ol/extent'

import droneIcon from '@/assets/drone.png'
import vehicleIcon from '@/assets/car_top_view.png'

// Import offline map utilities
import {
  createOfflineOSMSource,
  createOfflineXYZSource,
  downloadMapTiles,
  countTiles,
  clearTiles,
  isOffline,
  addConnectivityListeners,
  removeConnectivityListeners
} from '@/utils/OfflineMapUtils'

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
    default: () => ({})
  },
  droneMissionWaypoints: {
    type: Array,
    default: () => []
  },
  surveyComplete: {
    type: Boolean,
    default: false
  },
  isDroneSurveying: {
    type: Boolean,
    default: false
  }
})

const emit = defineEmits([
  'update:current-position',
  'update:drone-position',
  'update:vehicle-position',
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
const currentPosition = ref({ lat: 0.0078, lng: 36.9759 })
const dronePosition = ref({ x: 0, y: 0 })
const vehiclePosition = ref({ x: 0, y: 0 })
const coordinationLoading = ref(false)

const manualControl = ref(true)
const mapType = ref('osm')
const followVehicle = ref(true)
const followDrone = ref(false)

// Offline map state
const isDeviceOffline = ref(isOffline())
const showOfflineDialog = ref(false)
const downloadProgress = ref({
  osm: { current: 0, total: 0, percentage: 0 },
  satellite: { current: 0, total: 0, percentage: 0 },
  hybrid: { current: 0, total: 0, percentage: 0 }
})
const isDownloading = ref(false)
const downloadingMapType = ref('')
const offlineTileCounts = ref({
  osm: 0,
  satellite: 0,
  hybrid: 0
})
const offlineAreaRadius = ref(5) // 5km radius by default

// Following system variables
let lastFollowUpdate = 0
const followUpdateThrottle = 100 // milliseconds between follow updates
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

// Coordination functions
const toggleCoordination = async () => {
  coordinationLoading.value = true
  const action = props.isCoordinationActive ? 'stop' : 'start'
  try {
    const response = await fetch(`http://localhost:8000/coordination/${action}`, { method: 'POST' })
    if (!response.ok) {
      const errorData = await response.json()
      console.error(`Failed to ${action} coordination:`, errorData.detail || response.statusText)
    } else {
      console.log(`Coordination ${action} requested successfully.`)
    }
  } catch (error) {
    console.error(`Error during coordination ${action}:`, error)
  } finally {
    coordinationLoading.value = false
  }
}

// Offline map functions
const updateOfflineTileCounts = async () => {
  try {
    const [osmCount, satelliteCount, hybridCount] = await Promise.all([
      countTiles('osm'),
      countTiles('satellite'),
      countTiles('hybrid')
    ])

    offlineTileCounts.value = {
      osm: osmCount,
      satellite: satelliteCount,
      hybrid: hybridCount
    }
  } catch (error) {
    console.error('Error counting offline tiles:', error)
  }
}

const downloadOfflineMapTiles = async (type) => {
  if (isDownloading.value) return
  isDownloading.value = true
  downloadingMapType.value = type
  downloadProgress.value[type] = { current: 0, total: 0, percentage: 0 }

  try {
    const view = map.getView()
    const center = toLonLat(view.getCenter())
    await downloadMapTiles({
      mapType: type,
      center: center,
      radius: offlineAreaRadius.value,
      progressCallback: (current, total) => {
        downloadProgress.value[type] = {
          current,
          total,
          percentage: Math.round((current / total) * 100)
        }
      }
    })
    await updateOfflineTileCounts()
  } catch (error) {
    console.error(`Error downloading ${type} map tiles:`, error)
  } finally {
    isDownloading.value = false
    downloadingMapType.value = ''
  }
}

const clearOfflineMapTiles = async (type) => {
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
const centerMapOnVehicle = (coordinates) => {
  if (!map || !followVehicle.value || isUserInteracting) return
  const now = Date.now()
  if (now - lastFollowUpdate < followUpdateThrottle) return
  lastFollowUpdate = now
  map.getView().setCenter(coordinates)
}

const centerMapOnDrone = (coordinates) => {
  if (!map || !followDrone.value || isUserInteracting) return
  const now = Date.now()
  if (now - lastFollowUpdate < followUpdateThrottle) return
  lastFollowUpdate = now
  map.getView().setCenter(coordinates)
}

// Telemetry update functions
const updateDroneFromTelemetry = () => {
  if (!dronePositionAvailable.value || !droneFeature) return

  const { latitude, longitude } = props.droneTelemetryData.position
  const mapCoords = gpsToMapCoordinates(latitude, longitude)
  dronePosition.value = { x: mapCoords[0], y: mapCoords[1] }

  if (followDrone.value && !isUserInteracting) {
    centerMapOnDrone(mapCoords)
  }
  updateMapFeatures()
  emit('update:drone-position', { lat: latitude, lon: longitude })
}

const updateVehicleFromTelemetry = () => {
  if (!vehiclePositionAvailable.value || !vehicleFeature) return

  const { latitude, longitude } = props.vehicleTelemetryData.position
  const heading = props.vehicleTelemetryData.velocity.heading
  const mapCoords = gpsToMapCoordinates(latitude, longitude)
  vehiclePosition.value = { x: mapCoords[0], y: mapCoords[1] }
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
  emit('update:vehicle-position', { lat: latitude, lon: longitude })
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
const updateWaypointsOnMap = (waypointsObj) => {
  if (!waypointSource || !routeSource) return

  waypointSource.clear()
  routeSource.clear()

  const waypointsArray = Object.values(waypointsObj).sort((a, b) => a.seq - b.seq)
  if (waypointsArray.length === 0) {
    hasAutoFittedWaypoints = false
    return
  }

  const coordinates = []
  waypointsArray.forEach((waypoint) => {
    const coord = fromLonLat([waypoint.lon, waypoint.lat])
    coordinates.push(coord)

    const feature = new Feature({ geometry: new Point(coord), waypoint: waypoint })
    feature.setStyle(new Style({
      image: new CircleStyle({
        radius: 15,
        fill: new Fill({ color: '#ff6b35' }),
        stroke: new Stroke({ color: 'white', width: 2 })
      }),
      text: new Text({
        text: (waypoint.seq + 1).toString(),
        font: 'bold 12px Arial',
        fill: new Fill({ color: 'white' })
      })
    }))
    waypointSource.addFeature(feature)
  })

  if (coordinates.length > 1) {
    const routeFeature = new Feature({ geometry: new LineString(coordinates) })
    routeFeature.setStyle(new Style({
      stroke: new Stroke({ color: '#ff6b35', width: 3, lineDash: [5, 5] })
    }))
    routeSource.addFeature(routeFeature)

    if (!hasAutoFittedWaypoints) {
      const extent = routeSource.getExtent()
      if (extent && !ol.isEmpty(extent)) {
        map.getView().fit(extent, { padding: [50, 50, 50, 50], duration: 500 })
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

// Survey utility functions
const generateLawnmowerGrid = (waypoints) => {
  if (!waypoints || waypoints.length < 3) return []

  const sortedWaypoints = [...waypoints].sort((a, b) => a.seq - b.seq)
  const coordinates = sortedWaypoints.map(wp => fromLonLat([wp.lon, wp.lat]))

  // Create a simple line string connecting the waypoints in order
  return [new Feature({ geometry: new LineString(coordinates) })]
}

const saveSurveyedArea = (waypoints, vehicleId) => {
  try {
    const timestamp = Date.now()
    const surveyId = `survey_${vehicleId || 'unknown'}_${timestamp}`

    const surveyData = {
      id: surveyId,
      waypoints: waypoints.map(wp => ({ lat: wp.lat, lon: wp.lon, seq: wp.seq })),
      vehicleId: vehicleId || 'unknown',
      completedAt: new Date(timestamp).toISOString()
    }

    const existingData = JSON.parse(localStorage.getItem('ol_pejeta_surveys') || '{}')
    existingData[surveyId] = surveyData
    localStorage.setItem('ol_pejeta_surveys', JSON.stringify(existingData))

  } catch (error) {
    console.error('Error saving survey area:', error)
  }
}

const loadSurveyedAreas = () => {
  try {
    const data = JSON.parse(localStorage.getItem('ol_pejeta_surveys') || '{}')
    return Object.values(data)
  } catch (error) {
    console.error('Error loading surveyed areas:', error)
    return []
  }
}

const displaySurveyGrid = (waypoints) => {
  if (!surveyGridSource) return
  surveyGridSource.clear()

  if (!waypoints || waypoints.length < 2) return

  const features = generateLawnmowerGrid(waypoints)
  surveyGridSource.addFeatures(features)
}

const displayCompletedSurvey = (waypoints) => {
  if (!completedSurveySource || !waypoints || waypoints.length < 3) return

  // Convert waypoints to map coordinates first
  const coordinates = waypoints.map(wp => fromLonLat([wp.lon, wp.lat]))

  // Calculate the convex hull to represent the surveyed area as a clean polygon
  const hullCoordinates = calculateConvexHull(coordinates);

  // A valid polygon needs at least 3 unique points to form an area.
  if (hullCoordinates.length < 3) {
      console.warn("Not enough unique points to form a valid survey area polygon.");
      return;
  }

  // Close the polygon shape by adding the first point to the end of the array
  hullCoordinates.push(hullCoordinates[0])

  const surveyPolygon = new Feature({
    geometry: new Polygon([hullCoordinates]) // Note the double array for Polygon geometry
  })

  completedSurveySource.addFeature(surveyPolygon)
}

const loadExistingSurveys = () => {
  const surveys = loadSurveyedAreas()
  surveys.forEach(survey => {
    if (survey.waypoints) {
      displayCompletedSurvey(survey.waypoints)
    }
  })
}

const calculateConvexHull = (points) => {
  // Sort points lexicographically (by x, then y) to ensure a consistent order.
  points.sort((a, b) => a[0] - b[0] || a[1] - b[1]);

  const crossProduct = (o, a, b) => {
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0]);
  };

  // Build the lower hull
  const lower = [];
  for (const p of points) {
    while (lower.length >= 2 && crossProduct(lower[lower.length - 2], lower[lower.length - 1], p) <= 0) {
      lower.pop();
    }
    lower.push(p);
  }

  // Build the upper hull
  const upper = [];
  for (let i = points.length - 1; i >= 0; i--) {
    const p = points[i];
    while (upper.length >= 2 && crossProduct(upper[upper.length - 2], upper[upper.length - 1], p) <= 0) {
      upper.pop();
    }
    upper.push(p);
  }

  // Combine the hulls and remove the duplicate start/end points.
  return lower.slice(0, -1).concat(upper.slice(0, -1));
};
// Map initialization
const initializeFeatures = () => {
  // Create vector source for all dynamic features
  vectorSource = new VectorSource()

  // Create drone feature
  droneFeature = new Feature({
    geometry: new Point([0, 0])
  })
  droneFeature.setStyle(new Style({
    image: new Icon({
      src: droneIcon,
      scale: 0.1,
      anchor: [0.5, 0.5],
      anchorXUnits: 'fraction',
      anchorYUnits: 'fraction',
    })
  }))

  // Create vehicle feature
  vehicleFeature = new Feature({
    geometry: new Point([0, 0])
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
      offsetY: -35
    })
  }))

  // Create safety radius feature
  safetyRadiusFeature = new Feature({
    geometry: new Circle([0, 0], 500) // Radius in map units
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
    geometry: new LineString([[0, 0], [0, 0]])
  })
  distanceLineFeature.setStyle(new Style({
    stroke: new Stroke({
      color: 'rgba(142, 68, 173, 0.7)',
      width: 2,
    }),
  }))

  // Create distance label feature
  distanceLabelFeature = new Feature({
    geometry: new Point([0, 0])
  })
  distanceLabelFeature.setStyle(new Style({
    text: new Text({
      text: '0m',
      fill: new Fill({ color: 'white' }),
      stroke: new Stroke({ color: 'rgba(142, 68, 173, 0.8)', width: 5 }),
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
    zIndex: 15
  })

  // Create waypoint sources and layers
  waypointSource = new VectorSource()
  waypointLayer = new VectorLayer({
    source: waypointSource,
    zIndex: 10
  })

  routeSource = new VectorSource()
  routeLayer = new VectorLayer({
    source: routeSource,
    zIndex: 5
  })

  // Create survey sources and layers
  surveyGridSource = new VectorSource()
  surveyGridLayer = new VectorLayer({
    source: surveyGridSource,
    style: new Style({
      stroke: new Stroke({
        color: '#2196F3',
        width: 2,
        lineDash: [10, 5]
      })
    }),
    zIndex: 3
  })

  completedSurveySource = new VectorSource()
  completedSurveyLayer = new VectorLayer({
    source: completedSurveySource,
    style: new Style({
      fill: new Fill({
        color: 'rgba(76, 175, 80, 0.3)'
      }),
      stroke: new Stroke({
        color: '#4CAF50',
        width: 2
      })
    }),
    zIndex: 2
  })

  // Initialize map
  map = new Map({
    target: mapElement.value,
    layers: [
      osmLayer,
      satelliteLayer,
      hybridLabelsLayer,
      completedSurveyLayer,
      surveyGridLayer,
      routeLayer,
      vectorLayer,
      waypointLayer
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
    setTimeout(() => { isUserInteracting = false }, 1000)
  })

  map.on('movestart', (evt) => {
    if (evt.frameState && evt.frameState.viewHints[0] > 0) {
      isUserInteracting = true
      followVehicle.value = false
      followDrone.value = false
    }
  })

  map.on('moveend', () => {
    setTimeout(() => { isUserInteracting = false }, 500)
  })
}


// Watchers
watch(() => props.droneTelemetryData, updateDroneFromTelemetry, { deep: true })
watch(() => props.vehicleTelemetryData, updateVehicleFromTelemetry, { deep: true })
watch(() => props.distance, updateMapFeatures)
watch(() => props.isDroneFollowing, () => vectorSource?.changed())
watch(() => props.vehicleWaypoints, (waypoints) => {
  if (waypoints && Object.keys(waypoints).length > 0) {
    updateWaypointsOnMap(waypoints)
  } else {
    clearWaypoints()
  }
}, { deep: true })

watch(followVehicle, (isFollowing) => {
  if (isFollowing && vehiclePositionAvailable.value) {
    centerMapOnVehicle(gpsToMapCoordinates(props.vehicleTelemetryData.position.latitude, props.vehicleTelemetryData.position.longitude))
  }
})

watch(followDrone, (isFollowing) => {
  if (isFollowing && dronePositionAvailable.value) {
    centerMapOnDrone(gpsToMapCoordinates(props.droneTelemetryData.position.latitude, props.droneTelemetryData.position.longitude))
  }
})

// WATCHER 1: Handles showing/hiding the blue "planned" grid based on the presence of waypoints.
watch(() => props.droneMissionWaypoints, (waypoints) => {
  const hasWaypoints = waypoints && waypoints.length > 2;

  if (hasWaypoints) {
    // If waypoints exist, it means a survey is planned or active. Display the grid.
    console.log('Waypoints detected, displaying planned survey grid.');
    displaySurveyGrid(waypoints);
  } else {
    // If waypoints are cleared, the mission is over or reset. Clear the grid.
    if (surveyGridSource) {
      console.log('No waypoints detected, clearing planned survey grid.');
      surveyGridSource.clear();
    }
  }
}, { deep: true, immediate: true });


// WATCHER 2: Handles the moment a survey is marked as "complete".
watch(() => props.surveyComplete, (isComplete, wasComplete) => {
  // This runs only when surveyComplete transitions from false to true.
  if (isComplete && !wasComplete && props.droneMissionWaypoints.length > 2) {
    const waypoints = props.droneMissionWaypoints;
    const droneId = props.droneTelemetryData?.vehicle_id || 'unknown';

    console.log('Survey complete! Saving area, drawing green polygon, and clearing blue grid.');

    // Save the completed survey data to local storage
    saveSurveyedArea(waypoints, droneId);

    // Display the final completed area as a green polygon
    displayCompletedSurvey(waypoints);

    // Explicitly clear the blue "planned" grid, as the survey is now finished.
    if (surveyGridSource) {
      surveyGridSource.clear();
    }
  }
});

onMounted(() => {
  initMap()
  updateOfflineTileCounts()
  addConnectivityListeners(handleOnlineStatus, handleOfflineStatus)
  setTimeout(loadExistingSurveys, 1000)
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
  padding: 16px;
  z-index: 1;
}

.coordinates {
  display: inline-block;
  background-color: rgba(255, 255, 255, 0.8);
  border-radius: 20px;
  padding: 8px 16px;
  margin-bottom: 10px;
  font-size: 14px;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
}

.map-type-toggle {
  display: inline-block;
  margin-left: 11px;
  margin-bottom: 10px;
}

.toggle-wrapper {
  background-color: rgba(255, 255, 255, 0.95);
  border-radius: 8px;
  padding: 4px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  backdrop-filter: blur(10px);
}

.coordination-controls {
  display: inline-flex;
  margin-left: 11px;
  margin-bottom: 10px;
}

.follow-controls {
  display: inline-flex;
  margin-left: 11px;
  margin-bottom: 10px;
  gap: 8px;
}

.offline-controls {
  display: inline-flex;
  margin-left: 11px;
  margin-bottom: 10px;
}

.warning-bg {
  background-color: rgba(255, 193, 7, 0.15);
  border: 1px solid rgba(255, 193, 7, 0.3);
}
</style>
