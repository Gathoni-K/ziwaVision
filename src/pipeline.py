# the file only holds functions.
# What is handled in this file:
# 1.Find scenes covering the box.
# 2. Read bands, SCL, box-level cloud check.
# 3. Finds the lake mask

import numpy as np, rasterio, cv2
from pystac_client import Client
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds


def covers(scene, box):
    """
    True if the scene's footprint contains the whole box

    """
    w, s, e, n = scene.bbox
    return w <= box[0] and s <= box[1] and e >= box[2] and n >= box[3]

def find_scenes(bbox, date_range, max_items=20):
    """
    Search the catalogue, keep only the screens that cover the whole box.
    """
    catalog = Client.open("https://earth-search.aws.element84.com/v1")
    items = list(catalog.search(
        collections = ["sentinel-2-l2a"], bbox=bbox, datetime=date_range,
        query={"eo:cloud_cover": {"lt": 20}}, max_items=max_items,
    ).items())

    return [it for it in items if covers(it, bbox)]

def read_band(item, name, bbox, as_float=True):
    """
    Read one band of one scene, cropped to bbox.

    Reflectance scaling (resolved 2026-10-26):
    Element84 Earth Search sets earthsearch:boa_offset_applied=True on all
    scenes accessed via this catalogue. That means the stored DN values are
    already bottom-of-atmosphere reflectance * 10000, with the +1000 offset
    already subtracted by the provider. Typical water pixels read ~200-600,
    vegetation ~1500-4000, cloud >8000. No manual (value-1000)/10000
    correction is needed; dividing by 3000 for display (as done in the
    explore/vision scripts) keeps the range visually comfortable.
    """
    with rasterio.open(item.assets[name].href) as src:
        bounds = transform_bounds("EPSG:4326", src.crs, *bbox)
        window = from_bounds(*bounds, transform=src.transform)
        data = src.read(1, window=window)

        return data.astype("float32") if as_float else data


def read_scl(item, bbox, like):
    """
    Read the Scene CLassification Layer, stretched to match the array 'like'
    """
    scl = read_band(item, "scl", bbox, as_float=False)
    return cv2.resize(scl, (like.shape[1], like.shape[0]), interpolation=cv2.INTER_NEAREST)

BAD_CLASSES = [0, 1, 3, 8, 9, 10]
# no data, defective, cloud shadow, cloud, cirrus

def box_cloud(scl):
    """
    Share of pixels n the box that are cloud, shadow or missing.
    """

    return np.isin(scl, BAD_CLASSES).mean()


PIXEL_HA = 10**2 / 10_000
# 1 10 m pixel = 100m2 = 0.01 ha

def lake_mask(scl):
    """
    The gulf: the biggest water blob, with enclosed holes filled. 0/1 grid or None.
    """

    water = (scl == 6).astype("uint8")
    n, labels, stats, _ = cv2.connectedComponentsWithStats(water, connectivity=8)

    if n < 2:
        return None
    
    biggest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
    lake = (labels == biggest).astype("uint8")
    contours, _ = cv2.findContours(lake, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    filled = np.zeros_like(lake)
    cv2.drawContours(filled, contours, -1, 1, thickness=cv2.FILLED)

    return filled

def reference_lake(masks, min_share=0.6):
    """
    Pixels that are lake on at least `min_share` of the dates. 'masks' is a list of 0/1 grids.
    """
    stack = np.stack(masks)
    share = stack.mean(axis=0)
    return (share >= min_share).astype("uint8")


def ring(mask, inside_px, outside_px):
    """
    A strip around a mask's edge: pixels that are within `outside_px` of the
    mask boundary AND at least `inside_px` pixels inside the mask boundary.

    Formula: inside the dilated region AND outside the eroded region.
    This matches explore_tile.py which yields ~175 ha for the Winam Gulf box
    (inside_px=3, outside_px=5). The previous formula omitted '== 0' on the
    erode term, which made the band equal to the whole lake interior (~4536 ha).
    """
    k_out = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*outside_px + 1, 2*outside_px + 1))
    k_in  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*inside_px  + 1, 2*inside_px  + 1))

    band = (cv2.dilate(mask, k_out) == 1) & (cv2.erode(mask, k_in) == 0)

    # ── sanity guard ──────────────────────────────────────────────────────────
    # The shore band should be a narrow ring, not the whole lake interior.
    # If it is larger than 5 % of the lake area something is wrong.
    lake_px = int(mask.sum())
    band_px = int(band.sum())
    if lake_px > 0 and band_px > 0.05 * lake_px:
        import warnings
        warnings.warn(
            f"ring(): band is {band_px} px ({band_px * PIXEL_HA:.0f} ha), "
            f"which is {band_px / lake_px:.1%} of the lake ({lake_px} px). "
            "Expected < 5 %. Check inside_px / outside_px arguments.",
            stacklevel=2,
        )

    return band

def ndvi_of(red, nir):
    """NDVI = (NIR - red) / (NIR + red). The 1e-6 avoids dividing by zero."""
    return (nir - red) / (nir + red + 1e-6)


NDVI_THRESHOLD: float = 0.30


def candidates_mask(lake_filled, ndvi, scl, erode_shore_px: int = 7):
    """
    Candidate floating-vegetation pixels: inside the filled lake, away from
    the shore by `erode_shore_px` pixels, and either NDVI > threshold or
    SCL class 4 (vegetation).

    Returns a boolean array. Mirrors the logic in explore_tile.py and vision.py
    so all modules use the same definition.
    """
    kernel = cv2.getStructuringElement(
        cv2.MORPH_ELLIPSE,
        (2 * erode_shore_px + 1, 2 * erode_shore_px + 1)
    )
    interior = cv2.erode(lake_filled, kernel)
    veg_ndvi = ndvi > NDVI_THRESHOLD
    veg_scl  = scl == 4
    return (interior == 1) & (veg_ndvi | veg_scl)