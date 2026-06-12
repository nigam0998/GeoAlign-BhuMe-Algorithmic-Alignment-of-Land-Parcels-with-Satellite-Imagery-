import rasterio
import numpy as np

src = rasterio.open(
    "data/34855_vadnerbhairav_chandavad_nashik/boundaries.tif"
)

arr = src.read(1)

print("Shape:", arr.shape)
print("Min:", np.min(arr))
print("Max:", np.max(arr))
print("Mean:", np.mean(arr))
print("Unique sample:", np.unique(arr)[:20])