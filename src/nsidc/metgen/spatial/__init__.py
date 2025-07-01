"""
Spatial polygon generation module for MetGenC.

This module provides functionality for generating optimized spatial coverage
polygons from point data, particularly for LVIS/ILVIS2 LIDAR flightline data.
"""

from .cmr_client import CMRClient, PolygonComparator, UMMGParser, sanitize_granule_ur
from .polygon_generator import PolygonGenerator
from .simplification import iterative_simplify_polygon

__all__ = [
    'PolygonGenerator',
    'CMRClient',
    'UMMGParser', 
    'PolygonComparator',
    'sanitize_granule_ur',
    'iterative_simplify_polygon'
]