from pipeline import find_scenes, read_band, read_scl, box_cloud, lake_mask, PIXEL_HA

# what this file does, it tries to test a pattern, the lake area climbs from 4,519, 2 Sep to 4,604 12 Sep which would fit 'unclassified shrinks again'
# this is based on the output from 'run_diff.py'
# If the assumptions are correct, the unclassified share of the box should go the opposite way.

BBOX = [34.73, -0.22, 34.83, -0.12]
scenes = find_scenes(BBOX, "2026-07-01/2026-09-30")

for s in scenes:
    red = read_band(s, "red", BBOX)
    scl = read_scl(s, BBOX, red)

    if box_cloud(scl) > 0.05:
        continue
    # skips the cloudy dates as before.

    lake = lake_mask(scl)
    print(s.datetime.date(), s.id[:3],
    f"unclassified in box {(scl == 7).mean():.1%}",
    # this is the share of the box labelled as unclassified
    f"| title unclassified {s.properties.get('s2:unclassified_percentage')}",
    # this is ESA's figure for the whole tile, from the key list in our meta output
    f"| lake{lake.sum() * PIXEL_HA:.0f} ha"
    )

# 2026-09-12 S2C unclassified in box 2.8% | title unclassified 1.337726 | lake4604 ha
# 2026-09-07 S2B unclassified in box 3.5% | title unclassified 0.280022 | lake4584 ha
# 2026-09-04 S2A unclassified in box 3.7% | title unclassified 0.806474 | lake4536 ha
# 2026-09-02 S2C unclassified in box 3.5% | title unclassified 0.305921 | lake4519 ha
# 2026-08-28 S2B unclassified in box 1.3% | title unclassified 0.117793 | lake4766 ha
# 2026-08-25 S2A unclassified in box 1.5% | title unclassified 0.146937 | lake4747 ha
# 2026-08-23 S2C unclassified in box 1.2% | title unclassified 0.230523 | lake4779 ha
# 2026-08-18 S2B unclassified in box 1.2% | title unclassified 0.388336 | lake4756 ha
# 2026-07-24 S2C unclassified in box 0.5% | title unclassified 0.373227 | lake4773 ha

# at this point, the data shows us that the step shows up in both columns on the same date.
# unclassified goes from 1.3% to 3.5% between 28 Aug and 2 Sep, about 2.2 points, roughly 270ha
# the lake 247ha
# this is good evidence that the lake step classifier is becoming less sure