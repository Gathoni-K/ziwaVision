from numpy import tile
from pipeline import find_scenes, read_band, read_scl, box_cloud

BBOX = [34.73, -0.22, 34.83, -0.12]

scenes = find_scenes(BBOX, "2026-07-01/2026-09-30")
print(len(scenes), "scenes over the box")

for s in scenes:
    red = read_band(s, "red", BBOX)
    scl = read_scl(s, BBOX, red)
    print(s.datetime.date(), red.shape,
    f"tile cloud {s.properties['eo:cloud_cover']:.1f}%",
    f"box cloud {box_cloud(scl):.1%}"
    )


# below is what the terminal outputs:
# 2026-09-12 (1106, 1113) tile cloud 17.0% box cloud 0.0%
# 2026-09-07 (1106, 1113) tile cloud 4.4% box cloud 0.0%
# 2026-09-04 (1106, 1113) tile cloud 11.4% box cloud 0.0%
# 2026-09-02 (1106, 1113) tile cloud 15.1% box cloud 0.0%
# 2026-08-28 (1106, 1113) tile cloud 0.0% box cloud 0.0%
# 2026-08-25 (1106, 1113) tile cloud 5.0% box cloud 0.0%
# 2026-08-23 (1106, 1113) tile cloud 4.4% box cloud 0.0%
# 2026-08-18 (1106, 1113) tile cloud 4.1% box cloud 0.9%
# 2026-08-15 (1106, 1113) tile cloud 2.2% box cloud 17.5%
# 2026-08-08 (1106, 1113) tile cloud 14.6% box cloud 8.9%
# 2026-07-24 (1106, 1113) tile cloud 5.5% box cloud 0.0%


# As suspetced, tile cloud and box cloud disagree, compare the outputs from run.py and this file:
# 15 Aug: tile 2.2% but 17.5% of the box is cloud, the tile figure would have told us if it was a clear day
# 8 AUg: tile 14.6% but box shows 0

# Nine out of the eleven dates are useful

# Tile-level cloud is a poor guide for a small area and measuring per box changes what dates are trusted.
# It is also the first piece of the agent's evaluation confidence step, with a rule like 'box cloud above 5% skip this date and try another'
# Whatever cutoff is chosen should be recorded as a choice and not a  proven value