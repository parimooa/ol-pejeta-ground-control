// Coordinate validation utilities
export class CoordinateValidator {
  static isValidLatitude (lat) {
    return lat != null && !isNaN(lat) && Math.abs(lat) <= 90
  }

  static isValidLongitude (lon) {
    return lon != null && !isNaN(lon) && Math.abs(lon) <= 180
  }

  static isValidCoordinate (coord) {
    return coord && Array.isArray(coord) && coord.length >= 2 &&
           isFinite(coord[0]) && isFinite(coord[1])
  }

  static isValidWaypoint (waypoint) {
    return waypoint &&
           this.isValidLatitude(waypoint.lat) &&
           this.isValidLongitude(waypoint.lon)
  }

  static filterValidWaypoints (waypoints) {
    if (!Array.isArray(waypoints)) return []

    return waypoints.filter(wp => this.isValidWaypoint(wp))
  }

  static filterValidCoordinates (coordinates) {
    if (!Array.isArray(coordinates)) return []

    return coordinates.filter(coord => this.isValidCoordinate(coord))
  }

  static validateWaypointsForPolygon (waypoints, minPoints = 3) {
    const validWaypoints = this.filterValidWaypoints(waypoints)

    if (validWaypoints.length < minPoints) {
      console.warn(`Not enough valid waypoints to form polygon. Need ${minPoints}, got ${validWaypoints.length}`)
      return { isValid: false, validWaypoints: [] }
    }

    return { isValid: true, validWaypoints }
  }

  static validateCoordinatesForPolygon (coordinates, minPoints = 3) {
    const validCoordinates = this.filterValidCoordinates(coordinates)

    if (validCoordinates.length < minPoints) {
      console.warn(`Not enough valid coordinates after conversion. Need ${minPoints}, got ${validCoordinates.length}`)
      return { isValid: false, validCoordinates: [] }
    }

    return { isValid: true, validCoordinates }
  }

  static logValidationWarning (message, data = null) {
    console.warn(message, data ? data : '')
  }
}
