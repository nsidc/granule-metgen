# MetGenC Pipeline Refactoring Plan

## Overview

This document outlines a plan to refactor the MetGenC pipeline using a State Monad-inspired pattern to create a composable, testable, and maintainable architecture that separates side-effects from pure computation.

## Current Pipeline Issues

The current pipeline has several architectural limitations:

1. **Mixed concerns**: Decision-making and execution are intertwined throughout operations
2. **Embedded I/O**: Reading and writing occur within pipeline operations rather than at boundaries
3. **Mutable state**: The `Granule` dataclass is modified throughout the pipeline
4. **Tight coupling**: Components depend heavily on each other and configuration state
5. **Limited composability**: Pipeline stages cannot be easily rearranged or tested in isolation
6. **Side-effect entanglement**: Business logic is mixed with I/O operations

## Key Benefit Goals

1. **Functional Composition**: Pipeline stages compose functionally with explicit state threading
2. **Side-Effect Isolation**: All side-effects are specified as data and executed separately
3. **Immutable State**: Pipeline context and data flow through stages immutably
4. **Dynamic Pipeline Construction**: Pipeline is built dynamically based on configuration and CMR metadata
5. **Comprehensive Auditing**: Processing ledger tracks all operations for debugging and monitoring
6. **Strategy Pattern**: Explicit strategies for geometry and temporal processing
7. **Testability**: Each stage can be tested with mock state, no I/O required

## Success Criteria

- [ ] Pipeline stages are pure functions that return (result, new_state) tuples
- [ ] All side-effects are deferred until the execution phase
- [ ] Pipeline can be constructed dynamically based on configuration
- [ ] Processing ledger provides complete audit trail
- [ ] Each granule's processing is independent and parallelizable
- [ ] Existing functionality is preserved
- [ ] Performance is maintained or improved
- [ ] Code coverage remains above 90%

## Risk Mitigation

1. **Simplified State Pattern**: Use a pragmatic Python approach rather than full State Monad
2. **Feature Flags**: Toggle between old/new implementations via CLI or config
3. **Gradual Migration**: Implement one pipeline stage at a time
4. **Comprehensive Testing**: Test each stage in isolation and integration
5. **Performance Monitoring**: Track pipeline performance throughout migration

## New Pipeline Architecture

### Conceptual Flow

```
1. Configuration Phase
   ├─ Read configuration (Configuration Reader)
   ├─ Invoke CMR reader for collection metadata
   └─ Construct pipeline with strategies

2. Pipeline Construction Phase
   ├─ Select appropriate readers for file types
   ├─ Choose geometry strategy
   ├─ Choose temporal strategy
   └─ Build granule processing pipeline

3. Granule Processing Phase (per granule)
   ├─ Read granule files (science, premet, spatial)
   ├─ Process metadata using strategies
   ├─ Specify side-effects (don't execute)
   └─ Update processing ledger

4. Side-Effect Execution Phase
   ├─ Group related side-effects
   ├─ Execute side-effects in batches
   └─ Record results in ledger

5. Reporting Phase
   └─ Generate summary from ledger
```

### Custom Reader Extension System

MetGenC will support custom readers for unsupported file types through configuration:

```ini
[custom_readers]
# Define custom readers for specific file patterns
*.hdf5 = /path/to/hdf5_reader.py --format json
*.custom = python /path/to/custom_reader.py
*.dat = /usr/local/bin/dat2json

[reader_timeouts]
# Optional timeouts for custom readers (seconds)
*.hdf5 = 30
*.custom = 60
```

### Custom Reader Interface

