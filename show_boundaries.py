import rasterio
import matplotlib.pyplot as plt

src = rasterio.open(
    "data/34855_vadnerbhairav_chandavad_nashik/boundaries.tif"
)

arr = src.read(1)

plt.figure(figsize=(10,10))
plt.imshow(arr, cmap="gray")
plt.title("boundaries.tif")
plt.axis("off")

plt.show()