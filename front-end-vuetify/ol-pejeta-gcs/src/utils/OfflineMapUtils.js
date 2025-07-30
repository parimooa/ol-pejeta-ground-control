/**
 * OfflineMapUtils.js
 * Utilities for handling offline map functionality in OpenLayers
 */

import { fromLonLat, toLonLat } from 'ol/proj'
import { getTopLeft, getWidth } from 'ol/extent'
import TileSource from 'ol/source/Tile'
import XYZ from 'ol/source/XYZ'
import OSM from 'ol/source/OSM'

// Database name and version
const DB_NAME = 'ol-pejeta-map-tiles'
const DB_VERSION = 1

// Store names for different map types
const STORE_NAMES = {
  osm: 'osm-tiles',
  satellite: 'satellite-tiles',
  hybrid: 'hybrid-tiles',
}

// Ol Pejeta Conservancy coordinates and default zoom levels
const OL_PEJETA_CENTER = [36.9759, 0.0078]
const DEFAULT_MIN_ZOOM = 12
const DEFAULT_MAX_ZOOM = 18

/**
 * Initialize the IndexedDB database for storing map tiles
 * @returns {Promise} Promise that resolves when the database is ready
 */
export function initTileDatabase () {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION)

    request.onerror = event => {
      console.error('Error opening IndexedDB:', event.target.error)
      reject(event.target.error)
    }

    request.onupgradeneeded = event => {
      const db = event.target.result

      // Create object stores for each map type if they don't exist
      if (!db.objectStoreNames.contains(STORE_NAMES.osm)) {
        db.createObjectStore(STORE_NAMES.osm, { keyPath: 'tileKey' })
      }

      if (!db.objectStoreNames.contains(STORE_NAMES.satellite)) {
        db.createObjectStore(STORE_NAMES.satellite, { keyPath: 'tileKey' })
      }

      if (!db.objectStoreNames.contains(STORE_NAMES.hybrid)) {
        db.createObjectStore(STORE_NAMES.hybrid, { keyPath: 'tileKey' })
      }
    }

    request.onsuccess = event => {
      const db = event.target.result
      resolve(db)
    }
  })
}

/**
 * Store a tile in IndexedDB
 * @param {string} mapType - The map type (osm, satellite, hybrid)
 * @param {string} tileKey - The unique key for the tile (z/x/y)
 * @param {Blob} tileBlob - The tile image as a Blob
 * @returns {Promise} Promise that resolves when the tile is stored
 */
export function storeTile (mapType, tileKey, tileBlob) {
  return new Promise((resolve, reject) => {
    initTileDatabase().then(db => {
      const transaction = db.transaction([STORE_NAMES[mapType]], 'readwrite')
      const store = transaction.objectStore(STORE_NAMES[mapType])

      const request = store.put({
        tileKey,
        blob: tileBlob,
        timestamp: Date.now(),
      })

      request.onsuccess = () => resolve()
      request.onerror = event => reject(event.target.error)
    }).catch(reject)
  })
}

/**
 * Get a tile from IndexedDB
 * @param {string} mapType - The map type (osm, satellite, hybrid)
 * @param {string} tileKey - The unique key for the tile (z/x/y)
 * @returns {Promise<Blob>} Promise that resolves with the tile blob or null if not found
 */
export function getTile (mapType, tileKey) {
  return new Promise((resolve, reject) => {
    initTileDatabase().then(db => {
      const transaction = db.transaction([STORE_NAMES[mapType]], 'readonly')
      const store = transaction.objectStore(STORE_NAMES[mapType])

      const request = store.get(tileKey)

      request.onsuccess = () => {
        if (request.result) {
          resolve(request.result.blob)
        } else {
          resolve(null)
        }
      }

      request.onerror = event => reject(event.target.error)
    }).catch(reject)
  })
}

/**
 * Clear all stored tiles for a specific map type
 * @param {string} mapType - The map type (osm, satellite, hybrid)
 * @returns {Promise} Promise that resolves when the tiles are cleared
 */
export function clearTiles (mapType) {
  return new Promise((resolve, reject) => {
    initTileDatabase().then(db => {
      const transaction = db.transaction([STORE_NAMES[mapType]], 'readwrite')
      const store = transaction.objectStore(STORE_NAMES[mapType])

      const request = store.clear()

      request.onsuccess = () => resolve()
      request.onerror = event => reject(event.target.error)
    }).catch(reject)
  })
}

/**
 * Count the number of stored tiles for a specific map type
 * @param {string} mapType - The map type (osm, satellite, hybrid)
 * @returns {Promise<number>} Promise that resolves with the count
 */
export function countTiles (mapType) {
  return new Promise((resolve, reject) => {
    initTileDatabase().then(db => {
      const transaction = db.transaction([STORE_NAMES[mapType]], 'readonly')
      const store = transaction.objectStore(STORE_NAMES[mapType])

      const request = store.count()

      request.onsuccess = () => resolve(request.result)
      request.onerror = event => reject(event.target.error)
    }).catch(reject)
  })
}

