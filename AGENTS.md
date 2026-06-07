# Impresso Content Item Classification Agents

This file defines custom agents for the Impresso Content Item Classification repository.

## Repository Overview

This repository implements the **Impresso content-item ad classifier** pipeline for processing newspaper content. It classifies newspaper articles as advertisements or non-advertisements using a multilingual machine learning model.

### Key Components

- **Build System**: Make-based orchestration system using the shared Impresso cookbook
- **Input**: Rebuilt JSONL/JSONL.BZ2 newspaper content from S3
- **Output**: Minimal JSONL with `id`, `tp`, and `ad_classification` fields
- **Storage**: S3-based data storage with local stamp files for distributed processing
- **Processing**: Python CLI tool (`lib/cli_content_item_classification.py`) performs classification

### Architecture

The repository uses a **two-layer structure**:

1. **Root level**: Task-specific logic (content item classification)
   - `Makefile`: Main orchestration
   - `configs/`: Model and pipeline configurations
   - `lib/cli_content_item_classification.py`: Classification CLI tool

2. **Cookbook submodule** (`cookbook/`): Shared Impresso processing infrastructure
   - Data synchronization (S3 ↔ local)
   - Parallel processing coordination
   - Logging and monitoring
   - Path management and conventions

### Processing Workflow

1. **Sync**: Download rebuilt newspaper data from S3
2. **Classify**: Run ad classification on content items
3. **Upload**: Push results and logs back to S3

The pipeline supports:

- Single newspaper processing
- Batch collection processing with parallelization
- Multi-machine distributed builds
- Incremental processing with stamp files

---

## Custom Agents

### Agent: Impresso Pipeline Expert

**Description**: Specialized agent for understanding and working with the Impresso Make-based processing pipeline, cookbook infrastructure, and newspaper content classification workflows.

**When to use**:

- Understanding the Make-based build system
- Debugging pipeline execution issues
- Modifying processing configurations
- Working with S3 synchronization
- Understanding the cookbook infrastructure
- Troubleshooting parallelization or distributed builds
- Creating or modifying processing targets

**Expertise**:

- GNU Make 4+ advanced patterns and conventions
- S3 data synchronization and path management
- Stamp-based incremental build systems
- Parallel and distributed processing patterns
- Python CLI tools using smart_open for S3/local I/O
- Impresso newspaper data formats (JSONL/JSONL.BZ2)
- The shared cookbook infrastructure and conventions

**Key Knowledge Areas**:

- **Makefile structure**: Understanding include files, targets, and dependencies
- **Path conventions**: Local vs S3 path mappings, stamp files, data directories
- **Parallelization**: `COLLECTION_JOBS` and `NEWSPAPER_JOBS` parameters
- **Configuration**: `.env` files, config files, runtime overrides
- **Logging**: Make logging system and Python logging integration
- **Cookbook patterns**: Setup, sync, processing, aggregation targets

**Common Tasks**:

- Explain how to run processing for a specific newspaper or collection
- Debug why builds fail or skip steps
- Add new configuration files or model versions
- Modify the classification logic or output format
- Understand stamp file dependencies
- Troubleshoot S3 synchronization issues

---

### Agent: Ad Classification Developer

**Description**: Specialized agent for understanding and modifying the content item ad classification logic, model integration, and output processing.

**When to use**:

- Understanding the classification algorithm
- Modifying classification logic or thresholds
- Debugging classification errors or unexpected results
- Adding new classification features or outputs
- Understanding the model pipeline and data flow
- Working with the Python CLI tool

**Expertise**:

- Python data processing with JSONL formats
- smart_open for transparent S3/local file handling
- The impresso_cookbook Python package conventions
- Content item classification and ad detection
- Batch processing and streaming data patterns
- Logging and diagnostics for ML pipelines

**Key Knowledge Areas**:

- **Input format**: Rebuilt newspaper JSONL structure (`id`, `tp`, article fields)
- **Output format**: Minimal JSONL with classification results
- **Classification logic**: How ads are identified and scored
- **Model configuration**: Model paths, parameters, and versioning
- **CLI conventions**: Input/output arguments, logging, batch processing
- **Error handling**: Graceful degradation and error reporting

**Common Tasks**:

- Explain the classification algorithm and decision logic
- Add new fields to the output format
- Modify classification thresholds or criteria
- Debug classification accuracy issues
- Add diagnostic outputs or logging
- Integrate new model versions or features

---

## Usage Examples

### Working with Pipeline Structure

```bash
# Show all available targets
gmake help

# Run classification on one newspaper
gmake CFG=configs/config-content-item-classification-multilingual_v1-0-0.mk \
      NEWSPAPER=BNL/actionfem \
      newspaper

# Run on a collection with parallelization
gmake CFG=configs/config-content-item-classification-multilingual_v1-0-0.mk \
      COLLECTION_JOBS=4 \
      collection
```

### Configuration Variables

**Environment** (`.env`):

- `SE_ACCESS_KEY`: S3 access key
- `SE_SECRET_KEY`: S3 secret key
- `SE_HOST_URL`: S3 endpoint URL

**Runtime overrides**:

- `CFG`: Configuration file path
- `NEWSPAPER`: Single newspaper to process
- `COLLECTION_JOBS`: Parallel newspaper processing
- `NEWSPAPER_JOBS`: Parallelism within one newspaper
- `LOGGING_LEVEL`: Verbosity level

### File Paths to Understand

**Task-Specific**:

- `Makefile`: Main pipeline orchestration
- `lib/cli_content_item_classification.py`: Classification implementation
- `configs/config-*.mk`: Model and pipeline configurations

**Cookbook Infrastructure**:

- `cookbook/main_targets.mk`: Core processing targets
- `cookbook/processing.mk`: Processing behavior configuration
- `cookbook/sync.mk`: S3 synchronization logic
- `cookbook/paths_*.mk`: Path definitions for different stages
- `cookbook/log.mk`: Logging system

---

## Notes for AI Assistants

When working in this repository:

1. **Always use `gmake`** on macOS (not system `make`) - GNU Make 4+ required
2. **Check stamp files** when debugging - they track what's been processed
3. **Configuration is layered**: `.env` → config files → runtime overrides
4. **Paths follow conventions**: Understand local vs S3 path mappings
5. **Parallelization is two-level**: collection-level and newspaper-level
6. **Cookbook is shared**: Changes to cookbook affect other Impresso pipelines
7. **S3 is the source of truth**: Local files are temporary/cache
8. **Logging is hierarchical**: Make logs + Python logs with configurable levels

### Common Pitfalls

- Using system `make` instead of `gmake` on macOS
- Missing `.env` file or incorrect S3 credentials
- Stale stamp files causing skipped processing
- Path mismatches between local and S3
- Insufficient parallelization for large collections
- Missing cookbook submodule initialization (`--recursive` clone)
