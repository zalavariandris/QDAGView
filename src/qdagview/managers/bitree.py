from typing import Any, Dict, List, Optional, Tuple, Iterator

class Node:
    def __init__(self, value: Any, parent: Optional["Node"] = None, index: int = 0):
        self.value = value
        self.parent = parent
        self.index = index
        self.children: List["Node"] = []

    def path(self) -> Tuple[int, ...]:
        parts = []
        node = self
        while node.parent is not None:
            parts.append(node.index)
            node = node.parent
        return tuple(reversed(parts))

class BiTree:
    def __init__(self):
        self.root = Node(None)  # dummy root
        self._value_to_node: Dict[Any, Node] = {}

    # ---------- Insert ----------
    def insert(self, path: Tuple[int, ...], value: Any):
        parent = self.root
        for comp in path[:-1]:
            parent = parent.children[comp]

        new_node = Node(value, parent, path[-1])
        parent.children.insert(path[-1], new_node)

        # update sibling indices
        for i, child in enumerate(parent.children):
            child.index = i

        self._value_to_node[value] = new_node

    # ---------- Lookup ----------
    def get(self, path: Tuple[int, ...]) -> Any:
        node = self.root
        for comp in path:
            node = node.children[comp]
        return node.value

    def index(self, value: Any) -> Optional[Tuple[int, ...]]:
        node = self._value_to_node.get(value)
        return node.path() if node else None

    # ---------- Remove ----------
    def remove(self, path: Tuple[int, ...]):
        """Remove node at path (and all its descendants) iteratively."""
        # Navigate to parent of the node to remove
        parent = self.root
        for comp in path[:-1]:
            parent = parent.children[comp]

        # Remove the target node from parent's children
        target = parent.children.pop(path[-1])

        # Update sibling indices after removal
        for i, child in enumerate(parent.children):
            child.index = i

        # Iteratively remove target and all descendants from reverse lookup
        stack = [target]
        while stack:
            current = stack.pop()
            self._value_to_node.pop(current.value, None)
            stack.extend(current.children)


    # ---------- Traversal ----------
    def items(self) -> Iterator[Tuple[Tuple[int, ...], Any]]:
        def _rec(node: Node, prefix: Tuple[int, ...]):
            for child in node.children:
                path = prefix + (child.index,)
                yield path, child.value
                yield from _rec(child, path)
        yield from _rec(self.root, ())