/**
 * Create a custom XYZ source that supports offline caching
 * @param {Object} options - Options for the tile source
 * @returns {XYZ} The custom XYZ source
 */
export function createOfflineXYZSource (options) {
  const { url, mapType, maxZoom = 19 } = options

  const source = new XYZ({
    url,
    maxZoom,
    crossOrigin: 'anonymous',
    tileLoadFunction: (tile, src) => {
      const tileCoord = tile.getTileCoord()
      const z = tileCoord[0]
      const x = tileCoord[1]
      const y = tileCoord[2]
      const tileKey = `${z}/${x}/${y}`

      // Try to load the tile from IndexedDB first
      getTile(mapType, tileKey).then(blob => {
        if (blob) {
          // If the tile is in the cache, use it
          const url = URL.createObjectURL(blob)
          tile.getImage().src = url
        } else {
          // Otherwise, load it from the network and cache it
          const xhr = new XMLHttpRequest()
          xhr.open('GET', src, true)
          xhr.responseType = 'blob'

          xhr.onload = () => {
            if (xhr.status === 200) {
              const blob = xhr.response
              // Store the tile in IndexedDB
              storeTile(mapType, tileKey, blob).catch(err => {
                console.error('Error storing tile:', err)
              })

              const url = URL.createObjectURL(blob)
              tile.getImage().src = url
            } else {
              tile.getImage().src = ''
            }
          }

          xhr.onerror = () => {
            tile.getImage().src = ''
          }

          xhr.send()
        }
      }).catch(err => {
        console.error('Error getting tile from cache:', err)
        // Fall back to normal loading
        tile.getImage().src = src
      })
    },
  })

  return source
}

/**
 * Create a custom OSM source that supports offline caching
 * @returns {OSM} The custom OSM source
 */
export function createOfflineOSMSource () {
  const source = new OSM({
    crossOrigin: 'anonymous',
    tileLoadFunction: (tile, src) => {
      const tileCoord = tile.getTileCoord()
      const z = tileCoord[0]
      const x = tileCoord[1]
      const y = tileCoord[2]
      const tileKey = `${z}/${x}/${y}`

      // Try to load the tile from IndexedDB first
      getTile('osm', tileKey).then(blob => {
        if (blob) {
          // If the tile is in the cache, use it
          const url = URL.createObjectURL(blob)
          tile.getImage().src = url
        } else {
          // Otherwise, load it from the network and cache it
          const xhr = new XMLHttpRequest()
          xhr.open('GET', src, true)
          xhr.responseType = 'blob'

          xhr.onload = () => {
            if (xhr.status === 200) {
              const blob = xhr.response
              // Store the tile in IndexedDB
              storeTile('osm', tileKey, blob).catch(err => {
                console.error('Error storing tile:', err)
              })

              const url = URL.createObjectURL(blob)
              tile.getImage().src = url
            } else {
              tile.getImage().src = ''
            }
          }

          xhr.onerror = () => {
            tile.getImage().src = ''
          }

          xhr.send()
        }
      }).catch(err => {
        console.error('Error getting tile from cache:', err)
        // Fall back to normal loading
        tile.getImage().src = src
      })
    },
  })

  return source
}

/**
 * Calculate the number of tiles in a given area and zoom range
 * @param {Array} extent - The extent [minX, minY, maxX, maxY] in EPSG:3857
 * @param {number} minZoom - The minimum zoom level
 * @param {number} maxZoom - The maximum zoom level
 * @returns {number} The number of tiles
 */
function calculateTileCount (extent, minZoom, maxZoom) {
  let count = 0

  for (let z = minZoom; z <= maxZoom; z++) {
    const resolution = getWidth(extent) / 256 / Math.pow(2, z)
    const tileSize = 256 * resolution

    const minX = Math.floor((extent[0] - getTopLeft(extent)[0]) / tileSize)
    const maxX = Math.ceil((extent[2] - getTopLeft(extent)[0]) / tileSize)

    const minY = Math.floor((getTopLeft(extent)[1] - extent[3]) / tileSize)
    const maxY = Math.ceil((getTopLeft(extent)[1] - extent[1]) / tileSize)

    const tilesX = maxX - minX
    const tilesY = maxY - minY

    count += tilesX * tilesY
  }

  return count
}

/**
 * Download map tiles for offline use
 * @param {Object} options - Options for downloading tiles
 * @param {string} options.mapType - The map type (osm, satellite, hybrid)
 * @param {Array} options.center - The center coordinates [longitude, latitude]
 * @param {number} options.radius - The radius in kilometers
 * @param {number} options.minZoom - The minimum zoom level
 * @param {number} options.maxZoom - The maximum zoom level
 * @param {Function} options.progressCallback - Callback for download progress
 * @returns {Promise} Promise that resolves when all tiles are downloaded
 */
