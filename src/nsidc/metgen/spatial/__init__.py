"""
Spatial polygon generation module for MetGenC.

This module provides functionality for generating optimized spatial coverage
polygons from point data, particularly for LVIS/ILVIS2 LIDAR flightline data.
"""

from .polygon_generator import create_flightline_polygon

__all__ = [
    "create_flightline_polygon",
]
