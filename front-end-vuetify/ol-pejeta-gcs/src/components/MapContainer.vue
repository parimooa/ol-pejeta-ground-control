
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
            @click="startCoordination"
            size="small"
            color="green"
            variant="outlined"
            prepend-icon="mdi-sync"
          >Coordination On</v-btn>
          <v-btn
            @click="stopCoordination"
            size="small"
            color="red"
            class="ml-2"
            variant="outlined"
            prepend-icon="mdi-sync-off"
          >Coordination Off</v-btn>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import Map from 'ol/Map'
import View from 'ol/View'
import TileLayer from 'ol/layer/Tile'
import OSM from 'ol/source/OSM'
import XYZ from 'ol/source/XYZ'
import { fromLonLat, toLonLat } from 'ol/proj'
import Feature from 'ol/Feature'
import Point from 'ol/geom/Point'
import LineString from 'ol/geom/LineString'
import Circle from 'ol/geom/Circle'
import { Vector as VectorLayer } from 'ol/layer'
import { Vector as VectorSource } from 'ol/source'
import { Circle as CircleStyle, Fill, Icon, Stroke, Style, Text } from 'ol/style'
import * as ol from 'ol/extent'

import droneIcon from '@/assets/drone.png'
import vehicleIcon from '@/assets/car_top_view.png'

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

// Following system variables
let lastFollowUpdate = 0
const followUpdateThrottle = 100 // milliseconds between follow updates
let isUserInteracting = false

// Helper computed properties
const dronePositionAvailable = computed(() => {
  return props.isDroneConnected &&
    props.droneTelemetryData &&
    props.droneTelemetryData.position &&
    props.droneTelemetryData.position.latitude !== null &&
    props.droneTelemetryData.position.longitude !== null
})

const vehiclePositionAvailable = computed(() => {
  return props.isVehicleConnected &&
    props.vehicleTelemetryData &&
    props.vehicleTelemetryData.position &&
    props.vehicleTelemetryData.position.latitude !== null &&
    props.vehicleTelemetryData.position.longitude !== null
})

const isManualControlEnabled = computed(() => {
  return manualControl.value && !props.isDroneConnected && !props.isVehicleConnected
})

// Coordination functions
const startCoordination = async () => {
  try {
    await fetch('http://localhost:8000/coordination/start', { method: 'POST' })
    console.log('Coordination started')
  } catch (error) {
    console.error('Failed to start coordination:', error)
  }
}

const stopCoordination = async () => {
  try {
    await fetch('http://localhost:8000/coordination/stop', { method: 'POST' })
    console.log('Coordination stopped')
  } catch (error) {
    console.error('Failed to stop coordination:', error)
  }
}

// Map utility functions
const switchMapType = newType => {
  if (!map) return

  osmLayer.setVisible(false)
  satelliteLayer.setVisible(false)
  hybridLabelsLayer.setVisible(false)

  switch (newType) {
    case 'osm':
      osmLayer.setVisible(true)
      break
    case 'satellite':
      satelliteLayer.setVisible(true)
      break
    case 'hybrid':
      satelliteLayer.setVisible(true)
      hybridLabelsLayer.setVisible(true)
      break
  }

  console.log(`Map type switched to: ${newType}`)
}

const gpsToMapCoordinates = (lat, lng) => {
  return fromLonLat([lng, lat])
}

// Improved following functions
const centerMapOnVehicle = (coordinates) => {
  if (!map || !followVehicle.value || isUserInteracting) return

  const now = Date.now()
  if (now - lastFollowUpdate < followUpdateThrottle) return

  lastFollowUpdate = now

  // Set center directly without animation for smooth following
  const view = map.getView()
  view.setCenter(coordinates)
}

const centerMapOnDrone = (coordinates) => {
  if (!map || !followDrone.value || isUserInteracting) return

  const now = Date.now()
  if (now - lastFollowUpdate < followUpdateThrottle) return

  lastFollowUpdate = now

  // Set center directly without animation for smooth following
  const view = map.getView()
  view.setCenter(coordinates)
}

