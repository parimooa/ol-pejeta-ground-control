# Offline Maps for Ol Pejeta Conservancy

This document provides instructions for using the offline map functionality in the Ol Pejeta Ground Control System.

## Overview

The Ol Pejeta GCS now supports offline maps, allowing you to download map tiles for the Ol Pejeta Conservancy area and use them when you don't have an internet connection. This is particularly useful for field operations where connectivity may be limited.

## Features

- Download map tiles for the Ol Pejeta Conservancy area
- Use maps offline when no internet connection is available
- Switch between different map types (standard, satellite, hybrid) while offline
- Manage downloaded map tiles (view counts, delete)

## How to Use Offline Maps

### Downloading Map Tiles

1. Ensure you have an active internet connection
2. In the map view, click the "Download Maps" button in the top controls area
3. In the dialog that appears:
   - Adjust the "Download Area Radius" slider to set how large an area to download (1-10km)
   - For each map type (Standard, Satellite, Hybrid), click the "Download" button
   - Wait for the download to complete (progress will be shown)

### Using Offline Maps

Once you've downloaded map tiles:

1. The maps will automatically use cached tiles when you're offline
2. You can switch between map types (Standard, Satellite, Hybrid) using the map type toggle
3. If you go outside the downloaded area, you may see blank tiles

### Managing Offline Maps

To manage your downloaded map tiles:

1. Click the "Offline Maps" or "Download Maps" button in the top controls area
2. The dialog shows how many tiles are stored for each map type
3. To delete cached tiles for a map type, click the delete button next to it

## Technical Details

### Storage

Map tiles are stored in your browser's IndexedDB database. The storage requirements depend on:

- The area radius you select (larger radius = more storage)
- The zoom levels (fixed from zoom level 12 to 18)
- The map types you download (Satellite tiles are larger than Standard map tiles)

Approximate storage requirements:
- Standard map: ~10MB for 5km radius
- Satellite map: ~20-30MB for 5km radius
- Hybrid map: ~15-20MB for 5km radius

### Limitations

- You cannot download new map tiles while offline
- The maps are centered on the current view position when you download
- Downloaded tiles are specific to your browser/device and won't be shared with other devices
- Very large download areas may take significant time and storage

## Troubleshooting

If you encounter issues with offline maps:

1. **Maps not showing offline**: Check that you've downloaded the map tiles for the area you're viewing
2. **Download fails**: Ensure you have a stable internet connection and try again
3. **Storage issues**: Try clearing some tiles and downloading a smaller area

For persistent issues, you can clear all cached data by:
1. Opening your browser's developer tools
2. Going to Application > Storage > IndexedDB
3. Finding and deleting the "ol-pejeta-map-tiles" database

## Support

For additional help or to report issues with the offline map functionality, please contact the development team.