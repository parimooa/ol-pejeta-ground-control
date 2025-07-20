<template>
  <div class="map-container flex-grow-1">
    <div ref="mapElement" class="map" />

    <div class="map-controls">
      <div class="coordinates pa-2">
        Lat: {{ formatCoordinate(currentPosition.lat, 'lat') }},
        Long: {{ formatCoordinate(currentPosition.lng, 'lng') }}
      </div>

    </div>
  </div>
</template>

<script>
  import { onMounted, ref, watch } from 'vue'
  import Map from 'ol/Map'
  import View from 'ol/View'
  import TileLayer from 'ol/layer/Tile'
  import OSM from 'ol/source/OSM'
  import { fromLonLat } from 'ol/proj'
  import Feature from 'ol/Feature'
  import Point from 'ol/geom/Point'
  import LineString from 'ol/geom/LineString'
  import Circle from 'ol/geom/Circle'
  import { Vector as VectorLayer } from 'ol/layer'
  import { Vector as VectorSource } from 'ol/source'
  import { Circle as CircleStyle, Fill, Stroke, Style, Text } from 'ol/style'

  export default {
    props: {
      currentPosition: {
        type: Object,
        required: true,
      },
      distance: {
        type: Number,
        required: true,
      },
    },


    setup (props) {
      // Map reference
      const mapElement = ref(null)
      let map = null

      // Map layers
      let droneFeature = null
      let vehicleFeature = null
      let safetyRadiusFeature = null
      let distanceLineFeature = null
      let distanceLabelFeature = null
      let vectorSource = null
      let vectorLayer = null

      // Position tracking
      const dronePosition = ref({ x: 0, y: 0 })
      const vehiclePosition = ref({ x: 0, y: 0 })

      // Search
      const searchQuery = ref('')

      // Format coordinates for display
      const formatCoordinate = (value, type) => {
        const absValue = Math.abs(value)
        const degrees = Math.floor(absValue)
        const minutes = Math.floor((absValue - degrees) * 60)
        const seconds = ((absValue - degrees - minutes/60) * 3600).toFixed(2)

        let direction = ''
        if (type === 'lat') {
          direction = value >= 0 ? ' N' : ' S'
        } else {
          direction = value >= 0 ? ' E' : ' W'
        }

        return `${degrees}° ${minutes}' ${seconds}"${direction}`
      }

      // Update distance and status
      const updateDistanceAndStatus = () => {
        // Calculate distance between drone and vehicle
        const dx = vehiclePosition.value.x - dronePosition.value.x
        const dy = vehiclePosition.value.y - dronePosition.value.y
        const distancePixels = Math.sqrt(dx * dx + dy * dy)

        // Update map features if they exist
        if (map && vectorSource) {
          updateMapFeatures()
        }
      }

      // Initialize OpenLayers map
      const initMap = () => {
        // Create vector source for features
        vectorSource = new VectorSource()

        // Create vector layer
        vectorLayer = new VectorLayer({
          source: vectorSource,
          style (feature) {
            const type = feature.get('type')

            if (type === 'drone') {
              return new Style({
                image: new CircleStyle({
                  radius: 10,
                  fill: new Fill({
                    color: '#3498db',
                  }),
                  stroke: new Stroke({
                    color: 'rgba(52, 152, 219, 0.5)',
                    width: 3,
                  }),
                }),
                text: new Text({
                  text: 'D',
                  fill: new Fill({
                    color: 'white',
                  }),
                  font: 'bold 12px sans-serif',
                }),
              })
            } else if (type === 'vehicle') {
              return new Style({
                image: new CircleStyle({
                  radius: 8,
                  fill: new Fill({
                    color: '#e74c3c',
                  }),
                  stroke: new Stroke({
                    color: 'rgba(231, 76, 60, 0.5)',
                    width: 30,
                  }),
                }),
                text: new Text({
                  text: 'V',
                  fill: new Fill({
                    color: 'white',
                  }),
                  font: 'bold 12px sans-serif',
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

        // Create the map
        map = new Map({
          target: mapElement.value,
          layers: [
            new TileLayer({
              source: new OSM(),
            }),
            vectorLayer,
          ],
          view: new View({
            center: fromLonLat([-122.4194, 37.7749]), // San Francisco
            zoom: 15,
          }),
        })

        // Initialize features
        const center = map.getView().getCenter()

        dronePosition.value = {
          x: center[0] - 500,
          y: center[1] - 500,
        }

        vehiclePosition.value = {
          x: center[0] + 500,
          y: center[1] + 500,
        }

        // Create map features
        droneFeature = new Feature({
          geometry: new Point([dronePosition.value.x, dronePosition.value.y]),
          type: 'drone',
        })

        vehicleFeature = new Feature({
          geometry: new Point([vehiclePosition.value.x, vehiclePosition.value.y]),
          type: 'vehicle',
        })

        // Safety radius (100m = arbitrary pixel value for visualization)
        safetyRadiusFeature = new Feature({
          geometry: new Circle([dronePosition.value.x, dronePosition.value.y], 200),
          type: 'safety-radius',
        })

        // Distance line
        distanceLineFeature = new Feature({
          geometry: new LineString([
            [dronePosition.value.x, dronePosition.value.y],
            [vehiclePosition.value.x, vehiclePosition.value.y],
          ]),
          type: 'distance-line',
        })

        // Distance label
        const midPoint = [
          (dronePosition.value.x + vehiclePosition.value.x) / 2,
          (dronePosition.value.y + vehiclePosition.value.y) / 2,
        ]

        distanceLabelFeature = new Feature({
          geometry: new Point(midPoint),
          type: 'distance-label',
        })

        // Add features to source
        vectorSource.addFeatures([
          droneFeature,
          vehicleFeature,
          safetyRadiusFeature,
          distanceLineFeature,
          distanceLabelFeature,
        ])

        // Map click handler for dragging objects in demo
        let selectedFeature = null

        map.on('pointermove', function (e) {
          if (selectedFeature) {
            const coords = e.coordinate

            if (selectedFeature === droneFeature) {
              dronePosition.value = { x: coords[0], y: coords[1] }
              droneFeature.getGeometry().setCoordinates(coords)
              safetyRadiusFeature.getGeometry().setCenter(coords)
            } else if (selectedFeature === vehicleFeature) {
              vehiclePosition.value = { x: coords[0], y: coords[1] }
              vehicleFeature.getGeometry().setCoordinates(coords)
            }

            updateDistanceAndStatus()
          }
        })

        map.on('pointerdown', function (e) {
          map.forEachFeatureAtPixel(e.pixel, function (feature) {
            if (feature === droneFeature || feature === vehicleFeature) {
              selectedFeature = feature
              return true
            }
          })
        })

        map.on('pointerup', function () {
          selectedFeature = null
        })

        // Initial distance calculation
        updateDistanceAndStatus()
      }

      // Update map features based on drone and vehicle positions
      const updateMapFeatures = () => {
        // Update drone and vehicle positions
        droneFeature.getGeometry().setCoordinates([dronePosition.value.x, dronePosition.value.y])
        vehicleFeature.getGeometry().setCoordinates([vehiclePosition.value.x, vehiclePosition.value.y])

        // Update safety radius
        safetyRadiusFeature.getGeometry().setCenter([dronePosition.value.x, dronePosition.value.y])

        // Update distance line
        distanceLineFeature.getGeometry().setCoordinates([
          [dronePosition.value.x, dronePosition.value.y],
          [vehiclePosition.value.x, vehiclePosition.value.y],
        ])

        // Update distance label
        const midPoint = [
          (dronePosition.value.x + vehiclePosition.value.x) / 2,
          (dronePosition.value.y + vehiclePosition.value.y) / 2,
        ]
        distanceLabelFeature.getGeometry().setCoordinates(midPoint)

        // Refresh vector layer
        vectorSource.changed()
      }

      // Watch for distance changes to update the label
      watch(() => props.distance, () => {
        if (distanceLabelFeature) {
          vectorSource.changed(); // Refresh to update the distance label
        }
      });

      // Initialize map when component is mounted
      onMounted(() => {
        initMap()
      })

      return {
        mapElement,
        searchQuery,
        formatCoordinate,
      }
    },
  }
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

.search-container {
  background-color: white;
  border-radius: 20px;
  box-shadow: 0 2px 5px rgba(0, 0, 0, 0.1);
  margin-bottom: 10px;
  max-width: 250px;
}

.control-buttons {
  position: absolute;
  bottom: 20px;
  left: 20px;
}
</style>
