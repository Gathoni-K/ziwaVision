import numpy as np
import matplotlib.pyplot as plt
from pipeline import (find_scenes, read_band, read_scl, box_cloud, lake_mask, reference_lake, ring, ndvi_of, PIXEL_HA)

BBOX = [34.73, -0.22, 34.83, -0.12]
NDVI_THRESHOLD = 0.3

scenes = find_scenes(BBOX, "2026-07-01/2026-09-30")

data, masks = [], []
# we read each scene once and keep red, nir and scl in a list
# data holds one tuple per date
# masks one tuple per data
for s in scenes:
    red = read_band(s, "red", BBOX)
    nir = read_band(s, "nir", BBOX)
    scl = read_scl(s, BBOX, red)

    if box_cloud(scl) > 0.05:
        continue

    lake = lake_mask(scl)

    if lake is None:
        continue

    data.append((str(s.datetime.date()), red, nir, scl))
    masks.append(lake)

ref = reference_lake(masks, min_share=0.6)
band = ring(ref, inside_px=3, outside_px=5)
n = band.sum()

print("fixed shore band:", f"{n * PIXEL_HA:.0f} ha")
# what it does, it prints the area in curly braces formatted to 2 d.p
# n = band.sum() is the count of true pixels in band
print("band px:", band.sum(), "| reference px:", ref.sum())
plt.imsave("outputs/band_check.png", band, cmap="gray")

for date, red, nir, scl in sorted(data, key=lambda d: d[0]):
    # each tuple is unpacked straight into 4 names, sorted/// orders by the first item, so the output reads as a time series
    ndvi = ndvi_of(red, nir)
    veg_ndvi = band & (ndvi > NDVI_THRESHOLD)
    # is the line that ensures that green pixels elsewhere in the picture are not counted, because the '&' leeps only the pixels that are inside the band
    veg_scl = band & (scl == 4)
    unc = band & (scl == 7)
    # we measure vegetation two ways on purpose, veg_ndvi only uses the bands so it is not dependent on scl
    # veg_scl is dependent on SCL labels
    # scl's labelling shift around Sep 2 so if both measures move together we can trust the signal

    print(date,
    f"NDVI-green {veg_ndvi.sum() * PIXEL_HA:5.1f} ha ({veg_ndvi.sum() / n:.1%})",
    f"| SCL-veg {veg_scl.sum() * PIXEL_HA:5.1f} ha",
    f"| unclassified {unc.sum() / n:.1%}"
    )

# fixed shore band: 4536 ha
# 2026-07-24 NDVI-green  15.6 ha (0.3%) | SCL-veg   0.0 ha | unclassified 0.0%
# 15.6 ha with NDVI > 0.4 that are also inside the band, SCL - veg are the pixels in the band that ESA labels as vegetation, and unclassified is the share of the band labelled 7
# 2026-08-18 NDVI-green  11.7 ha (0.3%) | SCL-veg   0.0 ha | unclassified 0.1%
# 2026-08-23 NDVI-green   4.0 ha (0.1%) | SCL-veg   0.0 ha | unclassified 0.0%
# 2026-08-25 NDVI-green   1.1 ha (0.0%) | SCL-veg   0.0 ha | unclassified 0.0%
# 2026-08-28 NDVI-green   0.0 ha (0.0%) | SCL-veg   0.0 ha | unclassified 0.0%
# 2026-09-02 NDVI-green   0.0 ha (0.0%) | SCL-veg   0.0 ha | unclassified 0.9%
# 2026-09-04 NDVI-green   0.0 ha (0.0%) | SCL-veg   0.0 ha | unclassified 0.8%
# 2026-09-07 NDVI-green   0.0 ha (0.0%) | SCL-veg   0.0 ha | unclassified 0.3%
# 2026-09-12 NDVI-green   0.0 ha (0.0%) | SCL-veg   0.0 ha | unclassified 0.2%