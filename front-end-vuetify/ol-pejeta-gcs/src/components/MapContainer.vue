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

let droneFeature = null
let vehicleFeature = null
let safetyRadiusFeature = null
let distanceLineFeature = null
let distanceLabelFeature = null
let vectorSource = null
let vectorLayer = null
let waypointFeatures = {}

const currentPosition = ref({ lat: 0.0078, lng: 36.9759 })
const dronePosition = ref({ x: 0, y: 0 })
const vehiclePosition = ref({ x: 0, y: 0 })
const coordinationLoading = ref(false)

const manualControl = ref(true) // Toggle between manual and telemetry control
const mapType = ref('osm') // 'osm', 'satellite', or 'hybrid'
const followVehicle = ref(true) // Whether to follow the vehicle
const followDrone = ref(false) // Whether to follow the drone

// Helper computed property to check if position data is available
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


  const startCoordination = async () => {
    try {
      await fetch('http://localhost:8000/coordination/start', { method: 'POST' });
      console.log('Coordination started');
      // You can also emit an event to show a snackbar in App.vue
    } catch (error) {
      console.error('Failed to start coordination:', error);
    }
  };

  const stopCoordination = async () => {
    try {
      await fetch('http://localhost:8000/coordination/stop', { method: 'POST' });
      console.log('Coordination stopped');
    } catch (error) {
      console.error('Failed to stop coordination:', error);
    }
  };

  const formatCoordinate = (value, type) => {
    const absValue = Math.abs(value)
    const degrees = Math.floor(absValue)
    const minutes = Math.floor((absValue - degrees) * 60)
    const seconds = ((absValue - degrees - minutes / 60) * 3600).toFixed(2)

    let direction
    if (type === 'lat') {
      direction = value >= 0 ? ' N' : ' S'
    } else {
      direction = value >= 0 ? ' E' : ' W'
    }

    return `${degrees}° ${minutes}' ${seconds}"${direction}`
  }

  // Function to switch map types
  const switchMapType = newType => {
    if (!map) return

    // Hide all base layers first
    osmLayer.setVisible(false)
    satelliteLayer.setVisible(false)
    hybridLabelsLayer.setVisible(false)

    // Show appropriate layers based on selection
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

  // Function to convert GPS coordinates to map coordinates
  const gpsToMapCoordinates = (lat, lng) => {
    return fromLonLat([lng, lat])
  }

  // Function to center map on coordinates
  const centerMapOn = (coordinates) => {
    if (!map) return

    const view = map.getView()
    view.animate({
      center: coordinates,
      duration: 500, // Smooth transition
      easing: (t) => t // Linear easing
    })
  }

  // Function to update drone position from telemetry data
  const updateDroneFromTelemetry = () => {
    if (!props.isDroneConnected || !dronePositionAvailable.value || !droneFeature) {
      return
    }

    const { latitude, longitude } = props.droneTelemetryData.position
    const mapCoords = gpsToMapCoordinates(latitude, longitude)

    // Update drone position
    dronePosition.value = { x: mapCoords[0], y: mapCoords[1] }

    // Center map on drone if following is enabled
    if (followDrone.value) {
      centerMapOn([dronePosition.value.x, dronePosition.value.y])
    }

    // Update map features
    updateMapFeatures()

    // Emit position update
    emit('update:drone-position', dronePosition.value)
    console.log(`Drone position updated from telemetry: ${latitude}, ${longitude}`)
  }

  // Function to update vehicle position from telemetry data
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

    // Center map on vehicle if following is enabled
    if (followVehicle.value) {
      centerMapOn([vehiclePosition.value.x, vehiclePosition.value.y])
    }

    // Update map features (but remove the problematic setStyle() call)
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

    // Update distance label by setting a new style
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

  const initMap = () => {
    vectorSource = new VectorSource()

    vectorLayer = new VectorLayer({
      source: vectorSource,
      style (feature) {
        const type = feature.get('type')
                 if (type === 'waypoint') {
                   const isVisited = feature.get('isVisited')
                   const isCurrent = feature.get('isCurrent')

                   let fillColor = 'rgba(255, 255, 255, 0.6)'
                   let strokeColor = '#6c757d' // Grey for pending
                   let radius = 6
                   let zIndex = 10

                   if (isVisited) {
                     fillColor = 'rgba(40, 167, 69, 0.8)' // Green
                     strokeColor = '#1a7431'
                     zIndex = 5
                   } else if (isCurrent) {
                     fillColor = 'rgba(255, 193, 7, 0.9)' // Yellow
                     strokeColor = '#b38600'
                   }
                 } else


        if (type === 'drone') {
          // Different styling based on telemetry connection
          let color = props.isDroneConnected ? '#2ecc71' : '#3498db'
          let strokeColor = props.isDroneConnected ? 'rgba(46, 204, 113, 0.5)' : 'rgba(52, 152, 219, 0.5)'

          // Override style if the drone is in safety-follow mode
          if (props.isDroneFollowing) {
            color = '#f39c12' // Warning orange
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
            // Optional: Add a circle behind the icon for better visibility
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
          const headingInRadians = (heading *  Math.PI) / 180
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
            // Optional: Add a circle behind the icon for better visibility
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
        } else if (type === 'distance-label') {
          return new Style({
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
          })
        }
      },
    })

    // Create different map layers
    osmLayer = new TileLayer({
      source: new OSM(),
      visible: true,
    })

    // Using Google Satellite tiles (you can replace with other providers)
    satelliteLayer = new TileLayer({
      source: new XYZ({
        url: 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        maxZoom: 40,
      }),
      visible: false,
    })

    // Hybrid labels layer (roads, labels, etc. over satellite)
    hybridLabelsLayer = new TileLayer({
      source: new XYZ({
        url: 'https://mt1.google.com/vt/lyrs=h&x={x}&y={y}&z={z}',
        maxZoom: 40,
      }),
      visible: false,
    })

    map = new Map({
      target: mapElement.value,
      layers: [
        osmLayer,
        satelliteLayer,
        hybridLabelsLayer,
        vectorLayer,
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
    let userInteracting = false

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

      // Disable following when user interacts with map
      userInteracting = true
      followVehicle.value = false
      followDrone.value = false
    })

    map.on('pointerup', function () {
      selectedFeature = null
      userInteracting = false
    })

    // Disable following when user pans the map
    map.on('movestart', function () {
      if (!userInteracting) return // Only disable if user initiated the move
      followVehicle.value = false
      followDrone.value = false
    })

    map.on('moveend', function () {
      const center = map.getView().getCenter()
      const lonLat = toLonLat(center)
      currentPosition.value = {
        lng: lonLat[0],
        lat: lonLat[1],
      }
      emit('update:current-position', currentPosition.value)
    })

    // Initial update
    updateMapFeatures()
  }

  // Watch for drone telemetry data changes
  watch(() => props.droneTelemetryData, (newTelemetry) => {
    console.log('Drone telemetry data changed:', newTelemetry)
    if (newTelemetry && dronePositionAvailable.value) {
      updateDroneFromTelemetry()
      // Disable manual control when telemetry is active
      manualControl.value = false
    }
  }, { deep: true })

  // Watch for vehicle telemetry data changes
  watch(() => props.vehicleTelemetryData, (newTelemetry) => {
    console.log('Vehicle telemetry data changed:', newTelemetry)
    if (newTelemetry && vehiclePositionAvailable.value) {
      updateVehicleFromTelemetry()
      // Disable manual control when telemetry is active
      manualControl.value = false
    }
  }, { deep: true })

  // Updated manual control computed property
  const isManualControlEnabled = computed(() => {
    return manualControl.value && !props.isDroneConnected && !props.isVehicleConnected
  })

  // Watch for changes in distance prop
  watch(() => props.distance, () => {
    updateMapFeatures()
  })

  // Watch for changes in the following status to redraw the map
  watch(() => props.isDroneFollowing, () => {
    if (vectorSource) {
      vectorSource.changed(); // This forces the style function to re-run
    }
  });

  onMounted(() => {
    initMap()
  })

  onUnmounted(() => {
    // Map instance is automatically cleaned up by OpenLayers
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

.control-buttons {
  position: fixed;
  bottom: 30px;
  left: 50%;
  transform: translateX(-50%);
  z-index: 2000;
}

.button-container {
  display: flex;
  gap: 16px;
  background-color: rgba(255, 255, 255, 0.95);
  padding: 16px 24px;
  border-radius: 30px;
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.2);
  backdrop-filter: blur(10px);
}
</style>
