# ZiwaVision progress

Deadline: 24 Oct 2026. Rule: a concept moves to "Understand" only when I can explain it in my own words without help.

## Concepts I understand
Move items here once you can explain them without looking.
- (nothing yet: fill this in as you go)

## Concepts I've seen but need to revisit
- Dictionaries and `KeyError` (keys must match exactly)
- Reading a traceback: last line first, then the line number above it
- Functions, default arguments (`as_float=True`)
- `with ... as` (open and close automatically)
- Unpacking with `*` (arguments, and shapes like `(*scl.shape, 3)`)
- List comprehension: `[it for it in items if covers(it, BBOX)]`
- `lambda` and `key=` in `min(...)`
- Failing early with `raise SystemExit(...)`
- Coordinates: lon/lat vs projected metres (CRS, EPSG:4326)
- Bounding box order: west, south, east, north
- Pixels, resolution (10 m vs 20 m), transform, window
- Sentinel-2 tiles (`36MXE`, `36MYE`), footprints, assets
- NDVI and thresholding; boolean masks (`mask.mean()` = fraction)
- Scene Classification Layer (SCL) classes
- NumPy: `.shape`, `dtype`, `dstack`, `clip`, `isin`, `unique`, painting with a mask
- OpenCV: `imwrite` fails silently; `resize` takes (width, height)
- matplotlib: `subplots`, `imshow`, `savefig`
- &/| on masks, array slicing, connected components, contours and filling, erosion, and pixel area to hectares.

## Day log

### Day 1 (1 Oct)
- **Did:** read the project brief, set up accounts and packages, created the project folder and virtual environment, wrote the first script.
- **Learned:** `KeyError` from a space in `"eo: cloud_cover"`; `CRSError` from `"ESPG"`; `cv2.imwrite` doesn't create folders.
- **Still confusing:** coordinate systems, windows.

### Day 2 (2 Oct)
- **Did:** true-colour image next to the NDVI mask; fixed `imshow(items)` and the `outpus/` typo; set a box around Dunga Beach (lat -0.1667, lon 34.7833); read `.shape` and found it was clipped.
- **Learned:** white = vegetation, black = not vegetation; cloud % is per tile, not per box; a window silently clips to what exists.
- **Still confusing:** why the footprint mattered; what SCL is.

### Day 3 (3 Oct)
- **Did:** chose the scene automatically by footprint (`covers`), read SCL and resized it to 10 m, coloured it, built a 3-panel comparison. Wrote README and guide.
- **Result:** `S2B_36MXE_20260907_0_L2A` covers the whole box, 4.4% cloud, image size 1106 x 1113 pixels, about 11 km square.
- **Learned:** the true-colour image shows the Winam Gulf clearly, with a dark green band along the shore.
- **Still confusing:** the numbers in the terminal output (see the notes below).
- **Next:** read the SCL and NDVI panels; find the lake; look for floating green inside it.

## Reading my terminal output (Day 3 run)

| Line | Means |
|---|---|
| `S2B_36MXE_20260907_0_L2A 4.43 [33.90, -0.99, 34.89, -0.00]` | scene ID, cloud % for the whole tile, footprint (west, south, east, north) |
| `2 scenes cover the whole box` | two of the five footprints contain `BBOX` |
| `using: ...` | the one with the lowest cloud % |
| `shape: (1106, 1113)` | 1106 rows by 1113 columns, at 10 m each |
| `np.unique(scl)` values and counts | which SCL classes appear and how many pixels each has |
| `cloud/no-data fraction: 0.0` | none of the pixels are cloud, shadow or missing |
| `green fraction: 0.378` | 37.8% of pixels have NDVI above 0.3 |

## Questions I still want answered
- Where is the lake in the SCL panel, and does it match the true-colour image?
- Why does NDVI call 38% green while SCL calls 19% vegetation?
- Can I see any floating vegetation in open water, or only the shore band?
- Is 10 m enough for the mat sizes that matter?

## Habits to keep
- Change one thing at a time, then re-run.
- Check `.shape` and a picture after every new step.
- Time-box: stuck for 45 minutes, ask for help.
- Commit after each working step.