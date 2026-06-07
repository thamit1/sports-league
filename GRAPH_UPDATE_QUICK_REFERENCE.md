# Quick Reference: Graph Update Workflow

## Daily Development

### After Making Code Changes

**Linux/Mac:**
```bash
./update_graph.sh backend
```

**Windows:**
```batch
update_graph.bat backend
```

**What happens:**
- ✓ Backs up previous graph
- ✓ Analyzes your code
- ✓ Generates new JSON, GraphML, HTML
- ✓ Displays statistics

---

## Major Changes or Refactoring

### Before and After Comparison

**Linux/Mac:**
```bash
# Before refactoring
./update_graph.sh backend
cp graph_output/current_graph.json graph_output/before_refactor.json

# ... make your changes ...

# After refactoring
./update_graph.sh backend --compare
```

**Windows:**
```batch
# Before refactoring
update_graph.bat backend
copy graph_output\current_graph.json graph_output\before_refactor.json

# ... make your changes ...

# After refactoring
update_graph.bat backend /compare
```

**Output: Detailed report of all changes**
- New files/classes/functions
- Removed code
- New dependencies
- Changed metrics

---

## Version Control Integration

### Keep Graphs in Git

```bash
# Add to .gitignore (optional, if not tracking graphs)
# echo "graph_output/graph_*.json" >> .gitignore

# Track only current/previous
git add graph_output/current_graph.json graph_output/previous_graph.json
git add graph_output/comparison_*.txt
git commit -m "Update knowledge graph"
git push
```

---

## Automated Workflow

### Git Post-Commit Hook (Optional)

Create `.git/hooks/post-commit`:

```bash
#!/bin/bash
./update_graph.sh backend 2>/dev/null &
```

Make executable:
```bash
chmod +x .git/hooks/post-commit
```

Now graphs auto-update after each commit!

---

## Output Files

After running update script:

| File | Purpose |
|------|---------|
| `current_graph.json` | Latest full graph (use for analysis) |
| `previous_graph.json` | Previous version (for comparison) |
| `current_report.html` | Visual summary (open in browser) |
| `comparison_*.txt` | Change reports (if --compare used) |
| `graph_YYYYMMDD_*.graphml` | For Cytoscape visualization |

---

## Viewing Results

### HTML Report (Easiest)
```bash
# Linux/Mac
open graph_output/current_report.html

# Windows
start graph_output\current_report.html
```

Shows:
- File/class/function counts
- Top imported modules
- Graph statistics

### Interactive Visualization (Advanced)

1. **Open Cytoscape** (free, online at cytoscape.org)
2. **File → Open**
3. **Select:** `graph_output/current_graph.graphml`
4. **Explore:** Click nodes, see relationships

---

## Troubleshooting

### Script Won't Run (Windows)
```batch
# Try with python explicitly
python graph_generator.py backend graph_output

# Or check Python version
python --version
```

### Script Won't Run (Linux/Mac)
```bash
# Make executable first time only
chmod +x update_graph.sh
chmod +x run_graph_generator.py

# Then run
./update_graph.sh backend
```

### Missing `compare_graphs.py`
Make sure all Python files are in the same directory:
- `graph_generator.py`
- `compare_graphs.py` 
- `update_graph.sh` (or `.bat`)

### No Changes Detected
First time? That's normal - just creating baseline.
No changes in code? Previous and current will be identical.

---

## Common Tasks

### Compare Two Different Versions

```bash
python compare_graphs.py graph_output/previous_graph.json graph_output/current_graph.json
```

### See What Files Changed

```bash
# From comparison report
cat graph_output/comparison_*.txt | grep -A 50 "FILE CHANGES"
```

### Find Most Important Files

```bash
# From HTML report - shows most imported/dependent files
open graph_output/current_report.html
```

### Export for Sharing

```bash
# All graphs ready to share
zip -r knowledge_graph_export.zip graph_output/
```

---

## Tips

✅ **Run after big commits**
```bash
git commit -m "Add new feature"
./update_graph.sh backend --compare
```

✅ **Keep previous graph backed up**
- Script does this automatically
- Accessible as `previous_graph.json`

✅ **Use for code review**
- Show new dependencies in PR
- Demonstrate architecture changes

✅ **Track over time**
- Keep dated copies for evolution tracking
- Run weekly/monthly for insights

❌ **Don't** manually edit JSON files
- Always regenerate with script

❌ **Don't** rely only on current graph
- Always keep previous for comparison

---

## Need Help?

1. Check HTML report: `graph_output/current_report.html`
2. Read full docs: `GRAPH_GENERATOR_README.md`
3. View comparison: `graph_output/comparison_*.txt`
4. Inspect JSON: `cat graph_output/current_graph.json | python -m json.tool`

---

## One-Liners

```bash
# Quick update and compare
./update_graph.sh backend --compare && cat graph_comparison_report.txt

# Get file count
python -c "import json; d=json.load(open('graph_output/current_graph.json')); print(f\"Files: {d['metadata']['stats']['files_analyzed']}\")"

# List all new imports from comparison
grep "New dependencies" graph_output/comparison_*.txt -A 20
```