```python
@dataclass(frozen=True)
class CustomReaderConfig:
    """Configuration for a custom reader"""
    file_pattern: str
    command: str
    timeout: int = 120
    output_format: str = "json"  # json or yaml
    
@dataclass(frozen=True) 
class CustomReaderResult:
    """Result from custom reader execution"""
    metadata: Dict[str, Any]
    stdout: str
    stderr: str
    exit_code: int
    execution_time: float

class CustomReader:
    """Executes user-defined readers for unsupported file types"""
    
    def __init__(self, config: CustomReaderConfig):
        self.config = config
        
    def read(self, file_path: Path) -> CustomReaderResult:
        """Execute custom reader and parse output"""
        cmd = self.config.command.replace('{}', str(file_path))
        
        # Execute with timeout
        result = subprocess.run(
            shlex.split(cmd),
            capture_output=True,
            text=True,
            timeout=self.config.timeout
        )
        
        # Parse output based on format
        if self.config.output_format == "json":
            metadata = json.loads(result.stdout)
        elif self.config.output_format == "yaml":
            metadata = yaml.safe_load(result.stdout)
        else:
            raise ValueError(f"Unsupported output format: {self.config.output_format}")
            
        return CustomReaderResult(
            metadata=metadata,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
            execution_time=time.time() - start_time
        )

# Custom Reader Protocol/Contract
"""
Custom readers must:
1. Accept a file path as the first argument
2. Write metadata to stdout in JSON or YAML format
3. Write errors/warnings to stderr
4. Return 0 on success, non-zero on failure
5. Complete within the configured timeout

Expected output structure:
{
    "temporal": {
        "start_datetime": "2024-01-01T00:00:00Z",
        "end_datetime": "2024-01-01T23:59:59Z"
    },
    "spatial": {
        "type": "Point",
        "coordinates": [-105.0, 40.0]
    },
    "attributes": {
        "instrument": "CustomSensor",
        "processing_level": "L2"
    }
}
"""
```

### Pipeline State Architecture

```python
# Simplified State-like pattern for Python
@dataclass(frozen=True)
class PipelineState:
    """Immutable state threaded through pipeline stages"""
    configuration: Configuration
    cmr_metadata: CMRMetadata
    geometry_strategy: GeometryStrategy
    temporal_strategy: TemporalStrategy
    custom_readers: Dict[str, CustomReader]  # Pattern -> Reader mapping
    processing_ledger: Tuple[ProcessingEvent, ...]
    error_accumulator: Tuple[ProcessingError, ...]
    
    def with_ledger_entry(self, event: ProcessingEvent) -> 'PipelineState':
        """Return new state with added ledger entry"""
        return replace(self, processing_ledger=self.processing_ledger + (event,))
    
    def with_error(self, error: ProcessingError) -> 'PipelineState':
        """Return new state with added error"""
        return replace(self, error_accumulator=self.error_accumulator + (error,))

# Pipeline Result type
@dataclass(frozen=True)
class PipelineResult:
    """Result of a pipeline stage with new state"""
    value: Any
    state: PipelineState

# Side-effect specifications (data, not execution)
@dataclass(frozen=True)
class SideEffect:
    """Base class for side-effect specifications"""
    granule_id: str
    
@dataclass(frozen=True)
class GenerateUMMG(SideEffect):
    metadata: ProcessedMetadata
    template: str
    
@dataclass(frozen=True)
class GenerateCNM(SideEffect):
    metadata: ProcessedMetadata
    template: str
    
@dataclass(frozen=True)
class WriteFile(SideEffect):
    path: Path
    content: str
    
@dataclass(frozen=True)
class S3Transfer(SideEffect):
    source_path: Path
    s3_key: str
    
@dataclass(frozen=True)
class KinesisMessage(SideEffect):
    stream_name: str
    message: str
```

### Pipeline Stages

