# 🌊 HydroGuard Pro: Hydrodynamic Dam Safety & Warning System

> Real-time geotechnical failure prediction, down-valley hydrodynamic flood wave routing, and multi-channel disaster dispatch.

HydroGuard Pro is an early warning decision-support platform designed to protect downstream populations from catastrophic dam breaches. By coupling Random Forest machine learning with classical open-channel hydrodynamics and geospatial mapping, the system translates live dam structural telemetry into down-valley flood arrival times, inundation depths, and automated evacuation orders.

---

## 🌟 Key Capabilities

### 1. 🤖 AI Geotechnical Risk Assessment
* Employs a `RandomForestClassifier` trained on multi-sensor geotechnical indicators: reservoir water levels (% crest), piezometer seepage rates (L/min), pore pressures (kPa), crest displacement strain (mm), catchment rainfall (mm/hr), and peak ground acceleration (PGA in $g$).
* Classifies dam structural failure probability in real time and triggers defensive alert tiers (Normal, Elevated Hazard, Critical Emergency)[cite: 6].

### 2. 🌊 Hydrodynamic Inundation Modeling
* **Breach Peak Discharge ($Q_p$):** Computed using the empirical Froehlich breach outflow formulation scaled to active reservoir volume ($V_w$) and hydraulic head ($h_w$)[cite: 6]:
  $$Q_p = 0.607 \cdot (V_w)^{0.295} \cdot (h_w)^{1.24} \cdot 10$$
* **Wave Front Celerity:** Approximated using Saint-Venant shallow-water theory with bed roughness dampening ($v_w \approx 0.55 \sqrt{g \cdot h_w}$)[cite: 6].
* **Downstream Flood Attenuation:** Models depth decay along the primary river thalweg corridor via exponential attenuation[cite: 6]:
  $$y(x) = y_0 \cdot e^{-\alpha x}$$
* **Evacuation Metrics:** Calculates wave arrival minutes, local inundation depth, dynamic valley floor width expansion, and flood corridor containment for any downstream coordinate[cite: 6].

### 3. 🗺️ Interactive Geospatial Mapping
* **Click-to-Locate:** Interactive Leaflet/Folium map allows users to click anywhere downstream to recalculate along-channel thalweg distances and arrival times instantly[cite: 6].
* **Corridor Buffering:** Plots primary valley thalweg paths and dynamic hazard buffer zones down-channel from major facilities (Tehri, Bhakra, Sardar Sarovar, Idukki, Hirakud)[cite: 6].
* **Nominatim Geocoder:** Resolves human-readable place names and landmarks directly to geodetic coordinates[cite: 6].

### 4. 📢 Multi-Channel Emergency Dispatcher
* Automatically triggers when failure risk reaches the critical $\ge 75\%$ threshold or when dispatched manually[cite: 6]:
  * **Civil Defense Webhooks:** Dispatches payloads to emergency operation center sirens, Slack, or Discord[cite: 6].
  * **Twilio SMS:** Sends evacuation SMS blasts with estimated wave arrival windows[cite: 6].
  * **Firebase Cloud Messaging (FCM):** Delivers push alerts to citizen mobile devices[cite: 6].
* Maintains an in-memory audit log of all transmission timestamps, channel statuses, and HTTP responses[cite: 6].

---

## 🛠️ Tech Stack

* **Frontend & Dashboard:** [Streamlit](https://streamlit.io/)[cite: 6]
* **Machine Learning:** [Scikit-Learn](https://scikit-learn.org/) (`RandomForestClassifier`)[cite: 6]
* **Geospatial & Mapping:** [Folium](https://python-visualization.github.io/folium/), [streamlit-folium](https://github.com/randyzwitch/streamlit-folium), [GeoPy](https://geopy.readthedocs.io/)[cite: 6]
* **Visualization:** [Plotly](https://plotly.com/python/) (Gauge indicators and multi-axis attenuation curves)[cite: 6]
* **Alert Delivery:** [Requests](https://requests.readthedocs.io/) (HTTP Webhooks, Twilio REST API, FCM REST API)[cite: 6]
