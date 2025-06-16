"""
Geometry resolver for determining and validating geometry sources based on UMM-G rules.

This module implements a functional approach to geometry resolution, following the
rules defined in the README for handling different geometry sources and their
valid combinations.
"""

import logging
from dataclasses import dataclass
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from nsidc.metgen.constants import CARTESIAN, GEODETIC

logger = logging.getLogger(__name__)


class GeometrySource(Enum):
    """Enumeration of possible geometry sources in priority order."""

    SPO_FILE = auto()
    SPATIAL_FILE = auto()
    DATA_FILE = auto()
    COLLECTION = auto()
    NONE = auto()


class GeometryType(Enum):
    """Types of geometry that can be output to UMM-G."""

    POINT = auto()
    BOUNDING_RECTANGLE = auto()
    GPOLYGON = auto()


class GeometryError(Exception):
    """Raised when geometry configuration is invalid."""

    pass


@dataclass(frozen=True)
class GeometryContext:
    """Immutable context containing all information needed for geometry resolution."""

    gsr: str  # CARTESIAN or GEODETIC
    collection_geometry_override: bool
    has_spo_file: bool
    has_spatial_file: bool
    has_data_file_geometry: bool
    has_collection_geometry: bool
    point_count: Optional[int] = None
    spo_filename: Optional[Path] = None
    spatial_filename: Optional[Path] = None


@dataclass(frozen=True)
class GeometryDecision:
    """Result of geometry resolution containing source and expected type."""

    source: GeometrySource
    geometry_type: GeometryType
    error: Optional[str] = None

    @property
    def is_valid(self) -> bool:
        return self.error is None


# Type aliases for clarity
GeometryRule = Callable[[GeometryContext], Optional[GeometryDecision]]
GeometryPoints = List[Dict[str, float]]


def rule_spo_cartesian(context: GeometryContext) -> Optional[GeometryDecision]:
    """Rule: .spo files with CARTESIAN GSR are always an error."""
    if context.has_spo_file and context.gsr == CARTESIAN:
        return GeometryDecision(
            source=GeometrySource.SPO_FILE,
            geometry_type=GeometryType.GPOLYGON,
            error="SPO files cannot be used with CARTESIAN coordinate system",
        )
    return None


def rule_spo_geodetic_insufficient_points(
    context: GeometryContext,
) -> Optional[GeometryDecision]:
    """Rule: .spo files with GEODETIC GSR and ≤2 points are an error."""
    if (
        context.has_spo_file
        and context.gsr == GEODETIC
        and context.point_count is not None
        and context.point_count <= 2
    ):
        return GeometryDecision(
            source=GeometrySource.SPO_FILE,
            geometry_type=GeometryType.GPOLYGON,
            error=f"SPO files require at least 3 points, found {context.point_count}",
        )
    return None


def rule_spo_geodetic_valid(context: GeometryContext) -> Optional[GeometryDecision]:
    """Rule: .spo files with GEODETIC GSR and >2 points produce GPolygon."""
    if (
        context.has_spo_file
        and context.gsr == GEODETIC
        and context.point_count is not None
        and context.point_count > 2
    ):
        return GeometryDecision(
            source=GeometrySource.SPO_FILE, geometry_type=GeometryType.GPOLYGON
        )
    return None


def rule_spatial_cartesian(context: GeometryContext) -> Optional[GeometryDecision]:
    """Rule: .spatial files with CARTESIAN GSR produce bounding rectangle."""
    if context.has_spatial_file and context.gsr == CARTESIAN:
        if context.point_count != 2:
            return GeometryDecision(
                source=GeometrySource.SPATIAL_FILE,
                geometry_type=GeometryType.BOUNDING_RECTANGLE,
                error=f"CARTESIAN spatial files require exactly 2 points, found {context.point_count}",
            )
        return GeometryDecision(
            source=GeometrySource.SPATIAL_FILE,
            geometry_type=GeometryType.BOUNDING_RECTANGLE,
        )
    return None


def rule_spatial_geodetic_single_point(
    context: GeometryContext,
) -> Optional[GeometryDecision]:
    """Rule: .spatial files with GEODETIC GSR and 1 point produce Point."""
    if (
        context.has_spatial_file
        and context.gsr == GEODETIC
        and context.point_count == 1
    ):
        return GeometryDecision(
            source=GeometrySource.SPATIAL_FILE, geometry_type=GeometryType.POINT
        )
    return None


def rule_spatial_geodetic_multiple_points(
    context: GeometryContext,
) -> Optional[GeometryDecision]:
    """Rule: .spatial files with GEODETIC GSR and >1 point produce GPolygon."""
    if (
        context.has_spatial_file
        and context.gsr == GEODETIC
        and context.point_count is not None
        and context.point_count > 1
    ):
        return GeometryDecision(
            source=GeometrySource.SPATIAL_FILE, geometry_type=GeometryType.GPOLYGON
        )
    return None


def rule_data_file_cartesian(context: GeometryContext) -> Optional[GeometryDecision]:
    """Rule: Data files with CARTESIAN GSR produce bounding rectangle."""
    if context.has_data_file_geometry and context.gsr == CARTESIAN:
        return GeometryDecision(
            source=GeometrySource.DATA_FILE,
            geometry_type=GeometryType.BOUNDING_RECTANGLE,
        )
    return None