```python
# Type alias for pipeline functions
PipelineStage = Callable[[Any, PipelineState], PipelineResult]

# Configuration reading stage
def read_configuration(config_path: Path, state: PipelineState) -> PipelineResult:
    """Read configuration file - treated as a data source"""
    try:
        config = ConfigurationReader().read(config_path)
        new_state = state.with_ledger_entry(
            ConfigurationRead(config_path, config)
        )
        return PipelineResult(config, new_state)
    except Exception as e:
        return PipelineResult(
            None, 
            state.with_error(ConfigurationError(str(e)))
        )

# Reader selection with custom reader support
def select_readers(configuration: Configuration, granule_paths: GranulePaths, 
                  custom_readers: Dict[str, CustomReader]) -> ReaderSet:
    """Select appropriate readers for granule files, preferring custom readers"""
    readers = ReaderSet()
    
    # Check each file against custom reader patterns
    for file_path in granule_paths.all_files:
        for pattern, custom_reader in custom_readers.items():
            if fnmatch.fnmatch(file_path.name, pattern):
                readers.add_custom(file_path, custom_reader)
                break
        else:
            # No custom reader matched, use built-in reader
            if file_path.suffix in ['.nc', '.nc4', '.h5']:
                readers.add_builtin(file_path, NetCDFReader())
            elif file_path.suffix == '.csv':
                readers.add_builtin(file_path, CSVReader())
            elif 'premet' in file_path.name:
                readers.add_builtin(file_path, PremetReader())
            elif 'spatial' in file_path.name or '.spo' in file_path.suffix:
                readers.add_builtin(file_path, SpatialReader())
    
    return readers

# Granule file reading stage
def read_granule_files(granule_paths: GranulePaths, state: PipelineState) -> PipelineResult:
    """Read all files for a granule using appropriate readers"""
    readers = select_readers(state.configuration, granule_paths, state.custom_readers)
    
    # Read files with appropriate readers
    all_metadata = {}
    for file_path, reader in readers.items():
        try:
            if isinstance(reader, CustomReader):
                result = reader.read(file_path)
                if result.exit_code != 0:
                    state = state.with_error(
                        CustomReaderError(file_path, result.stderr)
                    )
                else:
                    all_metadata[file_path] = result.metadata
            else:
                # Built-in reader
                all_metadata[file_path] = reader.read(file_path)
        except Exception as e:
            state = state.with_error(
                ReaderError(file_path, str(e))
            )
    
    # Organize metadata by type
    granule_data = GranuleData(
        science_data=merge_science_metadata(all_metadata),
        premet_data=extract_premet_data(all_metadata),
        spatial_data=extract_spatial_data(all_metadata),
        custom_data=extract_custom_data(all_metadata)
    )
    
    new_state = state.with_ledger_entry(
        GranuleFilesRead(granule_paths.granule_id, granule_data, readers.summary())
    )
    return PipelineResult(granule_data, new_state)

# Metadata processing stage
def process_metadata(granule_data: GranuleData, state: PipelineState) -> PipelineResult:
    """Process metadata using configured strategies"""
    temporal = state.temporal_strategy.extract(granule_data, state.cmr_metadata)
    geometry = state.geometry_strategy.extract(granule_data, state.cmr_metadata)
    
    metadata = ProcessedMetadata(
        temporal_extent=temporal,
        spatial_extent=geometry,
        attributes=merge_attributes(granule_data, state.configuration)
    )
    
    new_state = state.with_ledger_entry(
        MetadataProcessed(granule_data.id, metadata)
    )
    return PipelineResult(metadata, new_state)

# Side-effect specification stage
def specify_side_effects(metadata: ProcessedMetadata, state: PipelineState) -> PipelineResult:
    """Specify side-effects without executing them"""
    effects = []
    
    # Always generate UMM-G
    effects.append(GenerateUMMG(
        granule_id=metadata.granule_id,
        metadata=metadata,
        template=state.configuration.ummg_template
    ))
    
    # Conditionally add other side-effects
    if state.configuration.cnm_enabled:
        effects.append(GenerateCNM(
            granule_id=metadata.granule_id,
            metadata=metadata,
            template=state.configuration.cnm_template
        ))
    
    if state.configuration.write_files:
        effects.extend([
            WriteFile(
                granule_id=metadata.granule_id,
                path=state.configuration.output_dir / f"{metadata.granule_id}.ummg.json",
                content=None  # Will be filled during execution
            )
        ])
    
    if state.configuration.s3_staging:
        effects.append(S3Transfer(
            granule_id=metadata.granule_id,
            source_path=state.configuration.output_dir / f"{metadata.granule_id}.ummg.json",
            s3_key=f"{state.configuration.s3_prefix}/{metadata.granule_id}.ummg.json"
        ))
    
    if state.configuration.kinesis_enabled:
        effects.append(KinesisMessage(
            granule_id=metadata.granule_id,
            stream_name=state.configuration.kinesis_stream,
            message=None  # Will be CNM content
        ))
    
    new_state = state.with_ledger_entry(
        SideEffectsSpecified(metadata.granule_id, len(effects))
    )
    return PipelineResult(effects, new_state)
```

