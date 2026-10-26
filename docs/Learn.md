# ZiwaVision concepts: what we practised and where it lives in the code

As of 10 Oct 2026. For each concept: what it is, the real code where we used it, why it was needed, and what to watch for.
Files referred to: `src/explore_tile.py` (your notebook), `src/pipeline.py` (functions), `src/run*.py` (scripts that call them).

Status markers: **[ran]** you ran it and saw output. **[added]** code was given but you haven't run it yet.

## Contents
1. Python
2. Maps and coordinates
3. Satellite data (Sentinel-2)
4. NumPy
5. OpenCV
6. matplotlib
7. Thinking like an analyst
8. Mistakes log
9. Still ahead

---

## 1. Python

### 1.1 Lists and dictionaries
- **What:** a list is ordered and read by position (`items[0]`). A dictionary stores `key: value` pairs and is read by key (`props["eo:cloud_cover"]`).
- **Where:**
  ```python
  BBOX = [34.73, -0.22, 34.83, -0.12]                    # list: west, south, east, north
  it.properties["eo:cloud_cover"]                        # dictionary lookup
  palette = {4: (0, 160, 0), 6: (0, 0, 255)}             # dictionary used as a lookup table
  ```
- **Used for:** holding the search box, reading scene metadata, mapping SCL labels to colours.
- **Watch for:** a key must match exactly. `"eo: cloud_cover"` (with a space) gave a `KeyError`. `.get("key")` returns `None` instead of failing, which is how `baseline: None` appeared when the key was spelled wrong.

### 1.2 Reading a traceback
- **What:** read the **last line** first (the error type and message), then the line number above it.
- **Where:** `KeyError: 'eo: cloud_cover'`, `CRSError ... "ESPG"`, `TypeError ... dtype object`, `ModuleNotFoundError: No module named 'numpy'`.
- **Watch for:** if the named line looks fine, check the lines just above it (the `imshow(items)` bug showed up on a `set_title` line).

### 1.3 Functions, parameters and return values
- **What:** a named piece of code that receives inputs (parameters) and gives back an output (`return`). A default argument (`as_float=True`) makes an input optional.
- **Where (`pipeline.py`) [ran]:**
  ```python
  def read_band(item, name, bbox, as_float=True):
      """Read one band of one scene, cropped to bbox."""
      with rasterio.open(item.assets[name].href) as src:
          bounds = transform_bounds("EPSG:4326", src.crs, *bbox)
          window = from_bounds(*bounds, transform=src.transform)
          data = src.read(1, window=window)
      return data.astype("float32") if as_float else data
  ```
- **Used for:** the same function reads `red`, `nir`, `scl` for any scene. In the old script, `item` was a global defined at the top; now the caller hands it in.
- **Watch for:** a function can `return None` to say "nothing found" (`lake_mask` does this when a scene has no water). The caller must check for it.

### 1.4 Unpacking with `*` and tuple unpacking
- **What:** splitting a collection into separate pieces.
- **Where:**
  ```python
  w, s, e, n = scene.bbox                       # four numbers into four names (covers)
  transform_bounds("EPSG:4326", src.crs, *bbox) # list spread into four arguments
  np.zeros((*scl.shape, 3), dtype="uint8")      # (rows, cols) becomes (rows, cols, 3)
  ```
- **Watch for:** `*` means different things in different places. Here it always spreads a collection out.

### 1.5 List and dictionary comprehensions
- **What:** a one-line loop that builds a list or dictionary.
- **Where:**
  ```python
  [it for it in items if covers(it, bbox)]                       # keep scenes that pass a test [ran]
  {str(s.datetime.date()): s for s in scenes}                    # date -> scene (run_diff.py) [ran]
  ```
- **Used for:** filtering scenes by footprint, and looking a scene up by its date.
- **Tip:** write it as a normal `for` loop first, then shorten it.

