# Ground Control System to air coordination system

A comprehensive drone-car coordination and ground control system designed for autonomous vehicle operations in wildlife conservation areas. The system provides real-time telemetry monitoring, coordinated survey missions, and advanced analytics data collection for research purposes.

##  Features

### Core Capabilities
- **Real-time Vehicle Coordination**: Autonomous drone-car coordination with configurable distance thresholds
- **Survey Operations**: Automated proximity-based survey mission execution
- **Live Telemetry**: Real-time vehicle status, position, and system health monitoring
- **Advanced Analytics**: Comprehensive data collection for mission effectiveness analysis
- **Web Interface**: Modern Vue.js-based ground control station with interactive mapping

### Analytics & Research
- **Proximity Data Collection**: Continuous tracking of vehicle interactions and coordination scenarios
- **Mission Effectiveness Metrics**: Performance analysis, success rates, and operational insights
- **System Health Monitoring**: Component status tracking and fault detection
- **Data Export**: JSON-based data persistence for research analysis

##  Architecture

```
┌─────────────────────────────────────┐
│           Frontend (Vue.js)         │
│     ┌─────────────────────────┐     │
│     │    Web Interface        │     │
│     │  - Map Visualization    │     │
│     │  - Vehicle Controls     │     │
│     │  - Analytics Dashboard  │     │
│     └─────────────────────────┘     │
└─────────────────────────────────────┘
                    │
                 HTTP/WS
                    │
┌─────────────────────────────────────┐
│          Backend (FastAPI)          │
│  ┌─────────────┐ ┌───────────────┐  │
│  │   Vehicle   │ │  Coordination │  │
│  │   Service   │ │    Service    │  │
│  └─────────────┘ └───────────────┘  │
│  ┌─────────────┐ ┌───────────────┐  │
│  │  Analytics  │ │    Survey     │  │
│  │   Service   │ │    Service    │  │
│  └─────────────┘ └───────────────┘  │
└─────────────────────────────────────┘
                    │
                 MAVLink
                    │
┌─────────────────────────────────────┐
│            Vehicles                 │
│   ┌─────────────┐ ┌─────────────┐   │
│   │    Drone    │ │     Car     │   │
│   │ (Copter)    │ │   (Rover)   │   │
│   └─────────────┘ └─────────────┘   │
└─────────────────────────────────────┘
```

##  Prerequisites

### System Requirements
- **Python**: 3.12 or higher
- **Node.js**: 18.0 or higher
- **npm**: 9.0 or higher (or compatible package manager)
- **Operating System**: Windows, macOS, or Linux

### Hardware Requirements
- MAVLink-compatible vehicles (drone and/or car)
- Network connection for vehicle communication
- Modern web browser for the interface

## ️ Installation

### 1. Clone the Repository
```bash
git clone <repository-url>
cd ol-pejeta-ground-control
```

### 2. Backend Setup

#### Using uv (Recommended)
```bash
# Install uv if not already installed
pip install uv

# Install dependencies
uv sync

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate
```

#### Using pip
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate

# Install dependencies
pip install -e .
```

### 3. Frontend Setup
```bash
cd front-end-vuetify/ol-pejeta-gcs
npm install
```

### 4. Configuration

#### Vehicle Configuration
Create or modify `settings.py` in the project root:

```python
# Site configuration
site_name = "your-site-name"

vehicle_settings = [
    {
        "type": "drone",
        "id": 1,
        "connection": "127.0.0.1",  # Vehicle IP address
        "port": "14550",  # MAVLink port
        "protocol": "udp",
        "home_location": {"lat": 0.0, "lon": 0.0, "alt": 10},
    },
    {
        "type": "car",
        "id": 2,
        "connection": "127.0.0.1",
        "port": "14570",
        "protocol": "udp",
        "home_location": {"lat": 0.0, "lon": 0.0, "alt": 10},
    },
    {
        "type": "operator",
        "connection": "127.0.0.1",
        "port": "COM6",
        "baud_rate": "115200",
        "protocol": "serial",
    },
]
```

#### Directory Structure Setup
The system will automatically create required directories:
- `analytics_data/` - Analytics data storage
- `surveyed_area/` - Survey result storage

## Usage

### Starting the System

#### 1. Start Backend Server
```bash
# From project root
python main.py
```
The backend will be available at: `http://localhost:8000`

#### 2. Start Frontend Development Server
```bash
# In separate terminal
cd front-end-vuetify/ol-pejeta-gcs
npm run dev
```
The frontend will be available at: `http://localhost:3000`

### Basic Operation Flow

1. **Connect Vehicles**
   - Use the web interface to connect drone and car
   - Verify telemetry data is streaming

2. **Start Coordination**
   - Click "Start Coordination" in the interface
   - System begins autonomous drone-car coordination

3. **Execute Surveys**
   - Position car at desired survey location
   - Wait for proximity threshold to be met
   - Click "Survey" button when enabled

