import numpy as np
import matplotlib.pyplot as plt
from pipeline import (find_scenes, read_band, read_scl, box_cloud, lake_mask, reference_lake, PIXEL_HA)

BBOX = [34.73, -0.22, 34.83, -0.12]
scenes = find_scenes(BBOX, "2026-07-01/2026-09-30")

masks, dates = [], []
# creates 2 empty lists
for s in scenes:
    red = read_band(s, "red", BBOX)
    scl = read_scl(s, BBOX, red)

    if box_cloud(scl) > 0.05:
        continue

    lake = lake_mask(scl)

    if lake is None:
        continue
    # handles the early exit from lake_mask, no water at all, so a bad scene does not crash the run

    masks.append(lake)
    dates.append(str(s.datetime.date()))

ref = reference_lake(masks, min_share=0.6)
# stacks the masks and keeps the pixels that are lake on at least 60% of the dates.
# pixels that SCL occassionally calls unclassified still count as lake
print("reference lake:", f"{ref.sum() * PIXEL_HA:.0f} ha", "from", len(masks), "dates")

for d, m in zip(dates, masks):
    covered = ((m ==1) & (ref ==1)).sum() / ref.sum()
    # finds pixels that are lake on that date and part of the reference
    # division by ref.sum gives the share of the reference lake that date recognised.
    print(d, f"share of reference lake that this date labels as lake: {covered:.1%}")

plt.imsave("outputs/reference_lake.png", ref, cmap="gray")
# saves the mask as a black and white picture.

# reference lake: 4610 ha from 9 dates
# 2026-09-12 share of reference lake that this date labels as lake: 99.5%
# 2026-09-07 share of reference lake that this date labels as lake: 99.2%
# 2026-09-04 share of reference lake that this date labels as lake: 98.2%
# 2026-09-02 share of reference lake that this date labels as lake: 97.9%
# 2026-08-28 share of reference lake that this date labels as lake: 100.0%
# 2026-08-25 share of reference lake that this date labels as lake: 100.0%
# 2026-08-23 share of reference lake that this date labels as lake: 100.0%
# 2026-08-18 share of reference lake that this date labels as lake: 99.9%
# 2026-07-24 share of reference lake that this date labels as lake: 100.0%

# that is what the file outputs.
# the test only works in one direction, it only asks how much of the reference does the date label as a lake.