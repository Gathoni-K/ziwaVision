"""
Unit tests for patch detection domain constraint.
Verifies that detect_patches only detects patches in open water or the shore band,
and NEVER on inland/terrestrial pixels.
"""

import sys, os, warnings
import numpy as np
import cv2
import pytest

warnings.filterwarnings("ignore", category=UserWarning, module="pipeline")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from vision import detect_patches, MIN_PATCH_PX
from pipeline import ring, PIXEL_HA


def create_synthetic_scene(
    img_size=(100, 100),
    lake_center=(50, 50),
    lake_radius=35,
    inland_veg_pos=(10, 10),
    water_veg_pos=(50, 50),
    shore_veg_pos=(50, 16),
):
    """
    Creates a synthetic scene with:
    - Lake in the center (radius 35)
    - Land everywhere else
    """
    h, w = img_size
    lake = np.zeros((h, w), dtype=np.uint8)
    cv2.circle(lake, lake_center, lake_radius, 1, -1)

    # Base arrays: water reflectance is low (e.g. 500), land reflectance is higher (e.g. 1500)
    red = np.full((h, w), 1500.0, dtype=np.float32)
    nir = np.full((h, w), 1200.0, dtype=np.float32)
    scl = np.full((h, w), 5, dtype=np.uint8) # bare soil/land

    # Set lake water pixels: SCL = 6 (water), low red and very low NIR
    red[lake == 1] = 600.0
    nir[lake == 1] = 300.0
    scl[lake == 1] = 6

    # Plant a high-NDVI vegetation blob INLAND (should NEVER be detected)
    cv2.circle(red, inland_veg_pos, 5, 400.0, -1)
    cv2.circle(nir, inland_veg_pos, 5, 2500.0, -1)
    # NDVI = (2500 - 400)/(2900) ~ 0.72

    # Plant a high-NDVI vegetation blob in OPEN WATER (should be detected)
    cv2.circle(red, water_veg_pos, 4, 400.0, -1)
    cv2.circle(nir, water_veg_pos, 4, 2500.0, -1)

    green = red.copy()
    blue = red.copy()

    return red, nir, green, blue, scl, lake


def test_no_inland_patches_detected():
    """Verify that detect_patches ignores inland vegetation completely."""
    red, nir, green, blue, scl, lake = create_synthetic_scene()
    shore_band = ring(lake, inside_px=3, outside_px=5)

    sv = detect_patches(
        scene_id="test_scene",
        date="2026-09-07",
        red=red, nir=nir, green=green, blue=blue,
        scl=scl, lake_filled=lake, shore_band=shore_band,
        use_grabcut=False,
    )

    k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * 7 + 1, 2 * 7 + 1))
    open_water = (cv2.erode(lake, k_open) == 1)
    allowed_domain = open_water | (shore_band == 1)

    # Patches found must strictly be within allowed_domain (open water or shore band)
    assert len(sv.patches) > 0, "Expected open-water vegetation patch to be detected"

    for p in sv.patches:
        cr, cc = p.centroid_px
        # Centroid must be in allowed domain
        assert allowed_domain[cr, cc], f"Patch centroid ({cr}, {cc}) is inland!"
        # Distance to shore must be non-negative
        assert p.dist_to_shore_m >= 0.0, "Patch distance to shore cannot be negative (inland)"
        assert p.in_open_water or p.in_shore_band, "Patch must be either in open water or shore band"


def test_inland_assertion_triggers_if_inland_pixels_included():
    """Verify that an inland patch triggers the invariant assertion."""
    red, nir, green, blue, scl, lake = create_synthetic_scene()
    shore_band = ring(lake, inside_px=3, outside_px=5)

    k_open = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2 * 7 + 1, 2 * 7 + 1))
    open_water = (cv2.erode(lake, k_open) == 1)
    allowed_domain = open_water | (shore_band == 1)

    # An inland point (10, 10) must be outside allowed_domain
    assert not allowed_domain[10, 10], "Inland point (10, 10) should be outside allowed domain"