### Pipeline Composition

```python
class GranulePipeline:
    """Composes pipeline stages for processing a single granule"""
    
    def __init__(self, initial_state: PipelineState):
        self.initial_state = initial_state
    
    def process_granule(self, granule_paths: GranulePaths) -> Tuple[List[SideEffect], PipelineState]:
        """Process a single granule through all pipeline stages"""
        # Thread state through each stage
        result = self.read_granule_files(granule_paths, self.initial_state)
        if result.value is None:
            return [], result.state
            
        result = self.process_metadata(result.value, result.state)
        if result.value is None:
            return [], result.state
            
        result = self.specify_side_effects(result.value, result.state)
        return result.value, result.state
    
    # Pipeline stages as methods for clarity
    read_granule_files = staticmethod(read_granule_files)
    process_metadata = staticmethod(process_metadata)
    specify_side_effects = staticmethod(specify_side_effects)
```

### Side-Effect Execution

```python
class SideEffectExecutor:
    """Executes side-effects in groups for efficiency"""
    
    def execute_effects(self, effects: List[SideEffect], state: PipelineState) -> PipelineState:
        """Execute all side-effects and update state with results"""
        # Group effects by type for batch processing
        grouped = self.group_effects(effects)
        
        # Execute file generation effects
        if grouped.get('generate'):
            state = self.execute_generation(grouped['generate'], state)
        
        # Execute file write effects
        if grouped.get('write'):
            state = self.execute_writes(grouped['write'], state)
        
        # Execute AWS effects in parallel
        if grouped.get('aws'):
            state = self.execute_aws_operations(grouped['aws'], state)
        
        return state
    
    def group_effects(self, effects: List[SideEffect]) -> Dict[str, List[SideEffect]]:
        """Group effects by operation type for batch processing"""
        groups = defaultdict(list)
        for effect in effects:
            if isinstance(effect, (GenerateUMMG, GenerateCNM)):
                groups['generate'].append(effect)
            elif isinstance(effect, WriteFile):
                groups['write'].append(effect)
            elif isinstance(effect, (S3Transfer, KinesisMessage)):
                groups['aws'].append(effect)
        return groups
    
    def execute_generation(self, effects: List[SideEffect], state: PipelineState) -> PipelineState:
        """Execute content generation effects"""
        for effect in effects:
            try:
                if isinstance(effect, GenerateUMMG):
                    content = generate_ummg_content(effect.metadata, effect.template)
                    # Update effect with content for downstream use
                    effect = replace(effect, content=content)
                elif isinstance(effect, GenerateCNM):
                    content = generate_cnm_content(effect.metadata, effect.template)
                    effect = replace(effect, content=content)
                
                state = state.with_ledger_entry(
                    GenerationCompleted(effect.granule_id, type(effect).__name__)
                )
            except Exception as e:
                state = state.with_error(
                    GenerationError(effect.granule_id, str(e))
                )
        return state
```

### Main Pipeline Orchestrator