export function downloadMapTiles (options) {
  const {
    mapType,
    center = OL_PEJETA_CENTER,
    radius = 5, // 5km radius
    minZoom = DEFAULT_MIN_ZOOM,
    maxZoom = DEFAULT_MAX_ZOOM,
    progressCallback = () => {},
  } = options

  return new Promise((resolve, reject) => {
    try {
      // Convert center to EPSG:3857
      const centerCoord = fromLonLat(center)

      // Calculate extent based on center and radius
      const radiusInMeters = radius * 1000
      const extent = [
        centerCoord[0] - radiusInMeters,
        centerCoord[1] - radiusInMeters,
        centerCoord[0] + radiusInMeters,
        centerCoord[1] + radiusInMeters,
      ]

      // Calculate total number of tiles
      const totalTiles = calculateTileCount(extent, minZoom, maxZoom)
      let downloadedTiles = 0

      // Create appropriate source based on map type
      let source
      if (mapType === 'osm') {
        source = new OSM()
      } else if (mapType === 'satellite') {
        source = new XYZ({
          url: 'https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}',
        })
      } else if (mapType === 'hybrid') {
        source = new XYZ({
          url: 'https://mt1.google.com/vt/lyrs=h&x={x}&y={y}&z={z}',
        })
      } else {
        throw new Error(`Unknown map type: ${mapType}`)
      }

      // Download tiles for each zoom level
      const promises = []

      for (let z = minZoom; z <= maxZoom; z++) {
        const resolution = getWidth(extent) / 256 / Math.pow(2, z)
        const tileSize = 256 * resolution

        const minX = Math.floor((extent[0] - getTopLeft(extent)[0]) / tileSize)
        const maxX = Math.ceil((extent[2] - getTopLeft(extent)[0]) / tileSize)

        const minY = Math.floor((getTopLeft(extent)[1] - extent[3]) / tileSize)
        const maxY = Math.ceil((getTopLeft(extent)[1] - extent[1]) / tileSize)

        for (let x = minX; x < maxX; x++) {
          for (let y = minY; y < maxY; y++) {
            const tileUrl = source.tileUrlFunction([z, x, y])
            const tileKey = `${z}/${x}/${y}`

            const promise = new Promise(resolveTile => {
              // Check if tile already exists in cache
              getTile(mapType, tileKey).then(blob => {
                if (blob) {
                  // Tile already exists, skip download
                  downloadedTiles++
                  progressCallback(downloadedTiles, totalTiles)
                  resolveTile()
                } else {
                  // Download tile
                  const xhr = new XMLHttpRequest()
                  xhr.open('GET', tileUrl, true)
                  xhr.responseType = 'blob'

                  xhr.onload = () => {
                    if (xhr.status === 200) {
                      const blob = xhr.response
                      // Store tile in IndexedDB
                      storeTile(mapType, tileKey, blob)
                        .then(() => {
                          downloadedTiles++
                          progressCallback(downloadedTiles, totalTiles)
                          resolveTile()
                        })
                        .catch(err => {
                          console.error('Error storing tile:', err)
                          resolveTile()
                        })
                    } else {
                      downloadedTiles++
                      progressCallback(downloadedTiles, totalTiles)
                      resolveTile()
                    }
                  }

                  xhr.onerror = () => {
                    downloadedTiles++
                    progressCallback(downloadedTiles, totalTiles)
                    resolveTile()
                  }

                  xhr.send()
                }
              }).catch(() => {
                downloadedTiles++
                progressCallback(downloadedTiles, totalTiles)
                resolveTile()
              })
            })

            promises.push(promise)
          }
        }
      }

      // Wait for all tiles to be downloaded
      Promise.all(promises).then(() => {
        resolve({
          mapType,
          totalTiles,
          downloadedTiles,
        })
      }).catch(reject)
    } catch (error) {
      reject(error)
    }
  })
}

/**
 * Check if the device is currently offline
 * @returns {boolean} True if offline, false if online
 */
export function isOffline () {
  return !navigator.onLine
}

/**
 * Add event listeners for online/offline status changes
 * @param {Function} onlineCallback - Callback when device goes online
 * @param {Function} offlineCallback - Callback when device goes offline
 */
export function addConnectivityListeners (onlineCallback, offlineCallback) {
  window.addEventListener('online', onlineCallback)
  window.addEventListener('offline', offlineCallback)
}

/**
 * Remove event listeners for online/offline status changes
 * @param {Function} onlineCallback - The online callback to remove
 * @param {Function} offlineCallback - The offline callback to remove
 */
export function removeConnectivityListeners (onlineCallback, offlineCallback) {
  window.removeEventListener('online', onlineCallback)
  window.removeEventListener('offline', offlineCallback)
}
