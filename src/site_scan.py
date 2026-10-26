"""Scan tiled Lake Victoria sites for candidate floating vegetation.

The scan uses the same scene-level gates as ``run_pipeline.py``:
box cloud fraction <= 5% and a stable lake mask built from clear dates with
``reference_lake(min_share=0.6)``. Candidate pixels are counted only after
eroding the reference lake by seven pixels.

The default cap is intentionally 40 tile-dates. Increase it explicitly only
after reviewing the first output.
"""

from __future__ import annotations

import argparse
import csv
import math
import os
import sys
from dataclasses import dataclass
from datetime import date
from typing import Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt
import numpy as np

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from pipeline import (  # noqa: E402
    PIXEL_HA,
    box_cloud,
    candidates_mask,
    find_scenes,
    lake_mask,
    read_band,
    read_scl,
    reference_lake,
)


DATE_RANGE = "2026-07-01/2026-09-30"
CLOUD_CUTOFF = 0.05
LAKE_MIN_SHARE = 0.6
OPEN_WATER_EROSION_PX = 7
TILE_KM = 5.0
OUTPUTS_DIR = os.path.join(os.path.dirname(_HERE), "outputs")
CSV_PATH = os.path.join(OUTPUTS_DIR, "site_scan.csv")
PREVIEW_DIR = os.path.join(OUTPUTS_DIR, "site_scan_previews")

SITES = (
    ("winam_gulf", (34.73, -0.22, 34.83, -0.12)),
    ("kenyan_side_lake_victoria", (33.8, -0.55, 35.0, 0.05)),
)


@dataclass(frozen=True)
class Tile:
    site: str
    row: int
    col: int
    bbox: Tuple[float, float, float, float]

    @property
    def tile_id(self) -> str:
        return f"{self.site}_r{self.row:03d}_c{self.col:03d}"


def _tile_size_degrees(latitude: float) -> Tuple[float, float]:
    """Return longitude/latitude degrees corresponding to approximately 5 km."""
    lat_km = 111.32
    lon_km = 111.32 * math.cos(math.radians(latitude))
    return TILE_KM / lon_km, TILE_KM / lat_km


def make_tiles(site: str, bounds: Tuple[float, float, float, float]) -> List[Tile]:
    west, south, east, north = bounds
    lon_step, lat_step = _tile_size_degrees((south + north) / 2)
    tiles: List[Tile] = []
    row = 0
    lat = south
    while lat < north - 1e-10:
        col = 0
        lon = west
        tile_north = min(lat + lat_step, north)
        while lon < east - 1e-10:
            tile_east = min(lon + lon_step, east)
            tiles.append(Tile(site, row, col, (lon, lat, tile_east, tile_north)))
            col += 1
            lon = tile_east
        row += 1
        lat = tile_north
    return tiles


def _scene_date(scene) -> str:
    return str(scene.datetime.date())


def _read_scl_and_red(scene, bbox):
    red = read_band(scene, "red", bbox)
    scl = read_scl(scene, bbox, red)
    return red, scl


def _clear_scene_data(tile: Tile):
    """Read each scene once and return clear scenes plus lake masks."""
    scenes = find_scenes(tile.bbox, DATE_RANGE, max_items=30)
    by_date = {}
    for scene in sorted(scenes, key=lambda item: item.datetime):
        date_key = _scene_date(scene)
        if date_key in by_date:
            continue
        try:
            red, scl = _read_scl_and_red(scene, tile.bbox)
        except Exception as exc:
            print(f"  {tile.tile_id} {date_key}: read failed: {exc}")
            continue
        cloud = float(box_cloud(scl))
        if cloud > CLOUD_CUTOFF:
            continue
        lake = lake_mask(scl)
        if lake is None:
            continue
        by_date[date_key] = {
            "scene": scene,
            "red": red,
            "scl": scl,
            "lake": lake,
            "cloud": cloud,
        }
    return by_date


def _true_colour(scene, bbox):
    red = read_band(scene, "red", bbox)
    green = read_band(scene, "green", bbox)
    blue = read_band(scene, "blue", bbox)
    return np.clip(np.dstack([red, green, blue]) / 3000.0, 0, 1)


