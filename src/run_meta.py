from pipeline import find_scenes

BBOX = [34.72, -0.22, 34.83, -0.12]
scenes = find_scenes(BBOX, "2026-07-01/2026-09-30")

print(list(scenes[0].properties.keys()))

for s in scenes:
    p = s.properties
    print(s.datetime.date(), s.id[:3],
    "baseline:", p.get("s2.processing_baseline"),
    "sun elevation:", p.get("view:sun_elevation"),
    "platform:", p.get("platform")
    
    )

# the purpose of this file is to print the satelittes being used, the sun elevation and what does that help us with?
# it tests one specific idea, that something recorded aout the scenes changed at the same time as the step on September 2nd.
# this is tied to the discrepancy pointed out in the run_lake.py file.
# Metadata is cheap to rea, so we are ruling out simple explanations before lookin at hyacinth

# below is the output of this file upto this point:
# ['created', 'platform', 'constellation', 'instruments', 'eo:cloud_cover', 'proj:centroid', 'mgrs:utm_zone', 'mgrs:latitude_band', 'mgrs:grid_square', 'grid:code', 'view:azimuth', 'view:incidence_angle', 'view:sun_azimuth', 'view:sun_elevation', 's2:tile_id', 's2:degraded_msi_data_percentage', 's2:nodata_pixel_percentage', 's2:saturated_defective_pixel_percentage', 's2:cloud_shadow_percentage', 's2:vegetation_percentage', 's2:not_vegetated_percentage', 's2:water_percentage', 's2:unclassified_percentage', 's2:medium_proba_clouds_percentage', 's2:high_proba_clouds_percentage', 's2:thin_cirrus_percentage', 's2:snow_ice_percentage', 's2:product_type', 's2:processing_baseline', 's2:product_uri', 's2:generation_time', 's2:datatake_id', 's2:datatake_type', 's2:datastrip_id', 's2:reflectance_conversion_factor', 'datetime', 's2:sequence', 'earthsearch:s3_path', 'earthsearch:payload_id', 'earthsearch:boa_offset_applied', 'processing:software', 'updated', 'proj:code']
# 2026-09-12 S2C baseline: None sun elevation: 67.3997929190965 platform: sentinel-2c
# 2026-09-07 S2B baseline: None sun elevation: 66.5394947688412 platform: sentinel-2b
# 2026-09-04 S2A baseline: None sun elevation: 66.0527330283026 platform: sentinel-2a
# 2026-09-02 S2C baseline: None sun elevation: 65.6013147075496 platform: sentinel-2c
# 2026-08-28 S2B baseline: None sun elevation: 64.6058656844498 platform: sentinel-2b
# 2026-08-25 S2A baseline: None sun elevation: 64.0653465681329 platform: sentinel-2a
# 2026-08-23 S2C baseline: None sun elevation: 63.5931205548582 platform: sentinel-2c
# 2026-08-18 S2B baseline: None sun elevation: 62.5860765862635 platform: sentinel-2b
# 2026-08-15 S2A baseline: None sun elevation: 62.0629993325947 platform: sentinel-2a
# 2026-08-08 S2B baseline: None sun elevation: 60.697238864746 platform: sentinel-2b
# 2026-07-24 S2C baseline: None sun elevation: 58.4075412158138 platform: sentinel-2c

# The reason for noting the sun elevation is because it controls how bright the scene is and how the water reflects light and the classifier labels depend on brightness
# WHat the data reports, the sun elevation rises smoothly from JUly 24 to 12 Sep. The data tells us that lighting did not suddenly change on Sep 2, and it is unlikely to account for the 250 ha drop

print("---")
for s in scenes:
    p = s.properties
    print(s.datetime.date(), p.get("processing:software"),
        p.get("s2:product_uri", "")[-45:],
        "boa offset applied:", p.get("earthsearch:boa_offset_applied"),
        "tile water %:", p.get("s2:water_percentage"))


