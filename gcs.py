import sys
import os
from PySide6.QtCore import Qt, QUrl, Signal, Slot, QObject
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTabWidget,
    QGroupBox,
    QFormLayout,
    QLineEdit,
    QComboBox,
    QStatusBar,
    QFileDialog,
    QSplitter,
)
from PySide6.QtWebEngineWidgets import QWebEngineView
from PySide6.QtWebEngineCore import QWebEngineSettings, QWebChannel
from PySide6.QtGui import QIcon, QAction
from PySide6.QtCore import QTimer
from PySide6.QtWebEngineCore import QWebChannel


class MapView(QWebEngineView):
    """Custom map widget with offline capabilities"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.settings().setAttribute(QWebEngineSettings.WebGLEnabled, True)
        self.settings().setAttribute(QWebEngineSettings.LocalStorageEnabled, True)

        # Load offline map HTML (this would point to your local map files)
        offline_map_path = os.path.join(
            os.path.dirname(__file__), "assets/offline_map.html"
        )
        if os.path.exists(offline_map_path):
            self.load(QUrl.fromLocalFile(offline_map_path))
        else:
            # Fallback to OpenLayers with offline capabilities
            self.setHtml(self._get_default_map_html())

    def _get_default_map_html(self):
        """Generate a simple offline-capable map using OpenLayers"""
        return """
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Offline Map</title>
            <style>
                html, body, #map { margin: 0; padding: 0; width: 100%; height: 100%; }
            </style>
            <!-- Include local copies of OpenLayers -->
            <link rel="stylesheet" href="qrc:///assets/ol/ol.css" type="text/css">
            <script src="qrc:///assets/ol/ol.js"></script>
        </head>
        <body>
            <div id="map"></div>
            <script>
                // Initialize map with locally stored tiles
                var map = new ol.Map({
                    target: 'map',
                    layers: [
                        new ol.layer.Tile({
                            source: new ol.source.XYZ({
                                url: 'assets/tiles/{z}/{x}/{y}.png',
                                // Fallback to online if tile not found locally
                                tileLoadFunction: function(imageTile, src) {
                                    const img = imageTile.getImage();

                                    // Try to load from local cache first
                                    img.onerror = function() {
                                        // If local fails, try online source
                                        img.src = src.replace('assets/tiles', 
                                                  'https://tile.openstreetmap.org');
                                    };
                                    img.src = src;
                                }
                            })
                        })
                    ],
                    view: new ol.View({
                        center: ol.proj.fromLonLat([0, 0]),
                        zoom: 2
                    })
                });

                // Store waypoints
                var waypoints = [];
                var waypointSource = new ol.source.Vector();
                var waypointLayer = new ol.layer.Vector({
                    source: waypointSource,
                    style: new ol.style.Style({
                        image: new ol.style.Circle({
                            radius: 6,
                            fill: new ol.style.Fill({color: 'red'}),
                            stroke: new ol.style.Stroke({color: 'white', width: 2})
                        })
                    })
                });
                map.addLayer(waypointLayer);

                // Draw route path
                var routeSource = new ol.source.Vector();
                var routeLayer = new ol.layer.Vector({
                    source: routeSource,
                    style: new ol.style.Style({
                        stroke: new ol.style.Stroke({
                            color: 'blue',
                            width: 3
                        })
                    })
                });
                map.addLayer(routeLayer);

                // Interface for Python to call
                window.setWaypoints = function(waypointsJson) {
                    const points = JSON.parse(waypointsJson);

                    // Clear existing
                    waypointSource.clear();
                    routeSource.clear();

                    // Add waypoints
                    const coordinates = [];
                    points.forEach(function(point) {
                        const coord = ol.proj.fromLonLat([point.lon, point.lat]);
                        coordinates.push(coord);

                        // Add point feature
                        const feature = new ol.Feature({
                            geometry: new ol.geom.Point(coord)
                        });
                        waypointSource.addFeature(feature);
                    });

                    // Add route line
                    if (coordinates.length > 1) {
                        const routeFeature = new ol.Feature({
                            geometry: new ol.geom.LineString(coordinates)
                        });
                        routeSource.addFeature(routeFeature);

                        // Zoom to fit route
                        map.getView().fit(
                            routeFeature.getGeometry(), 
                            {padding: [50, 50, 50, 50], maxZoom: 15}
                        );
                    }
                };

                // Allow Python to move map view
                window.setMapCenter = function(lon, lat, zoom) {
                    map.getView().setCenter(ol.proj.fromLonLat([lon, lat]));
                    if (zoom) map.getView().setZoom(zoom);
                };

                // Return clicked coordinates to Python
                map.on('click', function(evt) {
                    const coord = ol.proj.toLonLat(evt.coordinate);
                    window.pyMapBridge.mapClicked(coord[0], coord[1]);
                });
            </script>
        </body>
        </html>
        """

    def add_waypoints(self, waypoints):
        """Add waypoints to the map

        Args:
            waypoints: List of dicts with lat, lon keys
        """
        waypoints_json = json.dumps(waypoints)
        self.page().runJavaScript(f"window.setWaypoints('{waypoints_json}');")

    def center_map(self, lon, lat, zoom=None):
        """Center the map on specific coordinates"""
        zoom_str = str(zoom) if zoom else "undefined"
        self.page().runJavaScript(f"window.setMapCenter({lon}, {lat}, {zoom_str});")


class MapBridge(QObject):
    """Bridge between JavaScript map and Python"""

    map_clicked = Signal(float, float)

    @Slot(float, float)
    def mapClicked(self, lon, lat):
        self.map_clicked.emit(lon, lat)


class MissionPanel(QWidget):
    """Panel for mission planning and control"""

    mission_loaded = Signal(list)  # Emits waypoints when a mission is loaded

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Mission file tools
        file_group = QGroupBox("Mission File")
        file_layout = QHBoxLayout()

        self.load_button = QPushButton("Load Mission")
        self.load_button.clicked.connect(self.load_mission)
        self.save_button = QPushButton("Save Mission")

        file_layout.addWidget(self.load_button)
        file_layout.addWidget(self.save_button)
        file_group.setLayout(file_layout)
        layout.addWidget(file_group)

        # Mission parameters
        params_group = QGroupBox("Mission Parameters")
        params_layout = QFormLayout()

        self.altitude_input = QLineEdit("100")
        self.speed_input = QLineEdit("5")
        self.survey_type = QComboBox()
        self.survey_type.addItems(["Grid", "Circular", "Corridor"])

        params_layout.addRow("Altitude (m):", self.altitude_input)
        params_layout.addRow("Speed (m/s):", self.speed_input)
        params_layout.addRow("Survey Type:", self.survey_type)
        params_group.setLayout(params_layout)
        layout.addWidget(params_group)

        # Control buttons
        control_group = QGroupBox("Mission Control")
        control_layout = QHBoxLayout()

        self.upload_button = QPushButton("Upload to Vehicle")
        self.start_button = QPushButton("Start Mission")
        self.start_button.setEnabled(False)
        self.pause_button = QPushButton("Pause")
        self.pause_button.setEnabled(False)
        self.rtl_button = QPushButton("Return to Launch")
        self.rtl_button.setEnabled(False)

        control_layout.addWidget(self.upload_button)
        control_layout.addWidget(self.start_button)
        control_layout.addWidget(self.pause_button)
        control_layout.addWidget(self.rtl_button)
        control_group.setLayout(control_layout)
        layout.addWidget(control_group)

        # Spacer at the bottom
        layout.addStretch()

        self.setLayout(layout)

    def load_mission(self):
        """Load mission from file"""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Open Mission File",
            "",
            "Waypoint Files (*.waypoints *.txt);;All Files (*)",
        )

        if filename:
            # This would call your backend code to parse the waypoint file
            # For demonstration, we'll create some sample waypoints
            sample_waypoints = [
                {"lat": 37.7749, "lon": -122.4194},
                {"lat": 37.7750, "lon": -122.4180},
                {"lat": 37.7765, "lon": -122.4175},
                {"lat": 37.7760, "lon": -122.4190},
            ]
            self.mission_loaded.emit(sample_waypoints)

            # Enable control buttons
            self.start_button.setEnabled(True)
            self.upload_button.setEnabled(True)


class TelemetryPanel(QWidget):
    """Panel for displaying vehicle telemetry"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Position info
        pos_group = QGroupBox("Position")
        pos_layout = QFormLayout()

        self.latitude_label = QLabel("N/A")
        self.longitude_label = QLabel("N/A")
        self.altitude_label = QLabel("N/A")

        pos_layout.addRow("Latitude:", self.latitude_label)
        pos_layout.addRow("Longitude:", self.longitude_label)
        pos_layout.addRow("Altitude:", self.altitude_label)
        pos_group.setLayout(pos_layout)
        layout.addWidget(pos_group)

        # Flight info
        flight_group = QGroupBox("Flight Data")
        flight_layout = QFormLayout()

        self.heading_label = QLabel("N/A")
        self.speed_label = QLabel("N/A")
        self.battery_label = QLabel("N/A")

        flight_layout.addRow("Heading:", self.heading_label)
        flight_layout.addRow("Speed:", self.speed_label)
        flight_layout.addRow("Battery:", self.battery_label)
        flight_group.setLayout(flight_layout)
        layout.addWidget(flight_group)

        # Status info
        status_group = QGroupBox("Status")
        status_layout = QFormLayout()

        self.mode_label = QLabel("N/A")
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: red;")

        status_layout.addRow("Flight Mode:", self.mode_label)
        status_layout.addRow("Connection:", self.status_label)
        status_group.setLayout(status_layout)
        layout.addWidget(status_group)

        # Add spacer
        layout.addStretch()

        self.setLayout(layout)

    def update_telemetry(self, data):
        """Update telemetry displays with new data"""
        # This would be called by your backend when new telemetry is available
        if "lat" in data:
            self.latitude_label.setText(f"{data['lat']:.6f}°")
        if "lon" in data:
            self.longitude_label.setText(f"{data['lon']:.6f}°")
        if "alt" in data:
            self.altitude_label.setText(f"{data['alt']:.1f} m")
        if "heading" in data:
            self.heading_label.setText(f"{data['heading']:.1f}°")
        if "speed" in data:
            self.speed_label.setText(f"{data['speed']:.1f} m/s")
        if "battery" in data:
            self.battery_label.setText(f"{data['battery']}%")
        if "mode" in data:
            self.mode_label.setText(data["mode"])
        if "connected" in data:
            if data["connected"]:
                self.status_label.setText("Connected")
                self.status_label.setStyleSheet("color: green;")
            else:
                self.status_label.setText("Disconnected")
                self.status_label.setStyleSheet("color: red;")


