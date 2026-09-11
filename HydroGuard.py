import streamlit as st
import numpy as np
import pandas as pd
import folium
from folium.plugins import AntPath
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import plotly.graph_objects as go
import plotly.express as px
import requests
import time
from datetime import datetime, timedelta
from math import radians, cos, sin, asin, sqrt, exp
from sklearn.ensemble import RandomForestClassifier

# ---------------------------------------------------------
# PAGE SETUP & THEME
# ---------------------------------------------------------
st.set_page_config(
    page_title="HydroGuard India | National Dam Safety & Inundation Network",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom Scannable UI Styling
st.markdown("""
<style>
    .safe-card {
        background-color: #e8f5e9;
        border-radius: 10px;
        padding: 16px 20px;
        border-left: 6px solid #2e7d32;
        color: #1b5e20;
        margin-bottom: 15px;
    }
    .danger-card {
        background-color: #ffebee;
        border-radius: 10px;
        padding: 16px 20px;
        border-left: 6px solid #c62828;
        color: #b71c1c;
        margin-bottom: 15px;
    }
    .weather-card {
        background-color: #f8f9fa;
        border-radius: 10px;
        padding: 14px;
        border: 1px solid #dee2e6;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)

# Initialize Session State
if "user_lat" not in st.session_state:
    st.session_state.user_lat = 28.6139  # Default: New Delhi
if "user_lon" not in st.session_state:
    st.session_state.user_lon = 77.2090
if "alert_history" not in st.session_state:
    st.session_state.alert_history = []
if "last_broadcast_state" not in st.session_state:
    st.session_state.last_broadcast_state = False

# ---------------------------------------------------------
# ALL-INDIA MAJOR DAMS REGISTRY
# ---------------------------------------------------------
DAMS_DATABASE = [
    # Northern Region
    {"id": "IND-01", "name": "Tehri Dam", "state": "Uttarakhand", "river": "Bhagirathi", "lat": 30.3780, "lon": 78.4803, "type": "Earth & Rock-fill", "capacity_mcm": 4000.0, "crest_height_m": 260.5,
     "valley_path": [(30.3780, 78.4803), (30.2500, 78.5800), (30.1450, 78.5980), (30.1000, 78.3500), (29.9457, 78.1642)]},
    {"id": "IND-02", "name": "Bhakra Dam", "state": "Himachal Pradesh", "river": "Sutlej", "lat": 31.4101, "lon": 76.4356, "type": "Concrete Gravity", "capacity_mcm": 9340.0, "crest_height_m": 226.0,
     "valley_path": [(31.4101, 76.4356), (31.3200, 76.5100), (31.2300, 76.5000), (31.1800, 76.5200)]},
    {"id": "IND-03", "name": "Pong Dam", "state": "Himachal Pradesh", "river": "Beas", "lat": 31.9634, "lon": 75.9525, "type": "Earth-fill Embankment", "capacity_mcm": 8570.0, "crest_height_m": 133.0},
    {"id": "IND-04", "name": "Ranjit Sagar Dam", "state": "Punjab / J&K", "river": "Ravi", "lat": 32.4419, "lon": 75.7336, "type": "Earth-fill Embankment", "capacity_mcm": 3280.0, "crest_height_m": 160.0},
    {"id": "IND-05", "name": "Salal Dam", "state": "Jammu & Kashmir", "river": "Chenab", "lat": 33.1436, "lon": 74.8311, "type": "Rock-fill & Concrete", "capacity_mcm": 286.0, "crest_height_m": 113.0},
    {"id": "IND-06", "name": "Baglihar Dam", "state": "Jammu & Kashmir", "river": "Chenab", "lat": 33.1539, "lon": 75.4053, "type": "Concrete Gravity", "capacity_mcm": 475.0, "crest_height_m": 144.0},

    # Western Region
    {"id": "IND-07", "name": "Sardar Sarovar Dam", "state": "Gujarat", "river": "Narmada", "lat": 21.8294, "lon": 73.7483, "type": "Concrete Gravity", "capacity_mcm": 9500.0, "crest_height_m": 163.0,
     "valley_path": [(21.8294, 73.7483), (21.8350, 73.5500), (21.7500, 73.2500), (21.7000, 72.9800)]},
    {"id": "IND-08", "name": "Ukai Dam", "state": "Gujarat", "river": "Tapi", "lat": 21.2489, "lon": 73.5853, "type": "Earth-cum-Masonry", "capacity_mcm": 7414.0, "crest_height_m": 80.8},
    {"id": "IND-09", "name": "Kadana Dam", "state": "Gujarat", "river": "Mahi", "lat": 23.3100, "lon": 73.8300, "type": "Earth-fill & Masonry", "capacity_mcm": 1542.0, "crest_height_m": 66.0},
    {"id": "IND-10", "name": "Dharoi Dam", "state": "Gujarat", "river": "Sabarmati", "lat": 24.0044, "lon": 72.8536, "type": "Composite Gravity", "capacity_mcm": 907.0, "crest_height_m": 45.9},
    {"id": "IND-11", "name": "Koyna Dam", "state": "Maharashtra", "river": "Koyna", "lat": 17.4000, "lon": 73.7500, "type": "Rubble-Concrete", "capacity_mcm": 2797.0, "crest_height_m": 103.2},
    {"id": "IND-12", "name": "Jayakwadi Dam", "state": "Maharashtra", "river": "Godavari", "lat": 19.4889, "lon": 75.3889, "type": "Earthen Embankment", "capacity_mcm": 2909.0, "crest_height_m": 41.3},
    {"id": "IND-13", "name": "Ujjani Dam", "state": "Maharashtra", "river": "Bhima", "lat": 18.0772, "lon": 75.1189, "type": "Concrete & Earth-fill", "capacity_mcm": 3140.0, "crest_height_m": 56.4},

    # Southern Region
    {"id": "IND-14", "name": "Idukki Dam", "state": "Kerala", "river": "Periyar", "lat": 9.8500, "lon": 76.9667, "type": "Double Curvature Arch", "capacity_mcm": 1996.0, "crest_height_m": 168.9,
     "valley_path": [(9.8500, 76.9667), (9.9000, 76.8500), (10.0200, 76.6500), (10.1100, 76.3500)]},
    {"id": "IND-15", "name": "Mullaperiyar Dam", "state": "Kerala / TN", "river": "Periyar", "lat": 9.5294, "lon": 77.1408, "type": "Masonry Gravity", "capacity_mcm": 443.0, "crest_height_m": 53.6},
    {"id": "IND-16", "name": "Idamalayar Dam", "state": "Kerala", "river": "Idamalayar", "lat": 10.2222, "lon": 76.7056, "type": "Concrete Gravity", "capacity_mcm": 1089.0, "crest_height_m": 102.8},
    {"id": "IND-17", "name": "Mettur Dam", "state": "Tamil Nadu", "river": "Kaveri", "lat": 11.8000, "lon": 77.8000, "type": "Concrete Gravity", "capacity_mcm": 2640.0, "crest_height_m": 65.2},
    {"id": "IND-18", "name": "Bhavanisagar Dam", "state": "Tamil Nadu", "river": "Bhavani", "lat": 11.4700, "lon": 77.1100, "type": "Earthen & Masonry", "capacity_mcm": 929.0, "crest_height_m": 40.0},
    {"id": "IND-19", "name": "Vaigai Dam", "state": "Tamil Nadu", "river": "Vaigai", "lat": 10.0544, "lon": 77.5925, "type": "Earthen Gravity", "capacity_mcm": 194.0, "crest_height_m": 34.0},
    {"id": "IND-20", "name": "Nagarjuna Sagar Dam", "state": "AP / Telangana", "river": "Krishna", "lat": 16.5767, "lon": 79.3128, "type": "Masonry Gravity", "capacity_mcm": 11472.0, "crest_height_m": 124.0},
    {"id": "IND-21", "name": "Srisailam Dam", "state": "AP / Telangana", "river": "Krishna", "lat": 16.0867, "lon": 78.8978, "type": "Concrete Gravity", "capacity_mcm": 8722.0, "crest_height_m": 145.1},
    {"id": "IND-22", "name": "Polavaram Dam", "state": "Andhra Pradesh", "river": "Godavari", "lat": 17.2550, "lon": 81.6570, "type": "Earth-cum-Rockfill", "capacity_mcm": 5511.0, "crest_height_m": 48.0},
    {"id": "IND-23", "name": "Krishna Raja Sagara", "state": "Karnataka", "river": "Kaveri", "lat": 12.3817, "lon": 76.5728, "type": "Gravity & Masonry", "capacity_mcm": 1368.0, "crest_height_m": 42.6},
    {"id": "IND-24", "name": "Tungabhadra Dam", "state": "Karnataka", "river": "Tungabhadra", "lat": 15.2639, "lon": 76.3353, "type": "Earthen & Composite", "capacity_mcm": 3754.0, "crest_height_m": 49.5},
    {"id": "IND-25", "name": "Almatti Dam", "state": "Karnataka", "river": "Krishna", "lat": 16.3314, "lon": 75.8889, "type": "Concrete Gravity", "capacity_mcm": 3440.0, "crest_height_m": 52.2},
    {"id": "IND-26", "name": "Linganamakki Dam", "state": "Karnataka", "river": "Sharavathi", "lat": 14.1950, "lon": 74.8417, "type": "Masonry Gravity", "capacity_mcm": 4368.0, "crest_height_m": 61.3},

    # Central & Eastern Region
    {"id": "IND-27", "name": "Hirakud Dam", "state": "Odisha", "river": "Mahanadi", "lat": 21.5700, "lon": 83.8700, "type": "Composite Earth & Masonry", "capacity_mcm": 8136.0, "crest_height_m": 60.9,
     "valley_path": [(21.5700, 83.8700), (21.4500, 83.9800), (21.2000, 84.3000), (20.4600, 85.8800)]},
    {"id": "IND-28", "name": "Indira Sagar Dam", "state": "Madhya Pradesh", "river": "Narmada", "lat": 22.2858, "lon": 76.4678, "type": "Concrete Gravity", "capacity_mcm": 12220.0, "crest_height_m": 92.0},
    {"id": "IND-29", "name": "Gandhi Sagar Dam", "state": "Madhya Pradesh", "river": "Chambal", "lat": 24.7061, "lon": 75.7194, "type": "Masonry Gravity", "capacity_mcm": 7322.0, "crest_height_m": 62.2},
    {"id": "IND-30", "name": "Bansagar Dam", "state": "Madhya Pradesh", "river": "Sone", "lat": 24.1947, "lon": 81.2861, "type": "Concrete Gravity", "capacity_mcm": 5410.0, "crest_height_m": 67.0},
    {"id": "IND-31", "name": "Rihand Dam", "state": "Uttar Pradesh", "river": "Rihand", "lat": 24.2047, "lon": 83.0236, "type": "Concrete Gravity", "capacity_mcm": 10608.0, "crest_height_m": 91.4},
    {"id": "IND-32", "name": "Bisalpur Dam", "state": "Rajasthan", "river": "Banas", "lat": 26.0461, "lon": 75.4608, "type": "Gravity Masonry", "capacity_mcm": 1115.0, "crest_height_m": 39.5},
    {"id": "IND-33", "name": "Rana Pratap Sagar Dam", "state": "Rajasthan", "river": "Chambal", "lat": 24.9250, "lon": 75.5900, "type": "Masonry Gravity", "capacity_mcm": 2898.0, "crest_height_m": 53.8},
    {"id": "IND-34", "name": "Maithon Dam", "state": "Jharkhand", "river": "Barakar", "lat": 23.7889, "lon": 86.8150, "type": "Earth-fill & Concrete", "capacity_mcm": 1357.0, "crest_height_m": 50.3},
    {"id": "IND-35", "name": "Panchet Dam", "state": "Jharkhand", "river": "Damodar", "lat": 23.6706, "lon": 86.7450, "type": "Earthen Embankment", "capacity_mcm": 1497.0, "crest_height_m": 45.0},
    {"id": "IND-36", "name": "Subansiri Lower Dam", "state": "Arunachal / Assam", "river": "Subansiri", "lat": 27.5539, "lon": 94.2600, "type": "Concrete Gravity", "capacity_mcm": 1365.0, "crest_height_m": 116.0}
]

# ---------------------------------------------------------
# GEODETIC & HYDRODYNAMIC CALCULATION FUNCTIONS
# ---------------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    R = 6371.0
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    a = sin(dLat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2)**2
    c = 2 * asin(sqrt(a))
    return R * c

def compute_valley_distance(dam, target_lat, target_lon):
    """
    Computes along-channel down-valley distance and lateral deviation.
    Falls back gracefully if the dam has no explicitly pre-mapped valley_path.
    """
    path = dam.get("valley_path")
    if not path or len(path) < 2:
        direct = haversine(dam["lat"], dam["lon"], target_lat, target_lon)
        return max(direct * 1.25, 1.0), direct * 0.20

    min_lateral_offset = float("inf")
    channel_km_at_closest = 0.0
    accumulated_km = 0.0

    for i in range(len(path) - 1):
        p1 = path[i]
        p2 = path[i + 1]
        seg_len = haversine(p1[0], p1[1], p2[0], p2[1])
        d_to_node = haversine(target_lat, target_lon, p1[0], p1[1])
        if d_to_node < min_lateral_offset:
            min_lateral_offset = d_to_node
            channel_km_at_closest = accumulated_km
        accumulated_km += seg_len

    d_to_last = haversine(target_lat, target_lon, path[-1][0], path[-1][1])
    if d_to_last < min_lateral_offset:
        min_lateral_offset = d_to_last
        channel_km_at_closest = accumulated_km

    return max(channel_km_at_closest, 1.0), min_lateral_offset

def simulate_dam_break_hydrodynamics(dam, fill_percent, valley_km, lateral_offset_km):
    """
    Computes Froehlich's peak breach discharge and Saint-Venant flood wave celerity.
    """
    g = 9.81
    actual_head = dam["crest_height_m"] * (fill_percent / 100.0)
    actual_volume = dam["capacity_mcm"] * (fill_percent / 100.0)

    # Froehlich Peak Outflow (m³/s)
    q_peak = 0.607 * (actual_volume ** 0.295) * (actual_head ** 1.24) * 10.0

    # Shallow water wave front celerity with bed resistance
    v_wave_ms = 0.55 * sqrt(g * actual_head)
    v_wave_kmh = max(v_wave_ms * 3.6, 18.0)

    arrival_hours = valley_km / v_wave_kmh
    arrival_time_minutes = arrival_hours * 60.0

    # Flood wave depth exponential attenuation
    initial_depth = actual_head * 0.45
    channel_depth = initial_depth * exp(-0.018 * valley_km)

    # Dynamic Valley Floor Width Envelope
    valley_width_m = 300.0 + (18.0 * valley_km)
    valley_half_width_km = (valley_width_m / 2.0) / 1000.0

    # Inundation Corridor check (within direct risk horizon <= 85 km)
    in_flood_corridor = (lateral_offset_km <= (valley_half_width_km * 1.5)) and (valley_km <= 85.0)
    effective_depth = channel_depth if in_flood_corridor else 0.0

    return {
        "q_peak_cms": round(q_peak, 1),
        "wave_velocity_kmh": round(v_wave_kmh, 1),
        "arrival_time_min": round(arrival_time_minutes, 1),
        "peak_depth_m": round(effective_depth, 2),
        "in_flood_corridor": in_flood_corridor,
        "valley_width_km": round(valley_half_width_km * 2.0, 2)
    }

# ---------------------------------------------------------
# LIVE METEOROLOGICAL SERVICE (OPEN-METEO)
# ---------------------------------------------------------
@st.cache_data(ttl=600)
def fetch_live_weather(lat, lon):
    """Queries Open-Meteo for real-time weather data at the dam location."""
    url = f"[https://api.open-meteo.com/v1/forecast?latitude=](https://api.open-meteo.com/v1/forecast?latitude=){lat}&longitude={lon}&current=temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m&timezone=auto"
    try:
        r = requests.get(url, timeout=4)
        if r.status_code == 200:
            data = r.json().get("current", {})
            code = data.get("weather_code", 0)
            wmo_map = {
                0: "Clear Sky ☀️", 1: "Mainly Clear 🌤️", 2: "Partly Cloudy ⛅",
                3: "Overcast ☁️", 45: "Foggy 🌫️", 51: "Light Drizzle 🌦️",
                61: "Slight Rain 🌧️", 63: "Moderate Rain 🌧️", 65: "Heavy Downpour ⛈️",
                80: "Torrential Showers ⛈️", 95: "Severe Thunderstorm ⚡"
            }
            return {
                "temp_c": data.get("temperature_2m", "--"),
                "humidity": data.get("relative_humidity_2m", "--"),
                "rain_mm": data.get("precipitation", 0.0),
                "wind_kmh": data.get("wind_speed_10m", "--"),
                "condition": wmo_map.get(code, "Cloudy / Unsettled ⛅")
            }
    except Exception:
        pass
    return {"temp_c": "28.0", "humidity": "65", "rain_mm": 0.0, "wind_kmh": "10.5", "condition": "Station Normal ⛅"}

# ---------------------------------------------------------
# AI SENSOR PREDICTIVE CLASSIFIER
# ---------------------------------------------------------
def compute_structural_load_factor(dam):
    height_component = min(dam["crest_height_m"] / 300.0, 1.0)
    volume_component = min(dam["capacity_mcm"] / 10000.0, 1.0)
    return round(0.5 * height_component + 0.5 * volume_component, 4)

@st.cache_resource
def get_ai_risk_model():
    np.random.seed(42)
    n = 3500
    w_level = np.random.uniform(30, 105, n)
    seepage = np.random.uniform(5, 120, n)
    pore_p = np.random.uniform(80, 450, n)
    strain = np.random.uniform(0.5, 45.0, n)
    rain = np.random.uniform(0, 150, n)
    seismic = np.random.uniform(0.0, 0.45, n)
    struct_load = np.random.uniform(0.0, 1.0, n)

    threat_index = (
        (w_level / 100.0) * 0.30 +
        (seepage / 100.0) * 0.20 +
        (pore_p / 400.0) * 0.20 +
        (strain / 35.0) * 0.15 +
        (rain / 120.0) * 0.10 +
        (seismic / 0.30) * 0.25 +
        struct_load * 0.20
    )
    y = (threat_index > 0.82).astype(int)
    X = np.column_stack([w_level, seepage, pore_p, strain, rain, seismic, struct_load])

    clf = RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42)
    clf.fit(X, y)
    return clf

ai_model = get_ai_risk_model()

# ---------------------------------------------------------
# MULTI-CHANNEL BROADCAST DISPATCHER
# ---------------------------------------------------------
def dispatch_emergency_broadcast(channels, payload, twilio_cfg, webhook_url, fcm_cfg):
    results = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if channels.get("webhook") and webhook_url:
        try:
            r = requests.post(webhook_url, json=payload, timeout=4)
            results.append({"Channel": "Civil Siren Webhook", "Status": f"Delivered (HTTP {r.status_code})", "Time": timestamp})
        except Exception as e:
            results.append({"Channel": "Civil Siren Webhook", "Status": f"Failed: {str(e)[:40]}", "Time": timestamp})

    if channels.get("twilio") and twilio_cfg.get("sid") and twilio_cfg.get("token"):
        try:
            url = f"[https://api.twilio.com/2010-04-01/Accounts/](https://api.twilio.com/2010-04-01/Accounts/){twilio_cfg['sid']}/Messages.json"
            sms_body = (
                f"🚨 HYDROGUARD CRITICAL ALERT: Impending breach/overflow at {payload['dam_name']} "
                f"({payload['risk_score']}% Risk). Predicted hit: {payload.get('impact_time', 'N/A')}. Move to high ground!"
            )
            data = {"From": twilio_cfg["from"], "To": twilio_cfg["to"], "Body": sms_body}
            r = requests.post(url, data=data, auth=(twilio_cfg["sid"], twilio_cfg["token"]), timeout=4)
            results.append({"Channel": "Twilio Emergency SMS", "Status": f"Dispatched (HTTP {r.status_code})", "Time": timestamp})
        except Exception as e:
            results.append({"Channel": "Twilio Emergency SMS", "Status": f"Failed: {str(e)[:40]}", "Time": timestamp})

    if channels.get("fcm") and fcm_cfg.get("server_key"):
        try:
            fcm_url = "[https://fcm.googleapis.com/fcm/send](https://fcm.googleapis.com/fcm/send)"
            headers = {"Authorization": f"key={fcm_cfg['server_key']}", "Content-Type": "application/json"}
            fcm_payload = {
                "to": fcm_cfg.get("topic", "/topics/all_citizens"),
                "notification": {
                    "title": f"🚨 FLOOD EMERGENCY: {payload['dam_name']}",
                    "body": f"Failure Risk: {payload['risk_score']}%. Seek high elevation.",
                    "sound": "default"
                },
                "data": payload
            }
            r = requests.post(fcm_url, headers=headers, json=fcm_payload, timeout=4)
            results.append({"Channel": "FCM Citizen Push", "Status": f"Broadcasted (HTTP {r.status_code})", "Time": timestamp})
        except Exception as e:
            results.append({"Channel": "FCM Citizen Push", "Status": f"Failed: {str(e)[:40]}", "Time": timestamp})

    return results

# ---------------------------------------------------------
# SIDEBAR: SEARCH, SENSORS & CONTROLS
# ---------------------------------------------------------
st.sidebar.title("📍 Location & Sensors")

# Optional Custom Dam Registry CSV Upload
uploaded_csv = st.sidebar.file_uploader("📂 Import Custom NRLD CSV (Optional)", type=["csv"])
if uploaded_csv:
    try:
        custom_df = pd.read_csv(uploaded_csv)
        req_cols = {"name", "lat", "lon", "crest_height_m", "capacity_mcm"}
        if req_cols.issubset(set(custom_df.columns)):
            dams_list = custom_df.to_dict(orient="records")
            st.sidebar.success(f"Loaded {len(dams_list)} facilities from CSV!")
        else:
            st.sidebar.warning("CSV missing required columns. Using default catalog.")
            dams_list = DAMS_DATABASE
    except Exception as e:
        st.sidebar.error(f"Error loading CSV: {e}")
        dams_list = DAMS_DATABASE
else:
    dams_list = DAMS_DATABASE

st.sidebar.markdown(f"**Monitored Dams Across India:** `{len(dams_list)} Facilities`")

# Geocoding with Exponential Backoff and Cache (Bug Fix Preserved)
@st.cache_resource(show_spinner=False)
def get_geolocator():
    return Nominatim(user_agent="hydroguard_dam_safety_app_contact_ops_team", timeout=8)

@st.cache_data(show_spinner=False, ttl=3600)
def geocode_address(query: str, max_retries: int = 4, base_delay: float = 1.5):
    geolocator = get_geolocator()
    last_error = None
    for attempt in range(max_retries):
        try:
            return geolocator.geocode(query)
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            last_error = e
            is_rate_limited = "429" in str(e)
            sleep_for = base_delay * (2 ** attempt) * (1.5 if is_rate_limited else 1.0)
            if attempt < max_retries - 1:
                time.sleep(sleep_for)
    raise last_error

st.sidebar.subheader("🔍 Search Location")
address_query = st.sidebar.text_input("Enter Address, City, or Landmark", placeholder="e.g., Haridwar, Uttarakhand")
if st.sidebar.button("Geocode Address"):
    if address_query.strip():
        with st.sidebar.status("Contacting geocoding service...", expanded=False) as status:
            try:
                location = geocode_address(address_query.strip())
                if location:
                    st.session_state.user_lat = location.latitude
                    st.session_state.user_lon = location.longitude
                    status.update(label=f"Located: {location.address[:45]}...", state="complete")
                else:
                    status.update(label="Address not found. Please try another query.", state="error")
            except (GeocoderTimedOut, GeocoderServiceError):
                status.update(label="Geocoding service rate-limited (HTTP 429). Use manual inputs below.", state="error")
            except Exception as e:
                status.update(label=f"Geocoding error: {e}", state="error")
    else:
        st.sidebar.warning("Enter an address first.")

# Manual Coordinate Fallback
with st.sidebar.expander("✏️ Set coordinates manually"):
    manual_lat = st.number_input("Latitude", value=float(st.session_state.user_lat), format="%.6f", key="manual_lat_input")
    manual_lon = st.number_input("Longitude", value=float(st.session_state.user_lon), format="%.6f", key="manual_lon_input")
    if st.button("Apply Coordinates"):
        st.session_state.user_lat = manual_lat
        st.session_state.user_lon = manual_lon
        st.rerun()

st.sidebar.markdown(f"**Current Position:** `{st.session_state.user_lat:.4f}° N, {st.session_state.user_lon:.4f}° E`")

# Sensor Simulation Presets
st.sidebar.markdown("---")
st.sidebar.subheader("🎛️ Sensor Simulation Presets")
scenario = st.sidebar.selectbox(
    "Structural Scenario",
    ["Normal Steady State", "High Monsoon Runoff", "Active Foundation Piping", "Critical Imminent Breach"]
)

if scenario == "Normal Steady State":
    defaults = [62.0, 15.0, 110.0, 2.0, 4.0, 0.01]
elif scenario == "High Monsoon Runoff":
    defaults = [93.5, 55.0, 275.0, 7.5, 95.0, 0.03]
elif scenario == "Active Foundation Piping":
    defaults = [89.0, 92.0, 360.0, 24.0, 45.0, 0.09]
else:
    defaults = [104.2, 120.0, 440.0, 41.0, 140.0, 0.35]

s_water = st.sidebar.slider("Reservoir Water Level (% Crest)", 20.0, 115.0, float(defaults[0]))
s_seep = st.sidebar.slider("Piezometer Seepage (L/min)", 0.0, 150.0, float(defaults[1]))
s_pore = st.sidebar.slider("Pore Pressure (kPa)", 50.0, 500.0, float(defaults[2]))
s_strain = st.sidebar.slider("Crest Displacement Strain (mm)", 0.0, 50.0, float(defaults[3]))
s_rain = st.sidebar.slider("Catchment Rainfall (mm/hr)", 0.0, 160.0, float(defaults[4]))
s_seismic = st.sidebar.slider("Peak Ground Acceleration (g)", 0.0, 0.50, float(defaults[5]), step=0.01)

# ---------------------------------------------------------
# NEAREST FACILITY & HYDRODYNAMICS CALCULATION
# ---------------------------------------------------------
dams_with_dist = []
for d in dams_list:
    dist = haversine(st.session_state.user_lat, st.session_state.user_lon, d["lat"], d["lon"])
    dams_with_dist.append({**d, "direct_dist_km": dist})

sorted_dams = sorted(dams_with_dist, key=lambda x: x["direct_dist_km"])
nearest_dam = sorted_dams[0]

# Compute along-channel distance and inundation metrics
valley_km, lateral_offset = compute_valley_distance(
    nearest_dam, st.session_state.user_lat, st.session_state.user_lon
)
hydro_results = simulate_dam_break_hydrodynamics(
    nearest_dam, s_water, valley_km, lateral_offset
)

# AI Risk Assessment
dam_struct_load = compute_structural_load_factor(nearest_dam)
sample_features = np.array([[s_water, s_seep, s_pore, s_strain, s_rain, s_seismic, dam_struct_load]])
failure_prob = float(ai_model.predict_proba(sample_features)[0][1] * 100.0)

# Live Weather Fetch for Nearest Dam
weather = fetch_live_weather(nearest_dam["lat"], nearest_dam["lon"])

# ---------------------------------------------------------
# FLOOD HIT DATE & TIME PREDICTION
# ---------------------------------------------------------
# Breach/overflow risk condition: AI risk >= 50% OR Water Level >= 98% AND user in valley corridor
is_flood_expected = (failure_prob >= 50.0 or s_water >= 98.0) and hydro_results["in_flood_corridor"]

if is_flood_expected:
    arrival_delta = timedelta(minutes=hydro_results["arrival_time_min"])
    impact_datetime = datetime.now() + arrival_delta
    impact_date_str = impact_datetime.strftime("%A, %d %B %Y")
    impact_time_str = impact_datetime.strftime("%I:%M %p")
    hours_left = int(hydro_results["arrival_time_min"] // 60)
    mins_left = int(hydro_results["arrival_time_min"] % 60)

# ---------------------------------------------------------
# DASHBOARD HEADER & EXECUTIVE STATUS BANNERS
# ---------------------------------------------------------
st.title("🛡️ HydroGuard India: AI Dam Safety & Inundation Defense")

if is_flood_expected:
    st.markdown(f"""
    <div class="danger-card">
        <h3 style="margin:0; color:#b71c1c;">🚨 CRITICAL DAM OVERFLOW & INUNDATION THREAT</h3>
        <p style="font-size:15px; margin: 8px 0;">
            Severe stress / overflow detected at <b>{nearest_dam['name']}</b> (<b>{failure_prob:.1f}%</b> Failure Probability). 
            Your location is in the downstream drainage trajectory.
        </p>
        <div style="background:#ffffff; padding:12px 16px; border-radius:8px; border:1px solid #ef9a9a; display:inline-block;">
            <b>📅 PREDICTED IMPACT DATE:</b> <span style="font-size:17px; color:#b71c1c; font-weight:700;">{impact_date_str}</span><br>
            <b>⏰ PREDICTED IMPACT TIME:</b> <span style="font-size:17px; color:#b71c1c; font-weight:700;">{impact_time_str}</span> 
            <i>(~{hours_left}h {mins_left}m evacuation window)</i><br>
            <b>🌊 ESTIMATED INUNDATION DEPTH:</b> <span style="font-size:17px; color:#b71c1c; font-weight:700;">{hydro_results['peak_depth_m']} meters</span>
        </div>
        <p style="margin:10px 0 0 0; font-weight:600;">ACTION: Evacuate valley floor immediately. Move perpendicular to river flow toward high ground.</p>
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"""
    <div class="safe-card">
        <h3 style="margin:0; color:#1b5e20;">✅ SAFE FROM DIRECT DAM OVERFLOW</h3>
        <p style="font-size:15px; margin: 6px 0;">
            Based on current hydrodynamics and elevation offsets, your location is <b>not in the direct breach inundation corridor</b> 
            of <b>{nearest_dam['name']}</b> (Distance: <b>{nearest_dam['direct_dist_km']:.2f} km</b> | Failure Risk: <b>{failure_prob:.1f}%</b>).
        </p>
        <p style="margin:0; font-size:13px; color:#2e7d32;">
            ⚠️ <b>Advisory Notice:</b> Even though you are safe from catastrophic dam-break waves, <b>please remain cautious</b>. 
            Avoid active river channels, low bridges, and drainage underpasses during sudden monsoon cloudbursts or spillway gate operations.
        </p>
    </div>
    """, unsafe_allow_html=True)

# ---------------------------------------------------------
# EXECUTIVE KPI SUMMARY METRICS
# ---------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
k1.metric("Nearest Dam", nearest_dam["name"], f"{nearest_dam['direct_dist_km']:.1f} km away")
k2.metric("AI Failure Probability", f"{failure_prob:.1f}%", "Out of 100")
k3.metric("Live Dam Weather", f"{weather['temp_c']} °C", weather["condition"])
k4.metric("Reservoir Capacity", f"{nearest_dam['capacity_mcm']:,.0f} MCM", f"Crest: {nearest_dam['crest_height_m']}m")

# ---------------------------------------------------------
# TABBED CONTENT WORKFLOW
# ---------------------------------------------------------
tab_map, tab_weather, tab_hydro, tab_telemetry, tab_broadcast = st.tabs([
    "🗺️ Interactive Evacuation Map",
    "🌤️ Live Weather at Dam",
    "🌊 Hydrodynamic Inundation",
    "📊 Sensor Health Matrix",
    "📢 Civil Defense Broadcast"
])

# ------------------- TAB 1: INTERACTIVE MAP -------------------
with tab_map:
    st.caption("💡 **Tip**: Click anywhere on the map to recalibrate your location. The route line and impact times update dynamically.")

    # Initialize Folium Map
    m = folium.Map(
        location=[st.session_state.user_lat, st.session_state.user_lon],
        zoom_start=9,
        tiles="CartoDB positron"
    )

    # User Marker
    folium.Marker(
        [st.session_state.user_lat, st.session_state.user_lon],
        tooltip="Your Location",
        popup=f"User: {st.session_state.user_lat:.4f}, {st.session_state.user_lon:.4f}",
        icon=folium.Icon(color="blue", icon="user", prefix="fa")
    ).add_to(m)

    # Plot All Dams in Database
    for d in dams_list:
        is_nearest = d["name"] == nearest_dam["name"]
        color = "red" if (is_nearest and is_flood_expected) else ("orange" if is_nearest else "cadetblue")

        folium.Marker(
            [d["lat"], d["lon"]],
            tooltip=f"{d['name']} ({d.get('state', 'India')})",
            popup=f"<b>{d['name']}</b><br>Height: {d['crest_height_m']}m<br>Capacity: {d['capacity_mcm']} MCM",
            icon=folium.Icon(color=color, icon="tint", prefix="fa")
        ).add_to(m)

        # Plot Valley Path if available
        if is_nearest and d.get("valley_path"):
            folium.PolyLine(
                locations=d["valley_path"],
                color="#0077be",
                weight=6,
                opacity=0.7,
                tooltip=f"{d['name']} Primary River Thalweg Corridor"
            ).add_to(m)

            for pt in d["valley_path"]:
                folium.Circle(
                    location=pt,
                    radius=1800,
                    color="#d62728" if is_flood_expected else "#ff7f0e",
                    fill=True,
                    fill_opacity=0.25,
                    weight=1
                ).add_to(m)

    # Animated Route (AntPath) User -> Nearest Dam
    route_points = [
        [st.session_state.user_lat, st.session_state.user_lon],
        [nearest_dam["lat"], nearest_dam["lon"]]
    ]
    AntPath(
        locations=route_points,
        color="#1a73e8",
        weight=5,
        opacity=0.85,
        delay=800,
        dash_array=[10, 20],
        pulse_color="#ffffff",
        tooltip=f"{nearest_dam['name']}: {nearest_dam['direct_dist_km']:.2f} km away"
    ).add_to(m)

    # Midpoint Distance Badge
    mid_lat = (st.session_state.user_lat + nearest_dam["lat"]) / 2.0
    mid_lon = (st.session_state.user_lon + nearest_dam["lon"]) / 2.0
    folium.Marker(
        [mid_lat, mid_lon],
        icon=folium.DivIcon(html=f"""
            <div style="
                background:#1a73e8;
                color:#ffffff;
                padding:4px 10px;
                border-radius:14px;
                font-size:12px;
                font-weight:600;
                font-family:Arial, sans-serif;
                white-space:nowrap;
                box-shadow:0 1px 4px rgba(0,0,0,0.45);
                border:2px solid #ffffff;
                transform:translate(-50%, -50%);
            ">
                📏 {nearest_dam['direct_dist_km']:.2f} km
            </div>
        """)
    ).add_to(m)

    # Keep both points within the camera frame
    m.fit_bounds(route_points, padding=(50, 50))

    # Capture User Map Click
    map_interaction = st_folium(m, height=480, width="100%", returned_objects=["last_clicked"])

    if map_interaction and map_interaction.get("last_clicked"):
        clicked_lat = map_interaction["last_clicked"]["lat"]
        clicked_lon = map_interaction["last_clicked"]["lng"]

        if (round(clicked_lat, 4) != round(st.session_state.user_lat, 4) or
            round(clicked_lon, 4) != round(st.session_state.user_lon, 4)):
            st.session_state.user_lat = clicked_lat
            st.session_state.user_lon = clicked_lon
            st.rerun()

# ------------------- TAB 2: LIVE WEATHER -------------------
with tab_weather:
    st.subheader(f"🌤️ Real-Time Meteorology at {nearest_dam['name']}")
    st.markdown(f"**State / Basin:** {nearest_dam.get('state', 'India')} | **River:** {nearest_dam.get('river', 'Basin')} | **Coordinates:** `{nearest_dam['lat']}° N, {nearest_dam['lon']}° E`")

    wc1, wc2, wc3, wc4 = st.columns(4)
    wc1.markdown(f"""
    <div class="weather-card">
        <h5 style="margin:0; color:gray;">Atmosphere</h5>
        <h3 style="margin:8px 0;">{weather['condition']}</h3>
        <span style="font-size:12px; color:#0077be;">Live satellite telemetry</span>
    </div>
    """, unsafe_allow_html=True)

    wc2.markdown(f"""
    <div class="weather-card">
        <h5 style="margin:0; color:gray;">Precipitation Rate</h5>
        <h3 style="margin:8px 0;">{weather['rain_mm']} mm</h3>
        <span style="font-size:12px; color:#0077be;">Catchment rainfall</span>
    </div>
    """, unsafe_allow_html=True)

    wc3.markdown(f"""
    <div class="weather-card">
        <h5 style="margin:0; color:gray;">Relative Humidity</h5>
        <h3 style="margin:8px 0;">{weather['humidity']}%</h3>
        <span style="font-size:12px; color:#0077be;">Vapor saturation</span>
    </div>
    """, unsafe_allow_html=True)

    wc4.markdown(f"""
    <div class="weather-card">
        <h5 style="margin:0; color:gray;">Wind Speed</h5>
        <h3 style="margin:8px 0;">{weather['wind_kmh']} km/h</h3>
        <span style="font-size:12px; color:#0077be;">Crest anemometer</span>
    </div>
    """, unsafe_allow_html=True)

# ------------------- TAB 3: HYDRODYNAMIC INUNDATION -------------------
with tab_hydro:
    st.subheader("🌊 Hydrodynamic Dam-Break Simulation")

    h1, h2, h3, h4 = st.columns(4)
    h1.metric("Peak Breach Outflow (Qp)", f"{hydro_results['q_peak_cms']:,} m³/s", "Froehlich Formulation")
    h2.metric("Wave Front Celerity", f"{hydro_results['wave_velocity_kmh']} km/h", "Saint-Venant Shallow Water")
    h3.metric("Wave Arrival Window", f"{hydro_results['arrival_time_min']} mins", "Downstream Travel Time")
    h4.metric("Local Wave Depth", f"{hydro_results['peak_depth_m']} m", "Corridor Inundation Depth")

    # Downstream Profile Plot
    dist_steps = np.linspace(1, 80, 50)
    v_const = hydro_results["wave_velocity_kmh"]
    attenuation = [nearest_dam["crest_height_m"] * 0.45 * (s_water / 100.0) * exp(-0.018 * x) for x in dist_steps]
    arrival_steps = [(x / v_const) * 60 for x in dist_steps]

    fig_hydro = go.Figure()
    fig_hydro.add_trace(go.Scatter(x=dist_steps, y=attenuation, mode='lines', name='Peak Wave Depth (m)', line=dict(color='#0077be', width=3)))
    fig_hydro.add_trace(go.Scatter(x=dist_steps, y=arrival_steps, mode='lines', name='Arrival Time (mins)', yaxis='y2', line=dict(color='#d62728', width=2, dash='dot')))
    fig_hydro.add_vline(x=valley_km, line_width=2, line_dash="dash", line_color="black", annotation_text="Your Downstream Distance")

    fig_hydro.update_layout(
        title="Downstream Hydrodynamic Attenuation & Propagation Curve",
        xaxis=dict(title="Distance Downstream from Dam (km)"),
        yaxis=dict(title=dict(text="Peak Inundation Depth (m)", font=dict(color="#0077be"))),
        yaxis2=dict(title=dict(text="Arrival Time (Minutes)", font=dict(color="#d62728")), overlaying="y", side="right"),
        height=300,
        margin=dict(l=40, r=40, t=40, b=30),
        legend=dict(orientation="h", y=1.15)
    )
    st.plotly_chart(fig_hydro, use_container_width=True)

# ------------------- TAB 4: SENSOR TELEMETRY -------------------
with tab_telemetry:
    st.subheader("📊 Geotechnical Telemetry & AI Risk Driver Contribution")

    t1, t2, t3, t4, t5, t6 = st.columns(6)
    t1.metric("Water Level", f"{s_water:.1f}%", "Safe" if s_water < 90 else "Critical", delta_color="inverse")
    t2.metric("Seepage Rate", f"{s_seep:.1f} L/m", "Nominal" if s_seep < 60 else "Piping", delta_color="inverse")
    t3.metric("Pore Pressure", f"{s_pore:.0f} kPa", "Nominal" if s_pore < 300 else "High", delta_color="inverse")
    t4.metric("Strain / Disp", f"{s_strain:.1f} mm", "Stable" if s_strain < 15 else "Divergent", delta_color="inverse")
    t5.metric("Precipitation", f"{s_rain:.0f} mm/h", "Moderate" if s_rain < 50 else "Intense", delta_color="inverse")
    t6.metric("Seismic Accel", f"{s_seismic:.2f} g", "Quiet" if s_seismic < 0.15 else "Tremor", delta_color="inverse")

    # Risk Weights
    contributions = {
        "Reservoir Level Overfill": (s_water / 100.0) * 30,
        "Foundation Seepage": (s_seep / 100.0) * 20,
        "Piezometric Pore Pressure": (s_pore / 400.0) * 20,
        "Structural Displacement Strain": (s_strain / 35.0) * 15,
        "Catchment Rainfall": (s_rain / 120.0) * 10,
        "Seismic Acceleration": (s_seismic / 0.30) * 25,
        "Dam Structural Load Factor": dam_struct_load * 20
    }
    df_contrib = pd.DataFrame(list(contributions.items()), columns=["Indicator", "Threat Weight"])
    fig_bar = px.bar(df_contrib, x="Threat Weight", y="Indicator", orientation='h', color="Threat Weight", color_continuous_scale="Reds")
    fig_bar.update_layout(height=260, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig_bar, use_container_width=True)

# ------------------- TAB 5: CIVIL DEFENSE BROADCAST -------------------
with tab_broadcast:
    st.subheader("📢 Multi-Channel Civil Defense Broadcast Center")

    alert_payload = {
        "dam_id": nearest_dam["id"],
        "dam_name": nearest_dam["name"],
        "risk_score": round(failure_prob, 1),
        "is_flood_expected": is_flood_expected,
        "impact_date": impact_date_str if is_flood_expected else "N/A (Safe)",
        "impact_time": impact_time_str if is_flood_expected else "N/A (Safe)",
        "target_lat": st.session_state.user_lat,
        "target_lon": st.session_state.user_lon,
        "timestamp": datetime.now().isoformat()
    }

    with st.expander("⚙️ Configure API Credentials (Twilio, Webhook, FCM)", expanded=False):
        col_c1, col_c2, col_c3 = st.columns(3)
        with col_c1:
            webhook_input = st.text_input("Webhook URL (Slack/Civil Defense)", value="", type="password")
        with col_c2:
            tw_sid = st.text_input("Twilio Account SID", value="", type="password")
            tw_tok = st.text_input("Twilio Auth Token", value="", type="password")
            tw_from = st.text_input("From Phone Number", value="+1000000000")
            tw_to = st.text_input("Recipient Mobile", value="+910000000000")
        with col_c3:
            fcm_key = st.text_input("FCM Server API Key", value="", type="password")
            fcm_topic = st.text_input("Target Topic", value="/topics/all_citizens")

    c_t1, c_t2, c_t3, c_btn = st.columns([2, 2, 2, 3])
    send_webhook = c_t1.checkbox("Civil Siren Webhook", value=True)
    send_sms = c_t2.checkbox("Twilio SMS Blast", value=True)
    send_fcm = c_t3.checkbox("FCM Citizen Push", value=True)

    selected_channels = {"webhook": send_webhook, "twilio": send_sms, "fcm": send_fcm}
    twilio_cfg = {"sid": tw_sid, "token": tw_tok, "from": tw_from, "to": tw_to}
    fcm_cfg = {"server_key": fcm_key, "topic": fcm_topic}

    # Automated Trigger Threshold (>= 75%)
    if failure_prob >= 75.0 and not st.session_state.last_broadcast_state:
        st.session_state.last_broadcast_state = True
        new_logs = dispatch_emergency_broadcast(selected_channels, alert_payload, twilio_cfg, webhook_input, fcm_cfg)
        st.session_state.alert_history.extend(new_logs)

    if failure_prob < 70.0:
        st.session_state.last_broadcast_state = False

    if c_btn.button("🚨 Broadcast Emergency Alert Now", type="primary", use_container_width=True):
        new_logs = dispatch_emergency_broadcast(selected_channels, alert_payload, twilio_cfg, webhook_input, fcm_cfg)
        st.session_state.alert_history.extend(new_logs)
        st.success("Emergency broadcast sequence executed.")

    if st.session_state.alert_history:
        st.write("##### 📋 Live Emergency Dispatch Audit Log")
        st.dataframe(pd.DataFrame(st.session_state.alert_history[::-1]), use_container_width=True)
