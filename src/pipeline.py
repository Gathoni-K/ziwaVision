# the file only holds functions.

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