4. **Monitor Analytics**
   - View real-time data in the Analytics dashboard
   - Data is automatically saved every 5 minutes

##  Analytics System

### Data Collection
The system continuously collects:

- **Vehicle Telemetry**: Position, battery, system status (every 10 seconds during coordination)
- **Mission Effectiveness**: Survey completion rates and performance metrics
- **System Health**: Component status and error tracking
- **Coordination Events**: Follow/survey state changes and transitions

### Data Storage
- **Format**: JSON files in `analytics_data/` directory
- **Persistence**: Automatic save every 5 minutes
- **Export**: Manual export via API endpoints

### Key Analytics Files
- `vehicle_telemetry.json` - Comprehensive vehicle data
- `mission_effectiveness.json` - Survey performance metrics
- `coordination_events.json` - System state change events
- `system_health.json` - Component health tracking
- `safety_events.json` - Safety incident recording

##  Development

### Development Servers
```bash
# Backend with auto-reload
python main.py

# Frontend with hot reload
cd front-end-vuetify/ol-pejeta-gcs
npm run dev
```

### Code Formatting
```bash
# Python formatting
black .
ruff check . --fix

# Frontend linting
cd front-end-vuetify/ol-pejeta-gcs
npm run lint
```

### Project Structure
```
ol-pejeta-ground-control/
├── backend/                    # Python backend
│   ├── api/                   # FastAPI routes and WebSocket handlers
│   ├── core/                  # Core functionality (flight modes, etc.)
│   ├── models/                # Data models
│   ├── schemas/               # Pydantic schemas
│   └── services/              # Business logic services
├── front-end-vuetify/ol-pejeta-gcs/  # Vue.js frontend
│   ├── src/
│   │   ├── components/        # Vue components
│   │   ├── pages/            # Application pages
│   │   ├── config/           # Configuration constants
│   │   └── utils/            # Utility functions
├── analytics_data/            # Generated analytics data
├── surveyed_area/            # Survey results
├── main.py                   # Backend entry point
├── settings.py               # Vehicle configuration
└── pyproject.toml           # Python dependencies
```

##  API Reference

### Core Endpoints

#### Vehicle Management
- `POST /vehicles/{type}/connect` - Connect vehicle
- `POST /vehicles/{type}/disconnect` - Disconnect vehicle
- `GET /vehicles/{type}/status` - Get vehicle status

#### Coordination Control
- `POST /coordination/start` - Start coordination service
- `POST /coordination/stop` - Stop coordination service
- `GET /coordination/status` - Get coordination status
- `POST /coordination/initiate-proximity-survey` - Start survey

#### Analytics Data
- `GET /analytics/dashboard-data` - Get dashboard metrics
- `GET /analytics/export` - Export all analytics data

### WebSocket Endpoints
- `ws://localhost:8000/ws/telemetry` - Real-time telemetry stream

## ️ Configuration Parameters

### Coordination Settings (backend/config.py)
- `MAX_FOLLOW_DISTANCE`: 500m - Maximum distance before survey abandonment
- `FOLLOW_ALTITUDE`: 30m - Drone follow altitude
- `PROXIMITY_THRESHOLD`: 5m - Distance for survey button activation
- `LOOP_INTERVAL`: 2s - Coordination loop frequency

### Analytics Settings
- `PERSISTENCE_INTERVAL`: 300s (5 minutes) - Data save frequency
- Vehicle telemetry: Every 10 seconds when coordination active

##  Troubleshooting

### Common Issues

#### Backend Connection Errors
```
ECONNREFUSED errors in frontend
```
**Solution**: Ensure backend server is running on port 8000

#### Vehicle Connection Issues
```
Failed to connect to vehicle
```
**Solutions**:
1. Verify MAVLink vehicle is broadcasting telemetry
2. Check IP address and port in `settings.py`
3. Ensure network connectivity to vehicle

#### Frontend Build Errors
```
npm install fails
```
**Solutions**:
1. Clear npm cache: `npm cache clean --force`
2. Delete `node_modules` and reinstall: `rm -rf node_modules && npm install`
3. Check Node.js version compatibility

#### Analytics Data Not Saving
**Solutions**:
1. Check file permissions in `analytics_data/` directory
2. Verify disk space availability
3. Check backend logs for persistence errors

### Getting Help
- Check console logs in browser developer tools
- Review backend terminal output for error messages
- Ensure all dependencies are properly installed

##  Contributing

### Development Setup
1. Fork the repository
2. Create a feature branch
3. Make changes following code style guidelines
4. Test thoroughly with both simulated and real vehicles
5. Submit a pull request

### Code Style
- **Python**: Follow Black formatting and pass Ruff linting
- **JavaScript**: Follow ESLint configuration
- **Commits**: Use conventional commit messages

##  License

[]

## ️ Version

Current version: 0.1.0

---

