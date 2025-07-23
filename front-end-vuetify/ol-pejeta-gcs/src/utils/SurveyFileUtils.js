/**
 * SurveyFileUtils.js
 * Utilities for handling file-based survey storage
 */

// Survey storage configuration
const SURVEY_API_BASE = 'http://localhost:8000'

/**
 * Generate a filename for a survey based on site name, waypoint number, and timestamp
 * Format: <site-name>_<waypoint-no>_DD-MM-YY_HH-MM-SS.json
 * @param {string} siteName - The site name (e.g., "Site Ol Pejeta")
 * @param {number} waypointNumber - The closest waypoint number
 * @param {Date} timestamp - The timestamp for the survey
 * @returns {string} The generated filename
 */
export function generateSurveyFilename(siteName, waypointNumber, timestamp = new Date()) {
  // Clean site name (remove spaces, special characters)
  const cleanSiteName = siteName.replace(/\s+/g, '-').replace(/[^a-zA-Z0-9-]/g, '').toLowerCase()

  // Format timestamp as DD-MM-YY_HH-MM-SS
  const day = String(timestamp.getDate()).padStart(2, '0')
  const month = String(timestamp.getMonth() + 1).padStart(2, '0')
  const year = String(timestamp.getFullYear()).slice(-2)
  const hours = String(timestamp.getHours()).padStart(2, '0')
  const minutes = String(timestamp.getMinutes()).padStart(2, '0')
  const seconds = String(timestamp.getSeconds()).padStart(2, '0')

  // --- START OF FIX ---
  // Replaced colons with hyphens for cross-platform compatibility.
  // Example: 10:30:55 becomes 10-30-55
  const timestampStr = `${day}-${month}-${year}_${hours}-${minutes}-${seconds}`
  // --- END OF FIX ---

  return `${cleanSiteName}_${waypointNumber}_${timestampStr}.json`
}

/**
 * Find the closest waypoint to the current vehicle position
 * @param {Array} waypoints - Array of waypoints with lat, lon, seq properties
 * @param {Object} vehiclePosition - Vehicle position with lat, lon properties
 * @returns {number} The sequence number of the closest waypoint
 */
export function findClosestWaypoint(waypoints, vehiclePosition) {
  if (!waypoints || waypoints.length === 0 || !vehiclePosition) {
    return 1 // Default to waypoint 1
  }

  let closestWaypoint = waypoints[0]
  let shortestDistance = calculateDistance(
    vehiclePosition.lat, vehiclePosition.lon,
    closestWaypoint.lat, closestWaypoint.lon
  )

  for (const waypoint of waypoints) {
    const distance = calculateDistance(
      vehiclePosition.lat, vehiclePosition.lon,
      waypoint.lat, waypoint.lon
    )

    if (distance < shortestDistance) {
      shortestDistance = distance
      closestWaypoint = waypoint
    }
  }

  return closestWaypoint.seq + 1 // Return 1-indexed waypoint number
}

/**
 * Calculate distance between two GPS coordinates using Haversine formula
 * @param {number} lat1 - Latitude of first point
 * @param {number} lon1 - Longitude of first point
 * @param {number} lat2 - Latitude of second point
 * @param {number} lon2 - Longitude of second point
 * @returns {number} Distance in meters
 */
function calculateDistance(lat1, lon1, lat2, lon2) {
  const R = 6371000 // Earth's radius in meters
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

/**
 * Save a survey to file-based storage via backend API
 * @param {Object} surveyData - The survey data to save
 * @param {string} filename - The filename to save as
 * @returns {Promise} Promise that resolves when the survey is saved
 */
export async function saveSurveyToFile(surveyData, filename) {
  try {
    const response = await fetch(`${SURVEY_API_BASE}/survey/save`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        filename: filename,
        data: surveyData
      })
    })

    if (!response.ok) {
      // Try to get more detailed error from backend
      const errorBody = await response.json().catch(() => ({ detail: response.statusText }))
      throw new Error(`Failed to save survey: ${errorBody.detail || response.statusText}`)
    }

    const result = await response.json()
    console.log(`Survey saved successfully: ${filename}`)
    return result
  } catch (error) {
    console.error('Error saving survey to file:', error)
    throw error
  }
}

/**
 * Load all saved surveys from file-based storage via backend API
 * @returns {Promise<Array>} Promise that resolves with array of survey data
 */
export async function loadSurveysFromFiles() {
  try {
    const response = await fetch(`${SURVEY_API_BASE}/survey/load`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    })

    if (!response.ok) {
      throw new Error(`Failed to load surveys: ${response.statusText}`)
    }

    const surveys = await response.json()
    console.log(`Loaded ${surveys.length} surveys from files`)
    return surveys
  } catch (error) {
    console.error('Error loading surveys from files:', error)
    // Fallback to localStorage if file system is not available
    return loadSurveysFromLocalStorage()
  }
}

/**
 * Fallback function to load surveys from localStorage
  * @returns {Array} Array of survey data from localStorage
 */
function loadSurveysFromLocalStorage() {
  try {
    const data = JSON.parse(localStorage.getItem('ol_pejeta_surveys') || '{}')
    return Object.values(data)
  } catch (error) {
    console.error('Error loading surveys from localStorage:', error)
    return []
  }
}

/**
 * Delete a survey file

/**
 * Delete a survey file via backend API
 * @param {string} filename - The filename to delete
 * @returns {Promise} Promise that resolves when the survey is deleted
 */
export async function deleteSurveyFile(filename) {
  try {
    const response = await fetch(`${SURVEY_API_BASE}/survey/delete`, {
      method: 'DELETE',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ filename })
    })

    if (!response.ok) {
      throw new Error(`Failed to delete survey: ${response.statusText}`)
    }

    console.log(`Survey deleted successfully: ${filename}`)
    return await response.json()
  } catch (error) {
    console.error('Error deleting survey file:', error)
    throw error
  }
}

/**
 * List all available survey files via backend API
 * @returns {Promise<Array>} Promise that resolves with array of filenames
 */
export async function listSurveyFiles() {
  try {
    const response = await fetch(`${SURVEY_API_BASE}/survey/list`, {
      method: 'GET',
      headers: {
        'Content-Type': 'application/json',
      }
    })

    if (!response.ok) {
      throw new Error(`Failed to list surveys: ${response.statusText}`)
    }

    const filenames = await response.json()
    console.log(`Found ${filenames.length} survey files`)
    return filenames
  } catch (error) {
    console.error('Error listing survey files:', error)
    return []
  }
}
