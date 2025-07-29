import { fromLonLat } from 'ol/proj'

// Consolidated follow functionality
export class MapFollowManager {
  constructor () {
    this.lastFollowUpdate = 0
    this.followUpdateThrottle = 100 // milliseconds between follow updates
    this.isUserInteracting = false
  }

  setUserInteracting (isInteracting) {
    this.isUserInteracting = isInteracting
  }

  centerMapOnPosition (map, coordinates, isFollowingEnabled) {
    if (!map || !isFollowingEnabled || this.isUserInteracting) return

    const now = Date.now()
    if (now - this.lastFollowUpdate < this.followUpdateThrottle) return

    this.lastFollowUpdate = now
    map.getView().setCenter(coordinates)
  }

  gpsToMapCoordinates (lat, lng) {
    return fromLonLat([lng, lat])
  }

  createFollowHandler (map, followRef, oppositeFollowRef) {
    return telemetryData => {
      if (!telemetryData?.position?.latitude || !telemetryData?.position?.longitude) return

      const { latitude, longitude } = telemetryData.position
      const mapCoords = this.gpsToMapCoordinates(latitude, longitude)

      if (followRef.value && !this.isUserInteracting) {
        this.centerMapOnPosition(map, mapCoords, true)
      }

      return { mapCoords, lat: latitude, lon: longitude }
    }
  }

  setupMapInteractionHandlers (map, followVehicleRef, followDroneRef) {
    const disableFollowing = () => {
      followVehicleRef.value = false
      followDroneRef.value = false
    }

    map.on('pointerdown', () => {
      this.setUserInteracting(true)
      disableFollowing()
    })

    map.on('pointerup', () => {
      setTimeout(() => {
        this.setUserInteracting(false)
      }, 1000)
    })

    map.on('movestart', evt => {
      if (evt.frameState && evt.frameState.viewHints[0] > 0) {
        this.setUserInteracting(true)
        disableFollowing()
      }
    })

    map.on('moveend', () => {
      setTimeout(() => {
        this.setUserInteracting(false)
      }, 500)
    })
  }

  createMutuallyExclusiveFollowWatcher (followRef, oppositeFollowRef, positionAvailable, telemetryData, map) {
    return isFollowing => {
      if (isFollowing) {
        oppositeFollowRef.value = false

        if (positionAvailable.value && map) {
          const coordinates = this.gpsToMapCoordinates(
            telemetryData.position.latitude,
            telemetryData.position.longitude
          )
          this.centerMapOnPosition(map, coordinates, true)
        }
      }
    }
  }
}