def rule_data_file_geodetic(context: GeometryContext) -> Optional[GeometryDecision]:
    """Rule: Data files with GEODETIC GSR produce point or polygon based on data."""
    if context.has_data_file_geometry and context.gsr == GEODETIC:
        # The actual geometry type will be determined by the data file reader
        # This could be POINT for single coordinates or GPOLYGON for multiple
        return GeometryDecision(
            source=GeometrySource.DATA_FILE,
            geometry_type=GeometryType.POINT,  # Default, will be refined by reader
        )
    return None


def rule_collection_override(context: GeometryContext) -> Optional[GeometryDecision]:
    """Rule: Collection geometry override with CARTESIAN GSR."""
    if context.collection_geometry_override and context.has_collection_geometry:
        if context.gsr != CARTESIAN:
            return GeometryDecision(
                source=GeometrySource.COLLECTION,
                geometry_type=GeometryType.BOUNDING_RECTANGLE,
                error="Collection geometry override only supports CARTESIAN coordinate system",
            )
        return GeometryDecision(
            source=GeometrySource.COLLECTION,
            geometry_type=GeometryType.BOUNDING_RECTANGLE,
        )
    return None


def rule_collection_fallback_cartesian(
    context: GeometryContext,
) -> Optional[GeometryDecision]:
    """Rule: Collection as fallback for CARTESIAN GSR."""
    if context.has_collection_geometry and context.gsr == CARTESIAN:
        return GeometryDecision(
            source=GeometrySource.COLLECTION,
            geometry_type=GeometryType.BOUNDING_RECTANGLE,
        )
    return None


def rule_no_geometry(context: GeometryContext) -> Optional[GeometryDecision]:
    """Rule: No geometry available."""
    return GeometryDecision(
        source=GeometrySource.NONE,
        geometry_type=GeometryType.POINT,
        error="No valid geometry source available",
    )


# Ordered list of rules to apply
GEOMETRY_RULES: List[GeometryRule] = [
    # Collection override has highest priority
    rule_collection_override,
    # Then check for errors
    rule_spo_cartesian,
    rule_spo_geodetic_insufficient_points,
    # Then check valid sources in priority order
    rule_spo_geodetic_valid,
    rule_spatial_cartesian,
    rule_spatial_geodetic_single_point,
    rule_spatial_geodetic_multiple_points,
    rule_data_file_cartesian,
    rule_data_file_geodetic,
    rule_collection_fallback_cartesian,
    # Final fallback
    rule_no_geometry,
]


def resolve_geometry(context: GeometryContext) -> GeometryDecision:
    """
    Resolve the geometry source and type based on the context and rules.

    This function applies each rule in order until one matches, implementing
    a functional chain of responsibility pattern.

    Args:
        context: The geometry context containing all relevant information

    Returns:
        A GeometryDecision indicating the source, type, and any errors
    """
    for rule in GEOMETRY_RULES:
        decision = rule(context)
        if decision is not None:
            logger.debug(f"Geometry resolution: {decision}")
            return decision

    # This should never happen if rules are complete
    return GeometryDecision(
        source=GeometrySource.NONE,
        geometry_type=GeometryType.POINT,
        error="No geometry resolution rule matched",
    )


def validate_geometry_points(
    points: GeometryPoints, expected_type: GeometryType, gsr: str
) -> Tuple[bool, Optional[str]]:
    """
    Validate that the geometry points match the expected type and GSR.

    Args:
        points: List of point dictionaries with Longitude/Latitude keys
        expected_type: The expected geometry type
        gsr: The granule spatial representation

    Returns:
        Tuple of (is_valid, error_message)
    """
    point_count = len(points)

    if expected_type == GeometryType.POINT:
        if point_count != 1:
            return (
                False,
                f"Point geometry requires exactly 1 point, found {point_count}",
            )
        if gsr != GEODETIC:
            return False, "Point geometry only valid for GEODETIC coordinate system"

    elif expected_type == GeometryType.BOUNDING_RECTANGLE:
        if point_count != 2:
            return (
                False,
                f"Bounding rectangle requires exactly 2 points, found {point_count}",
            )
        if gsr != CARTESIAN:
            return (
                False,
                "Bounding rectangle only valid for CARTESIAN coordinate system",
            )

    elif expected_type == GeometryType.GPOLYGON:
        if point_count < 4:  # Minimum for closed polygon
            return (
                False,
                f"GPolygon requires at least 4 points (closed), found {point_count}",
            )
        if gsr != GEODETIC:
            return False, "GPolygon only valid for GEODETIC coordinate system"

    return True, None


def create_geometry_context(granule: Any, config: Any) -> GeometryContext:
    """
    Create a GeometryContext from a granule and configuration.

    This is a helper function to bridge the current pipeline structure
    with the functional geometry resolver.
    """
    collection = granule.collection

    # Determine available geometry sources
    spatial_path = None
    if granule.spatial_filename is not None and granule.spatial_filename != "":
        spatial_path = Path(granule.spatial_filename)

    has_spo = spatial_path is not None and spatial_path.suffix == ".spo"
    has_spatial = spatial_path is not None and spatial_path.suffix == ".spatial"

    # Count points if we have a spatial file
    point_count = None
    if has_spo or has_spatial:
        # This would need to be implemented to actually read the file
        # For now, this is a placeholder
        point_count = None  # Would be set by reading the file

    return GeometryContext(
        gsr=collection.granule_spatial_representation,
        collection_geometry_override=config.collection_geometry_override,
        has_spo_file=has_spo,
        has_spatial_file=has_spatial,
        has_data_file_geometry=True,  # Assume data files can provide geometry
        has_collection_geometry=collection.spatial_extent is not None,
        point_count=point_count,
        spo_filename=spatial_path if has_spo else None,
        spatial_filename=spatial_path if has_spatial else None,
    )