// Telemetry update functions
const updateDroneFromTelemetry = () => {
  if (!props.isDroneConnected || !dronePositionAvailable.value || !droneFeature) {
    return
  }

  const { latitude, longitude } = props.droneTelemetryData.position
  const mapCoords = gpsToMapCoordinates(latitude, longitude)

  // Update drone position
  dronePosition.value = { x: mapCoords[0], y: mapCoords[1] }

  // Center map on drone if following is enabled
  if (followDrone.value && !isUserInteracting) {
    centerMapOnDrone([dronePosition.value.x, dronePosition.value.y])
  }

  // Update map features
  updateMapFeatures()

  // Emit position update
  emit('update:drone-position', dronePosition.value)
  console.log(`Drone position updated from telemetry: ${latitude}, ${longitude}`)
}

const updateVehicleFromTelemetry = () => {
  if (!props.isVehicleConnected || !vehiclePositionAvailable.value || !vehicleFeature) {
    return
  }

  const { latitude, longitude } = props.vehicleTelemetryData.position
  const heading = props.vehicleTelemetryData.velocity.heading
  const mapCoords = gpsToMapCoordinates(latitude, longitude)

  // Update vehicle position
  vehiclePosition.value = { x: mapCoords[0], y: mapCoords[1] }

  // Update the vehicle feature with new coordinates
  vehicleFeature.getGeometry().setCoordinates([vehiclePosition.value.x, vehiclePosition.value.y])

  // Set the heading property on the feature for the style function to use
  if (heading !== undefined) {
    vehicleFeature.set('heading', heading)
  }

  // Center map on vehicle if following is enabled - use the new smooth method
  if (followVehicle.value && !isUserInteracting) {
    centerMapOnVehicle([vehiclePosition.value.x, vehiclePosition.value.y])
  }

  // Update map features
  updateMapFeatures()

  // Emit position update
  emit('update:vehicle-position', vehiclePosition.value)
  console.log(`Vehicle position updated from telemetry: ${latitude}, ${longitude}, heading: ${heading}`)
}

const updateMapFeatures = () => {
  if (!map || !vectorSource) return

  droneFeature.getGeometry().setCoordinates([dronePosition.value.x, dronePosition.value.y])
  vehicleFeature.getGeometry().setCoordinates([vehiclePosition.value.x, vehiclePosition.value.y])

  safetyRadiusFeature.getGeometry().setCenter([dronePosition.value.x, dronePosition.value.y])

  distanceLineFeature.getGeometry().setCoordinates([
    [dronePosition.value.x, dronePosition.value.y],
    [vehiclePosition.value.x, vehiclePosition.value.y],
  ])

  const midPoint = [
    (dronePosition.value.x + vehiclePosition.value.x) / 2,
    (dronePosition.value.y + vehiclePosition.value.y) / 2,
  ]
  distanceLabelFeature.getGeometry().setCoordinates(midPoint)

  // Update distance label
  distanceLabelFeature.setStyle(new Style({
    text: new Text({
      text: props.distance + 'm',
      fill: new Fill({
        color: 'white',
      }),
      stroke: new Stroke({
        color: 'rgba(142, 68, 173, 0.8)',
        width: 5,
      }),
      font: '12px sans-serif',
      padding: [3, 5, 3, 5],
    }),
  }))

  vectorSource.changed()
}

