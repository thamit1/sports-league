"""
Code Repository Knowledge Graph Generator

This module analyzes a Python repository and generates a knowledge graph that maps:
- Files and their relationships (imports, dependencies)
- Classes and their inheritance hierarchies
- Functions and their call relationships
- Module structure and organization

The output can be used for:
- Repository comparison and analysis
- Dependency visualization
- Impact analysis for refactoring
- Architecture documentation

Design principles:
- Modular: Easy to extend with new analyzers
- Incremental: Can compare graphs over time
- Multiple outputs: JSON, GraphML, HTML visualization
"""

import ast
import json
import networkx as nx
from pathlib import Path
from collections import defaultdict
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Set, Tuple, Optional, Any
from enum import Enum
import logging
from datetime import datetime
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class NodeType(Enum):
    """Types of nodes in the knowledge graph"""
    FILE = "file"
    MODULE = "module"
    CLASS = "class"
    FUNCTION = "function"
    VARIABLE = "variable"


class EdgeType(Enum):
    """Types of edges in the knowledge graph"""
    IMPORTS = "imports"
    CONTAINS = "contains"
    INHERITS = "inherits"
    CALLS = "calls"
    USES = "uses"
    DEFINES = "defines"
    DEPENDS_ON = "depends_on"


@dataclass
class Node:
    """Represents a node in the knowledge graph"""
    id: str
    name: str
    node_type: NodeType
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    doc_string: Optional[str] = None
    metrics: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert node to dictionary"""
        data = asdict(self)
        data['node_type'] = self.node_type.value
        return data


@dataclass
class Edge:
    """Represents an edge in the knowledge graph"""
    source: str
    target: str
    edge_type: EdgeType
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        """Convert edge to dictionary"""
        return {
            'source': self.source,
            'target': self.target,
            'edge_type': self.edge_type.value,
            'metadata': self.metadata
        }


class ASTAnalyzer(ast.NodeVisitor):
    """Analyzes Python AST to extract code structure"""
    
    def __init__(self, file_path: str, file_id: str):
        self.file_path = file_path
        self.file_id = file_id
        self.current_class = None
        self.current_function = None
        
        self.nodes: List[Node] = []
        self.edges: List[Edge] = []
        self.imports: Set[str] = set()
        self.dependencies: Set[str] = set()
    
    def add_node(self, node_id: str, name: str, node_type: NodeType, **kwargs) -> Node:
        """Add a node to the graph"""
        node = Node(
            id=node_id,
            name=name,
            node_type=node_type,
            file_path=self.file_path,
            **kwargs
        )
        self.nodes.append(node)
        return node
    
    def add_edge(self, source: str, target: str, edge_type: EdgeType, **metadata):
        """Add an edge to the graph"""
        edge = Edge(source, target, edge_type, metadata)
        self.edges.append(edge)
    
    def visit_Import(self, node: ast.Import):
        """Handle import statements"""
        for alias in node.names:
            module_name = alias.name
            self.imports.add(module_name)
            self.dependencies.add(module_name)
            
            # Create edge from this file to imported module
            module_id = f"module:{module_name}"
            self.add_edge(
                self.file_id,
                module_id,
                EdgeType.IMPORTS,
                module=module_name,
                line=node.lineno
            )
        
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node: ast.ImportFrom):
        """Handle from...import statements"""
        if node.module:
            module_name = node.module
            self.imports.add(module_name)
            self.dependencies.add(module_name)
            
            module_id = f"module:{module_name}"
            self.add_edge(
                self.file_id,
                module_id,
                EdgeType.IMPORTS,
                module=module_name,
                items=[alias.name for alias in node.names],
                line=node.lineno
            )
        
        self.generic_visit(node)
    
    def visit_ClassDef(self, node: ast.ClassDef):
        """Handle class definitions"""
        class_id = f"{self.file_id}:class:{node.name}"
        self.add_node(
            class_id,
            node.name,
            NodeType.CLASS,
            line_number=node.lineno,
            doc_string=ast.get_docstring(node)
        )
        
        # Add "contains" relationship from file
        self.add_edge(self.file_id, class_id, EdgeType.CONTAINS)
        
        # Handle inheritance
        for base in node.bases:
            if isinstance(base, ast.Name):
                base_id = f"{self.file_id}:class:{base.id}"
                self.add_edge(class_id, base_id, EdgeType.INHERITS)
            elif isinstance(base, ast.Attribute):
                # Handle inheritance from other modules
                base_name = self._get_full_name(base)
                self.add_edge(class_id, base_name, EdgeType.INHERITS)
        
        # Visit methods in the class
        old_class = self.current_class
        self.current_class = class_id
        for item in node.body:
            self.visit(item)
        self.current_class = old_class
    
    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Handle function and method definitions"""
        func_id = f"{self.file_id}:function:{node.name}"
        if self.current_class:
            func_id = f"{self.current_class}:method:{node.name}"
        
        self.add_node(
            func_id,
            node.name,
            NodeType.FUNCTION,
            line_number=node.lineno,
            doc_string=ast.get_docstring(node)
        )
        
        # Add relationship to parent (file or class)
        parent = self.current_class or self.file_id
        self.add_edge(parent, func_id, EdgeType.CONTAINS)
        
        # Analyze function body for calls and variable usage
        old_function = self.current_function
        self.current_function = func_id
        for item in node.body:
            self.visit(item)
        self.current_function = old_function
    
    def visit_Call(self, node: ast.Call):
        """Handle function calls"""
        if self.current_function:
            call_name = self._get_full_name(node.func)
            if call_name:
                call_id = f"call:{call_name}"
                self.add_edge(
                    self.current_function,
                    call_id,
                    EdgeType.CALLS,
                    name=call_name
                )
        
        self.generic_visit(node)
    
    def _get_full_name(self, node) -> str:
        """Extract full name from an AST node"""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value = self._get_full_name(node.value)
            return f"{value}.{node.attr}" if value else node.attr
        return ""
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        """Handle async function definitions"""
        self.visit_FunctionDef(node)


