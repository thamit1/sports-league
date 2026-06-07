# Code Repository Knowledge Graph Generator

A Python tool that analyzes your repository structure and generates a knowledge graph mapping files, classes, functions, and their relationships.

## Features

✅ **AST-based Analysis**: Parses Python files to extract code structure  
✅ **Relationship Mapping**: Tracks imports, inheritance, function calls, dependencies  
✅ **Multiple Outputs**: JSON, GraphML, and HTML reports  
✅ **Metrics & Analytics**: Calculate centrality, density, critical modules  
✅ **Incremental**: Can compare graphs over time to track evolution  
✅ **Extensible**: Modular design for adding new analyzers  

## Installation

### Requirements
- Python 3.8+
- networkx (for graph processing)

### Setup

```bash
# Install dependencies
pip install networkx

# Or use the provided script
python run_graph_generator.py
```

## Usage

### Basic Usage

```bash
# Analyze current directory
python graph_generator.py

# Analyze specific repository
python graph_generator.py /path/to/repo

# Specify output directory
python graph_generator.py /path/to/repo /path/to/output
```

### Quick Start Script

```bash
# Use the provided runner script (handles dependencies)
python run_graph_generator.py
```

### Update Graph Script (Recommended)

After making code changes, use the update script to regenerate and compare graphs:

**On Linux/Mac:**
```bash
# Make script executable (first time only)
chmod +x update_graph.sh

# Update current directory
./update_graph.sh

# Update specific folder
./update_graph.sh backend

# Update and compare with previous version
./update_graph.sh backend --compare
```

**On Windows:**
```batch
# Update current directory
update_graph.bat

# Update specific folder
update_graph.bat backend

# Update and compare with previous version
update_graph.bat backend /compare
```

**What the update script does:**
1. Backs up current graph to `previous_graph.json`
2. Regenerates the knowledge graph
3. Saves new graph as `current_graph.json`
4. Optionally compares previous vs current
5. Displays statistics and change summary

## Output Files

The tool generates three output files:

### 1. **JSON Graph** (`graph_YYYYMMDD_HHMMSS.json`)
Complete graph data in JSON format for programmatic analysis:

```json
{
  "metadata": {
    "repo_path": "...",
    "generated_at": "2024-01-15T10:30:00",
    "stats": {
      "files_analyzed": 26,
      "classes_found": 15,
      "functions_found": 120,
      "imports_found": 45
    },
    "metrics": { ... }
  },
  "nodes": [
    {
      "id": "file:backend/app/main.py",
      "name": "main.py",
      "node_type": "file",
      "file_path": "...",
      "metrics": { }
    },
    ...
  ],
  "edges": [
    {
      "source": "file:backend/app/main.py",
      "target": "module:fastapi",
      "edge_type": "imports",
      "metadata": { }
    },
    ...
  ]
}
```