import json  # Required for waypoint handling


class MainWindow(QMainWindow):
    """Main application window"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Aerial Survey Ground Control Station")
        self.setWindowIcon(QIcon("assets/icon.png"))
        self.resize(1200, 800)

        self.init_ui()
        self.init_menu()

    def init_ui(self):
        # Main widget and layout
        main_widget = QWidget()
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(2, 2, 2, 2)

        # Create map bridge for JS/Python communication
        self.map_bridge = MapBridge()

        # Create map view
        self.map_view = MapView()

        # Register the bridge with the web page
        self.map_view.page().setWebChannel(QWebChannel())
        self.map_view.page().webChannel().registerObject("pyMapBridge", self.map_bridge)

        # Connect map click signal
        self.map_bridge.map_clicked.connect(self.on_map_clicked)

        # Create panels
        control_tabs = QTabWidget()
        self.mission_panel = MissionPanel()
        self.telemetry_panel = TelemetryPanel()

        # Connect mission loaded signal
        self.mission_panel.mission_loaded.connect(self.on_mission_loaded)

        # Add panels to tabs
        control_tabs.addTab(self.mission_panel, "Mission")
        control_tabs.addTab(self.telemetry_panel, "Telemetry")

        # Create splitter for resizable layout
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.map_view)
        splitter.addWidget(control_tabs)
        splitter.setSizes([800, 400])  # Initial sizes

        main_layout.addWidget(splitter)
        main_widget.setLayout(main_layout)
        self.setCentralWidget(main_widget)

        # Create status bar
        status_bar = QStatusBar()
        self.coords_label = QLabel("Click on map to set coordinates")
        status_bar.addWidget(self.coords_label)
        self.setStatusBar(status_bar)

        # Simulate connection to a vehicle after 2 seconds
        QTimer.singleShot(2000, self.simulate_vehicle_connection)

    def init_menu(self):
        """Initialize application menus"""
        menu_bar = self.menuBar()

        # File menu
        file_menu = menu_bar.addMenu("&File")

        open_action = QAction("&Open Mission", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self.mission_panel.load_mission)
        file_menu.addAction(open_action)

        save_action = QAction("&Save Mission", self)
        save_action.setShortcut("Ctrl+S")
        file_menu.addAction(save_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Alt+F4")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        # Vehicle menu
        vehicle_menu = menu_bar.addMenu("&Vehicle")

        connect_action = QAction("&Connect", self)
        vehicle_menu.addAction(connect_action)

        disconnect_action = QAction("&Disconnect", self)
        vehicle_menu.addAction(disconnect_action)

        # Map menu
        map_menu = menu_bar.addMenu("&Map")

        cache_action = QAction("&Download Offline Maps", self)
        map_menu.addAction(cache_action)

        center_action = QAction("&Center on Vehicle", self)
        center_action.setShortcut("Ctrl+C")
        map_menu.addAction(center_action)

    def on_mission_loaded(self, waypoints):
        """Handle loaded mission waypoints"""
        self.map_view.add_waypoints(waypoints)

        # If waypoints exist, center map on first waypoint
        if waypoints:
            first_point = waypoints[0]
            self.map_view.center_map(first_point["lon"], first_point["lat"], 15)

    def on_map_clicked(self, lon, lat):
        """Handle map click event"""
        self.coords_label.setText(f"Selected: {lat:.6f}°, {lon:.6f}°")
        # Could add waypoint or do other actions here

    def simulate_vehicle_connection(self):
        """Simulate connecting to a vehicle for demonstration"""
        # Display connection info in status
        self.telemetry_panel.update_telemetry(
            {
                "connected": True,
                "lat": 37.7749,
                "lon": -122.4194,
                "alt": 100.0,
                "heading": 90.0,
                "speed": 5.2,
                "battery": 85,
                "mode": "LOITER",
            }
        )

        # Start a timer to simulate telemetry updates
        self.telemetry_timer = QTimer(self)
        self.telemetry_timer.timeout.connect(self.update_simulated_telemetry)
        self.telemetry_timer.start(1000)  # Update every second

        # Enable control buttons
        self.mission_panel.start_button.setEnabled(True)
        self.mission_panel.pause_button.setEnabled(True)
        self.mission_panel.rtl_button.setEnabled(True)

    def update_simulated_telemetry(self):
        """Simulate telemetry updates for demonstration"""
        import random

        # Get current values and slightly modify them
        current_lat = float(self.telemetry_panel.latitude_label.text().replace("°", ""))
        current_lon = float(
            self.telemetry_panel.longitude_label.text().replace("°", "")
        )
        current_alt = float(
            self.telemetry_panel.altitude_label.text().replace(" m", "")
        )

        # Update with small random changes
        self.telemetry_panel.update_telemetry(
            {
                "connected": True,
                "lat": current_lat + random.uniform(-0.0001, 0.0001),
                "lon": current_lon + random.uniform(-0.0001, 0.0001),
                "alt": current_alt + random.uniform(-0.5, 0.5),
                "heading": random.uniform(0, 359),
                "speed": 5.0 + random.uniform(-0.2, 0.2),
                "battery": max(
                    0,
                    min(
                        100,
                        int(self.telemetry_panel.battery_label.text().replace("%", ""))
                        - random.randint(0, 1),
                    ),
                ),
                "mode": self.telemetry_panel.mode_label.text(),
            }
        )


# Add QTimer import (accidentally omitted above)


# For a real application, you'd implement additional functionality:
# 1. Actual waypoint file parsing
# 2. Vehicle connection via MAVLink, MQTT, or your custom protocol
# 3. Mission generation algorithms
# 4. Data recording and export
# 5. Camera control interfaces
# 6. Better offline map management

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