class RepositoryAnalyzer:
    """Main analyzer for a Python repository"""
    
    def __init__(self, repo_path: str, exclude_dirs: Optional[List[str]] = None):
        self.repo_path = Path(repo_path)
        self.exclude_dirs = exclude_dirs or ['.git', '__pycache__', '.venv', 'venv', 'node_modules', '.pytest_cache']
        
        self.nodes: Dict[str, Node] = {}
        self.edges: List[Edge] = []
        self.graph = nx.DiGraph()
        
        self.stats = {
            'files_analyzed': 0,
            'classes_found': 0,
            'functions_found': 0,
            'imports_found': 0,
            'errors': 0,
        }
    
    def should_skip_path(self, path: Path) -> bool:
        """Check if path should be skipped"""
        return any(excluded in path.parts for excluded in self.exclude_dirs)
    
    def analyze(self):
        """Analyze the entire repository"""
        logger.info(f"Starting analysis of {self.repo_path}")
        
        # Add root node
        root_id = f"repo:{self.repo_path.name}"
        self.nodes[root_id] = Node(
            id=root_id,
            name=self.repo_path.name,
            node_type=NodeType.MODULE,
            file_path=str(self.repo_path)
        )
        
        # Find all Python files
        python_files = list(self.repo_path.rglob("*.py"))
        python_files = [f for f in python_files if not self.should_skip_path(f)]
        
        logger.info(f"Found {len(python_files)} Python files")
        
        for py_file in python_files:
            self._analyze_file(py_file, root_id)
        
        # Build networkx graph
        self._build_graph()
        
        logger.info(f"Analysis complete. Stats: {self.stats}")
    
    def _analyze_file(self, file_path: Path, root_id: str):
        """Analyze a single Python file"""
        try:
            file_id = f"file:{file_path.relative_to(self.repo_path)}"
            
            # Add file node
            self.nodes[file_id] = Node(
                id=file_id,
                name=file_path.name,
                node_type=NodeType.FILE,
                file_path=str(file_path)
            )
            
            # Connect to root
            self.edges.append(Edge(root_id, file_id, EdgeType.CONTAINS))
            
            # Read and parse file
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            tree = ast.parse(content, filename=str(file_path))
            
            # Analyze with AST visitor
            analyzer = ASTAnalyzer(str(file_path), file_id)
            analyzer.visit(tree)
            
            # Collect nodes and edges
            for node in analyzer.nodes:
                self.nodes[node.id] = node
                if node.node_type == NodeType.CLASS:
                    self.stats['classes_found'] += 1
                elif node.node_type == NodeType.FUNCTION:
                    self.stats['functions_found'] += 1
            
            self.edges.extend(analyzer.edges)
            self.stats['imports_found'] += len(analyzer.imports)
            self.stats['files_analyzed'] += 1
            
        except SyntaxError as e:
            logger.error(f"Syntax error in {file_path}: {e}")
            self.stats['errors'] += 1
        except Exception as e:
            logger.error(f"Error analyzing {file_path}: {e}")
            self.stats['errors'] += 1
    
    def _build_graph(self):
        """Build networkx graph from nodes and edges"""
        for node in self.nodes.values():
            self.graph.add_node(
                node.id,
                name=node.name,
                node_type=node.node_type.value,
                **node.metrics
            )
        
        for edge in self.edges:
            self.graph.add_edge(
                edge.source,
                edge.target,
                edge_type=edge.edge_type.value,
                **edge.metadata
            )
    
    def calculate_metrics(self) -> Dict[str, Any]:
        """Calculate various metrics for the graph"""
        if len(self.graph) == 0:
            return {}
        
        metrics = {
            'nodes': len(self.graph.nodes()),
            'edges': len(self.graph.edges()),
            'density': nx.density(self.graph),
            'num_strongly_connected_components': nx.number_strongly_connected_components(self.graph),
        }
        
        try:
            # Calculate centrality metrics (may be slow for large graphs)
            in_degree = dict(self.graph.in_degree())
            out_degree = dict(self.graph.out_degree())
            
            metrics['most_imported_modules'] = sorted(
                [(k, v) for k, v in in_degree.items() if 'module:' in k],
                key=lambda x: x[1],
                reverse=True
            )[:5]
            
            metrics['most_dependent_files'] = sorted(
                [(k, v) for k, v in out_degree.items() if 'file:' in k],
                key=lambda x: x[1],
                reverse=True
            )[:5]
        except Exception as e:
            logger.warning(f"Error calculating centrality metrics: {e}")
        
        return metrics
    
    def export_json(self, output_path: str):
        """Export graph to JSON format"""
        data = {
            'metadata': {
                'repo_path': str(self.repo_path),
                'generated_at': datetime.now().isoformat(),
                'stats': self.stats,
                'metrics': self.calculate_metrics(),
            },
            'nodes': [node.to_dict() for node in self.nodes.values()],
            'edges': [edge.to_dict() for edge in self.edges],
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, default=str)
        
        logger.info(f"Exported graph to {output_path}")
    
    def export_graphml(self, output_path: str):
        """Export graph to GraphML format for visualization tools"""
        # GraphML doesn't support complex types (lists, dicts), so convert to strings
        graph_copy = self.graph.copy()
        
        # Convert all attributes to strings for GraphML compatibility
        for node in graph_copy.nodes():
            for attr_name in list(graph_copy.nodes[node].keys()):
                attr_value = graph_copy.nodes[node][attr_name]
                if isinstance(attr_value, (list, dict)):
                    graph_copy.nodes[node][attr_name] = str(attr_value)
        
        for source, target in graph_copy.edges():
            for attr_name in list(graph_copy.edges[source, target].keys()):
                attr_value = graph_copy.edges[source, target][attr_name]
                if isinstance(attr_value, (list, dict)):
                    graph_copy.edges[source, target][attr_name] = str(attr_value)
        
        nx.write_graphml(graph_copy, output_path)
        logger.info(f"Exported GraphML to {output_path}")
    
    def export_html_report(self, output_path: str):
        """Export an HTML report with graph statistics"""
        metrics = self.calculate_metrics()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Repository Knowledge Graph - {self.repo_path.name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #333; }}
                h2 {{ color: #666; margin-top: 30px; }}
                table {{ border-collapse: collapse; width: 100%; max-width: 800px; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; }}
                th {{ background-color: #4CAF50; color: white; }}
                tr:nth-child(even) {{ background-color: #f2f2f2; }}
                .metric {{ font-size: 24px; font-weight: bold; color: #4CAF50; }}
            </style>
        </head>
        <body>
            <h1>Repository Knowledge Graph: {self.repo_path.name}</h1>
            <p>Generated: {datetime.now().isoformat()}</p>
            
            <h2>Overall Statistics</h2>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Files Analyzed</td><td class="metric">{self.stats['files_analyzed']}</td></tr>
                <tr><td>Classes Found</td><td class="metric">{self.stats['classes_found']}</td></tr>
                <tr><td>Functions Found</td><td class="metric">{self.stats['functions_found']}</td></tr>
                <tr><td>Imports Found</td><td class="metric">{self.stats['imports_found']}</td></tr>
                <tr><td>Parsing Errors</td><td class="metric">{self.stats['errors']}</td></tr>
            </table>
            
            <h2>Graph Metrics</h2>
            <table>
                <tr><th>Metric</th><th>Value</th></tr>
                <tr><td>Total Nodes</td><td>{metrics.get('nodes', 0)}</td></tr>
                <tr><td>Total Edges</td><td>{metrics.get('edges', 0)}</td></tr>
                <tr><td>Graph Density</td><td>{metrics.get('density', 0):.4f}</td></tr>
                <tr><td>Strongly Connected Components</td><td>{metrics.get('num_strongly_connected_components', 0)}</td></tr>
            </table>
            
            <h2>Most Imported Modules</h2>
            <table>
                <tr><th>Module</th><th>Import Count</th></tr>
        """
        
        for module, count in metrics.get('most_imported_modules', []):
            module_name = module.replace('module:', '')
            html += f"<tr><td>{module_name}</td><td>{count}</td></tr>"
        
        html += """
            </table>
            
            <h2>Most Dependent Files</h2>
            <table>
                <tr><th>File</th><th>Dependencies</th></tr>
        """
        
        for file_path, count in metrics.get('most_dependent_files', []):
            file_name = file_path.replace('file:', '')
            html += f"<tr><td>{file_name}</td><td>{count}</td></tr>"
        
        html += """
            </table>
        </body>
        </html>
        """
        
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(html)
        
        logger.info(f"Exported HTML report to {output_path}")


def main():
    """Main entry point"""
    import sys
    
    # Configuration
    repo_path = sys.argv[1] if len(sys.argv) > 1 else "."
    output_dir = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("./graph_output")
    
    # Create output directory
    output_dir.mkdir(exist_ok=True)
    
    # Analyze repository
    analyzer = RepositoryAnalyzer(repo_path)
    analyzer.analyze()
    
    # Generate outputs
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    analyzer.export_json(str(output_dir / f"graph_{timestamp}.json"))
    analyzer.export_graphml(str(output_dir / f"graph_{timestamp}.graphml"))
    analyzer.export_html_report(str(output_dir / f"report_{timestamp}.html"))
    
    print(f"\n✓ Graph generation complete!")
    print(f"  JSON: {output_dir / f'graph_{timestamp}.json'}")
    print(f"  GraphML: {output_dir / f'graph_{timestamp}.graphml'}")
    print(f"  HTML Report: {output_dir / f'report_{timestamp}.html'}")


if __name__ == "__main__":
    main()