### 2. **GraphML** (`graph_YYYYMMDD_HHMMSS.graphml`)
Graph format compatible with visualization tools:
- [Cytoscape](https://cytoscape.org/) (Free, browser-based)
- [Gephi](https://gephi.org/) (Desktop visualization)
- [Neo4j](https://neo4j.com/) (Graph database)

**Importing in Cytoscape:**
1. Open https://cytoscape.org/
2. File → Open → Select GraphML file
3. Use layout algorithms (Force-Directed, Hierarchical, etc.)

### 3. **HTML Report** (`report_YYYYMMDD_HHMMSS.html`)
Visual summary with statistics and metrics:
- File and class counts
- Function count
- Most imported modules
- Most dependent files
- Graph metrics

## Node Types

| Type | Description |
|------|-------------|
| `file` | Python source files |
| `module` | Imported modules/packages |
| `class` | Class definitions |
| `function` | Functions and methods |
| `variable` | Variables (future use) |

## Edge Types

| Type | Meaning |
|------|---------|
| `imports` | File imports a module |
| `contains` | File/Class contains function/class |
| `inherits` | Class inherits from another class |
| `calls` | Function calls another function |
| `uses` | Entity uses another entity |
| `depends_on` | Dependency relationship |

## Use Cases

### 1. Repository Comparison
```bash
# Generate graphs for v1 and v2
python graph_generator.py ./sports-league-v1 ./output/v1
python graph_generator.py ./sports-league-v2 ./output/v2

# Compare JSON files programmatically
# (See examples below)
```

### 2. Updating Graphs When Code Changes

The recommended workflow for tracking code evolution:

**Simple Update:**
```bash
# Make code changes...
git add -A && git commit -m "Add new feature"

# Update graph
./update_graph.sh backend    # or update_graph.bat backend on Windows

# Output: New current_graph.json with timestamp
```

**Update with Comparison:**
```bash
# Update and compare against previous version
./update_graph.sh backend --compare

# Output: 
# - Updated graph
# - Comparison report showing:
#   • New files/classes/functions
#   • Removed code
#   • Changed dependencies
#   • Statistics delta
```

**Typical Comparison Report Output:**
```
STATISTICS COMPARISON
─────────────────────
Files Analyzed:     26 → 27      (+1, +3.8%)
Classes Found:      45 → 47      (+2, +4.4%)
Functions Found:   180 → 185     (+5, +2.8%)
Imports Found:     120 → 125     (+5, +4.2%)

FILE CHANGES
New files (1):
  + backend/app/routers/new_feature.py

CLASS CHANGES
New classes (2):
  + RatingCache
  + CacheManager

MODULE DEPENDENCY CHANGES
New dependencies (1):
  + redis
Removed dependencies (1):
  - memcache
```

**Keeping History:**
```bash
# Keep timestamped backups
cp graph_output/current_graph.json "graph_output/backup_before_refactor.json"

# Make changes...
git add -A && git commit -m "Major refactoring"

# Update and compare
./update_graph.sh backend --compare

# Compare report clearly shows impact
python compare_graphs.py "graph_output/backup_before_refactor.json" \
                        "graph_output/current_graph.json"
```

### 3. Impact Analysis
Before refactoring, understand dependencies:
```python
import json

with open('graph.json') as f:
    data = json.load(f)

# Find all dependencies of a specific module
module = "app.services.rating_engine"
for edge in data['edges']:
    if edge['target'] == f"module:{module}":
        print(f"File using {module}: {edge['source']}")
```

### 4. Architecture Visualization
Export to GraphML and visualize in Cytoscape or Gephi for:
- Understanding module dependencies
- Identifying circular dependencies
- Finding critical components
- Detecting architecture violations

### 5. Tracking Evolution
Generate graphs at different time points:
```bash
# Initial baseline
python graph_generator.py . output/baseline

# After refactoring
python graph_generator.py . output/after_refactor

# Compare metrics to see what changed
```

## Advanced: Extending the Generator

The tool is designed to be extended. Add custom analyzers:

```python
from graph_generator import ASTAnalyzer, NodeType, EdgeType

class CustomAnalyzer(ASTAnalyzer):
    def visit_Decorator(self, node):
        """Custom analysis for decorators"""
        # Your custom logic here
        self.generic_visit(node)

# Register in RepositoryAnalyzer._analyze_file()
```

## Typical Output Example

For the Sports League Management System:

```
✓ Graph generation complete!
  - Files Analyzed: 26
  - Classes Found: 45
  - Functions Found: 180
  - Imports Found: 120
  - Graph Nodes: 350
  - Graph Edges: 420
  
  Outputs:
  - JSON: graph_20240115_103000.json
  - GraphML: graph_20240115_103000.graphml
  - HTML Report: report_20240115_103000.html
```

## Troubleshooting

### "No module named 'networkx'"
```bash
pip install networkx
```

### Syntax errors in specific files
The generator logs these but continues analyzing other files. Check the file for Python syntax issues.

### Large repository taking too long
For very large repositories, consider:
1. Excluding more directories in `exclude_dirs`
2. Analyzing specific subdirectories

```python
analyzer = RepositoryAnalyzer(
    repo_path,
    exclude_dirs=['.git', '__pycache__', '.venv', 'tests', 'migrations']
)
```

## Troubleshooting

### "No module named 'networkx'"
```bash
pip install networkx
```

### Syntax errors in specific files
The generator logs these but continues analyzing other files. Check the file for Python syntax issues.

### Large repository taking too long
For very large repositories, consider:
1. Excluding more directories in `exclude_dirs`
2. Analyzing specific subdirectories

```python
analyzer = RepositoryAnalyzer(
    repo_path,
    exclude_dirs=['.git', '__pycache__', '.venv', 'tests', 'migrations']
)
```

## Update Workflow

### File Organization

The update scripts maintain a clean file structure:

```
graph_output/
├── current_graph.json              # Latest graph (always up-to-date)
├── previous_graph.json             # Previous version (for comparison)
├── current_report.html             # Latest HTML report
├── graph_YYYYMMDD_HHMMSS.json     # Timestamped archive
├── report_YYYYMMDD_HHMMSS.html    # Timestamped report
├── comparison_YYYYMMDD_HHMMSS.txt # Comparison reports
└── graphml_YYYYMMDD_HHMMSS.graphml # GraphML visualization files
```

### Recommended Update Schedule

| Frequency | Trigger | Command |
|-----------|---------|---------|
| **After commits** | Major features | `./update_graph.sh backend` |
| **Before refactoring** | Architecture changes | `./update_graph.sh backend --compare` |
| **Weekly** | Regular development | `./update_graph.sh backend` |
| **Release preparation** | Version tagging | `./update_graph.sh backend --compare` |

### Automating with Git Hooks

Create `.git/hooks/post-commit` to auto-update graphs:

```bash
#!/bin/bash
# .git/hooks/post-commit
# Auto-update knowledge graph after commits

if command -v ./update_graph.sh >/dev/null 2>&1; then
    echo "Updating knowledge graph..."
    ./update_graph.sh backend >/dev/null 2>&1 &
fi
```

### Continuous Integration

For GitHub Actions (`.github/workflows/update-graph.yml`):

```yaml
name: Update Knowledge Graph

on: [push]

jobs:
  update-graph:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: pip install networkx
      
      - name: Make script executable
        run: chmod +x update_graph.sh
      
      - name: Update graph
        run: ./update_graph.sh backend
      
      - name: Compare with previous
        run: ./update_graph.sh backend --compare || true
      
      - name: Commit updates
        run: |
          git config user.email "bot@example.com"
          git config user.name "Graph Bot"
          git add graph_output/
          git commit -m "Update knowledge graph" --allow-empty || true
          git push
```

## Comparing Two Repositories

Use the `compare_graphs.py` script to understand differences:

```bash
# Generate graphs for both repos
python graph_generator.py ./repo-v1 ./output/v1
python graph_generator.py ./repo-v2 ./output/v2

# Compare
python compare_graphs.py output/v1/graph_*.json output/v2/graph_*.json
```

**Example comparison output:**
```
STATISTICS COMPARISON
Files Analyzed:     120 → 145     (+25, +20.8%)
Classes Found:      85 → 120      (+35, +41.2%)
Functions Found:    450 → 520     (+70, +15.6%)
```

## Performance Notes

- Small repos (< 5MB): < 1 second
- Medium repos (5-50MB): 1-5 seconds
- Large repos (> 50MB): 5-30 seconds

Most time is spent on AST parsing; networkx graph operations are negligible.

Graph comparison is instantaneous (< 1 second) regardless of size.

## Future Enhancements

Potential additions for evolution:

- [ ] Support for other languages (TypeScript, Go, etc.)
- [ ] Circular dependency detection
- [ ] Dead code identification
- [ ] Test coverage mapping
- [ ] API contract analysis
- [ ] Configuration file dependency tracking
- [ ] Interactive web-based visualization
- [ ] Git history integration (track graph over commits)
- [ ] Diff generation between graph versions
- [ ] Machine learning for anomaly detection

## License

Free to use and modify for your projects.

## Questions?

This generator is designed to evolve. Modify and extend as needed for your specific analysis requirements.
