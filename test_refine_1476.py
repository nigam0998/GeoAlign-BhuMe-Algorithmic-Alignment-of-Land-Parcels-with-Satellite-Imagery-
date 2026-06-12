from bhume import load
from bhume.geo import geom_to_imagery_crs

import rasterio
import geopandas as gpd
import numpy as np

from shapely.affinity import translate

VILLAGE = "data/34855_vadnerbhairav_chandavad_nashik"
PLOT = "1476"


def main():

    village = load(VILLAGE)

    official = village.plots.loc[PLOT].geometry
    truth = village.example_truths.loc[PLOT].geometry

    with rasterio.open(village.boundaries_path) as src:

        official_3857 = geom_to_imagery_crs(src, official)
        truth_3857 = geom_to_imagery_crs(src, truth)

        official_centroid = official_3857.centroid
        truth_centroid = truth_3857.centroid

        dx_truth = truth_centroid.x - official_centroid.x
        dy_truth = truth_centroid.y - official_centroid.y

        print("\nKnown truth shift:")
        print(f"dx = {dx_truth:.2f} m")
        print(f"dy = {dy_truth:.2f} m")

        print("\nBounds:")
        print("Official:", official_3857.bounds)
        print("Truth   :", truth_3857.bounds)


if __name__ == "__main__":
    main()