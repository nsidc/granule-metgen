# Extensible Reader Architecture Design

## Overview

This document outlines design options for making MetGenC's reader system extensible, allowing users to provide custom readers (shell scripts, Python code, etc.) without modifying the core codebase.

## Current Reader Architecture Analysis

### Reader Interface Pattern
All readers follow a common function signature:
```python
def extract_metadata(
    data_file: str,
    temporal_content: list,
    spatial_content: list,
    configuration: Config,
    gsr: str,  # Granule Spatial Representation
) -> dict
```

### Return Format
Readers must return a dictionary with:
```python
{
    "temporal": [...],  # List of temporal coverage info
    "geometry": [...],  # List of lat/lon points
    "production_date_time": "..."  # Optional
}
```

### Existing Components
- **Readers**: NetCDF, CSV, SnowEx CSV, Generic
- **Registry**: Simple lookup based on collection prefix and file extension
- **Selection**: One reader per collection, assigned at Granule instantiation

## Plugin Architecture Design Options

### 1. Configuration-Based Plugin System
Allow users to specify custom readers in INI configuration files:

```ini
[reader]
type = custom
module = /path/to/custom_reader.py
# or for shell scripts:
command = /path/to/extract_metadata.sh
```

**Pros:**
- Simple to implement
- Clear configuration
- No auto-discovery complexity

**Cons:**
- Requires manual configuration
- Path management considerations

### 2. Protocol-Based Interface
Define a clear protocol for external programs:

**Input Methods:**
- File path as first argument
- Configuration as JSON via stdin or arguments
- Environment variables for additional context

**Output Format:**
```json
{
  "temporal": [
    {"start": "2024-01-01T00:00:00", "end": "2024-01-01T23:59:59"}
  ],
  "geometry": [
    {"lat": 40.0, "lon": -105.0},
    {"lat": 40.1, "lon": -105.1}
  ],
  "production_date_time": "2024-01-01T12:00:00"
}
```

**Executor Types:**
- Python modules (dynamic import)
- Shell scripts (subprocess)
- Docker containers (for complex dependencies)
- HTTP services (REST API calls)

### 3. Plugin Discovery System
Structured plugin directory:

```
metgenc_plugins/
  readers/
    my_custom_reader.py
    extract_hdf5.sh
    reader_manifest.json
```

**Manifest Format:**
```json
{
  "readers": [
    {
      "name": "my_custom_reader",
      "type": "python",
      "module": "my_custom_reader",
      "collections": ["CUSTOM_*"],
      "extensions": [".hdf", ".h5"]
    }
  ]
}
```

### 4. Adapter Pattern Implementation
Create adapter classes for different plugin types:

```python
class ShellScriptReader:
    """Executes shell commands and parses JSON output"""
    
class PythonScriptReader:
    """Dynamically imports and calls Python functions"""
    
class HTTPReader:
    """Calls web services for metadata extraction"""
    
class DockerReader:
    """Runs containerized readers"""
```

### 5. Hook-Based System
Git-style hooks in predetermined locations:

```
.metgenc/
  hooks/
    pre-read          # Called before reading
    extract-metadata  # Main extraction
    post-process     # Called after extraction
```

## Recommended Hybrid Approach

Combine configuration-based selection with protocol adapters:

### 1. Extended INI Configuration
```ini
[reader.custom_hdf5]
enabled = true
type = shell
command = ${PROJECT_ROOT}/readers/extract_hdf5.sh
collections = HDF5_COLLECTION_*
extensions = .hdf, .h5

[reader.special_netcdf]
enabled = true
type = python
module = /opt/readers/special_netcdf.py
function = extract_metadata
collections = SPECIAL_NC_*
```

### 2. Adapter Classes
- `BaseReaderAdapter`: Abstract base class
- `PythonReaderAdapter`: Import and execute Python modules
- `ShellReaderAdapter`: Execute shell scripts with JSON I/O
- `HTTPReaderAdapter`: REST API integration

### 3. JSON Protocol Specification
```typescript
// Input (via stdin or file)
interface ReaderInput {
  file_path: string;
  config: {
    collection: string;
    environment: string;
    [key: string]: any;
  };
  context: {
    granule_ur: string;
    processing_time: string;
  };
}

// Output (via stdout)
interface ReaderOutput {
  temporal: Array<{
    start: string;  // ISO 8601
    end: string;    // ISO 8601
  }>;
  geometry: Array<{
    lat: number;
    lon: number;
  }>;
  production_date_time?: string;  // ISO 8601
  additional_attributes?: Record<string, any>;
}
```

### 4. Enhanced Registry
```python
class ReaderRegistry:
    def __init__(self):
        self._builtin_readers = {...}  # Existing readers
        self._custom_readers = {}       # Plugin readers
        
    def register_from_config(self, config: Config):
        """Load custom readers from configuration"""
        
    def get_reader(self, collection: str, file_ext: str):
        """Return appropriate reader (builtin or custom)"""
```

### 5. Helper Utilities
Provide tools for plugin developers:

```bash
# Validate plugin output
metgenc validate-reader my_reader.sh sample_file.nc

# Generate plugin template
metgenc create-reader --type python --name my_reader

# Test plugin integration
metgenc test-reader --config custom.ini sample_file.nc
```

## Implementation Roadmap

### Phase 1: Core Infrastructure
1. Create adapter base classes
2. Define JSON protocol
3. Extend configuration parser

### Phase 2: Basic Plugin Support
1. Implement ShellReaderAdapter
2. Implement PythonReaderAdapter
3. Update registry for custom readers

### Phase 3: Advanced Features
1. Add HTTPReaderAdapter
2. Implement plugin validation
3. Create helper utilities

### Phase 4: Documentation & Examples
1. Plugin developer guide
2. Example plugins (shell, Python)
3. Testing documentation

## Benefits

1. **Flexibility**: Users can integrate any tool or language
2. **Maintainability**: Core codebase remains clean
3. **Testability**: Plugins can be tested independently
4. **Backward Compatibility**: Existing readers continue to work
5. **Community Contributions**: Easier to share custom readers

## Security Considerations

1. **Sandboxing**: Consider running external scripts in restricted environments
2. **Input Validation**: Validate all plugin outputs
3. **Path Restrictions**: Limit file access for plugins
4. **Timeout Handling**: Prevent runaway processes
5. **Authentication**: For HTTP-based readers

## Example Custom Reader

### Python Plugin
```python
def extract_metadata(data_file, temporal_content, spatial_content, configuration, gsr):
    """Custom reader following MetGenC interface"""
    # Custom extraction logic
    return {
        "temporal": [...],
        "geometry": [...],
        "production_date_time": "2024-01-01T00:00:00"
    }
```

### Shell Script Plugin
```bash
#!/bin/bash
# Read JSON input from stdin
INPUT=$(cat)
FILE_PATH=$(echo $INPUT | jq -r '.file_path')

# Extract metadata using custom tools
# ... processing ...

# Output JSON result
cat <<EOF
{
  "temporal": [{"start": "2024-01-01T00:00:00", "end": "2024-01-01T23:59:59"}],
  "geometry": [{"lat": 40.0, "lon": -105.0}]
}
EOF
```

## Conclusion

The recommended hybrid approach provides maximum flexibility while maintaining simplicity. It allows users to:
- Configure custom readers without code changes
- Use any programming language or tool
- Test plugins independently
- Share readers with the community

This design preserves backward compatibility while enabling powerful extensibility for edge cases and specialized data formats.