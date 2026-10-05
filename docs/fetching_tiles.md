# ZiwaVision Guide: what we've built and what it taught us

A map of the work so far, the concepts behind it, and where to go deeper after the hackathon.
Last updated: Day 2 (2 Oct 2026). Keep this file in your project root next to `PROGRESS.md`.

---

## 1. Where you are

**Done**
- [x] Accounts and packages installed (`opencv-python`, `rasterio`, `numpy`, `matplotlib`, `pystac-client`, `acmadDL`, `boto3`)
- [x] Project structure: `src/`, `outputs/`, virtual environment
- [x] Searched the public Sentinel-2 archive for scenes over Dunga Beach
- [x] Read bands (red, near-infrared, green, blue) for just your area of interest
- [x] Computed NDVI and a vegetation mask
- [x] Built a true-colour image and a side-by-side comparison
- [x] Discovered that your scene only covers part of your box, and why
- [x] Found the Scene Classification Layer (`scl`) and read its labels

**Next**
- [ ] Pick a scene that fully covers the box (see section 4)
- [ ] Use SCL to mask clouds and find the lake
- [ ] Separate floating vegetation (candidate hyacinth) from land vegetation
- [ ] Clean the mask with OpenCV (morphology) and count mat area
- [ ] Repeat across dates to get a trend

---

## 2. The project map

ZiwaVision answers: *where is hyacinth growing, and where will it grow faster next?*

```
satellite scene ──► read bands ──► mask clouds ──► find lake ──► find floating green ──► area per zone
   (Sentinel-2)      (rasterio)       (SCL)         (SCL/NDWI)      (NDVI + OpenCV)           │
                                                                                              ▼
rainfall forecast (acmadDL) ─────────────────────────────────────────────────────────► risk score ──► DynamoDB ──► ZiwaClear
```

Today's script (`explore_tile.py`) covers the first three boxes and part of the fourth. Everything else in the brief builds on it, so getting this stage right matters most.

---

## 3. Concepts practised, in detail

### 3.1 Python

| Concept | What it is | Where you met it |
|---|---|---|
| Variable | A name pointing to a value | `BBOX`, `items`, `red` |
| List | An ordered collection, read by position (starting at 0) | `items[0]`, the `BBOX` list |
| Dictionary | `key: value` pairs, read by key | `it.properties["eo:cloud_cover"]` |
| `KeyError` | The key you asked for doesn't exist (typo, space, wrong case) | `"eo: cloud_cover"` |
| Function | Reusable code with a name | `read_band(name)` |
| Default argument | A parameter with a preset value | `as_float=True` |
| `for` loop | Repeat for each item | printing each scene |
| `with ... as` | Open something and close it automatically | `with rasterio.open(...) as src` |
| Unpacking (`*`) | Spread a list into separate arguments | `transform_bounds(..., *BBOX)` |
| Method vs built-in | `Client.open()` is a method of a library; `open()` is Python's file opener. Same word, different things. | the catalogue connection |

**Reading a traceback:** read the *last line* first (what went wrong), then the line number just above it (where). If that line looks fine, look at the lines before it. A function that fails silently (like `cv2.imwrite` returning `False`) is the hardest kind, so check return values.

### 3.2 Coordinates and maps (the part that trips everyone up)

- **Longitude/latitude (EPSG:4326):** angles on the globe, in degrees. Order in code: **west, south, east, north** (longitude first). Dunga: lat -0.1667, lon 34.7833.
- **CRS (coordinate reference system):** the rule for turning positions into numbers. Satellite files use a *projected* CRS measured in metres, so the lon/lat box has to be converted: `transform_bounds`.
- **Pixel and resolution:** Sentinel-2 red/green/blue/NIR bands have 10 m pixels, so a 50 m mat is about 5 pixels wide. `scl` is 20 m.
- **Transform:** the image's rule mapping pixel row/column to ground position.
- **Window:** a rectangle of pixels. Reading a window means reading only your area instead of the whole 100 km tile, and it works over the web because the files are cloud-optimized (more in section 7).
- **Degrees to distance:** near the equator, 0.1° is about 11 km. This is how we explained the `371` columns (section 4).

### 3.3 Satellite data (Sentinel-2)

- **STAC catalogue:** a standard way to search satellite archives. You send a bounding box, dates and filters, and get back *items* (scenes), each with *assets* (files).
- **Tile / scene:** Sentinel-2 divides the Earth into squares (e.g. `36MXE`). Tiles overlap a little, and a point near an edge may sit in two. Dunga is close to such an edge.
- **Bands:** each band is a slice of light. Red, green and blue make a normal photo. Near-infrared (NIR) is invisible to us but shows plants strongly.
- **Cloud cover metadata** (`eo:cloud_cover`) is a percentage for the **whole tile**, not for your box.
- **Reflectance scaling:** the raw numbers are integers, not 0 to 1. Real reflectance is `(value - 1000) / 10000`. Our script doesn't apply this yet; it's on the to-do list (see section 6).

### 3.4 Remote sensing

