"""Builds the active site's terrain grid from its DTM (see the core's
ingestion/terrain.py). Piazza Dante's is committed; a site without one is
flat.

Shaped under the baseline's streets and paths, if there's a baseline: the
DTM's centimetre bumps, harmless on a lawn, make a paved ribbon wobble. So
build the baseline first (it doesn't need the terrain).

    uv run python -m bologna_civic_dt.ingestion.build_terrain --dtm data/piazza_dante/lidar/dtm.asc
"""

import json
import sys
from pathlib import Path

from bologna_civic_dt.pack import UrbanPack
from civic_engagement.config import SITE
from civic_engagement.domain import register
from civic_engagement.ingestion import terrain
from civic_engagement.ingestion.terrain import TerrainLine
from civic_engagement.models.schema import BaselineScene

# Over how long a stretch each kind of line's height is smoothed: a street's
# grade changes slowly, a footpath's faster (the park's mounds). In this
# order, the later winning where they meet.
SMOOTH_M = {"path": 10.0, "street": 20.0}


def terrain_lines(baseline: BaselineScene) -> list[TerrainLine]:
    lines = []
    for kind, smooth_m in SMOOTH_M.items():
        for element in baseline.elements:
            if element.type != kind or element.properties.get("bridge"):
                continue
            geometry = element.geometry
            parts = [geometry["coordinates"]] if geometry["type"] == "LineString" else geometry["coordinates"]
            for part in parts:
                lines.append(TerrainLine(
                    points=[(lng, lat) for lng, lat, *_ in part],
                    width_m=float(element.properties["width"]),
                    smooth_m=smooth_m,
                ))
    return lines


if __name__ == "__main__":
    register(UrbanPack())
    baseline_path = Path(SITE.baseline_json_path)
    lines = terrain_lines(BaselineScene(**json.loads(baseline_path.read_text()))) if baseline_path.is_file() else []
    print(f"Shaping the ground under {len(lines)} lines (paths, streets)" if lines else "No baseline yet: the ground unshaped")
    terrain.main(sys.argv[1:], lines)
