"""Local residual-shift baseline.

This improves on the starter global median shift by keeping the robust village-wide
translation, then adding a small local correction estimated from nearby example truths.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass

import geopandas as gpd
from shapely.affinity import translate


DEFAULT_LOCAL_RADIUS_M = 1500.0
DEFAULT_FALLBACK_RADIUS_M = 2000.0
DEFAULT_NEIGHBORS = 3
DEFAULT_IDW_POWER = 2.0


@dataclass(frozen=True)
class ShiftAnchor:
    plot_number: str
    x: float
    y: float
    residual_dx: float
    residual_dy: float


def _utm_for(geom) -> str:
    lon = geom.centroid.x
    return f'EPSG:{32600 + int((lon + 180) // 6) + 1}'


def _local_influence(distance_m: float, local_radius_m: float, fallback_radius_m: float) -> float:
    if distance_m <= local_radius_m:
        return 1.0
    if distance_m >= fallback_radius_m:
        return 0.0
    return 1.0 - ((distance_m - local_radius_m) / (fallback_radius_m - local_radius_m))


def _idw_residual(
    x: float,
    y: float,
    anchors: list[ShiftAnchor],
    neighbors: int,
    power: float,
) -> tuple[float, float, float]:
    ranked = sorted(
        ((math.hypot(x - a.x, y - a.y), a) for a in anchors),
        key=lambda item: item[0],
    )[:neighbors]

    nearest_m = ranked[0][0]
    if nearest_m == 0:
        anchor = ranked[0][1]
        return anchor.residual_dx, anchor.residual_dy, nearest_m

    weighted_dx = 0.0
    weighted_dy = 0.0
    total_weight = 0.0
    for distance_m, anchor in ranked:
        weight = 1.0 / (distance_m ** power)
        weighted_dx += anchor.residual_dx * weight
        weighted_dy += anchor.residual_dy * weight
        total_weight += weight

    return weighted_dx / total_weight, weighted_dy / total_weight, nearest_m


def idw_local_shift(
    village,
    confidence: float = 0.55,
    neighbors: int = DEFAULT_NEIGHBORS,
    idw_power: float = DEFAULT_IDW_POWER,
    local_radius_m: float = DEFAULT_LOCAL_RADIUS_M,
    fallback_radius_m: float = DEFAULT_FALLBACK_RADIUS_M,
) -> gpd.GeoDataFrame:
    """Apply global median shift plus distance-decayed local residual IDW.

    The example truths define observed centroid shifts. Their median is the global correction.
    Each truth also contributes a residual from that global correction. For every plot, the
    three nearest truth anchors estimate a residual by inverse-distance weighting. That residual
    is used fully within `local_radius_m`, fades out to zero by `fallback_radius_m`, and therefore
    falls back to the global shift for unsupported areas.
    """
    if village.example_truths is None:
        raise ValueError(f'{village.slug} has no example_truths.geojson to estimate shifts from')
    if fallback_radius_m <= local_radius_m:
        raise ValueError('fallback_radius_m must be greater than local_radius_m')
    if neighbors < 1:
        raise ValueError('neighbors must be at least 1')

    utm = _utm_for(village.example_truths.geometry.iloc[0])
    official_u = village.plots.to_crs(utm)
    truth_u = village.example_truths.to_crs(utm)

    observed = []
    for pn in village.example_truths.index:
        if pn in official_u.index:
            official_centroid = official_u.loc[pn, 'geometry'].centroid
            truth_centroid = truth_u.loc[pn, 'geometry'].centroid
            observed.append((
                str(pn),
                official_centroid.x,
                official_centroid.y,
                truth_centroid.x - official_centroid.x,
                truth_centroid.y - official_centroid.y,
            ))

    if not observed:
        raise ValueError('no overlapping plots between example truths and the cadastre')

    mdx = statistics.median(dx for _, _, _, dx, _ in observed)
    mdy = statistics.median(dy for _, _, _, _, dy in observed)
    anchors = [
        ShiftAnchor(
            plot_number=pn,
            x=x,
            y=y,
            residual_dx=dx - mdx,
            residual_dy=dy - mdy,
        )
        for pn, x, y, dx, dy in observed
    ]

    shifted = official_u.copy()
    shifted_geometries = []
    notes = []

    for geom in official_u.geometry:
        centroid = geom.centroid
        residual_dx, residual_dy, nearest_m = _idw_residual(
            centroid.x,
            centroid.y,
            anchors,
            min(neighbors, len(anchors)),
            idw_power,
        )
        influence = _local_influence(nearest_m, local_radius_m, fallback_radius_m)
        dx = mdx + influence * residual_dx
        dy = mdy + influence * residual_dy
        shifted_geometries.append(translate(geom, dx, dy))
        notes.append(
            f'global median + IDW residual dx={dx:.1f}m dy={dy:.1f}m '
            f'influence={influence:.2f}'
        )

    shifted['geometry'] = shifted_geometries
    preds = shifted.to_crs('EPSG:4326')
    preds['status'] = 'corrected'
    preds['confidence'] = confidence
    preds['method_note'] = notes
    return preds[['plot_number', 'status', 'confidence', 'method_note', 'geometry']]
