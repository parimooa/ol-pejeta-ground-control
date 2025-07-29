import { Circle as CircleStyle, Fill, Icon, Stroke, Style, Text } from 'ol/style'

// Map type configurations
export const MAP_TYPE_CONFIGS = {
  osm: {
    title: 'Standard Map',
    icon: 'mdi-map',
  },
  satellite: {
    title: 'Satellite Map',
    icon: 'mdi-satellite-variant',
  },
  hybrid: {
    title: 'Hybrid Map',
    icon: 'mdi-layers',
  },
}

// Style constants
export const STYLE_CONSTANTS = {
  colors: {
    primary: '#2196F3',
    success: '#4CAF50',
    warning: '#FF9800',
    error: '#F44336',
    purple: '#9C27B0',
    orange: '#FF6B35',
    white: '#FFFFFF',
    black: '#000000',
  },
  opacity: {
    low: 0.1,
    medium: 0.3,
    high: 0.7,
    full: 1.0,
  },
  stroke: {
    thin: 2,
    medium: 3,
    thick: 4,
    extraThick: 5,
  },
  radius: {
    small: 15,
    medium: 500,
  },
}

// Style factory functions
export const createStrokeStyle = (color, width = STYLE_CONSTANTS.stroke.thin, lineDash = null) => {
  return new Stroke({
    color,
    width,
    ...(lineDash && { lineDash }),
  })
}

export const createFillStyle = color => {
  return new Fill({ color })
}

export const createTextStyle = (text, options = {}) => {
  const defaults = {
    font: '12px Arial',
    fill: createFillStyle(STYLE_CONSTANTS.colors.white),
    stroke: createStrokeStyle(STYLE_CONSTANTS.colors.black, STYLE_CONSTANTS.stroke.thin),
  }

  return new Text({
    text,
    ...defaults,
    ...options,
  })
}

export const createIconStyle = (src, scale = 0.1, anchor = [0.5, 0.5], rotateWithView = false) => {
  return new Icon({
    src,
    scale,
    anchor,
    anchorXUnits: 'fraction',
    anchorYUnits: 'fraction',
    rotateWithView,
  })
}

export const createCircleStyle = (radius, fillColor, strokeColor, strokeWidth = STYLE_CONSTANTS.stroke.thin) => {
  return new CircleStyle({
    radius,
    fill: createFillStyle(fillColor),
    stroke: createStrokeStyle(strokeColor, strokeWidth),
  })
}

// Pre-configured styles
export const FEATURE_STYLES = {
  waypoint: sequenceNumber => new Style({
    image: createCircleStyle(
      STYLE_CONSTANTS.radius.small,
      STYLE_CONSTANTS.colors.orange,
      STYLE_CONSTANTS.colors.white,
      STYLE_CONSTANTS.stroke.thin
    ),
    text: createTextStyle(sequenceNumber.toString(), {
      font: 'bold 12px Arial',
      fill: createFillStyle(STYLE_CONSTANTS.colors.white),
    }),
  }),

  route: new Style({
    stroke: createStrokeStyle(
      STYLE_CONSTANTS.colors.orange,
      STYLE_CONSTANTS.stroke.medium,
      [5, 5]
    ),
  }),

  safetyRadius: new Style({
    stroke: createStrokeStyle(
      `rgba(230, 126, 34, ${STYLE_CONSTANTS.opacity.high})`,
      STYLE_CONSTANTS.stroke.thin,
      [5, 5]
    ),
    fill: createFillStyle(`rgba(230, 126, 34, ${STYLE_CONSTANTS.opacity.low})`),
  }),

  distanceLine: new Style({
    stroke: createStrokeStyle(
      `rgba(142, 68, 173, ${STYLE_CONSTANTS.opacity.high})`,
      STYLE_CONSTANTS.stroke.thin
    ),
  }),

  distanceLabel: distance => new Style({
    text: createTextStyle(`${distance}m`, {
      fill: createFillStyle(STYLE_CONSTANTS.colors.white),
      stroke: createStrokeStyle(
        `rgba(142, 68, 173, ${STYLE_CONSTANTS.opacity.high + 0.1})`,
        STYLE_CONSTANTS.stroke.extraThick
      ),
      font: '12px sans-serif',
      padding: [3, 5, 3, 5],
    }),
  }),

  surveyGrid: new Style({
    stroke: createStrokeStyle(
      STYLE_CONSTANTS.colors.primary,
      STYLE_CONSTANTS.stroke.thick,
      [10, 5]
    ),
  }),

  completedSurvey: new Style({
    fill: createFillStyle(`rgba(76, 175, 80, ${STYLE_CONSTANTS.opacity.medium})`),
    stroke: createStrokeStyle(STYLE_CONSTANTS.colors.success, STYLE_CONSTANTS.stroke.thin),
  }),

  surveyBoundary: new Style({
    stroke: createStrokeStyle(
      STYLE_CONSTANTS.colors.primary,
      STYLE_CONSTANTS.stroke.medium,
      [8, 4]
    ),
    fill: createFillStyle(`rgba(33, 150, 243, ${STYLE_CONSTANTS.opacity.low / 2})`),
  }),
}