- **NDVI** = (NIR - red) / (NIR + red). Plants reflect a lot of NIR and absorb red, so NDVI is high over vegetation (roughly -1 to +1).
- **Threshold:** a cutoff (we used 0.3) that turns a continuous value into yes/no. It's a *choice*, not a fact; we'll tune and validate it.
- **True colour:** red, green and blue stacked into a normal picture. You always compare a derived mask against the real image.
- **SCL (Scene Classification Layer):** per-pixel labels from Sentinel's own classifier.

| Value | Class | | Value | Class |
|---|---|---|---|---|
| 0 | No data | | 6 | Water |
| 1 | Saturated/defective | | 8 | Cloud (medium) |
| 3 | Cloud shadow | | 9 | Cloud (high) |
| 4 | Vegetation | | 10 | Thin cirrus |
| 5 | Not vegetated | | | |

**Important caveat:** a floating hyacinth mat is a green plant, so SCL will often label it *vegetation (4)*, not *water (6)*. That means we can't simply say "count vegetation only where SCL says water". The lake has to be found some other way first (section 6).

### 3.5 NumPy (the engine under everything)

- **Array:** a grid of numbers. An image band is a 2D array; a colour image is 3D (rows, columns, 3).
- **`.shape`:** `(rows, columns)`. Always check it. It's the cheapest sanity test.
- **`dtype`:** the kind of number (`float32`, `uint8`). Labels like SCL must stay integers; measurements are floats.
- **Boolean mask:** `ndvi > 0.3` gives a True/False grid of the same shape.
- **`.mean()` on a mask:** the fraction of True values (True counts as 1).
- **`np.dstack`, `np.clip`, `np.isin`, `np.unique`:** stack, cap values, test membership in a list, and list distinct values with counts.

### 3.6 OpenCV

Used so far: `cv2.imwrite` (save an image; returns `False` if it fails, e.g. missing folder) and `cv2.resize` with `INTER_NEAREST` (stretch the 20 m SCL to 10 m without blending labels). **Remember:** OpenCV takes size as *(width, height)* while NumPy shapes are *(rows, columns)*.

Coming next: morphology (`erode`, `dilate`, `morphologyEx`) to remove speckle and fill holes, `findContours` to outline shapes, and `contourArea` to measure them.

### 3.7 matplotlib

`plt.subplots(1, 2)` makes panels; `imshow` draws an array as an image; `savefig` writes it to a file (more reliable than `show()` on Linux/WSL).

---

## 4. What your results taught us

Your five scenes and their footprints (west, south, east, north):

| Scene | Cloud % (whole tile) | Footprint west to east |
|---|---|---|
| S2B 36MYE 27 Sep | 8.7 | 34.797 to 35.783 |
| S2C 36MYE 22 Sep | 14.9 | 34.797 to 35.783 |
| S2C 36MXE 12 Sep | 17.0 | 33.899 to 34.885 |
| S2B 36MXE 07 Sep | 4.4 | 33.899 to 34.885 |
| S2B 36MYE 07 Sep | 7.6 | 34.797 to 35.783 |

Your box runs west 34.73 to east 34.83.

- **`36MYE` scenes start at 34.797.** Only the strip from 34.797 to 34.83 (0.033° ≈ 3.7 km ≈ 370 pixels) overlaps your box. That's why you got `371` columns: the window was silently clipped.
- **`36MXE` scenes cover 33.899 to 34.885**, so they contain the whole box. The best candidate is **S2B 36MXE 07 Sep (4.4% cloud)**, then S2C 36MXE 12 Sep.
- **The SCL counts** (`4, 5, 8, 9, 10` and no `6`) described only that clipped strip: about 98% cloud or no-data and no water at all. That was the cloudy strip you saw in the picture, not the gulf.
- **Lesson:** scenes with the same date and cloud percentage can still be the wrong ones. Check footprint and `.shape`, not just cloud percentage.

---

## 5. Mistakes log (every one of these is a skill)

| Mistake | Symptom | Rule |
|---|---|---|
| Space inside a key: `"eo: cloud_cover"` | `KeyError` | Keys match character for character |
| `"ESPG:4326"` | `CRSError` | Check spelling of codes and names |
| Missing `outputs/` folder | No file, no error | Create folders in code; check return values |
| `outpus/` typo | Next error waiting | Reuse a variable for repeated paths |
| `imshow(items)` instead of the mask | `TypeError` ... `dtype object` | "object" means non-numeric data went in |
| Box missed the site | Wrong area | West, south, east, north; test against known coordinates |
| Picked scene by cloud % only | Clipped, cloudy strip | Check footprint and `.shape` |

---

## 6. Next steps (short term)