### 1.6 `lambda` and `key=`
- **What:** `key=` tells `min`, `max` or `sorted` what to compare. A `lambda` is a tiny function written in place.
- **Where:**
  ```python
  item = min(good, key=lambda it: it.properties["eo:cloud_cover"])   # explore_tile.py
  sorted(data, key=lambda d: d[0])                                    # run_band.py [added]
  ```

### 1.7 `with ... as`
- **What:** open a resource and close it automatically at the end of the block.
- **Where:** `with rasterio.open(item.assets[name].href) as src:`. The file stays on AWS and only the window you ask for is read.

### 1.8 Modules, imports and the virtual environment
- **What:** one file can use another file's functions. A virtual environment (`venv`) holds the packages for this project.
- **Where:** `from pipeline import find_scenes, read_band, ...` at the top of every `run_*.py`.
- **Watch for:** run from the project root, with the environment active (`source venv/bin/activate`). If `numpy` "isn't installed", you're almost certainly outside the environment.

### 1.9 Constants
- **What:** values that act as settings, written in capitals at the top of a file.
- **Where:** `BBOX`, `PIXEL_HA`, `BAD_CLASSES`, `NDVI_THRESHOLD`.
- **Used for:** one place to change a setting, with a comment on what it is. Many of these are *choices* (see 7.4).

### 1.10 Loops, `continue`, f-strings and failing early
- **What:** repeat for each item; skip to the next; format text with values inside `{}`; stop with a clear message.
- **Where:**
  ```python
  if cloud > 0.05:
      print(s.datetime.date(), f"box cloud {cloud:.1%}: skipped")
      continue
  ```
  `raise SystemExit("No scene covers the box...")` in `explore_tile.py`.
- **Watch for:** `cloud > 0.05` means *more than* 5% cloud, which is when the scene is skipped. Clear scenes carry on past the `if`. The `:.1%` turns 0.175 into `17.5%`.

---

## 2. Maps and coordinates

### 2.1 Longitude/latitude and the bounding box
- **What:** positions as angles. A box is `[west, south, east, north]`, so **longitude comes first**.
- **Where:** `BBOX = [34.73, -0.22, 34.83, -0.12]`, built around Dunga Beach (lat -0.1667, lon 34.7833). My first guess missed Dunga, because its latitude was just outside the southern edge.
- **Rule:** check that your point sits between west and east, and between south and north.

### 2.2 Coordinate reference systems (CRS) and windows
- **What:** satellite files store positions in metres in a projected system, so a lon/lat box has to be converted (`transform_bounds`) and then turned into a rectangle of pixel rows and columns (`from_bounds`, the window).
- **Where:** inside `read_band` (see 1.3). `EPSG:4326` is the name of the lon/lat system. `"ESPG"` is a typo that fails.
- **Used for:** reading only a small area (about 11 km) of a 100 km tile, over the web.
- **Watch for:** a window is **silently clipped** to what exists. That produced the `(1106, 371)` strip. Always check `.shape`.

### 2.3 Pixel size and hectares
- **What:** a hectare is a fixed unit (10,000 m²). The pixel size comes from the sensor: 10 m for red, green, blue and NIR, so one pixel is 100 m² = 0.01 ha.
- **Where:** `PIXEL_HA = 10**2 / 10_000`, then `lake.sum() * PIXEL_HA`.
- **Watch for:** if you ever count 20 m pixels, the factor is 0.04, not 0.01. SCL is natively 20 m but we stretch it to 10 m.

### 2.4 Tiles, footprints and `covers`
- **What:** Sentinel-2 divides the Earth into tiles (e.g. `36MXE`). A scene's footprint is its bounding box. Dunga sits near a tile edge, so `36MYE` scenes cover only a strip of the box.
- **Where (`pipeline.py`) [ran]:**
  ```python
  def covers(scene, box):
      w, s, e, n = scene.bbox
      return w <= box[0] and s <= box[1] and e >= box[2] and n >= box[3]
  ```
- **Used for:** choosing scenes that cover the whole box. `find_scenes` runs this filter after the catalogue search.

