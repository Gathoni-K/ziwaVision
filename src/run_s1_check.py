"""
run_s1_check.py — Discovery and inspection of Sentinel-1 data on Element84 Earth Search.

Tasks:
1. List collections at https://earth-search.aws.element84.com/v1 that contain "sentinel-1".
2. Search for BBOX = [34.73, -0.22, 34.83, -0.12] from 2026-07-01 to 2026-09-30.
3. Print per item: id, datetime, platform, orbit direction, asset names.
4. Read one small VV and VH window and report shape, dtype, min, max, and read time.
"""

import time
import rasterio
from rasterio.windows import Window
from pystac_client import Client

STAC_URL = "https://earth-search.aws.element84.com/v1"
BBOX = [34.73, -0.22, 34.83, -0.12]
DATE_RANGE = "2026-07-01/2026-09-30"


def main():
    print("=" * 70)
    print("1. Querying STAC Collections at Element84 Earth Search")
    print("=" * 70)
    client = Client.open(STAC_URL)
    all_collections = list(client.get_collections())

    s1_collections = [c for c in all_collections if "sentinel-1" in c.id.lower()]
    print(f"Total collections found: {len(all_collections)}")
    print(f"Collections matching 'sentinel-1': {len(s1_collections)}")
    for c in s1_collections:
        print(f"  - ID: {c.id}")
        print(f"    Title: {c.title}")
        print(f"    Description: {c.description[:120]}...")

    if not s1_collections:
        print("No Sentinel-1 collections found on Element84.")
        return

    target_coll = s1_collections[0].id
    print("\n" + "=" * 70)
    print(f"2. Searching '{target_coll}' for Winam Gulf BBOX: {BBOX}")
    print(f"   Date Range: {DATE_RANGE}")
    print("=" * 70)

    search = client.search(
        collections=[target_coll],
        bbox=BBOX,
        datetime=DATE_RANGE,
    )
    items = list(search.items())
    print(f"Found {len(items)} matching scene(s).\n")

    for i, it in enumerate(items):
        dt = it.datetime.isoformat() if it.datetime else "N/A"
        platform = it.properties.get("platform", "N/A")
        orbit_dir = it.properties.get("sat:orbit_state", "N/A")
        assets = list(it.assets.keys())
        print(f"[{i+1}] ID: {it.id}")
        print(f"    Datetime:        {dt}")
        print(f"    Platform:        {platform}")
        print(f"    Orbit Direction: {orbit_dir}")
        print(f"    Asset Names:     {assets}")

    # 3. Read a small window from the first scene with VV and VH assets
    sample_item = next((it for it in items if "vv" in it.assets and "vh" in it.assets), None)
    if not sample_item:
        print("\nNo items with both VV and VH assets found.")
        return

    print("\n" + "=" * 70)
    print(f"3. Reading small VV & VH window from scene: {sample_item.id}")
    print("=" * 70)

    vv_href = sample_item.assets["vv"].href
    vh_href = sample_item.assets["vh"].href
    print(f"VV href: {vv_href}")
    print(f"VH href: {vh_href}")

    # Note: s3://sentinel-s1-l1c is public in eu-central-1 via AWS_NO_SIGN_REQUEST
    with rasterio.Env(AWS_NO_SIGN_REQUEST="YES", AWS_REGION="eu-central-1"):
        # VV window read
        t0 = time.time()
        with rasterio.open(vv_href) as src_vv:
            full_w, full_h = src_vv.width, src_vv.height
            window = Window(full_w // 2, full_h // 2, 256, 256)
            data_vv = src_vv.read(1, window=window)
        dt_vv = time.time() - t0

        print(f"\nVV window (center 256x256 px):")
        print(f"  Full scene dimensions: {full_w} x {full_h}")
        print(f"  Window shape:          {data_vv.shape}")
        print(f"  Data type:             {data_vv.dtype}")
        print(f"  Min value:             {data_vv.min()}")
        print(f"  Max value:             {data_vv.max()}")
        print(f"  Mean value:            {data_vv.mean():.2f}")
        print(f"  Read time:             {dt_vv:.2f} s")

        # VH window read
        t0 = time.time()
        with rasterio.open(vh_href) as src_vh:
            data_vh = src_vh.read(1, window=window)
        dt_vh = time.time() - t0

        print(f"\nVH window (center 256x256 px):")
        print(f"  Window shape:          {data_vh.shape}")
        print(f"  Data type:             {data_vh.dtype}")
        print(f"  Min value:             {data_vh.min()}")
        print(f"  Max value:             {data_vh.max()}")
        print(f"  Mean value:            {data_vh.mean():.2f}")
        print(f"  Read time:             {dt_vh:.2f} s")


if __name__ == "__main__":
    main()
