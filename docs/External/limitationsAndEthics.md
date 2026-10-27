# Limitations, Responsible Use & Environmental Ethics
**OpenCV AI Competition 2026: Ethical & Responsible AI Framework**  
**Project:** ZiwaVision Prototype  

---

## 1. Prototype Scope & Operational Boundaries

ZiwaVision is an investigative technical prototype developed to explore how computer vision and agentic workflows can support satellite-based environmental monitoring. 

It is **not** a validated, lake-wide operational early warning system, and it must not be represented as such.

### 1.1 Geographic & Temporal Scope
- The current implementation is focused on a single representative observation sector: **Dunga Beach, Winam Gulf, Kenya** (`[34.73, -0.22, 34.83, -0.12]`, EPSG:4326).
- Lake Victoria spans over $68,800\text{ km}^2$ across three sovereign nations (Kenya, Uganda, Tanzania). Hydrodynamic circulation, coastal bathymetry, and seasonal water turbidity vary dramatically across different gulfs and open waters.
- Findings and empirical thresholds tuned for Dunga Beach cannot be assumed to transfer directly to other lake sectors (e.g. Mwanza Gulf in Tanzania or Napoleon Gulf in Uganda) without extensive local recalibration and ground-truthing.

### 1.2 Respect for Existing Institutional Research
ZiwaVision does not operate in an institutional vacuum. Extensive, rigorous limnological and remote sensing research on Lake Victoria is conducted by regional and national bodies:
- The **Kenya Marine and Fisheries Research Institute (KMFRI)**
- The **Lake Victoria Basin Commission (LVBC)**
- The **Tanzania Fisheries Research Institute (TAFIRI)**
- The **National Fisheries Resources Research Institute (NaFIRRI, Uganda)**
- The **Copernicus Land Monitoring Service (CLMS)** and regional UNEP environmental assessments.

ZiwaVision is designed to investigate how open Earth observation data and OpenCV 5 can assist grassroots environmental initiatives (like ZiwaClear), complementing—never replacing or disparaging—these institutional authorities.

---

## 2. Technical Limitations & Physical Sensor Boundaries

### 2.1 Spatial Resolution (The 10-Metre Pixel Boundary)
- Copernicus Sentinel-2 MSI provides 10 m spatial resolution in the visible (B02, B03, B04) and near-infrared (B08) bands.
- One pixel corresponds to $10\text{ m} \times 10\text{ m} = 100\text{ m}^2 = 0.01\text{ ha}$.
- **Implication:** Dispersed, narrow ribbons of water hyacinth or small pioneering weed patches under $0.05\text{ ha}$ (5 pixels) fall below the reliable detection limit of 10 m optical sensors. Such sub-pixel vegetation cannot be reliably distinguished from mixed water-vegetation reflectance.

### 2.2 Temporal Latency & Orbital Revisit
- Sentinel-2 constellations (2A, 2B, 2C) offer a 5-day nominal revisit cycle over equatorial East Africa under ideal conditions.
- Wind-driven water hyacinth mats can drift several kilometres within 12–24 hours during convective storms.
- Consequently, satellite observations provide a periodic macro-level snapshot of mat distribution, not a real-time tracking feed.

### 2.3 Cloud Cover & Optical Occlusion
- The Lake Victoria basin experiences high convective cloud cover, especially during the inter-tropical convergence zone (ITCZ) rainy seasons (March–May and October–December).
- Optical satellite sensors cannot penetrate dense cloud cover. The Active Inspector automatically rejects degraded scenes ($Q < 0.70$) to prevent cloud shadow misclassifications, but this introduces data gaps during persistent cloudy periods.

---

## 3. False Positive Risks & Technical Mitigations

| Environmental Confounder | Physical Mechanism | Risk to Field Operations | ZiwaVision Technical Mitigation |
|---|---|---|---|
| **Turbid River Sediment Plumes** | Suspended clay and silt from river runoff increase Red and NIR reflectance, mimicking low-density vegetation. | Wasting boat fuel and crew labor searching large areas of bare muddy water. | **Area Anomaly Guard:** If candidate vegetation exceeds 20% of the lake surface area ($~922\text{ ha}$), the detection is flagged as an artifact and rejected. |
| **Microcystis Phytoplankton Blooms** | Dense cyanobacteria blooms on warm, sheltered bays reflect strongly in the NIR band. | Attempting to dispatch biomass harvesters for microscopic algae that cannot be manually collected. | **Alternative Analysis IoU Gate:** An independent segmentation at $\mathrm{NDVI} > 0.40$ is compared against GrabCut. Diffuse algae blooms exhibit low spatial agreement ($\mathrm{IoU} < 0.70$), triggering human escalation. |
| **Terrestrial Coastal Reeds & Papyrus** | Permanent coastal wetlands (*Cyperus papyrus*) line the shores of Winam Gulf with very high NDVI ($> 0.70$). | Misidentifying stationary shoreline papyrus as floating, harvestable weed mats. | **Morphological Erosion Buffer:** A 7-pixel ($70\text{ m}$) inland buffer (`cv2.erode`) separates open water from coastal wetlands. Runtime assertions guarantee 0% inland pixels. |

---

## 4. Human-in-the-Loop Safety & The Language Invariant

### 4.1 Strict Language Invariant
Across the entire repository, database schemas, API responses, and user interface elements, all automated detections are formally designated as **candidate floating vegetation** (never "hyacinth") until a qualified human operator has conducted visual verification.

This invariant prevents algorithmic overconfidence and acknowledges that optical satellite sensors detect spectral vegetation reflectance, not taxonomic species classifications.

### 4.2 Autonomous Dispatch Prohibition
- ZiwaVision strictly prohibits autonomous dispatch triggers.
- Under no circumstances should harvester cooperatives, commercial harvesting boats, or field teams be deployed solely on the basis of an autonomous computer vision alert.
- The human verification interface in `dashboard/` and the authenticated `/api/hotspots/<id>/verify` endpoint serve as mandatory ethical checkpoints. A human operator must visually inspect the overlay against true-colour imagery before any physical follow-up is initiated.

---

## 5. Community Impact & Harvester Welfare

The parent initiative, **ZiwaClear**, works directly with artisanal fishing communities and youth harvesting cooperatives around Lake Victoria. In designing ZiwaVision, several community welfare considerations were integrated:

1. **Fuel Conservation & Safety:** Lake Victoria is notorious for sudden, dangerous squalls. Preventing "blind dispatch" across open water saves scarce cooperative fuel and protects artisanal boats from unnecessary exposure to hazardous lake crossings.
2. **Fair & Transparent Compensation:** ZiwaClear tracks biomass harvesting yields and distributes digital payouts via M-Pesa. Accurate spatial reporting ensures that cooperative collection efforts are directed to high-density zones where harvesting is commercially viable.
3. **Data Accessibility:** Environmental data belongs to the lake basin community. The ZiwaVision dashboard is designed as a lightweight, dark-mode web application that runs efficiently on low-bandwidth mobile connections and devices common across East Africa.
