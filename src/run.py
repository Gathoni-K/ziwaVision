from pipeline import find_scenes, read_band

BBOX = [34.73, -0.22, 34.83, -0.12]

scenes = find_scenes(BBOX, "2026-07-01/2026-09-30")
for s in scenes:
    print(s.id, s.datetime.date(), s.properties["eo:cloud_cover"])

item = scenes[0]
red = read_band(item, "red", BBOX)
print("shape:", red.shape)


# Below is what the terminal outputs on running the file, it is correct as the shape matches the old script.
# S2C_36MXE_20260912_0_L2A 2026-09-12 17.03563
# S2B_36MXE_20260907_0_L2A 2026-09-07 4.425055
# S2A_36MXE_20260904_0_L2A 2026-09-04 11.389966
# S2C_36MXE_20260902_0_L2A 2026-09-02 15.144572
# S2B_36MXE_20260828_0_L2A 2026-08-28 0.000401
# S2A_36MXE_20260825_0_L2A 2026-08-25 5.033407
# S2C_36MXE_20260823_0_L2A 2026-08-23 4.411591
# S2B_36MXE_20260818_0_L2A 2026-08-18 4.063706
# S2A_36MXE_20260815_0_L2A 2026-08-15 2.163115
# S2B_36MXE_20260808_0_L2A 2026-08-08 14.622639
# S2C_36MXE_20260724_0_L2A 2026-07-24 5.463661
# shape: (1106, 1113)