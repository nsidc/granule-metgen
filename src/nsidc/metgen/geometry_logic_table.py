"""
Geometry Logic Table Implementation.

This module provides a visual, logic-table based approach to geometry decisions,
similar to digital logic circuit design patterns.
"""

from dataclasses import dataclass
from enum import IntEnum
from typing import Optional, Tuple


class GeometryOutput(IntEnum):
    """Geometry output types with binary encoding."""

    ERROR = 0x00  # 0000
    POINT = 0x11  # 0001 0001 (valid + type 1)
    BBOX = 0x12  # 0001 0010 (valid + type 2)
    POLYGON = 0x14  # 0001 0100 (valid + type 4)


class SourceType(IntEnum):
    """Source type encoding for multiplexer logic."""

    COLLECTION = 0b00
    SPO = 0b01
    SPATIAL = 0b10
    SCIENCE = 0b11


class CoordSystem(IntEnum):
    """Coordinate system binary flags."""

    GEODETIC = 0b1
    CARTESIAN = 0b0


@dataclass
class GeometryLogicEntry:
    """Single entry in the geometry logic table."""

    source: str
    points: str  # "0", "1", "2", ">2", "*"
    coord: str  # "GEO", "CAR", "*"
    valid: bool
    output: GeometryOutput

    def matches(self, source_type: str, point_count: int, coord_system: str) -> bool:
        """Check if this entry matches the given conditions."""
        if self.source != source_type:
            return False

        # Check points condition
        if self.points != "*":
            if self.points == "0" and point_count != 0:
                return False
            elif self.points == "1" and point_count != 1:
                return False
            elif self.points == "2" and point_count != 2:
                return False
            elif self.points == ">2" and point_count <= 2:
                return False
            elif self.points == "≤2" and point_count > 2:
                return False

        # Check coordinate system
        if self.coord != "*":
            if self.coord != coord_system:
                return False

        return True


# Complete geometry logic truth table
GEOMETRY_LOGIC_TABLE = [
    # SPO File Rules
    GeometryLogicEntry("SPO", "≤2", "*", False, GeometryOutput.ERROR),
    GeometryLogicEntry("SPO", ">2", "GEO", True, GeometryOutput.POLYGON),
    GeometryLogicEntry("SPO", "*", "CAR", False, GeometryOutput.ERROR),
    # SPATIAL File Rules
    GeometryLogicEntry("SPATIAL", "0", "*", False, GeometryOutput.ERROR),
    GeometryLogicEntry("SPATIAL", "1", "GEO", True, GeometryOutput.POINT),
    GeometryLogicEntry("SPATIAL", "1", "CAR", False, GeometryOutput.ERROR),
    GeometryLogicEntry("SPATIAL", "2", "CAR", True, GeometryOutput.BBOX),
    GeometryLogicEntry("SPATIAL", "2", "GEO", True, GeometryOutput.POLYGON),
    GeometryLogicEntry("SPATIAL", ">2", "GEO", True, GeometryOutput.POLYGON),
    GeometryLogicEntry("SPATIAL", ">2", "CAR", False, GeometryOutput.ERROR),
    # SCIENCE File Rules
    GeometryLogicEntry("SCIENCE", "*", "CAR", True, GeometryOutput.BBOX),
    GeometryLogicEntry("SCIENCE", "*", "GEO", True, GeometryOutput.POLYGON),
    # COLLECTION Override Rules
    GeometryLogicEntry("COLLECT", "*", "CAR", True, GeometryOutput.BBOX),
]


def lookup_geometry_output(
    source_type: str, point_count: int, coord_system: str
) -> GeometryOutput:
    """
    Look up geometry output using the truth table.

    This implements a simple table-driven approach similar to
    a logic array or ROM lookup in digital circuits.
    """
    for entry in GEOMETRY_LOGIC_TABLE:
        if entry.matches(source_type, point_count, coord_system):
            return entry.output
    return GeometryOutput.ERROR


