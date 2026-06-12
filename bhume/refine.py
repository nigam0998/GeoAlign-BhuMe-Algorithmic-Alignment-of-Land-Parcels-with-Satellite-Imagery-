from shapely.geometry.base import BaseGeometry


def local_boundary_score(
    geometry: BaseGeometry,
    boundary_src,
):
    """
    Score how well a geometry aligns
    with detected field boundaries.
    """
    raise NotImplementedError


def search_best_shift(
    geometry: BaseGeometry,
    boundary_src,
):
    """
    Search nearby shifts and return
    the best-scoring geometry.
    """
    raise NotImplementedError


def refine_with_boundaries(
    geometry: BaseGeometry,
    boundary_src,
):
    """
    Refine a geometry using
    boundary evidence.
    """
    raise NotImplementedError