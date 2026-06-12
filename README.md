# GeoAlign-BhuMe: Algorithmic Alignment of Land Parcels with Satellite Imagery

[![Python 3.12](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/)
[![GIS - GeoPandas](https://img.shields.io/badge/GIS-GeoPandas%20%7C%20Rasterio-green.svg)](https://geopandas.org/)
[![Interpolation - IDW](https://img.shields.io/badge/Math-IDW%20Interpolation-orange.svg)](https://en.wikipedia.org/wiki/Inverse_distance_weighting)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Official land registry outlines (cadastral maps) in India often suffer from historical georeferencing shifts, sitting several meters off actual on-the-ground field boundaries. **GeoAlign-BhuMe** is a geospatial pipeline designed to correct this cadastral drift by combining official land parcel data with high-resolution satellite imagery and local spatial interpolation.

---

## 📌 Project Overview

Historical paper maps digitized into land records (such as Maharashtra's cadastre) are prone to systematic and localized distortions when overlaid on modern satellite imagery. 

This repository implements a spatial correction engine that:
1. **Establishes Control Shifts** from a small set of hand-aligned, ground-truth parcels.
2. **Computes Local Drift Vectors** using an Inverse Distance Weighting (IDW) residual translation.
3. **Extracts On-The-Ground Boundaries** by analyzing visible RGB edges and pre-detected field boundaries.
4. **Calculates Alignment Confidence** and flags parcels where the true boundary is too ambiguous to place.

<p align="center">
  <img src="bhume/patch_example.png" alt="Example Parcel Boundary Shift" width="550px">
</p>

---

## 🛠 Key Features

- **Robust Global Translation:** Computes the village-wide median shift vector to remove bulk georeferencing bias.
- **Local Residual Interpolation (IDW):** Interpolates localized terrain-based distortions using nearby ground-truth anchors, fading out gracefully to the global shift in data-sparse zones.
- **Visual Diagnostics Overlay Engine:** Generates high-fidelity overlays depicting satellite imagery, official shapes, ground-truths, and detected raster boundaries.
- **Geo-Plumbing Abstraction:** Automated coordinate system alignment (EPSG:4326 to Web Mercator EPSG:3857/UTM) and sub-raster cropping.
- **Precision Validation Suite:** Computes Intersection over Union (IoU) scores, calibration metrics (Spearman Rank Correlation), and restraint indicators.

---

## 📂 Project Structure

```
├── bhume/                  # Core geospatial package
│   ├── io.py               # Data loading, shapefile/geojson parser, and CRS handler
│   ├── geo.py              # Coordinate converters (pixel-space to geographic crs)
│   ├── solution.py         # IDW residual-shift algorithm implementation
│   ├── score.py            # Evaluation metrics (IoU, Calibration, Spearman rank)
│   └── refine.py           # Interface for fine-grained boundary refinement
├── data/                   # Input datasets (imagery GeoTIFFs, cadastral GeoJSONs)
├── boundary_analysis/      # Generated visual overlays and alignment summaries (CSV/TXT)
├── analyze_boundaries.py   # Analysis script evaluating edge strength and signal overlap
├── boundary_score.py       # Helper to compare parcel overlap scores
├── compare_truths.py       # Visual comparison script generating plot-by-plot PNGs
├── quickstart.py           # Baseline evaluation runner
└── pyproject.toml          # Project configuration and dependency manifest
```

---

## 🚀 Getting Started

### Prerequisites

This project uses [uv](https://docs.astral.sh/uv/) for fast, reproducible dependency and environment management.

Install `uv` (if not already installed):
```bash
# macOS/Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/nigam0998/GeoAlign-BhuMe-Algorithmic-Alignment-of-Land-Parcels-with-Satellite-Imagery-.git
   cd GeoAlign-BhuMe-Algorithmic-Alignment-of-Land-Parcels-with-Satellite-Imagery-
   ```

2. Sync the dependencies and set up the virtual environment:
   ```bash
   uv sync
   ```

This will automatically configure a Python 3.12 virtual environment (`.venv`) and install all required GIS packages (`geopandas`, `rasterio`, `shapely`, `numpy`, `scipy`, `pillow`, `matplotlib`) with bundled GDAL wheels.

### Data Setup

Place your unzipped village dataset inside a `data/` directory. The structure should look like this:
```
data/
  34855_vadnerbhairav_chandavad_nashik/
    input.geojson          # Official shifted plot boundaries
    imagery.tif            # High-resolution satellite imagery (RGB)
    boundaries.tif         # (Optional) Auto-detected field boundary probability mask
    example_truths.geojson # Hand-aligned ground-truth parcels for validation
```

---

## 💻 Running the Pipeline

### 1. Run the Quickstart Baseline
Execute the local IDW shift baseline and evaluate it against example truths:
```bash
uv run quickstart.py data/34855_vadnerbhairav_chandavad_nashik
```

### 2. Analyze Boundary Alignment Signals
Analyze how well the official and true boundaries match the satellite image gradients and boundary probability rasters:
```bash
uv run analyze_boundaries.py data/34855_vadnerbhairav_chandavad_nashik boundary_analysis
```
This script writes plot-by-plot overlay images (PNGs) and statistical summaries in `boundary_analysis/` showing:
- **`boundary_alignment_summary.csv`**: Comparison of signals near official vs. ground-truth lines.
- **`boundary_alignment_stats.txt`**: Village-wide improvement metrics.

### 3. Compare Outlines Visually
Generate plot comparisons showing the official boundary (red) vs. the target ground-truth (green) overlaid directly on satellite crops:
```bash
uv run python compare_truths.py
```
Outputs are saved to the `truth_comparisons/` directory.

---

## 📈 Methodology

### Cadastral Drift Model

The shift vector $S(p)$ for a plot $p$ at centroid coordinates $(x, y)$ is modeled as:

$$S(p) = S_{\text{global}} + \lambda(x, y) \cdot S_{\text{local}}(x, y)$$

Where:
- $S_{\text{global}}$ is the robust median shift of all control points.
- $S_{\text{local}}(x, y)$ is the residual shift calculated via Inverse Distance Weighting (IDW) interpolation from the 3 nearest ground-truth anchors.
- $\lambda(x, y)$ is an influence decay function that scales from $1.0$ (close to anchors) down to $0.0$ (at distances $\ge 2.0\text{km}$), reverting to the global offset in unanchored regions.

---

## 🔮 Future Enhancements

- **Active Contour (Snake) Fitting:** Implement boundary-snapping to high-gradient edges on the satellite raster near the estimated shift.
- **Deep Edge Detection:** Train a lightweight U-Net on satellite imagery to dynamically predict field boundaries where pre-computed layers are missing or noisy.
- **Convex Hull / Area Optimization:** Introduce shape constraints to preserve the total area of parcels during refinement.