def geometry_karnaugh_map(
    point_count: int, coord_system: str
) -> Optional[GeometryOutput]:
    """
    Karnaugh map style lookup for spatial files.

    Visual representation:
                  Points Count
                | 0 | 1 | 2 | >2 |
            ----+---+---+---+----+
    Coord   GEO | ✗ | • | ⬟ | ⬟ |
            CAR | ✗ | ✗ | ▢ | ✗ |
                +---+---+---+----+
    """
    # Create the K-map as a 2D lookup
    kmap = {
        ("GEO", 0): GeometryOutput.ERROR,
        ("GEO", 1): GeometryOutput.POINT,
        ("GEO", 2): GeometryOutput.POLYGON,
        ("GEO", 3): GeometryOutput.POLYGON,  # >2 encoded as 3
        ("CAR", 0): GeometryOutput.ERROR,
        ("CAR", 1): GeometryOutput.ERROR,
        ("CAR", 2): GeometryOutput.BBOX,
        ("CAR", 3): GeometryOutput.ERROR,  # >2 encoded as 3
    }

    # Encode point count for lookup
    if point_count == 0:
        pts_key = 0
    elif point_count == 1:
        pts_key = 1
    elif point_count == 2:
        pts_key = 2
    else:  # >2
        pts_key = 3

    return kmap.get((coord_system, pts_key))


class GeometryPriorityEncoder:
    """
    Priority encoder for geometry source selection.

    Implements a hardware-style priority encoder where the highest
    priority active input determines the output.
    """

    def __init__(self):
        self.priorities = [
            ("COLLECTION", 4),
            ("SPO", 3),
            ("SPATIAL", 2),
            ("SCIENCE", 1),
            ("DEFAULT", 0),
        ]

    def encode(
        self,
        has_collection: bool,
        has_spo: bool,
        has_spatial: bool,
        has_science: bool,
    ) -> Tuple[str, int]:
        """
        Encode the active inputs to determine source and priority.

        Returns:
            Tuple of (source_name, priority_level)
        """
        active_sources = []
        if has_collection:
            active_sources.append(("COLLECTION", 4))
        if has_spo:
            active_sources.append(("SPO", 3))
        if has_spatial:
            active_sources.append(("SPATIAL", 2))
        if has_science:
            active_sources.append(("SCIENCE", 1))

        if not active_sources:
            return ("DEFAULT", 0)

        # Return highest priority
        return max(active_sources, key=lambda x: x[1])


class GeometryStateMachine:
    """
    State machine implementation for geometry decisions.

    Models the decision process as a finite state machine with
    defined states and transitions.
    """

    def __init__(self):
        self.state = "INIT"
        self.output = None

    def transition(
        self,
        source: str,
        point_count: Optional[int] = None,
        coord_system: Optional[str] = None,
    ) -> GeometryOutput:
        """
        Process state transition based on inputs.

        State diagram:
        INIT → CHECK_SOURCE → VALIDATE → OUTPUT
        """
        if self.state == "INIT":
            if source == "COLLECTION":
                self.state = "COLL_GEOM"
                self.output = GeometryOutput.BBOX
            elif source == "SPO":
                self.state = "CHECK_SPO"
            elif source == "SPATIAL":
                self.state = "CHECK_SPATIAL"
            elif source == "SCIENCE":
                self.state = "CHECK_SCIENCE"
            else:
                self.state = "ERROR"
                self.output = GeometryOutput.ERROR

        if self.state == "CHECK_SPO":
            if coord_system == "CAR":
                self.output = GeometryOutput.ERROR
            elif point_count and point_count <= 2:
                self.output = GeometryOutput.ERROR
            else:
                self.output = GeometryOutput.POLYGON

        elif self.state == "CHECK_SPATIAL":
            if coord_system == "GEO":
                if point_count == 1:
                    self.output = GeometryOutput.POINT
                elif point_count >= 2:
                    self.output = GeometryOutput.POLYGON
                else:
                    self.output = GeometryOutput.ERROR
            elif coord_system == "CAR":
                if point_count == 2:
                    self.output = GeometryOutput.BBOX
                else:
                    self.output = GeometryOutput.ERROR

        elif self.state == "CHECK_SCIENCE":
            if coord_system == "CAR":
                self.output = GeometryOutput.BBOX
            else:
                self.output = GeometryOutput.POLYGON

        return self.output


