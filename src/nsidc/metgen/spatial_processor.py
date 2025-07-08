"""
Spatial Processor for MetGenC

This module handles spatial polygon generation during UMM-G metadata creation,
following the project rules for when spatial polygons should be generated.
"""

import json
import logging
from typing import Dict, List, Optional, Tuple, Any

from nsidc.metgen import constants

LOGGER = logging.getLogger(constants.ROOT_LOGGER)


class SpatialProcessor:
    """
    Processes spatial data during UMM-G generation, applying polygon generation
    when appropriate based on project rules and configuration.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the spatial processor.
        
        Parameters:
        -----------
        config : dict
            MetGenC configuration dictionary
        """
        self.config = config
        self.spatial_config = config.get('spatial', {})
        self.enabled = self.spatial_config.get('enabled', False)
        
    def should_generate_polygon(self, 
                              collection_name: str,
                              spatial_representation: str,
                              point_count: int,
                              data_file_path: str = None) -> bool:
        """
        Determine if spatial polygon generation should be applied based on project rules.
        
        Based on the README table:
        - .spatial files with >= 2 geodetic points -> GPolygon(s) calculated to enclose all points
        - data files with >= 2 geodetic points -> GPolygon(s) calculated to enclose all points
        - NetCDF gridded data with >= 3 geodetic points -> GPolygon calculated from grid perimeter
        
        Parameters:
        -----------
        collection_name : str
            The collection short name
        spatial_representation : str
            Either 'cartesian' or 'geodetic' 
        point_count : int
            Number of spatial points available
        data_file_path : str, optional
            Path to the data file for additional context
            
        Returns:
        --------
        bool : True if polygon generation should be applied
        """
        if not self.enabled:
            return False
            
        # Rule 1: Must be geodetic coordinates (not cartesian)
        if spatial_representation != constants.GEODETIC:
            LOGGER.debug("Spatial polygon generation skipped: not geodetic coordinates")
            return False
            
        # Rule 2: Must have sufficient points
        if point_count < 2:
            LOGGER.debug(f"Spatial polygon generation skipped: insufficient points ({point_count})")
            return False
            
        # Rule 3: Check collection-specific rules
        if self._is_flightline_collection(collection_name):
            LOGGER.debug(f"Spatial polygon generation enabled: flightline collection {collection_name}")
            return True
            
        # Rule 4: Check file type specific rules
        if data_file_path:
            if self._is_gridded_data(data_file_path) and point_count >= 3:
                LOGGER.debug("Spatial polygon generation enabled: gridded NetCDF data")
                return True
                
            if self._is_point_data_file(data_file_path) and point_count >= 2:
                LOGGER.debug("Spatial polygon generation enabled: point data file")
                return True
                
        # Rule 5: Generic case - if >= 2 geodetic points, generate polygon
        if point_count >= 2:
            LOGGER.debug(f"Spatial polygon generation enabled: {point_count} geodetic points")
            return True
            
        return False
        
    def _is_flightline_collection(self, collection_name: str) -> bool:
        """Check if this is a known flightline/LIDAR collection."""
        flightline_collections = {
            'LVISF2', 'IPFLT1B', 'ILVIS2', 'LVIS', 'ICEBRIDGE',
            # Add other known flightline collections
        }
        return any(collection in collection_name.upper() for collection in flightline_collections)
        
    def _is_gridded_data(self, file_path: str) -> bool:
        """Check if this appears to be gridded NetCDF data."""
        if not file_path:
            return False
        return file_path.lower().endswith(('.nc', '.netcdf', '.hdf', '.h5'))
        
    def _is_point_data_file(self, file_path: str) -> bool:
        """Check if this appears to be point data."""
        if not file_path:
            return False
        return file_path.lower().endswith(('.txt', '.csv', '.dat'))
        
    def process_spatial_extent(self, 
                             spatial_representation: str,
                             spatial_values: List[List[float]],
                             collection_name: str = "",
                             data_file_path: str = None,
                             coordinate_data: Optional[Dict[str, Any]] = None) -> str:
        """
        Process spatial extent, applying polygon generation when appropriate.
        
        Parameters:
        -----------
        spatial_representation : str
            Either 'cartesian' or 'geodetic'
        spatial_values : list
            List of [lon, lat] coordinate pairs
        collection_name : str
            Collection short name for rule checking
        data_file_path : str, optional
            Path to data file for context
        coordinate_data : dict, optional
            Full coordinate arrays for polygon generation
            
        Returns:
        --------
        str : JSON string representation of the spatial extent
        """
        point_count = len(spatial_values)
        
        # Check if we should generate a polygon
        if self.should_generate_polygon(
            collection_name=collection_name,
            spatial_representation=spatial_representation, 
            point_count=point_count,
            data_file_path=data_file_path
        ):
            # Attempt polygon generation
            polygon_extent = self._generate_polygon_extent(
                spatial_values=spatial_values,
                coordinate_data=coordinate_data,
                collection_name=collection_name
            )
            
            if polygon_extent:
                LOGGER.info(f"Generated spatial polygon for {collection_name}")
                return polygon_extent
            else:
                LOGGER.warning("Polygon generation failed, falling back to default spatial extent")
                
        # Fall back to default spatial extent processing
        return self._generate_default_extent(spatial_representation, spatial_values)
        
    def _generate_polygon_extent(self,
                               spatial_values: List[List[float]],
                               coordinate_data: Optional[Dict[str, Any]] = None,
                               collection_name: str = "") -> Optional[str]:
        """
        Generate polygon-based spatial extent using the spatial module.
        
        Parameters:
        -----------
        spatial_values : list
            List of [lon, lat] coordinate pairs
        coordinate_data : dict, optional
            Full coordinate arrays for polygon generation
        collection_name : str
            Collection name for logging
            
        Returns:
        --------
        str or None : JSON string of polygon extent, or None if generation failed
        """
        try:
            from nsidc.metgen.spatial import create_flightline_polygon
            
            # Use full coordinate data if available, otherwise use spatial_values
            if coordinate_data and 'longitude' in coordinate_data and 'latitude' in coordinate_data:
                lon = coordinate_data['longitude']
                lat = coordinate_data['latitude']
            else:
                # Extract from spatial_values
                lon = [point[0] for point in spatial_values]
                lat = [point[1] for point in spatial_values]
                
            if len(lon) < 3:
                LOGGER.debug("Insufficient points for polygon generation, using default extent")
                return None
                
            # Generate the polygon
            polygon, metadata = create_flightline_polygon(lon, lat)
            
            if polygon is None:
                LOGGER.warning("Polygon generation returned None")
                return None
                
            # Log generation results
            LOGGER.info(f"Generated polygon: {metadata['vertices']} vertices, "
                       f"{metadata['final_data_coverage']:.1%} coverage, "
                       f"{metadata['generation_time_seconds']:.3f}s")
                       
            # Convert to UMM-G format
            return self._polygon_to_ummg(polygon)
            
        except ImportError:
            LOGGER.warning("Spatial module not available, using default spatial extent")
            return None
        except Exception as e:
            LOGGER.error(f"Error generating spatial polygon: {e}")
            return None
            
    def _polygon_to_ummg(self, polygon) -> str:
        """
        Convert a Shapely polygon to UMM-G spatial extent format.
        
        Parameters:
        -----------
        polygon : shapely.geometry.Polygon
            The polygon to convert
            
        Returns:
        --------
        str : JSON string of UMM-G spatial extent
        """
        try:
            # Extract exterior coordinates (excluding duplicate last point)
            coords = list(polygon.exterior.coords)[:-1]
            
            # Convert to UMM-G points format
            points = [{"Longitude": float(lon), "Latitude": float(lat)} for lon, lat in coords]
            
            # Create UMM-G structure
            spatial_extent = {
                "Geometry": {
                    "GPolygons": [{
                        "Boundary": {
                            "Points": points
                        }
                    }]
                }
            }
            
            return json.dumps(spatial_extent)
            
        except Exception as e:
            LOGGER.error(f"Error converting polygon to UMM-G format: {e}")
            raise
            
    def _generate_default_extent(self, spatial_representation: str, spatial_values: List[List[float]]) -> str:
        """
        Generate default spatial extent using existing MetGenC logic.
        
        Parameters:
        -----------
        spatial_representation : str
            Either 'cartesian' or 'geodetic'
        spatial_values : list
            List of coordinate pairs
            
        Returns:
        --------
        str : JSON string of spatial extent
        """
        # Import here to avoid circular imports
        from nsidc.metgen.metgen import populate_spatial
        
        return populate_spatial(spatial_representation, spatial_values)


# Convenience function for integration
def process_spatial_extent_with_polygon_generation(
    config: Dict[str, Any],
    spatial_representation: str,
    spatial_values: List[List[float]],
    collection_name: str = "",
    data_file_path: str = None,
    coordinate_data: Optional[Dict[str, Any]] = None
) -> str:
    """
    Convenience function to process spatial extent with polygon generation.
    
    This function can be used as a drop-in replacement for the existing
    populate_spatial function when polygon generation is desired.
    """
    processor = SpatialProcessor(config)
    return processor.process_spatial_extent(
        spatial_representation=spatial_representation,
        spatial_values=spatial_values,
        collection_name=collection_name,
        data_file_path=data_file_path,
        coordinate_data=coordinate_data
    )