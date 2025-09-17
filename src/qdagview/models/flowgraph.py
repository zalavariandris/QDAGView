from __future__ import annotations
from typing import List, DefaultDict, Iterable

from dataclasses import dataclass
from collections import defaultdict

from ..utils import bfs
from ..utils.unique import make_unique_id

from .code_analyzer import CodeAnalyzer


class ExpressionOperator:
    def __init__(self, expression: str = "Operator", name:str|None = None):
        self._expression = expression
        self._inlets: List[Inlet] = [] 
        self._update_inlets()
        self._outlets: List[Outlet] = [Outlet("result", self)]
        self._name = name if name else make_unique_id()

    def expression(self) -> str:
        """Return the expression of the operator."""
        return self._expression
    
    def _update_inlets(self):
        """Reset the inlets based on the current expression."""
          # Validate syntax
        variables = CodeAnalyzer(self._expression).get_unbound_nodes()

        # Add new inlets if needed
        if len(variables) > len(self._inlets):
            for var in variables:
                if var not in [inlet.name for inlet in self._inlets]:
                    self._inlets.append(Inlet(var, self))

        # Remove any inlets that are no longer needed
        if len(variables) < len(self._inlets):
            for inlet in self._inlets[len(variables):]:
                if inlet.name not in variables:
                    self._inlets.remove(inlet)

        # update inlet names
        for var, inlet in zip(variables, self._inlets):
            inlet.name = var
        
    def setExpression(self, expression:str):
        """Set the expression of the operator."""
        self._expression = expression
        self._update_inlets()

    def name(self) -> str:
        """Return the name of the operator."""
        return self._name
    
    def setName(self, name:str):
        """Set the name of the operator."""
        self._name = name

    def __call__(self, *args, **kwds):
        ...

    def inlets(self) -> List[Inlet]:
        """Return the list of inlets for this operator."""
        return self._inlets
    
    def outlets(self) -> List[Outlet]:
        """Return the list of outlets for this operator."""
        return self._outlets
    
    def __str__(self):
        return f"{self._name}[{self._expression}]"

    def __repr__(self):
        return f"Operator({self._expression})"
    
    def evaluate(self, *args, **kwargs) -> str:
        """Evaluate the operator."""
        return f"Evaluating {self._expression}"


@dataclass()
class Inlet:
    name: str = "Inlet"
    operator: ExpressionOperator|None = None

    def __str__(self):
        return f"{self.name}"

    def __repr__(self):
        return f"Inlet({self.operator}.{self.name})"
    
    def __hash__(self):
        return hash((self.name, self.operator))

    
@dataclass()
class Outlet:
    name: str = "Outlet"
    operator: ExpressionOperator|None = None

    def __str__(self):
        return f"{self.name}"
    
    def __repr__(self):
        return f"Outlet({self.operator}.{self.name})"

    def __hash__(self):
        return hash((self.name, self.operator))

@dataclass()
class Link:
    source: Outlet = None
    target: Inlet = None

    def __str__(self):
        return  f"Link({self.source} -> {self.target})"


