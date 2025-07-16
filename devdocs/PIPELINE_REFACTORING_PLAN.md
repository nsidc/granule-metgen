# MetGenC Pipeline Refactoring Plan

## Overview

This document outlines a plan to incrementally refactor the MetGenC pipeline to separate decision-making from execution, implement immutable data structures, and disentangle reading/writing from processing components.

## Current Pipeline Issues

The current pipeline has several architectural characteristics:

1. **Mixed concerns**: Decision-making and execution are intertwined throughout the operations
2. **Embedded I/O**: Reading and writing occur within pipeline operations rather than at boundaries
3. **Mutable state**: The `Granule` dataclass is modified throughout the pipeline
4. **Tight coupling**: Components depend heavily on each other and configuration state

## Key Benefit Goals

1. **Separation of Concerns**: Decision-making is isolated from execution
2. **Immutable Data**: All data structures are immutable, preventing side effects
3. **Testability**: Each phase can be tested independently with predictable inputs/outputs
4. **Maintainability**: Clear boundaries between reading, processing, building, and writing
5. **Flexibility**: New readers, processors, or outputs can be added without affecting other phases
6. **Error Handling**: Failures are contained within phases and can be handled appropriately

## Success Criteria

- [ ] All I/O operations occur only at pipeline boundaries
- [ ] Decision-making is separated from execution
- [ ] All data structures are immutable
- [ ] Each pipeline phase can be tested independently
- [ ] Existing functionality is preserved
- [ ] Performance is maintained or improved
- [ ] Code coverage remains above 90%

## Risk Mitigation

1. **Feature Flags**: Toggle between old/new implementations -- either through CLI or .INI
2. **Gradual Migration**: One component / feature at a time
3. **Comprehensive Testing**: Test each change thoroughly
4. **Performance Monitoring**: Track pipeline performance throughout migration

This refactoring plan ensures the pipeline becomes more maintainable, testable, and extensible while minimizing risk through incremental changes that preserve existing functionality.

## New Pipeline Architecture

### Pipeline Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    DECISION PHASE                               │
├─────────────────────────────────────────────────────────────────┤
│ 1. Configuration Analysis                                       │
│    └─ Parse config → Determine processing strategy              │
│                                                                 │
│ 2. File Discovery & Grouping                                   │
│    └─ Scan directories → Group related files                   │
│                                                                 │
│ 3. Reader Selection                                             │
│    └─ Analyze file types → Select appropriate readers          │
│                                                                 │
│ 4. Geometry Strategy                                            │
│    └─ Analyze spatial config → Choose geometry approach        │
│                                                                 │
│ 5. Template Selection                                           │
│    └─ Based on outputs → Select UMM-G/CNM templates           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                     READING PHASE                              │
├─────────────────────────────────────────────────────────────────┤
│ 1. Collection Metadata Reader                                  │
│    └─ CMR API → Collection info                                │
│                                                                 │
│ 2. Premet File Reader                                          │
│    └─ Parse premet files → Temporal/additional attributes      │
│                                                                 │
│ 3. Spatial File Reader                                         │
│    └─ Parse spatial/spo files → Coordinate data               │
│                                                                 │
│ 4. Science Data Reader                                         │
│    └─ Extract metadata from NetCDF/CSV → Temporal/spatial     │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   PROCESSING PHASE                             │
├─────────────────────────────────────────────────────────────────┤
│ 1. Temporal Processor                                          │
│    └─ Merge temporal data → Normalized temporal extent         │
│                                                                 │
│ 2. Spatial Processor                                           │
│    └─ Process coordinates → Geometry (point/bbox/polygon)      │
│                                                                 │
│ 3. Metadata Merger                                             │
│    └─ Combine all sources → Complete granule metadata          │
│                                                                 │
│ 4. Validation Processor                                        │
│    └─ Validate against schemas → Validated metadata            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    BUILDING PHASE                              │
├─────────────────────────────────────────────────────────────────┤
│ 1. UMM-G Builder                                               │
│    └─ Apply templates → UMM-G JSON                            │
│                                                                 │
│ 2. CNM Builder                                                 │
│    └─ Apply templates → CNM JSON                              │
│                                                                 │
│ 3. Output Organizer                                           │
│    └─ Prepare file operations → File operation list            │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    WRITING PHASE                               │
├─────────────────────────────────────────────────────────────────┤
│ 1. Local File Writer                                           │
│    └─ Write UMM-G/CNM files → Local filesystem                │
│                                                                 │
│ 2. AWS Stager                                                  │
│    └─ Upload files → S3 staging area                          │
│                                                                 │
│ 3. Notification Publisher                                      │
│    └─ Send CNM messages → Kinesis stream                      │
└─────────────────────────────────────────────────────────────────┘
```

### Core Data Structures (Immutable)

```python
@dataclass(frozen=True)
class ProcessingDecisions:
    reader_strategy: ReaderStrategy
    geometry_strategy: GeometryStrategy
    template_strategy: TemplateStrategy
    output_strategy: OutputStrategy

