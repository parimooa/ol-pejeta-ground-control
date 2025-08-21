// Centralized configuration constants for the Ol Pejeta Ground Control System

// Distance thresholds (in meters)
export const DISTANCE_CONSTANTS = {
  WARNING_THRESHOLD: 400,     // Distance at which warning is shown
  MAX_SAFE_DISTANCE: 490,     // Maximum safe operating distance
  CRITICAL_THRESHOLD: 500,    // Critical distance requiring immediate action
}

// Connection and networking settings
export const CONNECTION_CONSTANTS = {
  TIMEOUT: 5000,              // Connection timeout in milliseconds
  CHECK_INTERVAL: 5000,       // Interval for connection status checks
  HEARTBEAT_TO_MS: 1000,      // Multiplier to convert heartbeat seconds to milliseconds
  WS_RECONNECT_BASE_DELAY: 1000,  // Base delay for WebSocket reconnection
  WS_RECONNECT_MAX_DELAY: 10000,  // Maximum delay for WebSocket reconnection
  DISCONNECT_DELAY: 2000,     // Delay after disconnection operations
}

// API configuration
export const API_CONSTANTS = {
  BASE_URL: 'http://localhost:8000',
  WEBSOCKET_URL: 'ws://127.0.0.1:8000',
  PROXY_PREFIX: '/api',       // For Vite proxy configuration
}

// Animation and timing constants
export const TIMING_CONSTANTS = {
  MAP_FIT_DURATION: 500,      // Duration for map fit animations
  SURVEY_COMPLETION_DELAY: 3000,  // Delay after survey completion
  FOLLOW_UPDATE_THROTTLE: 100,    // Throttle for map follow updates
  STARTUP_DELAY: 1000,        // General startup delay for various operations
}

// Survey operation constants
export const SURVEY_CONSTANTS = {
  GRID_SPACING_SMALL: 25,     // Grid spacing for small survey areas (meters)
  GRID_SPACING_LARGE: 50,     // Grid spacing for large survey areas (meters)
  AREA_SIZE_THRESHOLD: 500,   // Threshold to determine small vs large areas
  SAFETY_RADIUS: 500,         // Safety radius for survey operations (meters)
  MAX_SURVEY_LINES: 50,       // Maximum number of survey lines to generate
  DEFAULT_CIRCLE_RADIUS: 500, // Default radius for circular survey areas
}

// Physical and mathematical constants
export const PHYSICAL_CONSTANTS = {
  EARTH_RADIUS_METERS: 6371000,  // Earth's radius in meters for distance calculations
}

// WebSocket close codes
export const WEBSOCKET_CONSTANTS = {
  NORMAL_CLOSURE: 1000,       // Normal WebSocket closure code
}

// Map and visualization constants  
export const MAP_CONSTANTS = {
  TILE_SIZE: 256,             // Standard tile size for mapping
  SAFETY_VISUALIZATION_RADIUS: 200,  // Radius for safety circle visualization
  MAP_EXTENT_OFFSET: 500,     // Offset for map extent calculations
}

// Compass component constants
export const COMPASS_CONSTANTS = {
  SIZE_DESKTOP: 120,          // Compass size in pixels for desktop
  SIZE_MOBILE: 100,           // Compass size in pixels for mobile
  NEEDLE_TRANSITION_MS: 300,  // Smooth transition duration for needle rotation
  UPDATE_THROTTLE_MS: 100,    // Throttle compass updates to prevent jitter
  CARDINAL_DIRECTIONS: ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE', 'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'],
  DEGREE_STEP: 22.5,          // Degrees per cardinal direction step
}

// HTTP status codes
export const HTTP_CONSTANTS = {
  OK: 200,                    // HTTP OK status
}