// Waypoint functions
const updateWaypointsOnMap = (waypointsObj) => {
  if (!waypointSource || !routeSource) return

  // Clear existing waypoint features
  waypointSource.clear()
  routeSource.clear()

  // Convert waypoints object to array and sort by sequence
  const waypointsArray = Object.values(waypointsObj).sort((a, b) => a.seq - b.seq)

  if (waypointsArray.length === 0) {
    hasAutoFittedWaypoints = false
    return
  }

  const coordinates = []

  waypointsArray.forEach((waypoint) => {
    const coord = fromLonLat([waypoint.lon, waypoint.lat])
    coordinates.push(coord)

    // Create waypoint marker with number
    const feature = new Feature({
      geometry: new Point(coord),
      waypoint: waypoint
    })

    // Style with waypoint number
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

  // Add route line connecting waypoints
  if (coordinates.length > 1) {
    const routeFeature = new Feature({
      geometry: new LineString(coordinates)
    })

    routeFeature.setStyle(new Style({
      stroke: new Stroke({
        color: '#ff6b35',
        width: 3,
        lineDash: [5, 5]
      })
    }))

    routeSource.addFeature(routeFeature)

    // Only auto-fit to waypoints on first load, not on subsequent updates
    if (!hasAutoFittedWaypoints) {
      const extent = routeSource.getExtent()
      if (extent && !ol.isEmpty(extent)) {
        // Removed maxZoom constraint to allow unlimited zooming
        map.getView().fit(extent, { padding: [50, 50, 50, 50] })
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

// Map initialization
const initMap = () => {
  vectorSource = new VectorSource()

  vectorLayer = new VectorLayer({
    source: vectorSource,
    style(feature) {
      const type = feature.get('type')

      if (type === 'drone') {
        let color = props.isDroneConnected ? '#2ecc71' : '#3498db'
        let strokeColor = props.isDroneConnected ? 'rgba(46, 204, 113, 0.5)' : 'rgba(52, 152, 219, 0.5)'

        if (props.isDroneFollowing) {
          color = '#f39c12'
          strokeColor = 'rgba(243, 156, 18, 0.7)'
        }

        return new Style({
          image: new Icon({
            src: droneIcon,
            scale: 0.1,
            anchor: [0.5, 0.5],
            anchorXUnits: 'fraction',
            anchorYUnits: 'fraction',
          }),
          stroke: new Stroke({
            color: strokeColor,
            width: 3,
          }),
          fill: new Fill({
            color,
          }),
        })
      } else if (type === 'car') {
        const heading = feature.get('heading') || 0
        const headingInRadians = (heading * Math.PI) / 180
        return new Style({
          image: new Icon({
            src: vehicleIcon,
            scale: 0.07,
            anchor: [0.5, 0.5],
            anchorXUnits: 'fraction',
            anchorYUnits: 'fraction',
            rotateWithView: true,
            rotation: headingInRadians,
          }),
          stroke: new Stroke({
            color: 'rgba(231, 76, 60, 0.5)',
            width: 3,
          }),
          fill: new Fill({
            color: '#e74c3c',
          }),
        })
      } else if (type === 'safety-radius') {
        return new Style({
          stroke: new Stroke({
            color: 'rgba(230, 126, 34, 0.7)',
            width: 2,
            lineDash: [5, 5],
          }),
          fill: new Fill({
            color: 'rgba(230, 126, 34, 0.1)',
          }),
        })
      } else if (type === 'distance-line') {
        return new Style({
          stroke: new Stroke({
            color: 'rgba(142, 68, 173, 0.7)',
            width: 2,
          }),
        })
      }
    },
  })

  // Create base layers
  osmLayer = new TileLayer({
    source: new OSM(),
    visible: true,
  })

  satelliteLayer = new TileLayer({
    source: new XYZ({
      url: 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
      maxZoom: 40,
    }),
    visible: false,
  })

  hybridLabelsLayer = new TileLayer({
    source: new XYZ({
      url: 'https://mt1.google.com/vt/lyrs=h&x={x}&y={y}&z={z}',
      maxZoom: 40,
    }),
    visible: false,
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

  // Initialize map
  map = new Map({
    target: mapElement.value,
    layers: [
      osmLayer,
      satelliteLayer,
      hybridLabelsLayer,
      routeLayer,
      vectorLayer,
      waypointLayer
    ],
    view: new View({
      center: fromLonLat([36.9759, 0.0078]), // Ol Pejeta coordinates
      zoom: 17,
    }),
  })

  const center = map.getView().getCenter()

  // Initial positions
  dronePosition.value = {
    x: center[0] - 500,
    y: center[1] - 500,
  }

  vehiclePosition.value = {
    x: center[0] + 500,
    y: center[1] + 500,
  }

  // Create features
  droneFeature = new Feature({
    geometry: new Point([dronePosition.value.x, dronePosition.value.y]),
    type: 'drone',
  })

  vehicleFeature = new Feature({
    geometry: new Point([vehiclePosition.value.x, vehiclePosition.value.y]),
    type: 'car',
  })

  safetyRadiusFeature = new Feature({
    geometry: new Circle([dronePosition.value.x, dronePosition.value.y], 200),
    type: 'safety-radius',
  })

  distanceLineFeature = new Feature({
    geometry: new LineString([
      [dronePosition.value.x, dronePosition.value.y],
      [vehiclePosition.value.x, vehiclePosition.value.y],
    ]),
    type: 'distance-line',
  })

  const midPoint = [
    (dronePosition.value.x + vehiclePosition.value.x) / 2,
    (dronePosition.value.y + vehiclePosition.value.y) / 2,
  ]

  distanceLabelFeature = new Feature({
    geometry: new Point(midPoint),
    type: 'distance-label',
  })

  vectorSource.addFeatures([
    droneFeature,
    vehicleFeature,
    safetyRadiusFeature,
    distanceLineFeature,
    distanceLabelFeature,
  ])

  // Map interaction handlers
  let selectedFeature = null

  map.on('pointermove', function (e) {
    if (selectedFeature && isManualControlEnabled.value) {
      const coords = e.coordinate
      if (selectedFeature === droneFeature) {
        dronePosition.value = { x: coords[0], y: coords[1] }
        emit('update:drone-position', dronePosition.value)
      } else if (selectedFeature === vehicleFeature) {
        vehiclePosition.value = { x: coords[0], y: coords[1] }
        emit('update:vehicle-position', vehiclePosition.value)
      }
      updateMapFeatures()
    }
  })

  map.on('pointerdown', function (e) {
    if (isManualControlEnabled.value) {
      map.forEachFeatureAtPixel(e.pixel, function (feature) {
        if (feature === droneFeature || feature === vehicleFeature) {
          selectedFeature = feature
          return true
        }
      })
    }

    // Set user interaction flag and disable following
    isUserInteracting = true
    followVehicle.value = false
    followDrone.value = false
  })

  map.on('pointerup', function () {
    selectedFeature = null
    // Keep user interaction flag for a short time to prevent immediate re-following
    setTimeout(() => {
      isUserInteracting = false
    }, 1000) // 1 second delay before allowing following again
  })

  // Handle map drag/pan
  map.on('movestart', function (evt) {
    // Only disable following if the move was initiated by user interaction
    if (evt.frameState && evt.frameState.viewHints[0] > 0) { // User is interacting
      isUserInteracting = true
      followVehicle.value = false
      followDrone.value = false
    }
  })

  map.on('moveend', function (evt) {
    const center = map.getView().getCenter()
    const lonLat = toLonLat(center)
    currentPosition.value = {
      lng: lonLat[0],
      lat: lonLat[1],
    }
    emit('update:current-position', currentPosition.value)

    // Reset interaction flag after move ends
    setTimeout(() => {
      isUserInteracting = false
    }, 500)
  })

  // Initial update
  updateMapFeatures()
}

// Watchers
watch(() => props.droneTelemetryData, (newTelemetry) => {
  if (newTelemetry && dronePositionAvailable.value) {
    updateDroneFromTelemetry()
    manualControl.value = false
  }
}, { deep: true })

watch(() => props.vehicleTelemetryData, (newTelemetry) => {
  if (newTelemetry && vehiclePositionAvailable.value) {
    updateVehicleFromTelemetry()
    manualControl.value = false
  }
}, { deep: true })

watch(() => props.distance, () => {
  updateMapFeatures()
})

watch(() => props.isDroneFollowing, () => {
  if (vectorSource) {
    vectorSource.changed()
  }
})

// Watch for waypoint changes from telemetry and update map
watch(() => props.vehicleWaypoints, (newWaypoints) => {
  if (newWaypoints && Object.keys(newWaypoints).length > 0) {
    updateWaypointsOnMap(newWaypoints)
  } else {
    clearWaypoints()
  }
}, { deep: true })

// Watch for follow vehicle changes to re-enable following
watch(followVehicle, (newValue) => {
  if (newValue && vehiclePositionAvailable.value) {
    // Immediately center on vehicle when following is enabled
    centerMapOnVehicle([vehiclePosition.value.x, vehiclePosition.value.y])
  }
})

// Watch for follow drone changes to re-enable following
watch(followDrone, (newValue) => {
  if (newValue && dronePositionAvailable.value) {
    // Immediately center on drone when following is enabled
    centerMapOnDrone([dronePosition.value.x, dronePosition.value.y])
  }
})

onMounted(() => {
  initMap()
})

onUnmounted(() => {
  if (map) {
    map.setTarget(null)
    map = null
  }
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
</style>
