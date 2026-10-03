import numpy as np, cv2, rasterio
from pystac_client import Client
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
import matplotlib.pyplot as plt


BBOX = [34.73, -0.22, 34.83, -0.12]
# longitude/latitude box

catalog = Client.open("https://earth-search.aws.element84.com/v1")
# Client.open() is a method from 'pystac_client' that connects a catalogue to a web service
items = list(catalog.search(
    # create an object items
    # the list is a class constructor used to create a new list or convert other collections into a list
    collections = ["sentinel-2-l2a"], bbox = BBOX,
    datetime="2026-08-01/2026-09-30",
    query={"eo:cloud_cover": {"lt": 20}}, max_items=5,
).items())
# so what this does, it asks for information of the defined long/lat defined inside BBOX, specifies the day 

for it in items:
    print(it.id, it.properties["eo:cloud_cover"], it.bbox)
    # loop through all the items and print the date, its properties and the id

# item = items[0]
# store the very first element in the list inside item

def covers(scene, box):
    # covers compares the scene's edges with the box's edges, western edge of the scene must be the west side of the box and so on for the other directions
    """True if the scene's footprint contains the whole box."""
    w, s, e, n = scene.bbox
    # this is classic tupple unpackng, splits 4 numbers into 4 names
    return w <= box[0] and s <= box[1] and e >= box[2] and n >= box[3]

# What the code block above does is that it shows True only if the scene's footprint contains the 
# entire box.
# scene.bbox is  arectangle but real tiles are tilted. covers is a quick filter and red.shape being the final check

good = [it for it in items if covers(it, BBOX)]
# it for it... is a list comprehension a loop that keeps only the scenes that pass the test
print(len(good), "scenes cover the whole box")
if not good:
    raise SystemExit("No scene covers the box: widen the data range or raise max_items")
    # stops the script with a message

"""
The above code block can be written in long-form as:

    good = []
    for it in items:
        if covers(it, BBOX):
            good.append(it)
"""

item = min(good, key=lambda it: it.properties["eo:cloud_cover"])
# the line above picks the scene with the lowest cloud percentage
print("using:", item.id, item.properties["eo:cloud_cover"])

print(list(item.assets.keys()))

def read_band(name, as_float=True):
    # define a function that takes in the name variable
    with rasterio.open(item.assets[name].href) as src:
        # a dictionary of files for the scene
        bounds = transform_bounds("EPSG:4326", src.crs,*BBOX )
        # the box is in long/lat(EPSG...).The image stores position in metres in a projected system, which converts the box into image's units.
        window = from_bounds(*bounds, transform=src.transform)
        # the left side is the image's rule for mapping pixels to positions.
        data =  src.read(1, window=window).astype("float32")
        # read 1 band of the file, and window ensures only the area between our bounds is covered
        return data.astype("float32") if as_float else data


red, nir = read_band("red"), read_band("nir")
print(item.id, "shape:", red.shape)
ndvi = ( nir - red) / (nir + red + 1e-6)
# healthy vegetation reflects a lot of near-infrared and absorbs red, so the result turns from -1 to +1, with higher meaning greener
# 1e-6 is 0.0000001 so a pixel where nir + red is 0, it will not cause a division by 0

scl = read_band("scl", as_float=False)
scl = cv2.resize(scl, (red.shape[1], red.shape[0]), interpolation=cv2.INTER_NEAREST)

print(np.unique(scl, return_counts=True))

bad = np.isin(scl, [0, 1, 3, 8, 9, 10])   # no data, defective, cloud shadow, clouds, cirrus
print("cloud/no-data fraction:", bad.mean())

veg = (ndvi > 0.3 ).astype("uint8") * 255
# the first part of L.H gives a grid of true/false values the same shape as the image
# .astype(...) turns True/False into 1/0 or 255/0, so true is white and false is black
# on testing, the earlier threshold of 0.3 was too lenient as NDVI counted dry cropland and scrub as green whilst we only want to account for hyacinth
cv2.imwrite("outputs/ndvi_mask.png", veg)
print("green fraction:", (ndvi > 0.3).mean())

green = read_band("green")
# reusing the earlier created function for the 2 more bands
blue = read_band("blue")

