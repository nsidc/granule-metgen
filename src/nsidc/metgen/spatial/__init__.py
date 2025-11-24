"""
Spatial polygon generation module for MetGenC.

This module provides two polygon generation algorithms:

1. **polygon_generator.create_flightline_polygon**: Complex concave hull algorithm
   - For point cloud data (LIDAR, radar, scattered measurements)
   - Uses coverage optimization and adaptive buffering

2. **simple_polygon.create_buffered_polygon**: Simple line buffering algorithm
   - For sequential ground tracks (satellite paths, flight lines)
   - Fast and predictable with excellent antimeridian handling

Algorithm selection is controlled by the 'spatial_polygon_algorithm' configuration
parameter. Users should not call these functions directly; use the configuration
system which routes to the appropriate algorithm via readers.utilities.parse_spatial().

For direct access (testing/debugging), import from the specific module:
    from nsidc.metgen.spatial.polygon_generator import create_flightline_polygon
    from nsidc.metgen.spatial.simple_polygon import create_buffered_polygon
"""

__all__ = []