```python
class PipelineOrchestrator:
    """Orchestrates the entire MetGenC pipeline"""
    
    def __init__(self, config_path: Path):
        self.config_path = config_path
        
    def run(self, input_paths: List[Path]) -> ProcessingReport:
        """Run the complete pipeline"""
        # Phase 1: Initialize pipeline
        state = self.initialize_pipeline()
        
        # Phase 2: Discover and group granules
        granule_groups = self.discover_granules(input_paths, state)
        
        # Phase 3: Process each granule (can be parallelized)
        all_effects = []
        for granule_paths in granule_groups:
            pipeline = GranulePipeline(state)
            effects, new_state = pipeline.process_granule(granule_paths)
            all_effects.extend(effects)
            state = new_state
        
        # Phase 4: Execute all side-effects
        executor = SideEffectExecutor()
        final_state = executor.execute_effects(all_effects, state)
        
        # Phase 5: Generate report
        return self.generate_report(final_state)
    
    def initialize_pipeline(self) -> PipelineState:
        """Initialize pipeline with configuration and strategies"""
        # Read configuration
        config = ConfigurationReader().read(self.config_path)
        
        # Get CMR metadata
        cmr_metadata = CMRReader().read_collection(config.collection_id)
        
        # Select strategies
        geometry_strategy = GeometryStrategyFactory.create(config, cmr_metadata)
        temporal_strategy = TemporalStrategyFactory.create(config, cmr_metadata)
        
        # Load custom readers from configuration
        custom_readers = self.load_custom_readers(config)
        
        return PipelineState(
            configuration=config,
            cmr_metadata=cmr_metadata,
            geometry_strategy=geometry_strategy,
            temporal_strategy=temporal_strategy,
            custom_readers=custom_readers,
            processing_ledger=(),
            error_accumulator=()
        )
    
    def load_custom_readers(self, config: Configuration) -> Dict[str, CustomReader]:
        """Load custom readers from configuration"""
        custom_readers = {}
        
        if 'custom_readers' in config.sections:
            for pattern, command in config.custom_readers.items():
                timeout = config.reader_timeouts.get(pattern, 120)
                reader_config = CustomReaderConfig(
                    file_pattern=pattern,
                    command=command,
                    timeout=timeout
                )
                custom_readers[pattern] = CustomReader(reader_config)
                
        return custom_readers
```

## Implementation Strategy for Time-Constrained Delivery

### Critical Context: Working Under Deadline Pressure

Given hard deadlines, we must prioritize phases that deliver immediate, standalone value. Each phase should be deployable independently and provide tangible benefits even if subsequent phases aren't completed.

### Minimum Viable Refactoring Path

If only one thing can be done, implement **Custom Readers** (2-3 days):
- Solves immediate user need for extensibility
- No changes to existing pipeline required
- Can be deployed immediately

### Reordered Phases for Maximum Incremental Value

### Phase 1: Custom Reader System (Week 1)
**Standalone Value**: Users can process any file format immediately

1. **Implement custom reader system**:
   - Create `CustomReader` class with subprocess execution
   - Add INI configuration parsing for reader definitions
   - Implement timeout and error handling
   - Create validation for JSON/YAML output format
2. Create documentation and example readers
3. Add integration tests for custom readers

**Benefit if stopped here**: MetGenC becomes extensible for any file format without code changes

### Phase 2: Reader Refactoring & Immutability (Week 2-3)
**Standalone Value**: More reliable system with better error handling

1. Extract CMR reader from utilities (improves testability)
2. Refactor readers to return immutable data structures
3. Implement non-fatal error accumulation
4. Create `ConfigurationReader` to treat config as data
5. Add comprehensive reader tests

**Benefit if stopped here**: Fewer bugs, easier debugging, better test coverage

### Phase 3: Strategy Pattern Implementation (Week 4)
**Standalone Value**: Cleaner code, easier to add new processing strategies

1. Extract geometry strategies from operations
2. Extract temporal strategies from operations
3. Create strategy factories
4. Refactor existing code to use strategies
5. Add strategy tests

**Benefit if stopped here**: More maintainable code, easier to add new geometry/temporal handling

### Phase 4: Basic Pipeline Separation (Week 5-6)
**Standalone Value**: I/O at boundaries, better testability

1. Create simple pipeline state (not full State Monad)
2. Move file writing to end of pipeline
3. Move AWS operations to end of pipeline
4. Create basic side-effect specifications
5. Add pipeline tests

**Benefit if stopped here**: Testable business logic, I/O isolation

### Phase 5: Full Pipeline Refactoring (Week 7-9)
**Only if time permits**: Complete State Monad pattern

1. Implement `PipelineState` and `PipelineResult`
2. Create pipeline stages as pure functions
3. Implement `ProcessingLedger`
4. Add `PipelineOrchestrator`
5. Create migration path

