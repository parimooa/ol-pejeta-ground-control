<template>
  <div class="map-container">
    <div ref="mapElement" class="map" />

    <div class="map-controls">
      <div class="coordinates pa-2">
        Lat: {{ formatCoordinate(currentPosition.lat, 'lat') }},
        Long: {{ formatCoordinate(currentPosition.lng, 'lng') }}
      </div>

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

      <!-- Telemetry status indicator -->
      <div v-if="telemetryData" class="telemetry-status pa-2">
        <v-chip
          :color="telemetryConnected ? 'green' : 'red'"
          prepend-icon="mdi-quadcopter"
          size="small"
          variant="flat"
        >
          {{ telemetryConnected ? ' Drone Telemetry Connected' : 'No Drone Telemetry' }}
        </v-chip>
      </div>

      <div v-if="telemetryData" class="telemetry-status pa-2">
        <v-chip
          :color="telemetryConnected ? 'green' : 'red'"
          prepend-icon="mdi-car-connected"
          size="small"
          variant="flat"
        >
          {{ telemetryConnected ? ' Vehicle Telemetry Connected' : 'No Vehicle Telemetry' }}
        </v-chip>
      </div>

      <div class="control-buttons">
        <div class="button-container">
          <v-btn
            class="mx-2"
            color="primary"
            prepend-icon="mdi-play"
            rounded="xl"
            variant="elevated"
            @click="handleStartMission('drone')"
          >
            Connect Drone
          </v-btn>
          <v-btn
            class="mx-2"
            color="error"
            prepend-icon="mdi-close"
            rounded="xl"
            variant="elevated"
            @click="handleEmergencyStop"
          >
            Emergency Stop (Drone)
          </v-btn>
          <v-btn
            class="mx-2"
            color="purple"
            prepend-icon="mdi-play"
            rounded="xl"
            variant="elevated"
            @click="handleStartMission('car')"
          >
            Connect Vehicle
          </v-btn>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
  import { computed, onMounted, ref, watch } from 'vue'
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
  import { Circle as CircleStyle, Fill, Icon, Stroke, Style,Text } from 'ol/style'

  import droneIcon from '@/assets/drone.png'
  import vehicleIcon from '@/assets/car.png'


  const props = defineProps({
    distance: {
      type: Number,
      required: true,
    },
    telemetryData: {
      type: Object,
      default: null,
    },
  })

  const emit = defineEmits([
    'update:current-position',
    'update:drone-position',
    'update:vehicle-position',
    'start-mission',
    'emergency-stop',
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

  const currentPosition = ref({ lat: 0.0078, lng: 36.9759 })
  const dronePosition = ref({ x: 0, y: 0 })
  const vehiclePosition = ref({ x: 0, y: 0 })
  const searchQuery = ref('')
  const manualControl = ref(true) // Toggle between manual and telemetry control
  const mapType = ref('osm') // 'osm', 'satellite', or 'hybrid'

  // Computed property to check if telemetry is connected
  const telemetryConnected = computed(() => {
    return props.telemetryData &&
      props.telemetryData.position.latitude &&
      props.telemetryData.position.longitude
  })

  // Add button handlers
  const handleStartMission = vehicleType => {
    console.log('MapContainer: Start Mission button clicked')
    emit('start-mission', vehicleType)
  }

  const handleEmergencyStop = () => {
    console.log('MapContainer: Emergency Stop button clicked')
    emit('emergency-stop')
  }

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

  // Function to update drone position from telemetry data
  const updateDroneFromTelemetry = () => {
    if (!props.telemetryData || !telemetryConnected.value || !droneFeature) {
      return
    }

    const { latitude, longitude } = props.telemetryData.position
    const mapCoords = gpsToMapCoordinates(latitude, longitude)

    // Update drone position
    dronePosition.value = { x: mapCoords[0], y: mapCoords[1] }
    vehiclePosition.value = { x: mapCoords[0], y: mapCoords[1] }
    // Disable manual control when telemetry is active
    manualControl.value = false

    // Update map features
    updateMapFeatures()

    // Emit position update
    emit('update:drone-position', dronePosition.value)
    emit('update:vehicle-position', vehiclePosition.value)
    console.log(`Drone position updated from telemetry: ${latitude}, ${longitude}`)
  }

  const updateMapFeatures = () => {
    if (!map || !vectorSource) return

    droneFeature.getGeometry().setCoordinates([dronePosition.value.x, dronePosition.value.y])
    // vehicleFeature.getGeometry().setCoordinates([vehiclePosition.value.x, vehiclePosition.value.y])

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
    distanceLabelFeature.getStyle().getText().setText(props.distance + 'm')

    vectorSource.changed()
  }

  const initMap = () => {
    vectorSource = new VectorSource()

    vectorLayer = new VectorLayer({
      source: vectorSource,
      style (feature) {
        const type = feature.get('type')

        if (type === 'drone') {
          // Different styling based on telemetry connection
          const color = telemetryConnected.value ? '#2ecc71' : '#3498db'
          const strokeColor = telemetryConnected.value ? 'rgba(46, 204, 113, 0.5)' : 'rgba(52, 152, 219, 0.5)'

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
          return new Style({
            image: new Icon({
              src: vehicleIcon,
              scale: 0.08,
              anchor: [0.5, 0.5],
              anchorXUnits: 'fraction',
              anchorYUnits: 'fraction',
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
        maxZoom: 20,
      }),
      visible: false,
    })

    // Hybrid labels layer (roads, labels, etc. over satellite)
    hybridLabelsLayer = new TileLayer({
      source: new XYZ({
        url: 'https://mt1.google.com/vt/lyrs=h&x={x}&y={y}&z={z}',
        maxZoom: 20,
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
        zoom: 15,
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
      if (selectedFeature && manualControl.value) {
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
      if (manualControl.value) {
        map.forEachFeatureAtPixel(e.pixel, function (feature) {
          if (feature === droneFeature || feature === vehicleFeature) {
            selectedFeature = feature
            return true
          }
        })
      }
    })

    map.on('pointerup', function () {
      selectedFeature = null
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

  // Watch for telemetry data changes
  watch(() => props.telemetryData, newTelemetry => {
    if (newTelemetry && newTelemetry.position.latitude && newTelemetry.position.longitude) {
      updateDroneFromTelemetry()
    }
  }, { deep: true })

  // Watch for changes in distance prop
  watch(() => props.distance, () => {
    updateMapFeatures()
  })

  onMounted(() => {
    initMap()
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

.telemetry-status {
  display: inline-block;
  margin-left: 11px;
  margin-bottom: 15px;
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