rgb = np.dstack([red, green, blue])
# stack 3 bands into 1 color image
# each band is a 2D grid (rows * cols)
rgb = np.clip(rgb / 3000, 0, 1)
# brighten and keep values in 0...1

palette = {0: (0, 0, 0), 1: (255, 0, 0), 2: (60, 60, 60), 3: (90, 90, 90),
        4: (0, 160, 0), 5: (200, 170, 100), 6: (0, 0, 255),
        7: (255, 0, 255), 8: (220, 220, 220), 9: (255, 255, 255),
        10: (180, 220, 255)}

water = scl == 6
green = ndvi > 0.3

print("NDVI-green pixels inside SCL water:", (green & water).sum())
print("NDVI-green but SCL says not vegetated:", (green & (scl == 5)).sum())
print("share of all pixels:", (green & (scl == 5)).mean())

scl_rgb = np.zeros((*scl.shape, 3), dtype="uint8")
# np.zeros... makes an empty color image the same size as SCL
for value, colour in palette.items():
    scl_rgb[scl == value] = colour
    # paints every pixel of that class with its color.


fig, axes = plt.subplots(1, 3, figsize=(18, 6))
axes[0].imshow(rgb);        axes[0].set_title("True colour")
axes[1].imshow(scl_rgb);    axes[1].set_title("SCL: blue=water, green=veg, grey/white=cloud")
axes[2].imshow(veg, cmap="gray"); axes[2].set_title("NDVI > 0.3")
for ax in axes:
    ax.axis("off")
plt.tight_layout()
plt.savefig("outputs/compare.png", dpi=150)
plt.imsave("outputs/truecolour.png", rgb)
plt.imsave("outputs/scl.png", scl_rgb)

crop = rgb[600:900, 100:500]
crop = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
plt.imsave("outputs/shore_crop.png", crop)

# for the black and white image (veg), the white shows vegetation while black shows no vegetation

# what the file tells us up to here:
# 1. 10m is good for landscape-scale features, field boundaries and the shoreline edges are crisp, so a mat tens of metres wide should be visible.

# This is what my terminal outputs on running this file, but by God, I cannot currently make sense of it, below is the breakdown of the numbers:

# S2B_36MYE_20260927_0_L2A 8.70088 [34.796703, -0.992893, 35.783039, -9e-06]
# the long threatening letters and numbers are simply the scenes picked for our image
# S2C_36MYE_20260922_0_L2A 14.917701 [34.796703, -0.992893, 35.783039, -9e-06]
# S2C_36MXE_20260912_0_L2A 17.03563 [33.898647, -0.993262, 34.885349, -9e-06]
# S2B_36MXE_20260907_0_L2A 4.425055 [33.898647, -0.993262, 34.885349, -9e-06]
# S2B_36MYE_20260907_0_L2A 7.58323 [34.796703, -0.992893, 35.783039, -9e-06]
# 2 scenes cover the whole box
# in our code we wanted to print out the scenes covering the entire box
# using: S2B_36MXE_20260907_0_L2A 4.425055
# the script chooses the 4.4% one
# ['aot', 'blue', 'cloud', 'coastal', 'granule_metadata', 'green', 'nir', 'nir08', 'nir09', 'product_metadata', 'red', 'rededge1', 'rededge2', 'rededge3', 'scl', 'snow', 'swir16', 'swir22', 'tileinfo_metadata', 'visual', 'wvp', 'thumbnail', 'aot-jp2', 'blue-jp2', 'coastal-jp2', 'green-jp2', 'nir-jp2', 'nir08-jp2', 'nir09-jp2', 'red-jp2', 'rededge1-jp2', 'rededge2-jp2', 'rededge3-jp2', 'scl-jp2', 'swir16-jp2', 'swir22-jp2', 'visual-jp2', 'wvp-jp2']
# S2B_36MXE_20260907_0_L2A shape: (1106, 1113)
# describes the shape, 1106 rows by 1113 columns at 10m per pixel, that is about 11km by 11km
# (array([2., 4., 5., 6., 7.], dtype=float32), array([   652, 232308, 493920, 461612,  42486]))
# cloud/no-data fraction: 0.0
# green fraction: 0.378209846154846
# 37.8% of pixels have NDVI above 0.3
