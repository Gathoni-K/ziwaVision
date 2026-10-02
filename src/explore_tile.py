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

item = items[0]
# store the very first element in the list inside item

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

fig, axes = plt.subplots(1, 2, figsize=(14, 7))
axes[0].imshow(rgb)
axes[0].set_title("True colour")
axes[1].imshow(veg, cmap="gray")
axes[1].set_title("NDVI > 0.3")
for ax in axes:
    ax.axis("off")
plt.tight_layout()
plt.savefig("outputs/compare.png", dpi=150)


# for the black and white image (veg), the white shows vegetation while black shows no vegetation