# ['created', 'platform', 'constellation', 'instruments', 'eo:cloud_cover', 'proj:centroid', 'mgrs:utm_zone', 'mgrs:latitude_band', 'mgrs:grid_square', 'grid:code', 'view:azimuth', 'view:incidence_angle', 'view:sun_azimuth', 'view:sun_elevation', 's2:tile_id', 's2:degraded_msi_data_percentage', 's2:nodata_pixel_percentage', 's2:saturated_defective_pixel_percentage', 's2:cloud_shadow_percentage', 's2:vegetation_percentage', 's2:not_vegetated_percentage', 's2:water_percentage', 's2:unclassified_percentage', 's2:medium_proba_clouds_percentage', 's2:high_proba_clouds_percentage', 's2:thin_cirrus_percentage', 's2:snow_ice_percentage', 's2:product_type', 's2:processing_baseline', 's2:product_uri', 's2:generation_time', 's2:datatake_id', 's2:datatake_type', 's2:datastrip_id', 's2:reflectance_conversion_factor', 'datetime', 's2:sequence', 'earthsearch:s3_path', 'earthsearch:payload_id', 'earthsearch:boa_offset_applied', 'processing:software', 'updated', 'proj:code']
# 2026-09-12 S2C baseline: None sun elevation: 67.3997929190965 platform: sentinel-2c
# 2026-09-07 S2B baseline: None sun elevation: 66.5394947688412 platform: sentinel-2b
# 2026-09-04 S2A baseline: None sun elevation: 66.0527330283026 platform: sentinel-2a
# 2026-09-02 S2C baseline: None sun elevation: 65.6013147075496 platform: sentinel-2c
# 2026-08-28 S2B baseline: None sun elevation: 64.6058656844498 platform: sentinel-2b
# 2026-08-25 S2A baseline: None sun elevation: 64.0653465681329 platform: sentinel-2a
# 2026-08-23 S2C baseline: None sun elevation: 63.5931205548582 platform: sentinel-2c
# 2026-08-18 S2B baseline: None sun elevation: 62.5860765862635 platform: sentinel-2b
# 2026-08-15 S2A baseline: None sun elevation: 62.0629993325947 platform: sentinel-2a
# 2026-08-08 S2B baseline: None sun elevation: 60.697238864746 platform: sentinel-2b
# 2026-07-24 S2C baseline: None sun elevation: 58.4075412158138 platform: sentinel-2c
# ---
# 2026-09-12 {'sentinel2-to-stac': '2026.08.16'} 074611_N0512_R135_T36MXE_20260912T111815.SAFE boa offset applied: True tile water %: 25.344265
# 2026-09-07 {'sentinel2-to-stac': '2026.08.16'} 074609_N0512_R135_T36MXE_20260907T101559.SAFE boa offset applied: True tile water %: 31.139138
# 2026-09-04 {'sentinel2-to-stac': '2026.08.16'} 080451_N0512_R135_T36MXE_20260904T130611.SAFE boa offset applied: True tile water %: 31.015465
# 2026-09-02 {'sentinel2-to-stac': '2026.08.16'} 074611_N0512_R135_T36MXE_20260902T113210.SAFE boa offset applied: True tile water %: 29.286888
# 2026-08-28 {'sentinel2-to-stac': '2026.08.16'} 074609_N0512_R135_T36MXE_20260828T101512.SAFE boa offset applied: True tile water %: 35.125089
# 2026-08-25 {'sentinel2-to-stac': '2026.08.16'} 075021_N0512_R135_T36MXE_20260825T144215.SAFE boa offset applied: True tile water %: 30.099541
# 2026-08-23 {'sentinel2-to-stac': '2026.08.16'} 074611_N0512_R135_T36MXE_20260823T112222.SAFE boa offset applied: True tile water %: 31.074509
# 2026-08-18 {'sentinel2-to-stac': '2026.08.16'} 074609_N0512_R135_T36MXE_20260818T100213.SAFE boa offset applied: True tile water %: 32.580915
# 2026-08-15 {'sentinel2-to-stac': '2025.03.06'} 080451_N0512_R135_T36MXE_20260815T111210.SAFE boa offset applied: True tile water %: 32.888132
# 2026-08-08 {'sentinel2-to-stac': '2025.03.06'} 074609_N0512_R135_T36MXE_20260808T100859.SAFE boa offset applied: True tile water %: 27.704266
# 2026-07-24 {'sentinel2-to-stac': '2025.03.06'} 074611_N0512_R135_T36MXE_20260724T111624.SAFE boa offset applied: True tile water %: 32.348642

# that is what the file now outputs.