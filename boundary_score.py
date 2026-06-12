from bhume import load
import rasterio
from rasterio.features import rasterize
import numpy as np
import geopandas as gpd

VILLAGE = "data/34855_vadnerbhairav_chandavad_nashik"


def boundary_overlap_score(geometry, raster_src):
    """
    Measure overlap between a plot boundary
    and detected boundaries in boundaries.tif.
    """

    mask = rasterize(
        [(geometry.boundary, 1)],
        out_shape=(raster_src.height, raster_src.width),
        transform=raster_src.transform,
        fill=0,
        all_touched=True,
        dtype=np.uint8,
    )

    boundary_pixels = raster_src.read(1)

    overlap = np.count_nonzero(
        (mask == 1) &
        (boundary_pixels == 255)
    )

    return int(overlap)


def main():

    village = load(VILLAGE)

    with rasterio.open(village.boundaries_path) as boundary_src:

        print("\nPlot\tOfficial\tTruth")

        for plot_no in village.example_truths.index:

            official_geom = village.plots.loc[plot_no].geometry
            truth_geom = village.example_truths.loc[plot_no].geometry

            # Convert from EPSG:4326 to raster CRS (EPSG:3857)
            official_geom_3857 = (
                gpd.GeoSeries(
                    [official_geom],
                    crs="EPSG:4326"
                )
                .to_crs(boundary_src.crs)
                .iloc[0]
            )

            truth_geom_3857 = (
                gpd.GeoSeries(
                    [truth_geom],
                    crs="EPSG:4326"
                )
                .to_crs(boundary_src.crs)
                .iloc[0]
            )

            official_score = boundary_overlap_score(
                official_geom_3857,
                boundary_src,
            )

            truth_score = boundary_overlap_score(
                truth_geom_3857,
                boundary_src,
            )

            print(
                f"{plot_no}\t{official_score}\t\t{truth_score}"
            )


if __name__ == "__main__":
    main()