### 2.5 Searching a catalogue (STAC)
- **What:** a standard way to search satellite archives by area, dates and filters. Results are *items* (scenes) with *assets* (files).
- **Where:** `Client.open(...)`, then `catalog.search(collections=..., bbox=..., datetime="2026-07-01/2026-09-30", query={"eo:cloud_cover": {"lt": 20}}, max_items=20)`.
- **Watch for:** `datetime` is a **range** (`start/end`), not a single day. Each scene carries its own capture date, which is also in its ID (`..._20260907_...`). `Client.open` is not Python's built-in `open`.

---

## 3. Satellite data (Sentinel-2)

### 3.1 Bands
- **What:** a band is a wavelength range measured separately. Red, green, blue and NIR are 10 m. Red-edge, SWIR and SCL are 20 m. Different materials reflect each band differently (water is dark in NIR, plants are bright in NIR).
- **Where:** `read_band(item, "red", bbox)`, `"nir"`, `"green"`, `"blue"`, `"scl"`. See `ZIWAVISION_GUIDE.md` and your band notes for the full table.

### 3.2 NDVI
- **What:** (NIR − red) / (NIR + red). High over plants, near 0 over bare ground, negative over water. It's a fixed formula; the **threshold is our choice**.
- **Where:**
  ```python
  ndvi = (nir - red) / (nir + red + 1e-6)     # explore_tile.py [ran]
  def ndvi_of(red, nir): ...                  # pipeline.py [added]
  ```
  `1e-6` stops a division by zero.
- **Used for:** the vegetation signal. At 0.3 it flags about twice as much as ESA's own vegetation label, mostly dry cropland (465,568 px vs 232,308 px on 7 Sep).
- **Reflectance offset (resolved):** `earthsearch:boa_offset_applied` is True for all scenes; Element84 already applied the baseline correction. Over lake water on 2026-08-28, red min=309, median=666, max=2737 and NIR min=139, median=325, max=4109 — these are normal 0 to 10,000 reflectance values, so no extra `(value - 1000) / 10000` step is needed.

### 3.3 The Scene Classification Layer (SCL)
- **What:** ESA's per-pixel labels. Used here: 2 dark, 4 vegetation, 5 not vegetated, 6 water, 7 unclassified, and 0, 1, 3, 8, 9, 10 for no data, defective, shadow, cloud and cirrus.
- **Where:**
  ```python
  def read_scl(item, bbox, like):
      scl = read_band(item, "scl", bbox, as_float=False)
      return cv2.resize(scl, (like.shape[1], like.shape[0]), interpolation=cv2.INTER_NEAREST)
  ```
- **Watch for:** labels must stay integers (`as_float=False`) and must be resized with `INTER_NEAREST`, otherwise labels get blended. A floating mat can be labelled vegetation, not water. Class 7 isn't a "bad" class in `BAD_CLASSES`.

### 3.4 Tile cloud vs box cloud
- **What:** `eo:cloud_cover` is for the whole 100 km tile. `box_cloud` measures cloud, shadow and missing data inside your box.
- **Where:**
  ```python
  BAD_CLASSES = [0, 1, 3, 8, 9, 10]
  def box_cloud(scl):
      return np.isin(scl, BAD_CLASSES).mean()
  ```
- **Result [ran]:** 15 Aug: tile 2.2% but box 17.5%. 12 Sep: tile 17.0% but box 0.0%. The tile figure would have rejected a clear date and accepted a cloudy one.

### 3.5 Metadata
- **What:** each scene records its platform, sun angle, processing details and more in `item.properties`.
- **Where:** `run_meta.py`: platform (A, B or C), `view:sun_elevation` (rose smoothly from 58.4° to 67.4°, no jump on 2 Sep).

---

## 4. NumPy

### 4.1 Arrays, `.shape` and `dtype`
- **What:** an image band is a 2D grid; a colour image is 3D `(rows, cols, 3)`. `.shape` is `(rows, columns)`. `dtype` is the number type (`float32` for measurements, integers for labels, `uint8` for 0-255 images).
- **Where:** `red.shape` is `(1106, 1113)` on every date, so masks line up pixel for pixel.
- **Rule:** after each new step, print the shape.

