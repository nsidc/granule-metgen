# MetGenC Pipeline Refactoring - Code Examples

This document contains the detailed code examples and technical implementations for the MetGenC pipeline refactoring plan.

NOTE: This was generated with the help of an AI coding assistant. Do not use this as-is without inspecting it carefully.

## Table of Contents

- [Phase 1: CMR Reader Extraction](#phase-1-cmr-reader-extraction)
- [Phase 2: Geometry Specification Extraction](#phase-2-geometry-specification-extraction)
- [Phase 3: Temporal Specification Extraction](#phase-3-temporal-specification-extraction)
- [Phase 4: Pipeline State Architecture](#phase-4-pipeline-state-architecture)
- [Phase 5: Reader Interface Definition](#phase-5-reader-interface-definition)
- [Phase 6: Custom Reader Implementation](#phase-6-custom-reader-implementation)
- [Phase 7: Existing Reader Adaptation](#phase-7-existing-reader-adaptation)
- [Phase 8: Specify/Execute Separation](#phase-8-specifyexecute-separation)
- [Configuration Examples](#configuration-examples)

## Phase 1: CMR Reader Extraction

Extract CMR reader from utilities into a standalone module that runs after configuration but before any pipeline processing.

```python
from dataclasses import dataclass
from typing import Optional, Dict, Any
from datetime import datetime

@dataclass(frozen=True)
class CMRMetadata:
    """Immutable container for collection metadata from CMR"""
    collection_id: str
    granule_spatial_representation: str
    temporal_extent_type: str
    processing_level: str
    platform: str
    instrument: str
    bounding_box: Optional[Dict[str, float]]
    temporal_extent: Optional[Dict[str, datetime]]
    additional_attributes: Dict[str, Any]

class CMRReader:
    """Reads collection metadata from NASA's Common Metadata Repository"""

    def __init__(self, cmr_url: str = "https://cmr.earthdata.nasa.gov"):
        self.cmr_url = cmr_url
        self._cache = {}

    def read_collection(self, collection_id: str, environment: str = "prod") -> CMRMetadata:
        """Read collection metadata from CMR with caching"""
        cache_key = f"{collection_id}:{environment}"

        if cache_key in self._cache:
            return self._cache[cache_key]

        # Fetch from CMR
        metadata = self._fetch_from_cmr(collection_id, environment)

        # Cache result
        self._cache[cache_key] = metadata

        return metadata

    def _fetch_from_cmr(self, collection_id: str, environment: str) -> CMRMetadata:
        """Fetch collection metadata from CMR API"""
        # Implementation details for CMR API call
        # This is extracted from existing CMR utility code
        pass

class MockCMRReader(CMRReader):
    """Mock CMR reader for testing"""

    def __init__(self, mock_data: Dict[str, CMRMetadata]):
        super().__init__()
        self.mock_data = mock_data

    def read_collection(self, collection_id: str, environment: str = "prod") -> CMRMetadata:
        """Return mock data instead of calling CMR"""
        key = f"{collection_id}:{environment}"
        if key in self.mock_data:
            return self.mock_data[key]
        raise ValueError(f"No mock data for {collection_id} in {environment}")
```

## Phase 2: Geometry Specification Extraction

Extract geometry decision-making logic into a specification that captures WHAT geometry to create and WHERE to get it from.

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, List
from pathlib import Path

class GeometrySource(Enum):
    """Where to get geometry data from"""
    GRANULE_METADATA = "granule_metadata"
    SPATIAL_FILE = "spatial_file"
    COLLECTION = "collection"
    NONE = "none"

class GeometryType(Enum):
    """What type of geometry to create"""
    POINT = "point"
    POLYGON = "polygon"
    BOUNDING_BOX = "bounding_box"
    NONE = "none"

@dataclass(frozen=True)
class GeometrySpec:
    """Specification for geometry decisions - WHAT and WHERE, not HOW"""
    source: GeometrySource
    type: GeometryType
    representation: str  # GEODETIC or CARTESIAN
    
    # Additional context for the decision
    source_file_path: Optional[Path] = None
    fallback_source: Optional[GeometrySource] = None
    validation_required: bool = True
    
    # Collection-specific settings
    use_collection_bbox: bool = False
    collection_bbox: Optional[Dict[str, float]] = None

def determine_geometry_spec(config: Dict[str, Any], 
                          collection: CMRMetadata,
                          available_files: Dict[str, Path]) -> GeometrySpec:
    """
    Determine WHAT geometry to create and WHERE to get it from.
    This function contains all the business rules for geometry decisions.
    """
    # Rule 1: Check if geometry is disabled
    if config.get("skip_geometry", False):
        return GeometrySpec(
            source=GeometrySource.NONE,
            type=GeometryType.NONE,
            representation="GEODETIC"
        )
    
    # Rule 2: Check collection override
    if config.get("collection_geometry_override", False):
        if not collection.bounding_box:
            raise ValueError("Collection geometry override requested but no bbox available")
        
        return GeometrySpec(
            source=GeometrySource.COLLECTION,
            type=GeometryType.BOUNDING_BOX,
            representation="CARTESIAN",
            use_collection_bbox=True,
            collection_bbox=collection.bounding_box
        )
    
    # Rule 3: Determine source priority
    # Priority: spatial file > granule metadata > collection
    spatial_file = available_files.get("spatial")
    
    if spatial_file and spatial_file.exists():
        # We have a spatial file
        geometry_type = _determine_geometry_type_from_file(spatial_file, collection)
        return GeometrySpec(
            source=GeometrySource.SPATIAL_FILE,
            type=geometry_type,
            representation=collection.granule_spatial_representation,
            source_file_path=spatial_file
        )
    
    # Rule 4: Fall back to granule metadata
    # The geometry type depends on the collection's spatial representation
    geometry_type = _map_representation_to_type(collection.granule_spatial_representation)
    
    return GeometrySpec(
        source=GeometrySource.GRANULE_METADATA,
        type=geometry_type,
        representation=collection.granule_spatial_representation,
        fallback_source=GeometrySource.COLLECTION if collection.bounding_box else None
    )

def _determine_geometry_type_from_file(spatial_file: Path, 
                                     collection: CMRMetadata) -> GeometryType:
    """Determine geometry type based on spatial file contents"""
    # This would inspect the file to determine if it contains
    # point, polygon, or other geometry data
    # For now, use collection hint
    gsr = collection.granule_spatial_representation.upper()
    
    if gsr == "GEODETIC":
        return GeometryType.POLYGON
    elif gsr == "CARTESIAN":
        return GeometryType.BOUNDING_BOX
    else:
        return GeometryType.POINT

def _map_representation_to_type(representation: str) -> GeometryType:
    """Map spatial representation to default geometry type"""
    mapping = {
        "GEODETIC": GeometryType.POLYGON,
        "CARTESIAN": GeometryType.BOUNDING_BOX,
        "POINT": GeometryType.POINT,
    }
    return mapping.get(representation.upper(), GeometryType.POINT)
```

## Phase 3: Temporal Specification Extraction

Extract temporal decision-making logic into a specification that captures WHAT temporal type to create and WHERE to get it from.

```python
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Dict, Any, List
from pathlib import Path

class TemporalSource(Enum):
    """Where to get temporal data from"""
    GRANULE_METADATA = "granule_metadata"
    PREMET_FILE = "premet_file"
    COLLECTION = "collection"
    FILENAME_PATTERN = "filename_pattern"
    NONE = "none"

class TemporalType(Enum):
    """What type of temporal to create"""
    SINGLE_DATETIME = "single_datetime"
    RANGE_DATETIME = "range_datetime"
    NONE = "none"

@dataclass(frozen=True)
class TemporalSpec:
    """Specification for temporal decisions - WHAT and WHERE, not HOW"""
    source: TemporalSource
    type: TemporalType
    
    # Additional context for the decision
    source_file_path: Optional[Path] = None
    filename_pattern: Optional[str] = None
    fallback_source: Optional[TemporalSource] = None
    
    # Collection temporal override settings
    use_collection_temporal: bool = False
    collection_temporal: Optional[Dict[str, Any]] = None
    
    # Validation rules
    require_complete_range: bool = True
    allow_future_dates: bool = False

def determine_temporal_spec(config: Dict[str, Any],
                          collection: CMRMetadata,
                          available_files: Dict[str, Path],
                          granule_id: str) -> TemporalSpec:
    """
    Determine WHAT temporal type to create and WHERE to get it from.
    This function contains all the business rules for temporal decisions.
    """
    # Rule 1: Check if temporal is disabled
    if config.get("skip_temporal", False):
        return TemporalSpec(
            source=TemporalSource.NONE,
            type=TemporalType.NONE
        )
    
    # Rule 2: Check collection temporal override
    if config.get("collection_temporal_override", False):
        if not collection.temporal_extent:
            raise ValueError("Collection temporal override requested but no temporal extent available")
        
        # Validate collection temporal
        if collection.temporal_extent_error:
            raise ValueError(f"Collection temporal error: {collection.temporal_extent_error}")
        
        return TemporalSpec(
            source=TemporalSource.COLLECTION,
            type=_determine_temporal_type_from_collection(collection),
            use_collection_temporal=True,
            collection_temporal=collection.temporal_extent
        )
    
    # Rule 3: Determine source priority
    # Priority: premet file > granule metadata > filename pattern > collection
    premet_file = available_files.get("premet")
    
    if premet_file and premet_file.exists():
        # We have a premet file with temporal info
        return TemporalSpec(
            source=TemporalSource.PREMET_FILE,
            type=TemporalType.RANGE_DATETIME,  # Premet typically has ranges
            source_file_path=premet_file
        )
    
    # Rule 4: Check if we can extract from filename
    if config.get("temporal_from_filename"):
        pattern = config.get("temporal_filename_pattern")
        if pattern and _can_extract_from_filename(granule_id, pattern):
            return TemporalSpec(
                source=TemporalSource.FILENAME_PATTERN,
                type=TemporalType.SINGLE_DATETIME,
                filename_pattern=pattern
            )
    
    # Rule 5: Default to granule metadata
    # Determine if we expect single or range based on collection
    temporal_type = _determine_expected_temporal_type(collection, config)
    
    return TemporalSpec(
        source=TemporalSource.GRANULE_METADATA,
        type=temporal_type,
        fallback_source=TemporalSource.COLLECTION if collection.temporal_extent else None
    )

def _determine_temporal_type_from_collection(collection: CMRMetadata) -> TemporalType:
    """Determine temporal type from collection temporal extent"""
    if not collection.temporal_extent:
        return TemporalType.NONE
    
    # Check if it's a range or single value
    extent = collection.temporal_extent[0]  # First extent
    if "BeginningDateTime" in extent and "EndingDateTime" in extent:
        return TemporalType.RANGE_DATETIME
    else:
        return TemporalType.SINGLE_DATETIME

def _can_extract_from_filename(filename: str, pattern: str) -> bool:
    """Check if temporal can be extracted from filename"""
    import re
    return bool(re.search(pattern, filename))

def _determine_expected_temporal_type(collection: CMRMetadata, 
                                    config: Dict[str, Any]) -> TemporalType:
    """Determine expected temporal type based on collection and config"""
    # Check explicit configuration
    if config.get("temporal_type"):
        return TemporalType(config["temporal_type"])
    
    # Use collection hints
    if collection.temporal_extent_type:
        if "range" in collection.temporal_extent_type.lower():
            return TemporalType.RANGE_DATETIME
    
    # Default
    return TemporalType.SINGLE_DATETIME
```

## Phase 4: Pipeline State Architecture

Create immutable pipeline state that threads through all operations.

```python
from dataclasses import dataclass, replace, field
from typing import Tuple, Any, Optional

@dataclass(frozen=True)
class ProcessingEvent:
    """Base class for processing events"""
    timestamp: datetime
    event_type: str
    details: Dict[str, Any]

@dataclass(frozen=True)
class ProcessingError:
    """Error that occurred during processing"""
    timestamp: datetime
    error_type: str
    message: str
    granule_id: Optional[str] = None

@dataclass(frozen=True)
class PipelineState:
    """Immutable state threaded through pipeline stages"""
    configuration: Dict[str, Any]
    cmr_metadata: CMRMetadata
    geometry_spec: GeometrySpec
    temporal_spec: TemporalSpec
    reader_registry: Optional['ReaderRegistry'] = None  # Added in Phase 5
    processing_ledger: Tuple[ProcessingEvent, ...] = field(default_factory=tuple)
    error_accumulator: Tuple[ProcessingError, ...] = field(default_factory=tuple)

    def with_ledger_entry(self, event: ProcessingEvent) -> 'PipelineState':
        """Return new state with added ledger entry"""
        return replace(self, processing_ledger=self.processing_ledger + (event,))

    def with_error(self, error: ProcessingError) -> 'PipelineState':
        """Return new state with added error"""
        return replace(self, error_accumulator=self.error_accumulator + (error,))

    def with_reader_registry(self, registry: 'ReaderRegistry') -> 'PipelineState':
        """Return new state with reader registry"""
        return replace(self, reader_registry=registry)

@dataclass(frozen=True)
class PipelineResult:
    """Result of a pipeline stage with new state"""
    value: Any
    state: PipelineState

class Pipeline:
    """Main pipeline class that uses immutable state"""

    def __init__(self, config_path: str):
        self.config_path = config_path

    def initialize(self) -> PipelineState:
        """Initialize pipeline state"""
        # Read configuration
        config = self._read_configuration(self.config_path)

        # Extract CMR reader and get metadata
        cmr_reader = CMRReader()
        cmr_metadata = cmr_reader.read_collection(
            config["collection_id"],
            config.get("environment", "prod")
        )

        # Determine specifications (decisions about WHAT and WHERE)
        available_files = self._discover_available_files(config["data_dir"])
        
        geometry_spec = determine_geometry_spec(config, cmr_metadata, available_files)
        temporal_spec = determine_temporal_spec(config, cmr_metadata, available_files, "")

        # Create initial state
        return PipelineState(
            configuration=config,
            cmr_metadata=cmr_metadata,
            geometry_spec=geometry_spec,
            temporal_spec=temporal_spec
        )

    def process_granule(self, granule_path: str, state: PipelineState) -> PipelineResult:
        """Process a single granule with state threading"""
        # Each action returns a new state
        result = self._discover_files(granule_path, state)
        if not result.value:
            return result

        result = self._read_metadata(result.value, result.state)
        if not result.value:
            return result

        result = self._process_metadata(result.value, result.state)
        return result
```

## Phase 5: Reader Interface Definition

Define granular reader interfaces for different metadata types.

```python
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class TemporalReader(ABC):
    """Interface for reading temporal metadata"""

    @abstractmethod
    def can_read(self, file_path: str) -> bool:
        """Check if this reader can handle the file"""
        pass

    @abstractmethod
    def extract_temporal(self, file_path: str,
                        configuration: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract temporal metadata from file"""
        pass

class SpatialReader(ABC):
    """Interface for reading spatial metadata"""

    @abstractmethod
    def can_read(self, file_path: str) -> bool:
        """Check if this reader can handle the file"""
        pass

    @abstractmethod
    def extract_spatial(self, file_path: str,
                       configuration: Dict[str, Any],
                       gsr: str) -> List[Dict[str, float]]:
        """Extract spatial metadata from file"""
        pass

class AttributeReader(ABC):
    """Interface for reading general metadata/attributes"""

    @abstractmethod
    def can_read(self, file_path: str) -> bool:
        """Check if this reader can handle the file"""
        pass

    @abstractmethod
    def extract_attributes(self, file_path: str,
                          configuration: Dict[str, Any]) -> Dict[str, Any]:
        """Extract additional attributes from file"""
        pass

class ReaderRegistry:
    """Registry for managing and selecting readers"""

    def __init__(self):
        self.temporal_readers: List[TemporalReader] = []
        self.spatial_readers: List[SpatialReader] = []
        self.attribute_readers: List[AttributeReader] = []

    def register_temporal(self, reader: TemporalReader) -> None:
        """Register a temporal reader"""
        self.temporal_readers.append(reader)

    def register_spatial(self, reader: SpatialReader) -> None:
        """Register a spatial reader"""
        self.spatial_readers.append(reader)

    def register_attribute(self, reader: AttributeReader) -> None:
        """Register an attribute reader"""
        self.attribute_readers.append(reader)

    def get_temporal_reader(self, file_path: str) -> Optional[TemporalReader]:
        """Get appropriate temporal reader for file"""
        for reader in self.temporal_readers:
            if reader.can_read(file_path):
                return reader
        return None

    def get_spatial_reader(self, file_path: str) -> Optional[SpatialReader]:
        """Get appropriate spatial reader for file"""
        for reader in self.spatial_readers:
            if reader.can_read(file_path):
                return reader
        return None

    def get_attribute_reader(self, file_path: str) -> Optional[AttributeReader]:
        """Get appropriate attribute reader for file"""
        for reader in self.attribute_readers:
            if reader.can_read(file_path):
                return reader
        return None
```

## Phase 6: Custom Reader Implementation

Implement custom readers that allow users to extend MetGenC.

```python
import subprocess
import json
import shlex
import time
from pathlib import Path
import fnmatch

@dataclass(frozen=True)
class CustomReaderConfig:
    """Configuration for a custom reader"""
    file_pattern: str
    command: str
    metadata_type: str  # "temporal", "spatial", or "attributes"

@dataclass(frozen=True)
class CustomReaderResult:
    """Result from custom reader execution"""
    metadata: Dict[str, Any]
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float

class CustomReader:
    """Base class for executing custom readers"""

    def __init__(self, config: CustomReaderConfig):
        self.config = config

    def execute_command(self, file_path: Path) -> CustomReaderResult:
        """Execute custom reader command and parse output"""
        cmd = self.config.command.replace('{}', str(file_path))
        start_time = time.time()

        try:
            # Execute with 120 second timeout
            result = subprocess.run(
                shlex.split(cmd),
                capture_output=True,
                text=True,
                timeout=120
            )

            # Parse JSON output
            metadata = json.loads(result.stdout) if result.stdout else {}

            return CustomReaderResult(
                metadata=metadata,
                stdout=result.stdout,
                stderr=result.stderr,
                exit_code=result.returncode,
                execution_time=time.time() - start_time
            )
        except subprocess.TimeoutExpired:
            return CustomReaderResult(
                metadata={},
                stdout="",
                stderr="Custom reader timed out after 120 seconds",
                exit_code=-1,
                execution_time=120.0
            )
        except json.JSONDecodeError as e:
            return CustomReaderResult(
                metadata={},
                stdout=result.stdout,
                stderr=f"Invalid JSON output: {str(e)}",
                exit_code=-2,
                execution_time=time.time() - start_time
            )

class CustomTemporalReader(TemporalReader):
    """Custom reader for temporal metadata"""

    def __init__(self, config: CustomReaderConfig):
        self.config = config
        self.reader = CustomReader(config)

    def can_read(self, file_path: str) -> bool:
        """Check if file matches pattern"""
        return fnmatch.fnmatch(Path(file_path).name, self.config.file_pattern)

    def extract_temporal(self, file_path: str,
                        configuration: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract temporal metadata using custom command"""
        result = self.reader.execute_command(Path(file_path))

        if result.exit_code != 0:
            raise RuntimeError(f"Custom temporal reader failed: {result.stderr}")

        # Handle both list and dict with 'temporal' key
        if isinstance(result.metadata, list):
            return result.metadata
        elif 'temporal' in result.metadata:
            return result.metadata['temporal']
        else:
            raise ValueError("Custom reader output must contain temporal data")

class CustomSpatialReader(SpatialReader):
    """Custom reader for spatial metadata"""

    def __init__(self, config: CustomReaderConfig):
        self.config = config
        self.reader = CustomReader(config)

    def can_read(self, file_path: str) -> bool:
        """Check if file matches pattern"""
        return fnmatch.fnmatch(Path(file_path).name, self.config.file_pattern)

    def extract_spatial(self, file_path: str,
                       configuration: Dict[str, Any],
                       gsr: str) -> List[Dict[str, float]]:
        """Extract spatial metadata using custom command"""
        result = self.reader.execute_command(Path(file_path))

        if result.exit_code != 0:
            raise RuntimeError(f"Custom spatial reader failed: {result.stderr}")

        # Handle various output formats
        if isinstance(result.metadata, list):
            return result.metadata
        elif 'spatial' in result.metadata:
            return result.metadata['spatial']
        elif 'geometry' in result.metadata:
            return result.metadata['geometry']
        else:
            raise ValueError("Custom reader output must contain spatial data")

class CustomAttributeReader(AttributeReader):
    """Custom reader for additional attributes"""

    def __init__(self, config: CustomReaderConfig):
        self.config = config
        self.reader = CustomReader(config)

    def can_read(self, file_path: str) -> bool:
        """Check if file matches pattern"""
        return fnmatch.fnmatch(Path(file_path).name, self.config.file_pattern)

    def extract_attributes(self, file_path: str,
                          configuration: Dict[str, Any]) -> Dict[str, Any]:
        """Extract attributes using custom command"""
        result = self.reader.execute_command(Path(file_path))

        if result.exit_code != 0:
            raise RuntimeError(f"Custom attribute reader failed: {result.stderr}")

        # Handle dict or nested attributes
        if 'attributes' in result.metadata:
            return result.metadata['attributes']
        elif isinstance(result.metadata, dict):
            return result.metadata
        else:
            raise ValueError("Custom reader output must contain attribute data")
```

### Custom Reader Protocol

Custom readers must follow this protocol:

1. Accept a file path as the first argument (replaced in `{}`)
2. Write metadata to stdout in JSON format
3. Write errors/warnings to stderr
4. Return 0 on success, non-zero on failure
5. Complete within 120 seconds

Expected JSON output formats:

**Temporal readers** (`data.bin.temporal`):
```json
[
    {
        "start_datetime": "2024-01-01T00:00:00Z",
        "end_datetime": "2024-01-01T23:59:59Z"
    }
]
```

**Spatial readers** (`data.bin.spatial`):
```json
[
    {"Longitude": -105.0, "Latitude": 40.0},
    {"Longitude": -104.0, "Latitude": 40.0},
    {"Longitude": -104.0, "Latitude": 39.0},
    {"Longitude": -105.0, "Latitude": 39.0}
]
```

**Attribute readers** (`data.bin.attributes`):
```json
{
    "instrument": "CustomSensor",
    "processing_level": "L2",
    "version": "1.0"
}
```

## Phase 7: Existing Reader Adaptation

Adapt existing readers to implement the new granular interfaces.

```python
# Example of adapting NetCDF reader to new interfaces

class NetCDFTemporalReader(TemporalReader):
    """NetCDF reader for temporal metadata"""

    def can_read(self, file_path: str) -> bool:
        """Check if file is NetCDF"""
        return file_path.endswith(('.nc', '.nc4', '.netcdf'))

    def extract_temporal(self, file_path: str,
                        configuration: Dict[str, Any]) -> List[Dict[str, str]]:
        """Extract temporal metadata from NetCDF"""
        # Extracted from existing NetCDFReader.extract_temporal_metadata
        import xarray as xr

        with xr.open_dataset(file_path) as ds:
            # Logic extracted from existing reader
            time_var = configuration.get('time_variable', 'time')
            if time_var in ds:
                times = ds[time_var].values
                # Convert to standard format
                return [{
                    "start_datetime": str(times[0]),
                    "end_datetime": str(times[-1])
                }]
        return []

class NetCDFSpatialReader(SpatialReader):
    """NetCDF reader for spatial metadata"""

    def can_read(self, file_path: str) -> bool:
        """Check if file is NetCDF"""
        return file_path.endswith(('.nc', '.nc4', '.netcdf'))

    def extract_spatial(self, file_path: str,
                       configuration: Dict[str, Any],
                       gsr: str) -> List[Dict[str, float]]:
        """Extract spatial metadata from NetCDF"""
        # Extracted from existing NetCDFReader.extract_spatial_metadata
        import xarray as xr

        with xr.open_dataset(file_path) as ds:
            lat_var = configuration.get('latitude_variable', 'latitude')
            lon_var = configuration.get('longitude_variable', 'longitude')

            if lat_var in ds and lon_var in ds:
                lats = ds[lat_var].values
                lons = ds[lon_var].values

                # Return points or bounds based on GSR
                if gsr == "POINT":
                    return [{"Latitude": float(lats[0]),
                            "Longitude": float(lons[0])}]
                else:
                    # Return bounding box corners
                    return [
                        {"Latitude": float(lats.min()), "Longitude": float(lons.min())},
                        {"Latitude": float(lats.min()), "Longitude": float(lons.max())},
                        {"Latitude": float(lats.max()), "Longitude": float(lons.max())},
                        {"Latitude": float(lats.max()), "Longitude": float(lons.min())}
                    ]
        return []

class NetCDFAttributeReader(AttributeReader):
    """NetCDF reader for additional attributes"""

    def can_read(self, file_path: str) -> bool:
        """Check if file is NetCDF"""
        return file_path.endswith(('.nc', '.nc4', '.netcdf'))

    def extract_attributes(self, file_path: str,
                          configuration: Dict[str, Any]) -> Dict[str, Any]:
        """Extract attributes from NetCDF"""
        # Extracted from existing NetCDFReader
        import xarray as xr

        with xr.open_dataset(file_path) as ds:
            # Extract global attributes
            attrs = dict(ds.attrs)

            # Add configured variable attributes
            for var_name in configuration.get('attribute_variables', []):
                if var_name in ds:
                    attrs[var_name] = ds[var_name].values.tolist()

            return attrs

# Similar adaptations for CSVReader and SnowExReader...
```

## Phase 8: Specify/Execute Separation

Separate the specification of side effects from their execution.

```python
# Side-effect specifications (data, not execution)
@dataclass(frozen=True)
class SideEffect:
    """Base class for side-effect specifications"""
    granule_id: str

@dataclass(frozen=True)
class CreateUMMG(SideEffect):
    """Specification to create UMM-G JSON"""
    metadata: Dict[str, Any]
    template_path: str

@dataclass(frozen=True)
class CreateCNM(SideEffect):
    """Specification to create CNM JSON"""
    metadata: Dict[str, Any]
    template_path: str

@dataclass(frozen=True)
class WriteFile(SideEffect):
    """Specification to write a file"""
    path: Path
    content: str

@dataclass(frozen=True)
class S3Upload(SideEffect):
    """Specification to upload to S3"""
    local_path: Path
    s3_key: str
    bucket: str

@dataclass(frozen=True)
class SendMessage(SideEffect):
    """Specification to send Kinesis message"""
    stream_name: str
    message: str

# Modified pipeline to collect specifications
class PurePipeline:
    """Pipeline that returns specifications instead of executing"""

    def process_granule(self, granule_path: str,
                       state: PipelineState) -> Tuple[List[SideEffect], PipelineState]:
        """Process granule and return side effect specifications"""
        # Process metadata (pure)
        metadata_result = self._extract_and_process_metadata(granule_path, state)
        if not metadata_result.value:
            return [], metadata_result.state

        metadata = metadata_result.value
        state = metadata_result.state

        # Specify side effects (don't execute)
        effects = []

        # Always create UMM-G
        effects.append(CreateUMMG(
            granule_id=metadata["granule_id"],
            metadata=metadata,
            template_path=state.configuration["ummg_template"]
        ))

        # Conditionally add other effects
        if state.configuration.get("create_cnm"):
            effects.append(CreateCNM(
                granule_id=metadata["granule_id"],
                metadata=metadata,
                template_path=state.configuration["cnm_template"]
            ))

        if state.configuration.get("write_local"):
            output_path = Path(state.configuration["output_dir"]) / f"{metadata['granule_id']}.json"
            effects.append(WriteFile(
                granule_id=metadata["granule_id"],
                path=output_path,
                content=""  # Will be filled during execution
            ))

        # Log specifications
        state = state.with_ledger_entry(ProcessingEvent(
            timestamp=datetime.now(),
            event_type="specifications_created",
            details={"granule_id": metadata["granule_id"],
                    "effect_count": len(effects)}
        ))

        return effects, state

# Side effect executor
class SideEffectExecutor:
    """Executes side effects with optimization"""

    def execute_all(self, effects: List[SideEffect],
                   state: PipelineState) -> PipelineState:
        """Execute all side effects with appropriate strategy"""
        # Analyze effects to determine execution strategy
        strategy = self._determine_strategy(effects)

        if strategy == "parallel_by_type":
            return self._execute_parallel_by_type(effects, state)
        elif strategy == "batch_s3":
            return self._execute_batch_s3(effects, state)
        else:
            return self._execute_sequential(effects, state)

    def _execute_sequential(self, effects: List[SideEffect],
                           state: PipelineState) -> PipelineState:
        """Execute effects one by one"""
        for effect in effects:
            try:
                if isinstance(effect, CreateUMMG):
                    content = self._render_ummg(effect.metadata, effect.template_path)
                    # Store for later effects
                    self._content_cache[effect.granule_id] = content

                elif isinstance(effect, WriteFile):
                    content = self._content_cache.get(effect.granule_id, effect.content)
                    effect.path.write_text(content)

                elif isinstance(effect, S3Upload):
                    self._upload_to_s3(effect.local_path, effect.bucket, effect.s3_key)

                # Log success
                state = state.with_ledger_entry(ProcessingEvent(
                    timestamp=datetime.now(),
                    event_type="effect_executed",
                    details={"effect_type": type(effect).__name__,
                            "granule_id": effect.granule_id}
                ))

            except Exception as e:
                # Log error but continue
                state = state.with_error(ProcessingError(
                    timestamp=datetime.now(),
                    error_type="execution_error",
                    message=str(e),
                    granule_id=effect.granule_id
                ))

        return state

# Main orchestrator with two phases
def main_pipeline(config_path: str, input_paths: List[str]):
    """Main pipeline with specification and execution phases"""
    # Initialize
    pipeline = PurePipeline()
    initial_state = pipeline.initialize_state(config_path)

    # Phase 1: Collect all specifications
    all_effects = []
    current_state = initial_state

    for granule_path in discover_granules(input_paths):
        effects, new_state = pipeline.process_granule(granule_path, current_state)
        all_effects.extend(effects)
        current_state = new_state

    # Phase 2: Execute all side effects
    executor = SideEffectExecutor()
    final_state = executor.execute_all(all_effects, current_state)

    # Generate report
    generate_report(final_state)
```

## Configuration Examples

### Configuration-Driven Reader Selection

```ini
[readers]
# Option 1: Auto-detection (default)
temporal_reader = auto
spatial_reader = auto
attribute_reader = auto

# Option 2: Specify reader types
temporal_reader = netcdf_time_dimension
spatial_reader = csv_point_columns
attribute_reader = netcdf_global_attrs

# Option 3: Chain multiple readers (first successful wins)
temporal_readers = filename_pattern,netcdf_time_var,csv_date_column

# Option 4: File-specific reader configuration
data.nc.temporal_reader = netcdf_time_dimension
data.nc.spatial_reader = netcdf_coordinate_vars
data.csv.temporal_reader = csv_date_time_columns
data.csv.spatial_reader = csv_lat_lon_columns

# Option 5: Disable specific metadata extraction
spatial_reader = none  # Skip spatial extraction
```

### Custom Reader Configuration

```ini
[custom_readers]
# Define custom readers using the same granular pattern as built-in readers
# Format: filename.extension.metadata_type = command

# Example 1: Binary file with separate readers for each metadata type
data.bin.temporal = /usr/local/bin/binary_temporal_extractor {}
data.bin.spatial = /usr/local/bin/binary_spatial_extractor {}
data.bin.attributes = python /opt/readers/binary_attributes.py {}

# Example 2: HDF5 file using h5dump for different datasets
data.hdf5.temporal = h5dump -d /time/dataset {} | python /opt/parsers/h5_time_parser.py
data.hdf5.spatial = h5dump -d /geolocation/dataset {} | python /opt/parsers/h5_geo_parser.py
data.hdf5.attributes = h5dump -H {} | python /opt/parsers/h5_attrs_parser.py

# Note: Custom readers have a default timeout of 120 seconds
```

### Loading Custom Readers

```python
def load_custom_readers(config: Dict[str, Any],
                       registry: ReaderRegistry) -> None:
    """Load custom readers from configuration"""
    custom_readers = config.get('custom_readers', {})

    for key, command in custom_readers.items():
        # Parse key: filename.extension.metadata_type
        parts = key.split('.')
        if len(parts) < 3:
            continue

        metadata_type = parts[-1]
        file_pattern = '.'.join(parts[:-1])

        reader_config = CustomReaderConfig(
            file_pattern=file_pattern,
            command=command,
            metadata_type=metadata_type
        )

        # Register appropriate reader type
        if metadata_type == 'temporal':
            registry.register_temporal(CustomTemporalReader(reader_config))
        elif metadata_type == 'spatial':
            registry.register_spatial(CustomSpatialReader(reader_config))
        elif metadata_type == 'attributes':
            registry.register_attribute(CustomAttributeReader(reader_config))
```
