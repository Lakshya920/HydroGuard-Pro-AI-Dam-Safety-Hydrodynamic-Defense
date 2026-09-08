import streamlit as st
import numpy as np
import pandas as pd
import folium
from streamlit_folium import st_folium
from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut, GeocoderServiceError
import plotly.graph_objects as go
import plotly.express as px
import requests
from datetime import datetime
from math import radians, cos, sin, asin, sqrt, exp
from sklearn.ensemble import RandomForestClassifier

# ---------------------------------------------------------
# PAGE SETUP & INITIAL STATE
# ---------------------------------------------------------
st.set_page_config(
    page_title="HydroGuard Pro | Hydrodynamic Dam Safety & Warning System",
    page_icon="🌊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Session State
if "user_lat" not in st.session_state:
    st.session_state.user_lat = 30.1200  # Default: downstream near Rishikesh
if "user_lon" not in st.session_state:
    st.session_state.user_lon = 78.3000
if "alert_history" not in st.session_state:
    st.session_state.alert_history = []
if "last_broadcast_state" not in st.session_state:
    st.session_state.last_broadcast_state = False

# ---------------------------------------------------------
# DAM DATABASE WITH DOWNSTREAM RIVER THALWEGS (COORDINATES)
# ---------------------------------------------------------
DAMS_DATABASE = [
    {
        "id": "DAM-01",
        "name": "Tehri Dam",
        "lat": 30.3780,
        "lon": 78.4803,
        "type": "Earth & Rock-fill",
        "capacity_mcm": 4000.0,
        "crest_height_m": 260.5,
        "valley_path": [
            (30.3780, 78.4803),  # Tehri Dam site
            (30.2500, 78.5800),  # Bhagirathi gorge
            (30.1450, 78.5980),  # Devprayag confluence
            (30.1000, 78.3500),  # Rishikesh valley
            (29.9457, 78.1642)   # Haridwar plains
        ]
    },
    {
        "id": "DAM-02",
        "name": "Bhakra Dam",
        "lat": 31.4101,
        "lon": 76.4356,
        "type": "Concrete Gravity",
        "capacity_mcm": 9340.0,
        "crest_height_m": 226.0,
        "valley_path": [
            (31.4101, 76.4356),
            (31.3200, 76.5100),
            (31.2300, 76.5000),
            (31.1800, 76.5200)
        ]
    },
    {
        "id": "DAM-03",
        "name": "Sardar Sarovar Dam",
        "lat": 21.8294,
        "lon": 73.7483,
        "type": "Concrete Gravity",
        "capacity_mcm": 9500.0,
        "crest_height_m": 163.0,
        "valley_path": [
            (21.8294, 73.7483),
            (21.8350, 73.5500),
            (21.7500, 73.2500),
            (21.7000, 72.9800)
        ]
    },
    {
        "id": "DAM-04",
        "name": "Idukki Dam",
        "lat": 9.8500,
        "lon": 76.9667,
        "type": "Concrete Double Curvature Arch",
        "capacity_mcm": 1996.0,
        "crest_height_m": 168.9,
        "valley_path": [
            (9.8500, 76.9667),
            (9.9000, 76.8500),
            (10.0200, 76.6500),
            (10.1100, 76.3500)
        ]
    },
    {
        "id": "DAM-05",
        "name": "Hirakud Dam",
        "lat": 21.5700,
        "lon": 83.8700,
        "type": "Composite Earth & Masonry",
        "capacity_mcm": 8136.0,
        "crest_height_m": 60.9,
        "valley_path": [
            (21.5700, 83.8700),
            (21.4500, 83.9800),
            (21.2000, 84.3000),
            (20.4600, 85.8800)
        ]
    }
]

# ---------------------------------------------------------
# GEODETIC & HYDRODYNAMIC SIMULATION ENGINES
# ---------------------------------------------------------
def haversine(lat1, lon1, lat2, lon2):
    """Calculates great-circle distance between two points in kilometers."""
    R = 6371.0
    dLat = radians(lat2 - lat1)
    dLon = radians(lon2 - lon1)
    a = sin(dLat / 2)**2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dLon / 2)**2
    c = 2 * asin(sqrt(a))
    return R * c