**Benefit**: Full functional pipeline with all architectural benefits

### Phase 6: Performance & Polish (Week 10-12)
**Only if time permits**: Optimization and documentation

1. Add parallel processing
2. Implement batch operations
3. Performance benchmarking
4. Complete documentation

### Decision Matrix for Time Constraints

| Time Available | Implement Phases | Key Benefits |
|----------------|------------------|--------------|
| 1 week | Phase 1 only | Custom reader extensibility |
| 2-3 weeks | Phases 1-2 | Extensibility + reliability |
| 4 weeks | Phases 1-3 | Above + maintainability |
| 6 weeks | Phases 1-4 | Above + testability |
| 9+ weeks | All phases | Full architectural benefits |

### Critical Success Factors

1. **Feature Flag Everything**: Each phase behind a flag
2. **No Breaking Changes**: Existing pipeline continues working
3. **Deploy Early**: Ship each phase as completed
4. **Document Incrementally**: Don't wait until the end

## Benefits of This Approach

1. **Testability**: Each stage is a pure function with no I/O
2. **Debugging**: Complete audit trail via processing ledger
3. **Flexibility**: Easy to add new strategies or side-effects
4. **Performance**: Batch operations and parallelization
5. **Maintainability**: Clear separation of concerns
6. **Error Handling**: Non-fatal errors don't stop processing
7. **Composability**: Pipeline stages can be easily rearranged
8. **Extensibility**: Custom readers allow processing any file format

## Custom Reader Use Cases

The custom reader feature enables several important scenarios:

1. **Legacy Formats**: Support proprietary or legacy file formats without modifying MetGenC
2. **Rapid Prototyping**: Test new file formats before building native support
3. **Mission-Specific Formats**: Handle specialized formats for specific missions
4. **External Tools**: Leverage existing command-line tools (e.g., GDAL, NCO utilities)
5. **Language Flexibility**: Write readers in any language (Python, R, Julia, shell scripts)

### Example Custom Readers

```ini
# Example 1: HDF5 reader using h5dump
[custom_readers]
*.hdf5 = h5dump -p -H -d /path/to/dataset {} | python /opt/parsers/h5dump_to_json.py

# Example 2: GeoTIFF reader using GDAL
*.tif = gdal_translate -of VRT {} /vsistdout/ | python /opt/parsers/vrt_to_json.py

# Example 3: Binary format with custom C program
*.bin = /usr/local/bin/binary_reader --json {}

# Example 4: R script for statistical data
*.rdata = Rscript /opt/readers/rdata_extractor.R {}
```

## Risk Assessment for Partial Implementation

### What Happens If We Stop Early?

**After Phase 1 (Custom Readers)**:
- ✅ Users can process new file formats
- ✅ No risk to existing functionality
- ❌ Technical debt remains in core pipeline

**After Phase 2 (Reader Refactoring)**:
- ✅ All above benefits
- ✅ More reliable reader system
- ✅ Better error messages
- ❌ Pipeline still has mixed concerns

**After Phase 3 (Strategies)**:
- ✅ All above benefits
- ✅ Easier to add new processing logic
- ✅ Cleaner code organization
- ❌ I/O still embedded in pipeline

**After Phase 4 (Basic Separation)**:
- ✅ All above benefits
- ✅ Testable business logic
- ✅ I/O at boundaries
- ❌ Missing advanced features (ledger, parallel processing)

### Recommendation for Time-Constrained Projects

**With 1-2 weeks**: Do Phase 1 (Custom Readers) - immediate user value
**With 3-4 weeks**: Do Phases 1-3 - significant code quality improvements  
**With 6+ weeks**: Do Phases 1-4 - achieve core architectural goals
**With 9+ weeks**: Complete all phases - full benefits

The key insight: **Each phase delivers value independently**, so even partial implementation is worthwhile.

## Migration Notes

- Old pipeline remains functional during migration
- Feature flag controls which pipeline is used
- Gradual rollout possible per collection type
- No changes to CLI interface or configuration format
- Existing tests continue to pass throughout migration