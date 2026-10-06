from pipeline import find_scenes, read_band, read_scl, box_cloud, lake_mask, PIXEL_HA

BBOX = [34.73, -0.22, 34.83, -0.12]

scenes = find_scenes(BBOX, "2026-07-01/2026-09-30")

for s in scenes:
    red = read_band(s, "red", BBOX)
    scl = read_scl(s, BBOX, red)
    cloud = box_cloud(scl)

    if cloud > 0.05:
        print(s.datetime.date(), f"box cloud {cloud:.1%}: skipped")
        continue

    lake = lake_mask(scl)
    print(s.datetime.date(), f"box cloud {cloud:.1%}", f"lake {lake.sum() * PIXEL_HA:.0f} ha")