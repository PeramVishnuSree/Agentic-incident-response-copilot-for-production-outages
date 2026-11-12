"""Service dependency graph loader (requirement E3)."""

from __future__ import annotations

from pathlib import Path

import networkx as nx
import yaml


def load_dependency_graph(path: str | Path) -> nx.DiGraph:
    """Load a YAML topology into a directed NetworkX graph."""
    data = yaml.safe_load(Path(path).read_text())
    g: nx.DiGraph = nx.DiGraph()
    services = data.get("services", {})
    for service, meta in services.items():
        g.add_node(service)
        for callee in meta.get("calls", []) or []:
            g.add_edge(service, callee)
    return g


def connected_in_undirected(a: str, b: str, graph: nx.DiGraph) -> bool:
    """True if a and b are the same node or connected ignoring edge direction."""
    if a == b:
        return True
    if a not in graph or b not in graph:
        return False
    undirected = graph.to_undirected()
    return nx.has_path(undirected, a, b)


def are_connected(graph: nx.DiGraph, a: str, b: str) -> bool:
    """Compatibility wrapper: (graph, a, b) argument order."""
    return connected_in_undirected(a, b, graph)


def upstreamness(service: str, graph: nx.DiGraph) -> float:
    """Higher score for services that many others depend on (more upstream).

    Approximated as the fraction of other nodes that can reach this service
    in the reverse graph (callers -> this service).
    """
    if service not in graph or graph.number_of_nodes() <= 1:
        return 0.0
    reverse = graph.reverse(copy=False)
    reachable = nx.descendants(reverse, service)
    return len(reachable) / (graph.number_of_nodes() - 1)
