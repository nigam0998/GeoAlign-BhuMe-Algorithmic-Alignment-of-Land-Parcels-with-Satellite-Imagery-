from pathlib import Path

import matplotlib.pyplot as plt
import rasterio
from shapely.geometry import Polygon, MultiPolygon

from bhume import load, patch_for_plot
from bhume.geo import lonlat_to_pixel


from rasterio.warp import transform
from shapely.geometry import Polygon, MultiPolygon


def draw_geometry(ax, geom, patch, color="red", linewidth=2):

    if isinstance(geom, Polygon):
        polys = [geom]
    elif isinstance(geom, MultiPolygon):
        polys = list(geom.geoms)
    else:
        return

    for poly in polys:

        lon, lat = poly.exterior.xy

        xs, ys = transform(
            "EPSG:4326",
            patch.crs,
            lon,
            lat,
        )

        px = []
        py = []

        for x, y in zip(xs, ys):

            col, row = ~patch.transform * (x, y)

            px.append(col)
            py.append(row)

        ax.plot(
            px,
            py,
            color=color,
            linewidth=linewidth,
        )


def main():
    village = load("data/34855_vadnerbhairav_chandavad_nashik")

    out_dir = Path("truth_comparisons")
    out_dir.mkdir(exist_ok=True)

    with rasterio.open(village.imagery_path) as src:

        for plot_no in village.example_truths.index:

            official_geom = village.plots.loc[plot_no].geometry
            truth_geom = village.example_truths.loc[plot_no].geometry

            patch = patch_for_plot(src, official_geom)

            fig, ax = plt.subplots(figsize=(8, 8))

            ax.imshow(patch.image)

            draw_geometry(
                ax,
                official_geom,
                patch,
                color="red",
                linewidth=2,
            )

            draw_geometry(
                ax,
                truth_geom,
                patch,
                color="lime",
                linewidth=2,
            )

            ax.set_title(f"Plot {plot_no}")
            ax.axis("off")

            plt.tight_layout()

            plt.savefig(
                out_dir / f"{plot_no}.png",
                dpi=200,
                bbox_inches="tight",
            )

            plt.close()

            print(f"Saved {plot_no}")

    print("\nDone.")


if __name__ == "__main__":
    main()