def compute_valley_distance(dam, target_lat, target_lon):
    """
    Computes along-channel down-valley distance and lateral deviation
    from the river corridor centerline.
    """
    path = dam["valley_path"]
    total_channel_distance = 0.0
    min_lateral_offset = float("inf")
    channel_km_at_closest = 0.0

    accumulated_km = 0.0
    for i in range(len(path) - 1):
        p1 = path[i]
        p2 = path[i + 1]
        seg_len = haversine(p1[0], p1[1], p2[0], p2[1])

        # Distance from target to segment start
        d_to_node = haversine(target_lat, target_lon, p1[0], p1[1])
        if d_to_node < min_lateral_offset:
            min_lateral_offset = d_to_node
            channel_km_at_closest = accumulated_km

        accumulated_km += seg_len

    # If beyond the last point
    d_to_last = haversine(target_lat, target_lon, path[-1][0], path[-1][1])
    if d_to_last < min_lateral_offset:
        min_lateral_offset = d_to_last
        channel_km_at_closest = accumulated_km

    total_channel_distance = max(channel_km_at_closest, 1.0)
    return total_channel_distance, min_lateral_offset

def simulate_dam_break_hydrodynamics(dam, fill_percent, valley_km, lateral_offset_km):
    """
    Hydraulic Dam-Break Model:
    1. Peak Breach Outflow (Froehlich Formulation):
       Qp = 0.607 * (V_w)^0.295 * (h_w)^1.24
    2. Wave Front Celerity (Saint-Venant Shallow Water approximation):
       c = sqrt(g * h_w) -> with bed resistance v_w ~ 0.55 * c
    3. Peak Inundation Depth and Arrival Time calculation.
    """
    g = 9.81
    actual_head = dam["crest_height_m"] * (fill_percent / 100.0)
    actual_volume = dam["capacity_mcm"] * (fill_percent / 100.0)

    # Froehlich Peak Outflow (m^3/s)
    q_peak = 0.607 * (actual_volume ** 0.295) * (actual_head ** 1.24) * 10.0

    # Wave Front Velocity in valley (m/s converted to km/h)
    v_wave_ms = 0.55 * sqrt(g * actual_head)
    v_wave_kmh = max(v_wave_ms * 3.6, 15.0)

    # Arrival time at target location along valley
    arrival_time_hours = valley_km / v_wave_kmh
    arrival_time_minutes = arrival_time_hours * 60.0

    # Attenuation with downstream distance
    # Flood depth decay: y(x) = y0 * exp(-alpha * x)
    initial_depth = actual_head * 0.45
    attenuation_factor = 0.018
    channel_depth = initial_depth * exp(-attenuation_factor * valley_km)

    # Dynamic Valley Floor Width Envelope (meters)
    valley_width_m = 300.0 + (18.0 * valley_km)
    valley_half_width_km = (valley_width_m / 2.0) / 1000.0

    # Inundation status check
    in_flood_corridor = lateral_offset_km <= (valley_half_width_km * 1.5)
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
# AI SENSOR PREDICTIVE MODEL
# ---------------------------------------------------------
def compute_structural_load_factor(dam):
    """
    Normalized (0-1) hydrostatic/volumetric loading factor for a dam, derived
    from its actual crest height and reservoir capacity. Taller dams and
    larger reservoirs carry proportionally greater structural loading.
    This is what lets the risk model differentiate between facilities --
    without it, every location feeds the classifier an identical feature
    vector and the gauge never moves.
    """
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
    struct_load = np.random.uniform(0.0, 1.0, n)  # per-dam structural loading factor

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
    """
    Dispatches alerts to Civil Webhooks, Twilio SMS, and Firebase Cloud Messaging.
    """
    results = []
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 1. Civil Defense Siren / Webhook
    if channels.get("webhook") and webhook_url:
        try:
            r = requests.post(webhook_url, json=payload, timeout=4)
            results.append({"Channel": "Civil Siren Webhook", "Status": f"Delivered (HTTP {r.status_code})", "Time": timestamp})
        except Exception as e:
            results.append({"Channel": "Civil Siren Webhook", "Status": f"Failed: {str(e)[:40]}", "Time": timestamp})

    # 2. Twilio SMS
    if channels.get("twilio") and twilio_cfg.get("sid") and twilio_cfg.get("token"):
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{twilio_cfg['sid']}/Messages.json"
            sms_body = (
                f"🚨 HYDROGUARD CRITICAL EVACUATION ALERT: Dam failure threat at {payload['dam_name']} "
                f"is {payload['risk_score']}%. Est. Flood wave arrival: {payload['arrival_time_min']} mins. "
                f"Move to high ground immediately!"
            )
            data = {
                "From": twilio_cfg["from"],
                "To": twilio_cfg["to"],
                "Body": sms_body
            }
            r = requests.post(url, data=data, auth=(twilio_cfg["sid"], twilio_cfg["token"]), timeout=4)
            results.append({"Channel": "Twilio Emergency SMS", "Status": f"Dispatched (HTTP {r.status_code})", "Time": timestamp})
        except Exception as e:
            results.append({"Channel": "Twilio Emergency SMS", "Status": f"Failed: {str(e)[:40]}", "Time": timestamp})

    # 3. Firebase Cloud Messaging (FCM)
    if channels.get("fcm") and fcm_cfg.get("server_key"):
        try:
            fcm_url = "https://fcm.googleapis.com/fcm/send"
            headers = {
                "Authorization": f"key={fcm_cfg['server_key']}",
                "Content-Type": "application/json"
            }
            fcm_payload = {
                "to": fcm_cfg.get("topic", "/topics/all_citizens"),
                "notification": {
                    "title": f"🚨 FLOOD EMERGENCY: {payload['dam_name']}",
                    "body": f"Failure Probability: {payload['risk_score']}%. Seek high elevation.",
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
# SIDEBAR: INTERACTIVE GEOCODING & TELEMETRY
# ---------------------------------------------------------
st.sidebar.title("📍 Geocoding & Sensors")

# Feature 1: Automated Plain-Text Geocoding
st.sidebar.subheader("🔍 Search Location")
address_query = st.sidebar.text_input("Enter Address, City, or Landmark", placeholder="e.g., Rishikesh, Uttarakhand")
if st.sidebar.button("Geocode Address"):
    if address_query.strip():
        try:
            geolocator = Nominatim(user_agent="hydroguard_dam_safety_v2")
            location = geolocator.geocode(address_query, timeout=5)
            if location:
                st.session_state.user_lat = location.latitude
                st.session_state.user_lon = location.longitude
                st.sidebar.success(f"Located: {location.address[:45]}...")
            else:
                st.sidebar.error("Address not found. Please try another query.")
        except (GeocoderTimedOut, GeocoderServiceError) as e:
            st.sidebar.error(f"Geocoding service error: {e}")

st.sidebar.markdown(f"**Current Coordinates:** `{st.session_state.user_lat:.4f}° N, {st.session_state.user_lon:.4f}° E`")

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
# NEAREST FACILITY & HYDRODYNAMIC RUN
# ---------------------------------------------------------
dam_list = []
for d in DAMS_DATABASE:
    dist = haversine(st.session_state.user_lat, st.session_state.user_lon, d["lat"], d["lon"])
    dam_list.append({**d, "direct_dist_km": dist})

sorted_dams = sorted(dam_list, key=lambda x: x["direct_dist_km"])
nearest_dam = sorted_dams[0]

# Compute River Thalweg distance & Hydrodynamics
valley_km, lateral_offset = compute_valley_distance(
    nearest_dam, st.session_state.user_lat, st.session_state.user_lon
)
hydro_results = simulate_dam_break_hydrodynamics(
    nearest_dam, s_water, valley_km, lateral_offset
)

# AI Risk Classification (features include the NEAREST dam's structural
# loading factor, so different locations -> different nearest dam -> different risk)
dam_struct_load = compute_structural_load_factor(nearest_dam)
sample_features = np.array([[s_water, s_seep, s_pore, s_strain, s_rain, s_seismic, dam_struct_load]])
failure_prob = float(ai_model.predict_proba(sample_features)[0][1] * 100.0)

# ---------------------------------------------------------
# TOP BAR: DISASTER STATUS BANNER
# ---------------------------------------------------------
st.title("🛡️ HydroGuard Pro: AI Dam Safety & Hydrodynamic Defense")

if failure_prob >= 75.0:
    st.error(
        f"🚨 **CRITICAL EMERGENCY**: High probability of failure (**{failure_prob:.1f}%**) at **{nearest_dam['name']}**! "
        f"Downstream arrival time: **{hydro_results['arrival_time_min']} mins**. Execute Emergency Action Plan!",
        icon="⚠️"
    )
elif failure_prob >= 40.0:
    st.warning(
        f"🟡 **ELEVATED HAZARD**: Dam structural telemetry indicates abnormal internal strain at **{nearest_dam['name']}**. "
        f"Failure risk: **{failure_prob:.1f}%**. Monitoring stations placed on Level 2 alert.",
        icon="⚠️"
    )
else:
    st.success(
        f"🟢 **SYSTEM OPERATIONAL**: All geotechnical metrics within tolerance limits for **{nearest_dam['name']}**. "
        f"Failure risk: **{failure_prob:.1f}%**.",
        icon="✅"
    )

# ---------------------------------------------------------
# INTERACTIVE MAP (FOLIUM + CLICK-TO-LOCATE + FLOOD CORRIDORS)
# ---------------------------------------------------------
col_left, col_right = st.columns([7, 5])

with col_left:
    st.subheader("🗺️ Inundation Valley Map & Real-Time Click-to-Locate")
    st.caption("💡 **Tip**: Click anywhere on the map to immediately recalibrate your location and assess flood risk.")

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
        popup=f"User Pos: {st.session_state.user_lat:.4f}, {st.session_state.user_lon:.4f}",
        icon=folium.Icon(color="blue", icon="user", prefix="fa")
    ).add_to(m)

    # Plot all Dams
    for d in DAMS_DATABASE:
        is_nearest = d["id"] == nearest_dam["id"]
        color = "red" if (is_nearest and failure_prob >= 75) else ("orange" if is_nearest else "gray")

        folium.Marker(
            [d["lat"], d["lon"]],
            tooltip=f"{d['name']} ({d['type']})",
            popup=f"<b>{d['name']}</b><br>Height: {d['crest_height_m']}m<br>Capacity: {d['capacity_mcm']} MCM",
            icon=folium.Icon(color=color, icon="tint", prefix="fa")
        ).add_to(m)

        # Draw Valley Inundation Path for Nearest Dam
        if is_nearest:
            folium.PolyLine(
                locations=d["valley_path"],
                color="#0077be",
                weight=6,
                opacity=0.7,
                tooltip=f"{d['name']} Primary River Thalweg Corridor"
            ).add_to(m)

            # Draw flood hazard buffer circle along each path point
            for pt in d["valley_path"]:
                folium.Circle(
                    location=pt,
                    radius=1800,  # Estimated 1.8km spread
                    color="#d62728" if failure_prob >= 75 else "#ff7f0e",
                    fill=True,
                    fill_opacity=0.25,
                    weight=1
                ).add_to(m)

    # Capture User Map Click
    map_interaction = st_folium(m, height=450, width="100%", returned_objects=["last_clicked"])

    if map_interaction and map_interaction.get("last_clicked"):
        clicked_lat = map_interaction["last_clicked"]["lat"]
        clicked_lon = map_interaction["last_clicked"]["lng"]

        # Only update and rerun if click coordinates changed appreciably
        if (round(clicked_lat, 4) != round(st.session_state.user_lat, 4) or
            round(clicked_lon, 4) != round(st.session_state.user_lon, 4)):
            st.session_state.user_lat = clicked_lat
            st.session_state.user_lon = clicked_lon
            st.rerun()

with col_right:
    st.subheader(f"📊 Facility Profile: {nearest_dam['name']}")

    gauge_fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=failure_prob,
        number={'suffix': "%", 'font': {'size': 38}},
        gauge={
            'axis': {'range': [0, 100]},
            'bar': {'color': "#d62728" if failure_prob >= 75 else "#ff7f0e" if failure_prob >= 40 else "#2ca02c"},
            'steps': [
                {'range': [0, 40], 'color': '#e8f5e9'},
                {'range': [40, 75], 'color': '#fff3e0'},
                {'range': [75, 100], 'color': '#ffebee'}
            ],
            'threshold': {'line': {'color': "black", 'width': 3}, 'value': 75.0}
        }
    ))
    gauge_fig.update_layout(height=230, margin=dict(l=15, r=15, t=15, b=15))
    st.plotly_chart(gauge_fig, use_container_width=True)

    st.markdown(f"""
    * **Direct Distance:** `{nearest_dam['direct_dist_km']:.2f} km`
    * **River Thalweg Distance:** `{valley_km:.1f} km`
    * **Lateral Distance from Valley Floor:** `{lateral_offset:.2f} km`
    * **Crest Height / Capacity:** `{nearest_dam['crest_height_m']} m` | `{nearest_dam['capacity_mcm']} MCM`
    """)