@dataclass(frozen=True)
class SourceData:
    collection_metadata: CollectionMetadata
    premet_data: Optional[PremetData]
    spatial_data: Optional[SpatialData]
    science_metadata: ScienceMetadata

@dataclass(frozen=True)
class ProcessedMetadata:
    temporal_extent: TemporalExtent
    spatial_extent: SpatialExtent
    additional_attributes: dict
    file_metadata: dict

@dataclass(frozen=True)
class BuildOutputs:
    ummg_content: str
    cnm_content: str
    file_operations: List[FileOperation]
```

## User Stories with Behavioral Acceptance Tests

### Story 1: Data Reading Isolation
**As a** MetGenC developer, **I can** process science data files through dedicated readers that only handle data extraction, **so that** I/O operations are isolated from business logic and data sources can be easily mocked for testing.

**Acceptance Tests:**
- Given a NetCDF file with temporal metadata, when I use the science data reader, then I receive immutable ScienceMetadata without any file system side effects
- Given CMR API credentials, when I use the collection metadata reader, then I receive immutable CollectionMetadata without coupling to pipeline operations
- Given premet and spatial files, when I use their respective readers, then I receive immutable PremetData and SpatialData independently of other pipeline components

### Story 2: Decision Making Separation
**As a** MetGenC maintainer, **I can** analyze configuration requirements in a dedicated decision phase, **so that** processing strategies are determined upfront and execution logic is decoupled from decision logic.

**Acceptance Tests:**
- Given a configuration file, when I run the decision phase, then I receive a ProcessingDecisions object that specifies all strategies without executing any operations
- Given different collection types, when I analyze processing requirements, then the decision phase selects appropriate readers, geometry strategies, and templates without performing I/O
- Given invalid configuration, when I run the decision phase, then it fails fast with clear error messages before any processing begins

### Story 3: Immutable Data Flow
**As a** MetGenC developer, **I can** process metadata through immutable data structures, **so that** I eliminate side effects and can safely parallelize operations without state corruption.

**Acceptance Tests:**
- Given a Granule dataclass, when I attempt to modify its fields, then the system prevents mutation and requires creating new instances
- Given source data from multiple readers, when I process it through the pipeline, then each stage returns new immutable objects without modifying inputs
- Given concurrent processing of multiple granules, when operations run in parallel, then no race conditions occur due to shared mutable state

### Story 4: Processing and I/O Separation
**As a** MetGenC operator, **I can** run metadata processing independently of file operations, **so that** I can validate processing logic without touching the file system or AWS services.

**Acceptance Tests:**
- Given immutable source data, when I run temporal and spatial processors, then I receive processed metadata without any file writes or AWS calls
- Given processed metadata, when I use output builders, then I receive UMM-G and CNM content as strings without writing files
- Given build outputs, when I use dedicated writers, then file operations and AWS staging occur only in the final phase

### Story 5: Enhanced Pipeline Management
**As a** MetGenC operator, **I can** orchestrate the entire pipeline with comprehensive monitoring and error handling, **so that** I have visibility into each phase

**Acceptance Tests:**
- Given a pipeline execution, when any phase fails, then I receive detailed error information with detailed error messages
- Given pipeline execution, when I monitor progress, then I receive metrics for each phase including timing and success/failure rates
- Given multiple granules, when I process them, then I can track individual granule progress and aggregate results

## Developer Implementation Guide

### Story 1: Data Reading Isolation
- **Goal**: Extract all data reading operations into dedicated readers that return immutable data structures
- **Tasks**:
  - Create `CollectionMetadata`, `PremetData`, `SpatialData`, `ScienceMetadata` immutable dataclasses
  - Extract `collection_from_cmr()` into `readers/cmr_reader.py`
  - Move premet parsing from `utilities.py` to `readers/premet_reader.py`
  - Move spatial/spo parsing from `utilities.py` to `readers/spatial_reader.py`
  - Refactor science data readers to return immutable structures
  - Update tests to mock readers independently
- **Risk**: Low - isolated file parsing and network operations

### Story 2: Decision Making Separation
- **Goal**: Create a dedicated decision phase that analyzes configuration and determines processing strategies
- **Tasks**:
  - Create `ReaderStrategy`, `GeometryStrategy`, `TemplateStrategy`, `OutputStrategy` classes
  - Create `pipeline_decisions.py` with `analyze_processing_requirements()` function
  - Move all configuration-based decision logic from operations into decision phase
  - Create `ProcessingDecisions` immutable dataclass to hold all strategies
  - Create `ProcessingContext` that combines decisions with source data
  - Refactor operations to accept context instead of configuration directly
- **Risk**: Medium - affects core processing logic and touches all operations

### Story 3: Immutable Data Flow
- **Goal**: Convert all data structures to immutable and implement functional pipeline patterns
- **Tasks**:
  - Add `@dataclass(frozen=True)` to `Collection`, `Granule`, and all data classes
  - Update all operations to return new instances instead of modifying existing ones
  - Fix all mutation patterns throughout codebase
  - Replace recorder pattern with functional composition
  - Implement proper error handling for functional pipeline
  - Ensure each stage takes immutable input and returns immutable output
- **Risk**: High - breaks existing mutation patterns and requires complete pipeline rewrite

### Story 4: Processing and I/O Separation
- **Goal**: Isolate all processing logic from I/O operations and move I/O to pipeline boundaries
- **Tasks**:
  - Create `temporal_processor.py`, `spatial_processor.py`, `metadata_merger.py` with pure functions
  - Move processing logic out of `create_ummg()` into dedicated processors
  - Create `ummg_builder.py`, `cnm_builder.py` for template application
  - Move template population out of operations into builders
  - Create `file_writer.py`, `aws_writer.py` for final phase I/O
  - Extract file writing and AWS operations from pipeline operations
  - Implement batch operations for efficiency
- **Risk**: High - core business logic changes with medium risk for isolated template and I/O logic

### Story 5: Enhanced Pipeline Management
- **Goal**: Create comprehensive pipeline orchestration with monitoring and error handling
- **Tasks**:
  - Create `PipelineOrchestrator` class to manage all phases
  - Implement proper error handling mechanisms
  - Add pipeline monitoring and metrics collection
  - Replace current logging with structured result collection
  - Add detailed success/failure reporting with granule-level tracking
  - Implement pipeline performance metrics and timing
- **Risk**: Low - new functionality that enhances existing capabilities

## Implementation Strategy

### Backward Compatibility
- Each story maintains existing CLI interface
- No breaking changes to configuration format
- Existing behavior preserved throughout transition

### Incremental Testing
- Add comprehensive tests for each extracted component
- Goal of test coverage above 90% from refactoring
- Add integration tests for new pipeline phases

### Feature Flags
- Use configuration to toggle between old/new implementations during transition
- Allow gradual rollout of new pipeline components
- Provide fallback mechanisms for critical operations
