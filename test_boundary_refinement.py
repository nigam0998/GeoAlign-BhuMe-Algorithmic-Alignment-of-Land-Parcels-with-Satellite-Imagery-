from bhume import load
import geopandas as gpd
import rasterio
from rasterio.features import rasterize
from shapely.affinity import translate
import numpy as np

VILLAGE = "data/34855_vadnerbhairav_chandavad_nashik"
TEST_PLOT = "1476"


def boundary_overlap_score(geometry, raster_src):

    mask = rasterize(
        [(geometry.boundary, 1)],
        out_shape=(raster_src.height, raster_src.width),
        transform=raster_src.transform,
        fill=0,
        all_touched=True,
        dtype=np.uint8,
    )

    boundary_pixels = raster_src.read(1)

    return int(
        np.count_nonzero(
            (mask == 1) &
            (boundary_pixels == 255)
        )
    )


def main():

    village = load(VILLAGE)

    with rasterio.open(village.boundaries_path) as boundary_src:

        official_geom = village.plots.loc[TEST_PLOT].geometry

        official_geom = (
            gpd.GeoSeries(
                [official_geom],
                crs="EPSG:4326"
            )
            .to_crs(boundary_src.crs)
            .iloc[0]
        )

        best_score = -1
        best_dx = None
        best_dy = None

        for dx in range(-20, 21, 5):
            for dy in range(-20, 21, 5):

                shifted = translate(
                    official_geom,
                    xoff=dx,
                    yoff=dy
                )

                score = boundary_overlap_score(
                    shifted,
                    boundary_src
                )

                if score > best_score:
                    best_score = score
                    best_dx = dx
                    best_dy = dy

        print("\nBEST RESULT")
        print("dx =", best_dx, "m")
        print("dy =", best_dy, "m")
        print("score =", best_score)


if __name__ == "__main__":
    main()