# ---------------------------------------------------------
# HYDRODYNAMIC INUNDATION MODELING METRICS
# ---------------------------------------------------------
st.markdown("---")
st.subheader("🌊 Hydrodynamic Inundation & Dam-Break Arrival Simulation")

h1, h2, h3, h4 = st.columns(4)

h1.metric(
    label="Peak Outflow Discharge (Qp)",
    value=f"{hydro_results['q_peak_cms']:,} m³/s",
    help="Computed via Froehlich's empirical breach outflow formulation"
)
h2.metric(
    label="Wave Front Speed",
    value=f"{hydro_results['wave_velocity_kmh']} km/h",
    help="Estimated shallow water celerity along channel slope"
)
h3.metric(
    label="Estimated Wave Arrival",
    value=f"{hydro_results['arrival_time_min']} mins",
    delta="Critical Window" if hydro_results['arrival_time_min'] < 60 else "Evacuation Window",
    delta_color="inverse"
)
h4.metric(
    label="Local Flood Wave Depth",
    value=f"{hydro_results['peak_depth_m']} meters",
    delta="In Hazard Valley" if hydro_results['in_flood_corridor'] else "High Ground (Safe)",
    delta_color="inverse" if hydro_results['in_flood_corridor'] else "normal"
)

# Downstream Profile Plot (Depth & Velocity Attenuation vs Distance)
dist_steps = np.linspace(1, 80, 50)
v_const = hydro_results["wave_velocity_kmh"]
attenuation = [nearest_dam["crest_height_m"] * 0.45 * (s_water / 100.0) * exp(-0.018 * x) for x in dist_steps]
arrival_steps = [(x / v_const) * 60 for x in dist_steps]

