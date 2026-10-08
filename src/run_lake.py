from pipeline import find_scenes, read_band, read_scl, box_cloud, lake_mask, PIXEL_HA

BBOX = [34.73, -0.22, 34.83, -0.12]
# define long and lat

scenes = find_scenes(BBOX, "2026-07-01/2026-09-30")
# record scenes from date 1 of July to date 30 September 
# the syntax for writing dat ein python is 'y-m-d'

for s in scenes:
    # then for every item recorded in the variable scenes
    red = read_band(s, "red", BBOX)
    # assign the red band, being the band plants absors, which is why NDVI uses it
    # it is read so that read_scl has an array to match its shape to (like=red), it will be used for ndvi later
    scl = read_scl(s, BBOX, red)
    # reads ESA's labels for the box and stretches them to the 10m grid
    cloud = box_cloud(scl)
    # stores cloud


    if cloud > 0.05:
        # if cloud coverage is more than 0.05, only then does it print its values
        print(s.datetime.date(), f"box cloud {cloud:.1%}: skipped")
        continue

    lake = lake_mask(scl)
    print(s.datetime.date(), f"box cloud {cloud:.1%}", f"lake {lake.sum() * PIXEL_HA:.0f} ha")


# 2026-09-12 box cloud 0.0% lake 4604 ha
# 2026-09-07 box cloud 0.0% lake 4584 ha
# 2026-09-04 box cloud 0.0% lake 4536 ha
# 2026-09-02 box cloud 0.0% lake 4519 ha
# 2026-08-28 box cloud 0.0% lake 4766 ha
# 2026-08-25 box cloud 0.0% lake 4747 ha
# 2026-08-23 box cloud 0.0% lake 4779 ha
# 2026-08-18 box cloud 0.9% lake 4756 ha
# 2026-08-15 box cloud 17.5%: skipped
# 2026-08-08 box cloud 8.9%: skipped
# 2026-07-24 box cloud 0.0% lake 4773 ha

# that is the output at this point.
# the lake mask counts pixels that SCL labels as water, so it changes when pixels change labels.
# There is a discrepancy in this data, the lake area between 28 August and 2 September
# before 2 Sep, the lake sits in a narrow range, 5 dates fall between 4,747 and 4779 ha, a spread of only 30 ha
# it then drops by 230 ha in 5 days, then after the drop it climbs back
# the drop does not line up with the satellite