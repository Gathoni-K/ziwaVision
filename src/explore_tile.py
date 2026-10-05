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

bad = np.isin(scl, [0, 1, 3, 8, 9, 10])  
print("cloud/no-data fraction:", bad.mean())
# what this does, bad is True where SCL says no data, defective, cloud shadow, clouds, cirrus

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

# what we have achieved upto this point is scene selection by footprint, SCL and a 3-panel comparison

# The next task is finding a lake mask and candidate floating vegetation.

water = (scl == 6).astype("uint8")
# the water mark is made as 0/1 integers.
# Open CV's shape functions want integer masks not True/False
n, labels, stats, _ = cv2.connectedComponentsWithStats(water, connectivity=8)
# connectedComponents... finds each separate blobs of 1s.
# labels numbers every blob and stats holds each blob's size.
# row 0 is the background which is why we search stats[1:, ...] and add 1 back
biggest = 1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])
# argmax is the position of the largest value so the 'biggest' is the blob number of the gulf
lake = (labels == biggest).astype("uint8")

# what this block of code does is that it keeps only the biggest water gulf and drops ponds and ricefields

contours, _ = cv2.findContours(lake, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
# findContours with RETR_ECTERNAL traces only the outer outline of each shape, ignoring any holes inside
lake_filled = np.zeros_like(lake)
cv2.drawContours(lake_filled, contours, -1, 1, thickness=cv2.FILLED)
# drawContours paints the inside of that outline solid, so holes in the lake get filled, a mat completely surrounded by water is no longer a hole

# this block of code ensure that anything completely surrounded by lake is filled

green = ndvi > 0.3
candidates = (lake_filled == 1) & (green | (scl == 4))
# the candidates are the green inside the filled lake
# the block of code ensures we capture any vegetation labelled as green either by scl or ndvi

kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 5))
interior = cv2.erode(lake_filled, kernel)
# .erode - shrinks the lake edge inwards by about 3 pixels all around which pushes the shoreline pixels out of the 'interior'
far = candidates & (interior == 1)

print("candidates:", candidates.sum(), "px =", candidates.sum() * 0.01, "ha")
print("away from shore:", far.sum(), "px =", far.sum() * 0.01, "ha")

#  picture: candidates in red on the true-colour image
overlay = rgb.copy()
overlay[candidates] = [1, 1, 0]      # yellow: all candidates
overlay[far] = [1, 0, 0]             # red: away from shore
plt.imsave("outputs/candidates.png", overlay)

# the block of code below creates the shore band.
# the Question we are answering is how much green sits right at the water's edge, where mats can attach?
# the expected output is : 'band', 'shore_green', 'printed hectares', 'outputs'

def ring(mask, inside_px, outside_px):
    """
    Pixels from `inside_px` isnide the mask edge to `outside_px` outside it.
    """
    k_out = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*outside_px + 1, 2*outside_px + 1))
    k_in = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (2*inside_px + 1, 2*inside_px + 1))
    grown = cv2.dilate(mask, k_out)
    shrunk = cv2.erode(mask, k_in)
    return (grown == 1) & (shrunk == 0)

band = ring(lake_filled, inside_px=3, outside_px=5)

# green_like = green | np.isin(scl, [4, 7])
# # what this line does is that it shows all green where the NDVI is above 0.3, SCL vegetation or SCL Unclassified.
# # the unclassified was included on purpose, it is the mixed-pixel strip where a mat at the edge could hide, but it also means yellow is not necessarily green
# shore_green = band & green_like


# Question: how much vegetation sits at the water's edge, and how much of the edge is uncertain?
# Output: shore_green, shore_uncertain, printed numbers, outputs/shore.png

green_like = green | (scl == 4)                       # vegetation only
shore_green = band & green_like                            # vegetation inside the band
shore_uncertain = band & (scl == 7) & ~green_like          # unclassified, no vegetation signal

overlay2 = rgb.copy()
overlay2[band] = overlay2[band] * 0.6 + np.array([0, 0.4, 0.4])   # cyan: the band
overlay2[shore_uncertain] = [1, 0, 1]                              # magenta: uncertain
overlay2[shore_green] = [1, 1, 0]                                  # yellow: vegetation signal
plt.imsave("outputs/shore.png", overlay2)

band_px = band.sum()
print("shore band:", band_px, "px =", band_px * 0.01, "ha")
print("band vegetation:", shore_green.sum(), "px =", shore_green.sum() * 0.01, "ha",
    f"({shore_green.sum() / band_px:.1%} of band)")
print("band uncertain:", shore_uncertain.sum(), "px =", shore_uncertain.sum() * 0.01, "ha",
    f"({shore_uncertain.sum() / band_px:.1%} of band)")


crop = overlay2[250:550, 0:330]
crop = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_NEAREST)
plt.imsave("outputs/shore_crop1.png", crop)

# this is what the terminal outputs upto here.
# cloud/no-data fraction: 0.0
# green fraction: 0.378209846154846
# NDVI-green pixels inside SCL water: 1752
# NDVI-green but SCL says not vegetated: 234678
# share of all pixels: 0.1906435370900211
# candidates: 272 px = 2.72 ha
# away from shore: 19 px = 0.19 ha
# shore band: 17459 px = 174.59 ha
# band vegetation: 2477 px = 24.77 ha (14.2% of band)
# band uncertain: 5333 px = 53.33 ha (30.5% of band)