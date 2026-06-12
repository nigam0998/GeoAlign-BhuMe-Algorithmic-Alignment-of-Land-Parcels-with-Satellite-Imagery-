#!/usr/bin/env python3
"""Visualize and score example truths against imagery and detected boundaries.

For each public example truth, this script writes a PNG overlay showing:

- imagery patch
- detected boundary raster signal
- official plot boundary
- example-truth boundary

It also writes summaries comparing two signals near the official and truth outlines:
detected-boundary raster strength and visible RGB image edge strength.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

import numpy as np
import rasterio
from PIL import Image, ImageDraw
from pyproj import Transformer
from rasterio.enums import Resampling
from rasterio.features import rasterize
from rasterio.windows import from_bounds
from shapely.geometry import box
from shapely.ops import transform as shp_transform
from shapely.ops import unary_union

from bhume import load, patch_for_plot
from bhume.geo import geom_to_imagery_crs, open_imagery

DEFAULT_VILLAGE = 'data/34855_vadnerbhairav_chandavad_nashik'
DEFAULT_OUT_DIR = 'boundary_analysis'
PAD_M = 40.0
BOUNDARY_BUFFER_M = 3.0


def _transformer(src_crs, dst_crs):
    return Transformer.from_crs(src_crs, dst_crs, always_xy=True)


def _transform_geom(geom, src_crs, dst_crs):
    if str(src_crs) == str(dst_crs):
        return geom
    tf = _transformer(src_crs, dst_crs)
    return shp_transform(lambda xs, ys, z=None: tf.transform(xs, ys), geom)


def _bounds_in_crs(bounds, src_crs, dst_crs):
    geom = box(*bounds)
    geom = _transform_geom(geom, src_crs, dst_crs)
    return geom.bounds


def _clip_bounds(bounds, dataset_bounds):
    left, bottom, right, top = bounds
    dl, db, dr, dt = dataset_bounds
    return max(left, dl), max(bottom, db), min(right, dr), min(top, dt)


def _read_window(src, bounds, indexes=1, out_shape=None):
    bounds = _clip_bounds(bounds, src.bounds)
    left, bottom, right, top = bounds
    if right <= left or top <= bottom:
        raise ValueError('requested bounds do not overlap raster extent')

    window = from_bounds(left, bottom, right, top, transform=src.transform)
    read_kwargs = {'window': window}
    if out_shape is not None:
        read_kwargs['out_shape'] = out_shape
        read_kwargs['resampling'] = Resampling.bilinear

    data = src.read(indexes, **read_kwargs)
    transform = src.window_transform(window)
    return data, transform


def _normalize_band(band):
    band = np.asarray(band, dtype='float32')
    finite = np.isfinite(band)
    if not finite.any():
        return np.zeros(band.shape, dtype='uint8')

    valid = band[finite]
    lo, hi = np.percentile(valid, [2, 98])
    if hi <= lo:
        hi = float(valid.max())
        lo = float(valid.min())
    if hi <= lo:
        return np.zeros(band.shape, dtype='uint8')

    norm = np.clip((band - lo) / (hi - lo), 0, 1)
    norm[~finite] = 0
    return (norm * 255).astype('uint8')


def _outline_mask(geom, src_crs, raster_crs, shape, transform, buffer_m):
    geom_raster = _transform_geom(geom, src_crs, raster_crs)
    outline = geom_raster.boundary.buffer(buffer_m)
    return rasterize(
        [(outline, 1)],
        out_shape=shape,
        transform=transform,
        fill=0,
        dtype='uint8',
    ).astype(bool)


def _mean_signal(boundary_band, mask):
    if not mask.any():
        return None
    values = np.asarray(boundary_band, dtype='float32')[mask]
    if values.size == 0:
        return None
    return float(values.mean())


def _image_edge_strength(image_rgb):
    gray = (
        0.299 * image_rgb[..., 0].astype('float32')
        + 0.587 * image_rgb[..., 1].astype('float32')
        + 0.114 * image_rgb[..., 2].astype('float32')
    ) / 255.0
    gy, gx = np.gradient(gray)
    edge = np.hypot(gx, gy)

    hi = np.percentile(edge, 98)
    if hi > 0:
        edge = np.clip(edge / hi, 0, 1)
    return edge.astype('float32')


def _mean(values):
    values = [value for value in values if value is not None]
    return sum(values) / len(values) if values else None


def _polygon_pixel_rings(geom_4326, image_src, patch_transform):
    geom_img = geom_to_imagery_crs(image_src, geom_4326)
    polygons = [geom_img] if geom_img.geom_type == 'Polygon' else list(geom_img.geoms)
    inverse = ~patch_transform
    rings = []

    for poly in polygons:
        for ring in [poly.exterior, *poly.interiors]:
            pts = []
            for x, y in ring.coords:
                col, row = inverse * (x, y)
                pts.append((float(col), float(row)))
            rings.append(pts)
    return rings


def _draw_outline(draw, geom_4326, image_src, patch_transform, color, width):
    for ring in _polygon_pixel_rings(geom_4326, image_src, patch_transform):
        if len(ring) >= 2:
            draw.line(ring, fill=color, width=width, joint='curve')


def _make_overlay(image_rgb, boundary_band_for_image, official_geom, truth_geom, image_src, patch_transform):
    base = Image.fromarray(image_rgb).convert('RGBA')
    boundary_norm = _normalize_band(boundary_band_for_image)

    boundary_alpha = np.where(boundary_norm > 0, np.clip(boundary_norm * 0.55, 0, 150), 0).astype('uint8')
    boundary_rgba = np.zeros((*boundary_norm.shape, 4), dtype='uint8')
    boundary_rgba[..., 0] = 255
    boundary_rgba[..., 1] = 230
    boundary_rgba[..., 3] = boundary_alpha
    base.alpha_composite(Image.fromarray(boundary_rgba, mode='RGBA'))

    draw = ImageDraw.Draw(base)
    _draw_outline(draw, official_geom, image_src, patch_transform, color=(255, 40, 40, 255), width=4)
    _draw_outline(draw, truth_geom, image_src, patch_transform, color=(40, 255, 80, 255), width=4)
    draw.rectangle((8, 8, 270, 75), fill=(0, 0, 0, 145))
    draw.line((20, 25, 75, 25), fill=(255, 40, 40, 255), width=4)
    draw.text((85, 17), 'official', fill=(255, 255, 255, 255))
    draw.line((20, 48, 75, 48), fill=(40, 255, 80, 255), width=4)
    draw.text((85, 40), 'truth', fill=(255, 255, 255, 255))
    draw.rectangle((180, 22, 215, 50), fill=(255, 230, 0, 120))
    draw.text((222, 29), 'boundaries.tif', fill=(255, 255, 255, 255))
    return base.convert('RGB')


def _make_edge_overlay(image_rgb, edge_band, official_geom, truth_geom, image_src, patch_transform):
    base = Image.fromarray(image_rgb).convert('RGBA')
    edge_norm = np.clip(edge_band * 255, 0, 255).astype('uint8')

    edge_alpha = np.where(edge_norm > 0, np.clip(edge_norm * 0.6, 0, 160), 0).astype('uint8')
    edge_rgba = np.zeros((*edge_norm.shape, 4), dtype='uint8')
    edge_rgba[..., 1] = 190
    edge_rgba[..., 2] = 255
    edge_rgba[..., 3] = edge_alpha
    base.alpha_composite(Image.fromarray(edge_rgba, mode='RGBA'))

    draw = ImageDraw.Draw(base)
    _draw_outline(draw, official_geom, image_src, patch_transform, color=(255, 40, 40, 255), width=4)
    _draw_outline(draw, truth_geom, image_src, patch_transform, color=(40, 255, 80, 255), width=4)
    draw.rectangle((8, 8, 255, 75), fill=(0, 0, 0, 145))
    draw.line((20, 25, 75, 25), fill=(255, 40, 40, 255), width=4)
    draw.text((85, 17), 'official', fill=(255, 255, 255, 255))
    draw.line((20, 48, 75, 48), fill=(40, 255, 80, 255), width=4)
    draw.text((85, 40), 'truth', fill=(255, 255, 255, 255))
    draw.rectangle((173, 22, 205, 50), fill=(0, 190, 255, 120))
    draw.text((212, 29), 'image edges', fill=(255, 255, 255, 255))
    return base.convert('RGB')


def analyze(village_dir: str | Path, out_dir: str | Path = DEFAULT_OUT_DIR) -> list[dict]:
    village = load(village_dir)
    if village.example_truths is None:
        raise ValueError(f'{village.slug} has no example_truths.geojson')
    if village.boundaries_path is None:
        raise ValueError(f'{village.slug} has no boundaries.tif')

    out_root = Path(out_dir) / village.slug
    out_root.mkdir(parents=True, exist_ok=True)
    rows = []

    with open_imagery(village.imagery_path) as image_src, rasterio.open(village.boundaries_path) as boundary_src:
        for pn in village.example_truths.index:
            official_geom = village.plot(pn)
            truth_geom = village.example_truths.loc[pn, 'geometry']
            patch_geom = unary_union([official_geom, truth_geom])
            image_patch = patch_for_plot(image_src, patch_geom, pad_m=PAD_M)

            boundary_bounds = _bounds_in_crs(image_patch.bounds, image_src.crs, boundary_src.crs)
            boundary_band, boundary_transform = _read_window(boundary_src, boundary_bounds, indexes=1)
            boundary_for_image, _ = _read_window(
                boundary_src,
                boundary_bounds,
                indexes=1,
                out_shape=image_patch.image.shape[:2],
            )
            image_edge_band = _image_edge_strength(image_patch.image)

            official_mask = _outline_mask(
                official_geom,
                'EPSG:4326',
                boundary_src.crs,
                boundary_band.shape,
                boundary_transform,
                BOUNDARY_BUFFER_M,
            )
            truth_mask = _outline_mask(
                truth_geom,
                'EPSG:4326',
                boundary_src.crs,
                boundary_band.shape,
                boundary_transform,
                BOUNDARY_BUFFER_M,
            )
            official_image_mask = _outline_mask(
                official_geom,
                'EPSG:4326',
                image_src.crs,
                image_edge_band.shape,
                image_patch.transform,
                BOUNDARY_BUFFER_M,
            )
            truth_image_mask = _outline_mask(
                truth_geom,
                'EPSG:4326',
                image_src.crs,
                image_edge_band.shape,
                image_patch.transform,
                BOUNDARY_BUFFER_M,
            )

            official_signal = _mean_signal(boundary_band, official_mask)
            truth_signal = _mean_signal(boundary_band, truth_mask)
            boundary_improvement = None
            if official_signal is not None and truth_signal is not None:
                boundary_improvement = truth_signal - official_signal

            official_image_signal = _mean_signal(image_edge_band, official_image_mask)
            truth_image_signal = _mean_signal(image_edge_band, truth_image_mask)
            image_improvement = None
            if official_image_signal is not None and truth_image_signal is not None:
                image_improvement = truth_image_signal - official_image_signal

            overlay = _make_overlay(
                image_patch.image,
                boundary_for_image,
                official_geom,
                truth_geom,
                image_src,
                image_patch.transform,
            )
            image_path = out_root / f'{pn}_boundary_overlay.png'
            overlay.save(image_path)
            edge_overlay = _make_edge_overlay(
                image_patch.image,
                image_edge_band,
                official_geom,
                truth_geom,
                image_src,
                image_patch.transform,
            )
            edge_image_path = out_root / f'{pn}_image_edge_overlay.png'
            edge_overlay.save(edge_image_path)

            rows.append({
                'plot_number': str(pn),
                'official_boundary_signal': official_signal,
                'truth_boundary_signal': truth_signal,
                'truth_minus_official_boundary': boundary_improvement,
                'truth_aligns_better_boundary': boundary_improvement is not None and boundary_improvement > 0,
                'official_image_edge_signal': official_image_signal,
                'truth_image_edge_signal': truth_image_signal,
                'truth_minus_official_image_edge': image_improvement,
                'truth_aligns_better_image_edge': image_improvement is not None and image_improvement > 0,
                'truth_aligns_better_either_signal': (
                    (boundary_improvement is not None and boundary_improvement > 0)
                    or (image_improvement is not None and image_improvement > 0)
                ),
                'boundary_overlay_path': str(image_path),
                'image_edge_overlay_path': str(edge_image_path),
            })

    summary_path = out_root / 'boundary_alignment_summary.csv'
    with summary_path.open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'plot_number',
            'official_boundary_signal',
            'truth_boundary_signal',
            'truth_minus_official_boundary',
            'truth_aligns_better_boundary',
            'official_image_edge_signal',
            'truth_image_edge_signal',
            'truth_minus_official_image_edge',
            'truth_aligns_better_image_edge',
            'truth_aligns_better_either_signal',
            'boundary_overlay_path',
            'image_edge_overlay_path',
        ])
        writer.writeheader()
        writer.writerows(rows)

    boundary_better = sum(1 for row in rows if row['truth_aligns_better_boundary'])
    image_better = sum(1 for row in rows if row['truth_aligns_better_image_edge'])
    either_better = sum(1 for row in rows if row['truth_aligns_better_either_signal'])
    aggregate = {
        'plots_analyzed': len(rows),
        'truth_aligns_better_boundary_count': boundary_better,
        'truth_aligns_better_boundary_fraction': boundary_better / len(rows) if rows else None,
        'truth_aligns_better_image_edge_count': image_better,
        'truth_aligns_better_image_edge_fraction': image_better / len(rows) if rows else None,
        'truth_aligns_better_either_signal_count': either_better,
        'truth_aligns_better_either_signal_fraction': either_better / len(rows) if rows else None,
        'mean_official_boundary_signal': _mean([row['official_boundary_signal'] for row in rows]),
        'mean_truth_boundary_signal': _mean([row['truth_boundary_signal'] for row in rows]),
        'mean_truth_minus_official_boundary': _mean([row['truth_minus_official_boundary'] for row in rows]),
        'mean_official_image_edge_signal': _mean([row['official_image_edge_signal'] for row in rows]),
        'mean_truth_image_edge_signal': _mean([row['truth_image_edge_signal'] for row in rows]),
        'mean_truth_minus_official_image_edge': _mean([row['truth_minus_official_image_edge'] for row in rows]),
    }
    stats_path = out_root / 'boundary_alignment_stats.txt'
    with stats_path.open('w', encoding='utf-8') as f:
        for key, value in aggregate.items():
            f.write(f'{key}: {value}\n')

    print(f'Wrote {len(rows)} overlays to {out_root}')
    print(f'Wrote summary statistics to {summary_path}')
    print(f'Wrote aggregate statistics to {stats_path}')
    print(f'Truth aligns better with boundaries.tif on {boundary_better}/{len(rows)} example plots')
    print(f'Truth aligns better with image edges on {image_better}/{len(rows)} example plots')
    print(f'Truth aligns better with either signal on {either_better}/{len(rows)} example plots')
    return rows


if __name__ == '__main__':
    village_arg = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_VILLAGE
    out_arg = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_OUT_DIR
    analyze(village_arg, out_arg)