1. In `explore_tile.py`, choose the 36MXE 07 Sep scene (it's the fourth in your list, so `items[3]`) and check that `red.shape` is about `(1100, 1100)`.
2. Re-run the SCL block. You should now see `6` (water) in `np.unique`.
3. Check how much of the box is cloud or no-data over the gulf. If it's too much, try the 12 Sep scene.
4. Apply the reflectance scaling (`(value - 1000) / 10000`) to the colour/NIR bands and re-check your NDVI threshold.
5. Find the lake: take the water class, fill its holes with OpenCV morphology, and treat everything inside that shape as lake. Candidate hyacinth is NDVI-green *inside* the lake shape but not labelled as land.

---

## 7. After the hackathon: concepts to strengthen

Ordered roughly by how much they help this project.

**Python and project hygiene**
- Virtual environments and `requirements.txt` properly; project layout; modules and imports
- Functions with type hints and docstrings; writing small tests with `pytest`
- Configuration and secrets: environment variables, `.env`, never committing keys
- Logging instead of `print`

**Geospatial fundamentals**
- Coordinate reference systems: why UTM zones exist, how reprojection works
- Raster vs vector data; `rasterio`, `geopandas` and `shapely` (polygons for lake zones)
- Cloud-Optimized GeoTIFFs and why reading windows over HTTP is fast
- STAC in depth, plus other archives (Landsat, Copernicus, Google Earth Engine)

**Remote sensing**
- Spectral indices: NDWI/MNDWI (water), FAI (floating algae/vegetation index, directly relevant), EVI
- Atmospheric correction and what L1C vs L2A means
- Cloud masking, compositing and time series; why single images mislead
- Mixed pixels: what happens when a mat is smaller than one pixel
- Validation: precision, recall, confusion matrices, labelled sample design

**Computer vision (OpenCV)**
- Morphological operations, connected components, contours
- Thresholding methods (Otsu, adaptive) and why a fixed 0.3 isn't a law
- From rules to learning: `scikit-learn` classifiers on band values, then small segmentation models (U-Net)

**Data and cloud engineering**
- NumPy/xarray for time series; `xarray` is already installed and suits climate data
- AWS basics: S3, IAM least-privilege, Lambda, DynamoDB design, Step Functions
- Cost and observability: CloudWatch, budgets
- Benchmarking properly: warm-up runs, repeats, controlling for I/O (relevant to the Graviton vs x86 comparison)

**Science and honesty**
- Causal vs correlational claims (rainfall to hyacinth growth)
- Uncertainty: reporting confidence, not just a number
- Documenting assumptions and failure modes in a technical report

---

## 8. Open questions to carry with you

- Is 10 m resolution enough for the mat sizes that matter at zone level? (Your first real answer will come from a clear scene over the gulf.)
- Where should the NDVI threshold sit, and how will we justify it?
- How will we handle scenes where clouds cover most of a zone? (The agent's "low confidence" path.)
- How will we label a small validation set for the segmentation step?

## 9.What each image represents so far:

1. ndvi_mask.png - this is produced by NDVI and a threshold, the 0.3.
- The purpose of this image was to test whether we can pick out green things from the satellite bands at all.
- It confirmed this as land lights up white.
- However, this produced a black and white image, the problem is this is that we could not differentiate the vegetation on land and on the lake.

2. compare.png - this is produced by rgb stackng.
- It's purpose was testing whether the mask matches what is truly there.
- However, this produced an image where there was no lake visible, the strip was clipped and cloudy.
- The problem with this image was that it was the wrong shape initially.

3. candidates.png - this is produced by the lake mask, fill and erode.
- It was used to test for which green pixels are inside the lake and which are away from the shore.
- This produced 272px with (5,5) inside and only 27 away from the shore.
- It was used to test for the vegetation touching the shore.

**Upto this point, none of the images are hyacinth detectors, everything so far is preparation, making sure we are checking at the right place with no cloud, with the lake separated from the land**

4. shore.png - this is a true-color photooe with 2 ovrlays painted on top:
- Greyish-green water - the real satellite colors.
- Cyan band - the shore band from 'ring(...)' about 30m inside the lake edge to 50m outside. It is a location not a class.
- Yellow - the pixels inside that band that passed 'green_like'


**NDVI vs SCL**

- NDVI was created and exists in our script.
- It is one formula on two bands (NIR - red ) / (NIR + red)
- It outputs a continuous number between -1 and 1.
- Its threshold is chosen as 0.3

- SCL is made by ESA, In their processing before it is downloaded.
- It is a longer set of tests on many bands plus thresholds.
- Outputs a category label (watre, vegetation, cloud)
- Its threshold is fixed by ESA.

- THEY OVERLAP BUT DO NOT AGREE EVERYWHERE, WHICH IS WHY WE COMPARE THEM:
'NDVI-green pixels inside SCL water is:'

   green & (scl == 6)

- Pixels where the test says 'green' and ESA's label says 'water'. If the two always agreed, it would be 0.

- But this is what the terminal outputs:

      NDVI-green pixels inside SCL water: 1752

- This difference is worth examining: possible floatng plants, (green, but over water), possible mixed shoreline pixels, possibly ponds.
- As for who decides the pixel size, the sensor's designers do.Sentinel-2's instrument was built by ESA so that each nand is recorded at a fixed ground size and that size is part of the data being downloaded.
- Different bands have different native sizes:

   Blue, green. red, NIR - 10m
   Red-edge, SWIR, SCL - 20m
   COastal, water vapour - 60m

- Pixels can be larger or smaller than 10m BUT THAT IS PER DATASET NOT PER CHOICE, AN IMAGE CAN BE RESIZED, BUT THAT ADDS NO INFORMATION.