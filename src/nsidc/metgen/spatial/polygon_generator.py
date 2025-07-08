"""
Polygon Generation Module - Wrapper for Standard Polygon Generator

This module provides backward compatibility by wrapping the standard_polygon_generator.
The old complex polygon generation methods have been replaced with a simpler, more
effective approach that achieves better results with less complexity.

Legacy method parameters are accepted but ignored - all polygon generation now uses
the optimized standard approach with concave hull and smart buffering.
"""

from . import standard_polygon_generator


class PolygonGenerator:
    """
    Backward-compatible wrapper for the standard polygon generator.
    
    This class maintains the same interface as the old PolygonGenerator but
    delegates all work to the improved standard_polygon_generator module.
    """
    
    def __init__(self):
        """Initialize the polygon generator."""
        # No initialization needed - standard generator is stateless
        pass
    
    def create_flightline_polygon(self, lon, lat, method="auto", **kwargs):
        """
        Create a polygon representing the flightline coverage.
        
        This method maintains backward compatibility but ignores the method
        parameter and any additional kwargs. All polygon generation now uses
        the optimized standard approach.
        
        Parameters:
        -----------
        lon, lat : array-like
            Longitude and latitude coordinates
        method : str (ignored)
            Legacy parameter - ignored for backward compatibility
        **kwargs : dict (ignored)
            Legacy parameters - ignored for backward compatibility
            
        Returns:
        --------
        polygon : shapely.geometry.Polygon or None
            The generated polygon
        metadata : dict
            Metadata about the generation process
        """
        # Log if legacy parameters are being used
        if method != "auto":
            print(f"[PolygonGenerator] Note: Legacy method '{method}' ignored - using optimized standard approach")
        
        if kwargs:
            ignored_params = ", ".join(kwargs.keys())
            print(f"[PolygonGenerator] Note: Legacy parameters ignored: {ignored_params}")
        
        # Delegate to standard generator
        polygon, metadata = standard_polygon_generator.create_flightline_polygon(lon, lat)
        
        # Add compatibility metadata
        metadata["legacy_method_requested"] = method
        metadata["legacy_params_ignored"] = list(kwargs.keys())
        
        return polygon, metadata
    
    # Legacy method stubs for backward compatibility
    def estimate_optimal_buffer(self, lon, lat):
        """Legacy method - returns default buffer size."""
        return 1000  # Default buffer in meters
    
    def _create_beam_polygon(self, *args, **kwargs):
        """Legacy method - not used."""
        raise NotImplementedError("Direct method calls not supported - use create_flightline_polygon()")
    
    def _create_union_buffer_polygon(self, *args, **kwargs):
        """Legacy method - not used."""
        raise NotImplementedError("Direct method calls not supported - use create_flightline_polygon()")
    
    def _create_line_buffer_polygon(self, *args, **kwargs):
        """Legacy method - not used."""
        raise NotImplementedError("Direct method calls not supported - use create_flightline_polygon()")