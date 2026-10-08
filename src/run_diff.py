import numpy as np
import matplotlib.pyplot as plt
from pipeline import find_scenes, read_band, read_scl, lake_mask, PIXEL_HA

BBOX = [34.73, -0.22, 34.83, -0.12]

scenes = find_scenes(BBOX, "2026-07-01/2026-09-30")
by_date = {str(s.datetime.date()): s for s in scenes}

def lake_for(date):
    s = by_date[date]
    red = read_band(s, "red", BBOX)
    scl = read_scl(s, BBOX, red)

    return red, lake_mask(scl)

red_a, lake_a = lake_for("2026-08-28")
red_b, lake_b, = lake_for("2026-09-02")

lost = (lake_a == 1) & (lake_b == 0)
gained = (lake_a == 0) & (lake_b == 1)
print("lost:", lost.sum() * PIXEL_HA, " ha gained:", gained.sum() * PIXEL_HA, "ha")

lo, hi = np.percentile(red_b, [2, 98])
base = np.clip((red_b - lo) / (hi - lo), 0, 1)
img = np.dstack([base, base, base])
img[lost] = [1, 0, 0]
img[gained] = [0, 0.4, 1]
plt.imsave("outputs/lake_diff2.png", img)

# the purpose of this file is to calculate the difference in lake coverage across the 2 dates, 28th August and 2nd September.
# this is the out put of the file:
# lost: 252.12  ha gained: 5.2 ha


scl_b = read_scl(by_date["2026-09-02"], BBOX, red_b)
names = {2: "dark", 4: "vegetation", 5: "not vegetated", 6: "water", 7: "unclassified"}
values, counts = np.unique(scl_b[lost], return_counts=True)
for v, c in zip(values, counts):
    print(int(v), names.get(int(v), "other"), f"{c * PIXEL_HA:.1f} ha", f"{c / lost.sum():.1%}")