def geometry_boolean_logic(
    source: str, point_count: int, coord_system: str
) -> GeometryOutput:
    """
    Boolean algebra implementation of geometry logic.

    Evaluates boolean expressions to determine output.
    """
    # Define boolean variables
    is_spo = source == "SPO"
    is_spatial = source == "SPATIAL"
    is_science = source == "SCIENCE"
    is_collection = source == "COLLECTION"
    is_geo = coord_system == "GEO"
    is_car = coord_system == "CAR"

    # Boolean expressions for each geometry type
    polygon = (
        (is_spo and is_geo and point_count > 2)
        or (is_spatial and is_geo and point_count >= 2)
        or (is_science and is_geo)
    )

    bbox = (
        is_collection
        or (is_spatial and is_car and point_count == 2)
        or (is_science and is_car)
    )

    point = is_spatial and is_geo and point_count == 1

    error = (
        (is_spo and is_car)
        or (is_spo and point_count <= 2)
        or (is_spatial and is_car and point_count != 2)
        or (is_spatial and point_count == 0)
    )

    # Return based on evaluation
    if error:
        return GeometryOutput.ERROR
    elif point:
        return GeometryOutput.POINT
    elif bbox:
        return GeometryOutput.BBOX
    elif polygon:
        return GeometryOutput.POLYGON
    else:
        return GeometryOutput.ERROR


def visualize_logic_table():
    """
    Generate a visual representation of the geometry logic table.

    Returns ASCII art representation suitable for documentation.
    """
    header = """
    ╔═══════════════════════════════════════════════════════════╗
    ║           GEOMETRY LOGIC DECISION TABLE                      ║
    ╠═══════════╤═══════╤═══════╤═══════╤═══════════════════════╣
    ║  Source   │ Points│ Coord │ Valid │      Output           ║
    ╠═══════════╪═══════╪═══════╪═══════╪═══════════════════════╣"""

    rows = []
    for entry in GEOMETRY_LOGIC_TABLE:
        valid_mark = "✓" if entry.valid else "✗"
        output_name = entry.output.name
        row = f"    ║ {entry.source:9} │ {entry.points:5} │ {entry.coord:5} │   {valid_mark}   │ {output_name:20} ║"
        rows.append(row)

    footer = "    ╚═══════════╧═══════╧═══════╧═══════╧═══════════════════════╝"

    return header + "\n" + "\n".join(rows) + "\n" + footer


def demonstrate_multiplexer_logic(
    source_select: int, point_count: int, coord_select: int
) -> GeometryOutput:
    """
    Demonstrate multiplexer-style selection logic.

    Uses binary selectors similar to hardware multiplexers.
    """
    # Level 1 MUX: Source selection
    source_outputs = {
        0b00: lambda p, c: GeometryOutput.BBOX,  # COLLECTION
        0b01: lambda p, c: (  # SPO
            GeometryOutput.POLYGON if p > 2 and c == 1 else GeometryOutput.ERROR
        ),
        0b10: lambda p, c: geometry_karnaugh_map(  # SPATIAL
            p, "GEO" if c == 1 else "CAR"
        ),
        0b11: lambda p, c: (  # SCIENCE
            GeometryOutput.POLYGON if c == 1 else GeometryOutput.BBOX
        ),
    }

    # Select and execute
    selector = source_outputs.get(source_select, lambda p, c: GeometryOutput.ERROR)
    return selector(point_count, coord_select)


if __name__ == "__main__":
    # Demonstrate the visual table
    print(visualize_logic_table())
    print("\n" + "=" * 60 + "\n")

    # Test examples
    test_cases = [
        ("SPO", 4, "GEO"),
        ("SPATIAL", 1, "GEO"),
        ("SPATIAL", 2, "CAR"),
        ("SCIENCE", 0, "CAR"),
        ("COLLECTION", 0, "CAR"),
    ]

    print("Testing Truth Table Lookup:")
    for source, points, coord in test_cases:
        result = lookup_geometry_output(source, points, coord)
        print(f"  {source:10} pts={points} {coord:3} → {result.name}")

    print("\nTesting Boolean Logic:")
    for source, points, coord in test_cases:
        result = geometry_boolean_logic(source, points, coord)
        print(f"  {source:10} pts={points} {coord:3} → {result.name}")