### 4.2 Boolean masks
- **What:** a True/False grid of the same shape, made by a comparison. Combine with `&` (and), `|` (or), `~` (not). `.sum()` counts True, `.mean()` gives the fraction of True.
- **Where:**
  ```python
  mask = ndvi > 0.3
  mask.mean()                                  # share of pixels that passed
  green & water                                # both true
  band & (scl == 7) & ~green_like              # in the band, unclassified, not vegetation
  overlay[mask] = [1, 1, 0]                    # paint those pixels
  scl[lost]                                    # read labels at only the lost pixels
  ```
- **Watch for:** use `&`/`|`/`~` on grids, never `and`/`or`/`not`. A mask must be True/False before `|` works (using the green *band* instead of `ndvi_green` caused a trap).

### 4.3 Lookups and counting
- **Where:**
  ```python
  np.isin(scl, [0, 1, 3, 8, 9, 10])                     # True if the label is in the list
  np.unique(scl_b[lost], return_counts=True)            # which labels, how many each
  np.argmax(stats[1:, cv2.CC_STAT_AREA])                # position of the largest blob
  ```

### 4.4 Building and reshaping
- **Where:**
  ```python
  np.dstack([red, green, blue])        # three grids into one colour image
  np.clip(rgb / 3000, 0, 1)            # cap values to 0-1
  np.zeros((*scl.shape, 3), dtype="uint8")   # empty colour image
  np.percentile(a, [2, 98])            # contrast stretch
  rgb[600:900, 100:500]                # slicing: rows, then columns
  ```

### 4.5 Stacking across dates
- **Where (`pipeline.py`) [ran]:**
  ```python
  def reference_lake(masks, min_share=0.6):
      stack = np.stack(masks)                  # (dates, rows, cols)
      share = stack.mean(axis=0)               # per pixel: fraction of dates it was lake
      return (share >= min_share).astype("uint8")
  ```
- **Concept:** `axis=0` collapses the first dimension (dates), leaving one number per pixel.

---

## 5. OpenCV

### 5.1 Saving and resizing
- `cv2.imwrite` fails **silently** if the folder doesn't exist (it returns `False`). Create `outputs/` in code and check the return value.
- `cv2.resize(img, (width, height))` takes **width first**, but NumPy shapes are (rows, columns). Hence `(like.shape[1], like.shape[0])`.
- `INTER_NEAREST` copies the closest pixel and is the right choice for labels.

### 5.2 Finding the lake: connected components and contours [ran]
```python
water = (scl == 6).astype("uint8")
n, labels, stats, _ = cv2.connectedComponentsWithStats(water, connectivity=8)
biggest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])      # row 0 is the background
lake = (labels == biggest).astype("uint8")
contours, _ = cv2.findContours(lake, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
filled = np.zeros_like(lake)
cv2.drawContours(filled, contours, -1, 1, thickness=cv2.FILLED)
```
- **Concept:** number each separate blob of water, keep the largest (the gulf, not the ponds), trace its outline and fill it so enclosed holes count as lake.
- **Watch for:** the rule "biggest water blob" depends on SCL labelling. If a piece is cut off, it drops out.

### 5.3 Erode, dilate and the shore band
```python
def ring(mask, inside_px, outside_px):                     # [added] in pipeline.py; same logic you ran in explore_tile.py
    k_out = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*outside_px + 1, 2*outside_px + 1))
    k_in = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*inside_px + 1, 2*inside_px + 1))
    return (cv2.dilate(mask, k_out) == 1) & (cv2.erode(mask, k_in) == 0)
```
- **Concept:** `dilate` grows a shape outwards, `erode` shrinks it inwards. Kernel sizes must be odd so there's a centre pixel. A strip around the shore is "grown minus shrunk".
- **Result [ran, first scene, 7 Sep]:** band 174.6 ha, 14.2% vegetation signal, 30.5% uncertain. The band reaches 50 m onto land, so it includes ordinary shoreline vegetation.

---