class FlowGraph:
    def __init__(self, name: str = "FlowGraph"):
        self._name = name
        self._operators: List[ExpressionOperator] = []
        self._in_links: DefaultDict[Inlet, List[Link]] = defaultdict(list)
        self._out_links: DefaultDict[Outlet, List[Link]] = defaultdict(list)

    ## CREATE
    def createOperator(self, expression: str, name: str) -> ExpressionOperator:
        """Create a new operator and add it to the graph."""
        operator = ExpressionOperator(expression, name)
        self._operators.append(operator)
        return operator

    ## READ
    def operators(self) -> List[ExpressionOperator]:
        """Return the list of nodes in the graph."""
        return self._operators
    
    def inlets(self, operator: ExpressionOperator) -> List[Inlet]:
        return operator.inlets()

    def outlets(self, op: ExpressionOperator) -> List[Outlet]:
        """Return the list of outlets for the given operator."""
        return op.outlets()

    def inLinks(self, inlet: Inlet) -> List[Link]:
        assert isinstance(inlet, Inlet), "Inlet must be an instance of Inlet"
        return [link for link in self._in_links[inlet]]

    def outLinks(self, outlet: Outlet) -> List[Link]:
        assert isinstance(outlet, Outlet), "Outlet must be an instance of Outlet"
        return [link for link in self._out_links[outlet]]

    def links(self):
        for links in self._in_links.values():
            for link in links:
                yield link

    def ancestors(self, node: ExpressionOperator) -> Iterable[ExpressionOperator]:
        """
        Get all dependencies of the given operator, in topological order.
        The current implementation uses breadth-first search, but it is not guaranteed.
        """
        assert node in self._operators
        def inputNodes(node: ExpressionOperator) -> Iterable[ExpressionOperator]:
            """Get all input nodes of the given operator."""
            for inlet in node.inlets():
                for link in self.inLinks(inlet):
                    if link.source.operator is not None:
                        yield link.source.operator
        
        for n in bfs(node, children=inputNodes):
            yield n

    def descendants(self, node: ExpressionOperator) -> Iterable[ExpressionOperator]:
        """Get all descendants of the given operator."""
        assert node in self._operators
        def outputNodes(node: ExpressionOperator) -> Iterable[ExpressionOperator]:
            """Get all output nodes of the given operator."""
            for outlet in node.outlets():
                for link in self._out_links[outlet]:
                    if link.target and link.target.operator is not None:
                        yield link.target.operator
        
        for n in bfs(node, children=outputNodes):
            yield n

    def evaluate(self, node: ExpressionOperator) -> str:
        """Evaluate the graph starting from the given node."""
        assert node in self._operators
        print(f"Evaluating graph starting from node: {node}")
        result = ""
        ancestors = list(self.ancestors(node))
        print(f"Evaluating item: {node}, ancestors: {ancestors}")
        for op in ancestors:
            result += f"{op.expression()}\n"
        return result
    
    def buildScript(self, node: ExpressionOperator) -> str:
        """Build a script representing the graph starting from the given node."""
        assert node in self._operators
        script_text = ""
        ancestors = self.ancestors(node)

        for op in reversed(list(ancestors)):
            match op:
                case ExpressionOperator():
                    params = dict()
                    inlets = op.inlets()  # Ensure inlets are populated
                    for inlet in inlets:
                        links = self.inLinks(inlet)
                        outlets = [link.source for link in links if link.source is not None]
                        if len(outlets) > 0:
                            params[inlet.name] = outlets[0].operator.name()
                        else:
                            params[inlet.name] = f"_{inlet.name}_"  # or some default value

                    expression_with_inputs = CodeAnalyzer(op.expression()).replace_unbound_nodes(params)

                    line = f"{op.name()} = {expression_with_inputs}"
                    
                    script_text += f"{line}\n"
                case "FunctionOperator()":
                    line = f"{op.name()} = {op.expression()}({', '.join(f'{k}={v}' for k, v in params.items())})"
                    script_text += f"{line}\n"
                case _:
                    continue

        return script_text

    ## CREATE
    def insertOperator(self, pos:int, operator: ExpressionOperator) -> bool:
        """Add an operator to the graph at the specified index."""
        self._operators.insert(pos, operator)
        return True
    
    def appendOperator(self, operator: ExpressionOperator) -> bool:
        pos = len(self._operators)
        self.insertOperator(pos, operator)

    def insertLink(self, index:int, source:Outlet|None, target:Inlet) -> Link | None:
        """Link an outlet of a source operator to an inlet of a target operator."""
        link = Link(source, target)
        if source is not None:
            self._out_links[source].append(link)
        self._in_links[target].insert(index, link)
        return link
    
    ## DELETE
    def removeOperator(self, operator: ExpressionOperator) -> bool:
        """Remove an operator from the graph."""
        if operator in self._operators:
            self._operators.remove(operator)

            # Remove all links associated with this operator
            # First, collect all links to remove
            links_to_remove = []
            
            # Collect links from inlets
            for inlet in operator.inlets():
                links_to_remove.extend(self._in_links[inlet][:])  # Copy the list
            
            # Collect links from outlets
            for outlet in operator.outlets():
                links_to_remove.extend(self._out_links[outlet][:])  # Copy the list
            
            # Remove each link properly
            for link in links_to_remove:
                self.removeLink(link)
            
            # Clean up the dictionaries
            for inlet in operator.inlets():
                self._in_links.pop(inlet, None)

            for outlet in operator.outlets():
                self._out_links.pop(outlet, None)

            return True
        return False
    
    def removeLink(self, link: Link) -> bool:
        """Remove a link from the graph."""
        if link.source is not None:
            self._out_links[link.source].remove(link)
        if link.target is not None:
            self._in_links[link.target].remove(link)
        return True

    ## UPDATE
    def setLinkSource(self, link: Link, source: Outlet | None) -> bool:
        """Relink an existing link to a new source outlet."""
        if link.source is not None:
            self._out_links[link.source].remove(link)
        if source is not None:
            self._out_links[source].append(link)
        link.source = source
        return True

import networkx as nx
def flowgraph_to_nx(graph: FlowGraph) -> nx.MultiDiGraph:
    G = nx.MultiDiGraph()
    for node in graph.operators():
        G.add_node(node.name(), 
                   expression=node.expression(), 
                   inlets=[_.name for _ in node.inlets()])
        
    for link in graph.links():
        G.add_edge(link.source.operator.name(), link.target.operator.name(), inlet=link.target.name)

    return G