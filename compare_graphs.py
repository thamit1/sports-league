"""
Graph Comparison Utility

Compare two knowledge graphs to understand how a repository has evolved.
Useful for:
- Tracking architectural changes over time
- Identifying new dependencies
- Finding removed or refactored code
- Analyzing project growth

Usage:
    python compare_graphs.py graph_v1.json graph_v2.json
"""

import json
import sys
from pathlib import Path
from collections import defaultdict
from typing import Dict, List, Set, Tuple


class GraphComparator:
    """Compare two repository knowledge graphs"""
    
    def __init__(self, graph1_path: str, graph2_path: str):
        self.graph1 = self._load_graph(graph1_path)
        self.graph2 = self._load_graph(graph2_path)
        self.graph1_path = graph1_path
        self.graph2_path = graph2_path
    
    def _load_graph(self, path: str) -> Dict:
        """Load a graph JSON file"""
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _extract_by_type(self, graph: Dict, node_type: str) -> Set[str]:
        """Extract all nodes of a specific type"""
        return {
            node['name']
            for node in graph['nodes']
            if node['node_type'] == node_type
        }
    
    def _extract_edges_by_type(self, graph: Dict, edge_type: str) -> Set[Tuple[str, str]]:
        """Extract all edges of a specific type"""
        return {
            (edge['source'], edge['target'])
            for edge in graph['edges']
            if edge['edge_type'] == edge_type
        }
    
    def compare_stats(self) -> Dict:
        """Compare basic statistics"""
        stats1 = self.graph1['metadata']['stats']
        stats2 = self.graph2['metadata']['stats']
        
        comparison = {}
        for key in stats1:
            v1 = stats1[key]
            v2 = stats2[key]
            delta = v2 - v1
            pct = (delta / v1 * 100) if v1 > 0 else 0
            
            comparison[key] = {
                'graph1': v1,
                'graph2': v2,
                'delta': delta,
                'pct_change': round(pct, 2)
            }
        
        return comparison
    
    def compare_files(self) -> Dict:
        """Compare file changes"""
        files1 = self._extract_by_type(self.graph1, 'file')
        files2 = self._extract_by_type(self.graph2, 'file')
        
        return {
            'total_graph1': len(files1),
            'total_graph2': len(files2),
            'new_files': list(files2 - files1),
            'removed_files': list(files1 - files2),
            'unchanged_files': list(files1 & files2),
        }
    
    def compare_classes(self) -> Dict:
        """Compare class definitions"""
        classes1 = self._extract_by_type(self.graph1, 'class')
        classes2 = self._extract_by_type(self.graph2, 'class')
        
        return {
            'total_graph1': len(classes1),
            'total_graph2': len(classes2),
            'new_classes': list(classes2 - classes1),
            'removed_classes': list(classes1 - classes2),
            'unchanged_classes': list(classes1 & classes2),
        }
    
    def compare_functions(self) -> Dict:
        """Compare function definitions"""
        funcs1 = self._extract_by_type(self.graph1, 'function')
        funcs2 = self._extract_by_type(self.graph2, 'function')
        
        return {
            'total_graph1': len(funcs1),
            'total_graph2': len(funcs2),
            'new_functions': list(funcs2 - funcs1),
            'removed_functions': list(funcs1 - funcs2),
            'unchanged_functions': list(funcs1 & funcs2),
        }
    
    def compare_imports(self) -> Dict:
        """Compare imported modules"""
        imports1 = self._extract_edges_by_type(self.graph1, 'imports')
        imports2 = self._extract_edges_by_type(self.graph2, 'imports')
        
        # Extract module names
        modules1 = {target for _, target in imports1}
        modules2 = {target for _, target in imports2}
        
        return {
            'total_graph1': len(modules1),
            'total_graph2': len(modules2),
            'new_modules': sorted(list(modules2 - modules1)),
            'removed_modules': sorted(list(modules1 - modules2)),
            'stable_modules': sorted(list(modules1 & modules2)),
        }
    
    def generate_report(self) -> str:
        """Generate a comprehensive comparison report"""
        report = []
        report.append("=" * 70)
        report.append("REPOSITORY KNOWLEDGE GRAPH COMPARISON")
        report.append("=" * 70)
        report.append("")
        
        report.append(f"Graph 1: {self.graph1_path}")
        report.append(f"Graph 2: {self.graph2_path}")
        report.append("")
        
        # Statistics comparison
        report.append("STATISTICS COMPARISON")
        report.append("-" * 70)
        stats_comp = self.compare_stats()
        
        report.append(f"{'Metric':<25} {'Graph 1':>12} {'Graph 2':>12} {'Change':>12}")
        report.append("-" * 70)
        
        for metric, values in stats_comp.items():
            change = f"{values['delta']:+d} ({values['pct_change']:+.1f}%)"
            report.append(
                f"{metric:<25} {values['graph1']:>12} {values['graph2']:>12} {change:>12}"
            )
        report.append("")
        
        # Files
        report.append("FILE CHANGES")
        report.append("-" * 70)
        files = self.compare_files()
        report.append(f"Total files: {files['total_graph1']} → {files['total_graph2']}")
        
        if files['new_files']:
            report.append(f"\nNew files ({len(files['new_files'])}):")
            for f in sorted(files['new_files'])[:10]:
                report.append(f"  + {f}")
            if len(files['new_files']) > 10:
                report.append(f"  ... and {len(files['new_files']) - 10} more")
        
        if files['removed_files']:
            report.append(f"\nRemoved files ({len(files['removed_files'])}):")
            for f in sorted(files['removed_files'])[:10]:
                report.append(f"  - {f}")
            if len(files['removed_files']) > 10:
                report.append(f"  ... and {len(files['removed_files']) - 10} more")
        report.append("")
        
        # Classes
        report.append("CLASS CHANGES")
        report.append("-" * 70)
        classes = self.compare_classes()
        report.append(f"Total classes: {classes['total_graph1']} → {classes['total_graph2']}")
        
        if classes['new_classes']:
            report.append(f"\nNew classes ({len(classes['new_classes'])}):")
            for c in sorted(classes['new_classes'])[:10]:
                report.append(f"  + {c}")
            if len(classes['new_classes']) > 10:
                report.append(f"  ... and {len(classes['new_classes']) - 10} more")
        
        if classes['removed_classes']:
            report.append(f"\nRemoved classes ({len(classes['removed_classes'])}):")
            for c in sorted(classes['removed_classes'])[:10]:
                report.append(f"  - {c}")
            if len(classes['removed_classes']) > 10:
                report.append(f"  ... and {len(classes['removed_classes']) - 10} more")
        report.append("")
        
        # Functions
        report.append("FUNCTION CHANGES")
        report.append("-" * 70)
        functions = self.compare_functions()
        report.append(f"Total functions: {functions['total_graph1']} → {functions['total_graph2']}")
        report.append("")
        
        # Imports
        report.append("MODULE DEPENDENCY CHANGES")
        report.append("-" * 70)
        imports = self.compare_imports()
        report.append(f"Total modules: {imports['total_graph1']} → {imports['total_graph2']}")
        
        if imports['new_modules']:
            report.append(f"\nNew dependencies ({len(imports['new_modules'])}):")
            for m in imports['new_modules'][:10]:
                report.append(f"  + {m}")
            if len(imports['new_modules']) > 10:
                report.append(f"  ... and {len(imports['new_modules']) - 10} more")
        
        if imports['removed_modules']:
            report.append(f"\nRemoved dependencies ({len(imports['removed_modules'])}):")
            for m in imports['removed_modules'][:10]:
                report.append(f"  - {m}")
            if len(imports['removed_modules']) > 10:
                report.append(f"  ... and {len(imports['removed_modules']) - 10} more")
        report.append("")
        
        report.append("=" * 70)
        report.append("END OF REPORT")
        report.append("=" * 70)
        
        return "\n".join(report)


def main():
    """Main entry point"""
    if len(sys.argv) < 3:
        print("Usage: python compare_graphs.py <graph1.json> <graph2.json>")
        print("\nExample:")
        print("  python compare_graphs.py graph_baseline.json graph_current.json")
        sys.exit(1)
    
    graph1_path = sys.argv[1]
    graph2_path = sys.argv[2]
    
    # Verify files exist
    if not Path(graph1_path).exists():
        print(f"Error: {graph1_path} not found")
        sys.exit(1)
    
    if not Path(graph2_path).exists():
        print(f"Error: {graph2_path} not found")
        sys.exit(1)
    
    # Compare
    comparator = GraphComparator(graph1_path, graph2_path)
    report = comparator.generate_report()
    
    # Print report
    print(report)
    
    # Optionally save report
    output_file = "graph_comparison_report.txt"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(report)
    
    print(f"\nReport saved to: {output_file}")


if __name__ == "__main__":
    main()