fig_hydro = go.Figure()
fig_hydro.add_trace(go.Scatter(x=dist_steps, y=attenuation, mode='lines', name='Flood Wave Peak Depth (m)', line=dict(color='blue', width=3)))
fig_hydro.add_trace(go.Scatter(x=dist_steps, y=arrival_steps, mode='lines', name='Wave Arrival Time (mins)', yaxis='y2', line=dict(color='red', width=2, dash='dot')))

# Highlight user's channel position
fig_hydro.add_vline(x=valley_km, line_width=2, line_dash="dash", line_color="black", annotation_text="Your Downstream Pos")

fig_hydro.update_layout(
    title="Downstream Hydrodynamic Attenuation Curve",
    xaxis=dict(title="Distance Downstream from Dam (km)"),
    yaxis=dict(title=dict(text="Peak Inundation Depth (m)", font=dict(color="blue"))),
    yaxis2=dict(title=dict(text="Arrival Time (Minutes)", font=dict(color="red")), overlaying="y", side="right"),
    height=280,
    margin=dict(l=40, r=40, t=40, b=30),
    legend=dict(orientation="h", y=1.15)
)
st.plotly_chart(fig_hydro, use_container_width=True)

# ---------------------------------------------------------
# MULTI-CHANNEL EMERGENCY BROADCAST DISPATCHER
# ---------------------------------------------------------
st.markdown("---")
st.subheader("📢 Multi-Channel Civil Broadcast Center")

