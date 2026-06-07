#!/bin/bash
#
# update_graph.sh - Update Repository Knowledge Graph
#
# This script regenerates the knowledge graph after code changes.
# It tracks the current and previous graphs for easy comparison.
#
# Usage:
#   ./update_graph.sh              # Update current directory
#   ./update_graph.sh backend      # Update backend folder
#   ./update_graph.sh backend --compare  # Update and compare with previous
#
# Features:
#   - Automatic timestamp-based naming
#   - Keeps previous graph for comparison
#   - Auto-compares if requested
#   - Generates HTML report
#

set -e

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
REPO_PATH="${1:-.}"
COMPARE_FLAG="${2:-}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="graph_output"
PYTHON_SCRIPT="graph_generator.py"

# Verify Python script exists
if [ ! -f "$PYTHON_SCRIPT" ]; then
    echo -e "${RED}✗ Error: $PYTHON_SCRIPT not found in current directory${NC}"
    exit 1
fi

# Verify repo path exists
if [ ! -d "$REPO_PATH" ]; then
    echo -e "${RED}✗ Error: Repository path '$REPO_PATH' not found${NC}"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}Repository Knowledge Graph Update${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Repository:${NC} $REPO_PATH"
echo -e "${YELLOW}Output Dir:${NC} $OUTPUT_DIR"
echo -e "${YELLOW}Timestamp:${NC} $TIMESTAMP"
echo ""

# ============================================================================
# Step 1: Backup previous graph
# ============================================================================
echo -e "${BLUE}[1/4]${NC} Backing up previous graph..."

if [ -f "$OUTPUT_DIR/current_graph.json" ]; then
    cp "$OUTPUT_DIR/current_graph.json" "$OUTPUT_DIR/previous_graph.json"
    echo -e "${GREEN}✓${NC} Previous graph backed up"
else
    echo -e "${YELLOW}⚠${NC} No previous graph found (first run)"
fi

# ============================================================================
# Step 2: Generate new graph
# ============================================================================
echo -e "${BLUE}[2/4]${NC} Analyzing repository and generating new graph..."

START_TIME=$(date +%s)

python "$PYTHON_SCRIPT" "$REPO_PATH" "$OUTPUT_DIR" 2>&1 | sed 's/^/  /'

END_TIME=$(date +%s)
DURATION=$((END_TIME - START_TIME))

# Find the latest generated graph
LATEST_GRAPH=$(ls -t "$OUTPUT_DIR"/graph_*.json 2>/dev/null | head -1)

if [ -z "$LATEST_GRAPH" ]; then
    echo -e "${RED}✗ Error: No graph file generated${NC}"
    exit 1
fi

# Copy to current
cp "$LATEST_GRAPH" "$OUTPUT_DIR/current_graph.json"
LATEST_REPORT=$(ls -t "$OUTPUT_DIR"/report_*.html 2>/dev/null | head -1)
if [ -n "$LATEST_REPORT" ]; then
    cp "$LATEST_REPORT" "$OUTPUT_DIR/current_report.html"
fi

echo -e "${GREEN}✓${NC} Graph generated in ${DURATION}s"
echo ""

# ============================================================================
# Step 3: Extract statistics
# ============================================================================
echo -e "${BLUE}[3/4]${NC} Extracting statistics..."

if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
else
    PYTHON_CMD="python"
fi

STATS=$($PYTHON_CMD << 'PYTHON_END'
import json
import sys

try:
    with open("graph_output/current_graph.json") as f:
        data = json.load(f)
    
    stats = data['metadata']['stats']
    metrics = data['metadata']['metrics']
    
    print(f"Files Analyzed:    {stats['files_analyzed']}")
    print(f"Classes Found:     {stats['classes_found']}")
    print(f"Functions Found:   {stats['functions_found']}")
    print(f"Imports Found:     {stats['imports_found']}")
    print(f"Graph Nodes:       {metrics['nodes']}")
    print(f"Graph Edges:       {metrics['edges']}")
    print(f"Parsing Errors:    {stats['errors']}")
    
except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
PYTHON_END
)

echo "$STATS" | sed 's/^/  /'
echo ""

# ============================================================================
# Step 4: Compare with previous (optional)
# ============================================================================
if [ "$COMPARE_FLAG" = "--compare" ] || [ "$COMPARE_FLAG" = "-c" ]; then
    if [ -f "$OUTPUT_DIR/previous_graph.json" ]; then
        echo -e "${BLUE}[4/4]${NC} Comparing with previous graph..."
        echo ""
        
        python compare_graphs.py "$OUTPUT_DIR/previous_graph.json" "$OUTPUT_DIR/current_graph.json" 2>&1 | sed 's/^/  /'
        
        if [ -f "graph_comparison_report.txt" ]; then
            mv "graph_comparison_report.txt" "$OUTPUT_DIR/comparison_${TIMESTAMP}.txt"
            echo ""
            echo -e "${GREEN}✓${NC} Comparison report saved: $OUTPUT_DIR/comparison_${TIMESTAMP}.txt"
        fi
    else
        echo -e "${BLUE}[4/4]${NC} Skipping comparison (no previous graph)"
    fi
else
    echo -e "${BLUE}[4/4]${NC} Skipping comparison (use --compare flag to enable)"
fi

echo ""
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}✓ Graph update complete!${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "${YELLOW}Generated files:${NC}"
echo "  • Graph:   $LATEST_GRAPH"
echo "  • Report:  $LATEST_REPORT"
echo ""
echo -e "${YELLOW}Quick links:${NC}"
echo "  • Current: graph_output/current_graph.json"
echo "  • Previous: graph_output/previous_graph.json"
echo "  • HTML Report: graph_output/current_report.html"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  • View HTML report: open graph_output/current_report.html"
echo "  • Compare with previous: ./update_graph.sh $REPO_PATH --compare"
echo "  • Visualize: Import current_graph.json.graphml to Cytoscape"
echo ""