def _write_previews(rows: List[dict], limit: int = 10) -> None:
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    for rank, row in enumerate(sorted(rows, key=lambda item: item["candidate_pixels"], reverse=True)[:limit], 1):
        try:
            rgb = _true_colour(row["_scene"], row["_bbox"])
        except Exception as exc:
            print(f"  preview failed for {row['tile_id']} {row['date']}: {exc}")
            continue
        filename = f"{rank:02d}_{row['tile_id']}_{row['date']}.png"
        path = os.path.join(PREVIEW_DIR, filename)
        plt.imsave(path, rgb)
        row["preview_path"] = path


def run(max_tile_dates: int) -> List[dict]:
    os.makedirs(OUTPUTS_DIR, exist_ok=True)
    all_tiles = [
        tile
        for site, bounds in SITES
        for tile in make_tiles(site, bounds)
    ]
    print(f"Generated {len(all_tiles)} approximately {TILE_KM:g} km tiles.")
    print(f"Processing at most {max_tile_dates} tile-dates.")

    rows: List[dict] = []
    for tile in all_tiles:
        if len(rows) >= max_tile_dates:
            break
        data = _clear_scene_data(tile)
        if not data:
            continue
        stable_lake = reference_lake([entry["lake"] for entry in data.values()], min_share=LAKE_MIN_SHARE)
        lake_area_ha = float(stable_lake.sum() * PIXEL_HA)
        if lake_area_ha <= 0:
            continue

        for date_key in sorted(data):
            if len(rows) >= max_tile_dates:
                break
            entry = data[date_key]
            red = entry["red"]
            scl = entry["scl"]
            nir = read_band(entry["scene"], "nir", tile.bbox)
            ndvi = (nir - red) / (nir + red + 1e-6)
            mask = candidates_mask(
                stable_lake,
                ndvi,
                scl,
                erode_shore_px=OPEN_WATER_EROSION_PX,
            )
            candidate_pixels = int(mask.sum())
            rows.append({
                "site": tile.site,
                "tile_id": tile.tile_id,
                "tile_row": tile.row,
                "tile_col": tile.col,
                "west": tile.bbox[0],
                "south": tile.bbox[1],
                "east": tile.bbox[2],
                "north": tile.bbox[3],
                "date": date_key,
                "scene_id": entry["scene"].id,
                "box_cloud_fraction": round(entry["cloud"], 6),
                "lake_pixels": int(stable_lake.sum()),
                "lake_area_ha": round(lake_area_ha, 3),
                "candidate_pixels": candidate_pixels,
                "candidate_area_ha": round(candidate_pixels * PIXEL_HA, 3),
                "open_water_erosion_px": OPEN_WATER_EROSION_PX,
                "cloud_cutoff": CLOUD_CUTOFF,
                "lake_min_share": LAKE_MIN_SHARE,
                "_scene": entry["scene"],
                "_bbox": tile.bbox,
                "preview_path": "",
            })
            print(f"  {tile.tile_id} {date_key}: {candidate_pixels} candidate pixels")

    _write_previews(rows)
    fieldnames = [
        key for key in rows[0] if not key.startswith("_")
    ] if rows else [
        "site", "tile_id", "tile_row", "tile_col", "west", "south", "east",
        "north", "date", "scene_id", "box_cloud_fraction", "lake_pixels",
        "lake_area_ha", "candidate_pixels", "candidate_area_ha",
        "open_water_erosion_px", "cloud_cutoff", "lake_min_share", "preview_path",
    ]
    with open(CSV_PATH, "w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})
    print(f"Wrote {len(rows)} rows to {CSV_PATH}")
    print(f"Wrote previews to {PREVIEW_DIR}")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-tile-dates",
        type=int,
        default=40,
        help="maximum number of tile-date rows to process (default: 40)",
    )
    args = parser.parse_args()
    if args.max_tile_dates < 1:
        parser.error("--max-tile-dates must be positive")
    run(args.max_tile_dates)


if __name__ == "__main__":
    main()
