from pathlib import Path
import matplotlib.pyplot as plt
import rasterio

from bhume import load, patch_for_plot

village = load("data/34855_vadnerbhairav_chandavad_nashik")

Path("visualizations").mkdir(exist_ok=True)

with rasterio.open(village.imagery_path) as src:
    for plot_no in village.example_truths.index:

        geom = village.plots.loc[plot_no].geometry

        patch = patch_for_plot(src, geom)

        plt.figure(figsize=(6, 6))
        plt.imshow(patch.image)
        plt.title(f"Plot {plot_no}")
        plt.axis("off")

        plt.savefig(f"visualizations/{plot_no}.png")
        plt.close()

print("Saved all example truth visualizations.")