alert_payload = {
    "dam_id": nearest_dam["id"],
    "dam_name": nearest_dam["name"],
    "risk_score": round(failure_prob, 1),
    "water_level_pct": s_water,
    "arrival_time_min": hydro_results["arrival_time_min"],
    "peak_depth_m": hydro_results["peak_depth_m"],
    "target_lat": st.session_state.user_lat,
    "target_lon": st.session_state.user_lon,
    "timestamp": datetime.now().isoformat()
}

with st.expander("⚙️ Configure API Credentials (Twilio, Siren Webhook, FCM)", expanded=False):
    col_c1, col_c2, col_c3 = st.columns(3)
    with col_c1:
        st.markdown("**🔔 Civil Siren Webhook**")
        webhook_input = st.text_input("Webhook URL (Slack/Discord/Custom)", value="", type="password")
    with col_c2:
        st.markdown("**📱 Twilio SMS**")
        tw_sid = st.text_input("Twilio Account SID", value="", type="password")
        tw_tok = st.text_input("Twilio Auth Token", value="", type="password")
        tw_from = st.text_input("From Phone Number", value="+1000000000")
        tw_to = st.text_input("Recipient Mobile", value="+910000000000")
    with col_c3:
        st.markdown("**🔥 Firebase Cloud Messaging (FCM)**")
        fcm_key = st.text_input("FCM Server API Key", value="", type="password")
        fcm_topic = st.text_input("Target Topic", value="/topics/valley_citizens")