## 6. matplotlib

- `plt.subplots(1, 3)` makes panels. `imshow` draws an array. `savefig` saves the figure; `imsave` saves an array directly.
- Colours mean something **only inside the figure that uses them**. `shore.png` uses cyan (the band), yellow (vegetation signal in it) and magenta (unclassified, no vegetation signal). The SCL map uses its own palette. Give every figure a legend.
- Painting order matters: later lines overwrite earlier ones.

---

## 7. Thinking like an analyst

### 7.1 Check against reality
A mask is only believable next to the real picture. The true-colour image caught the clipped strip and the cloud.

### 7.2 Two methods that disagree
NDVI is your formula with your threshold. SCL is ESA's label. They overlap, and the places where they disagree are informative (1752 NDVI-green px inside SCL water; 234,678 px NDVI-green but SCL "not vegetated").

### 7.3 A step in a time series needs a diagnosis
- The lake area fell from 4,766 ha (28 Aug) to 4,519 ha (2 Sep).
- Ruled out as a single-satellite effect: A, B and C each appear on both sides. (Nine points: suggestive, not proof.)
- Lost 252.1 ha, gained 5.2 ha: one-directional.
- 87.7% of the lost area became SCL class 7 (unclassified); only 0.1 ha became vegetation.
- Unclassified share of the box rose from 1.3% to 3.5% on the same date.
- **Conclusion:** mostly the classifier becoming less sure, not mats. We handle it with a fixed reference lake.

### 7.4 Chosen numbers are choices
`NDVI_THRESHOLD = 0.3`, box cloud 5%, band width 3 px in and 5 px out, `min_share=0.6`. None is proven. Each should be written down with a reason, and the report should say so. For example, with 9 dates, 0.6 means a pixel must be lake on 6 dates, which left the reference at 4,610 ha, closer to the conservative lake.

### 7.5 A fixed ruler
Build the shore band once from the reference lake, then measure inside it on each date. Only the contents change, not the strip. Every clear date recognised 97.9% to 100% of the reference. The test is one-directional: 100% means a date contains the reference, not that it matches it exactly.

### 7.6 Limits worth stating
- One image cannot separate hyacinth from reeds; change over time can help.
- 10 m pixels may miss small mats.
- A single box can't see wind or current moving mats across the lake or across borders.
- Nothing is validated against ground truth yet.

---

## 8. Mistakes log

| Mistake | Symptom | Rule |
|---|---|---|
| `"eo: cloud_cover"` | `KeyError` | keys match exactly |
| `"ESPG:4326"` | `CRSError` | check spelling of codes |
| No `outputs/` folder | no file, no error | create folders in code; check return values |
| `"outpus/..."` | next error | reuse a variable for repeated paths |
| `imshow(items)` | `TypeError ... dtype object` | check the variable you pass |
| Box missed Dunga | wrong area | west, south, east, north; test with a known point |
| Picked a scene by cloud % | clipped strip | check footprint and `.shape` |
| `green` used for both the band and a mask | trap | one name, one meaning |
| Painted `green_like` for the whole image | all green went magenta | each colour needs its own mask |
| Renamed a variable, kept old name in `print` | `NameError` | search for the old name |
| Comment said "less than 0.05", code says `> 0.05` | wrong mental model | comments must describe the code |
| Metadata key misspelled | `baseline: None` | print the keys first; `.get` hides a bad name |
| Ran outside the venv | `ModuleNotFoundError` | activate `venv` first |

---

## 9. Still ahead

- Floating-vegetation and water indices (FAI, NDWI/MNDWI) and the 20 m bands
- Reflectance offset check (resolved: `earthsearch:boa_offset_applied` is True; red/NIR water pixels on 2026-08-28 confirm normal 0–10,000 reflectance)
- Climate data (`acmadDL`) and the risk score
- `analyse()` as one function; results per date as a table
- AWS: S3, DynamoDB, Lambda or Fargate, Graviton vs x86 timing
- The retry-on-cloud rule and the approval flag
- A small hand-labelled validation set