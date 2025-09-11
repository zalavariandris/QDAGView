import networkx as nx
from dataclasses import dataclass
from typing import Set, Self, Hashable, Dict, Tuple, Any
# change data structure

@dataclass
class Change:
    ...



def diff(G1:nx.MultiDiGraph, G2:nx.MultiDiGraph)->Change:
    
    ...



def patch(G:nx.MultiDiGraph, changes:GraphChange):
    """Apply changes to the graph G in place."""
    ...