# Channel Toggles
c_t1, c_t2, c_t3, c_btn = st.columns([2, 2, 2, 3])
send_webhook = c_t1.checkbox("Civil Siren Webhook", value=True)
send_sms = c_t2.checkbox("Twilio SMS Blast", value=True)
send_fcm = c_t3.checkbox("FCM Citizen Push", value=True)

selected_channels = {"webhook": send_webhook, "twilio": send_sms, "fcm": send_fcm}
twilio_cfg = {"sid": tw_sid, "token": tw_tok, "from": tw_from, "to": tw_to}
fcm_cfg = {"server_key": fcm_key, "topic": fcm_topic}

# Automated Trigger Condition check (>=75% risk threshold)
if failure_prob >= 75.0 and not st.session_state.last_broadcast_state:
    st.session_state.last_broadcast_state = True
    new_logs = dispatch_emergency_broadcast(
        selected_channels, alert_payload, twilio_cfg, webhook_input, fcm_cfg
    )
    st.session_state.alert_history.extend(new_logs)

if failure_prob < 70.0:
    st.session_state.last_broadcast_state = False  # Reset latch when safe

if c_btn.button("🚨 Broadcast Emergency Alert Now", type="primary", use_container_width=True):
    new_logs = dispatch_emergency_broadcast(
        selected_channels, alert_payload, twilio_cfg, webhook_input, fcm_cfg
    )
    st.session_state.alert_history.extend(new_logs)
    st.success("Manual broadcast sequence dispatched.")

# Incident & Dispatch Audit Log
if st.session_state.alert_history:
    st.write("##### 📋 Live Emergency Dispatch Audit Log")
    log_df = pd.DataFrame(st.session_state.alert_history[::-1])
    st.dataframe(log_df, use_container_width=True)
