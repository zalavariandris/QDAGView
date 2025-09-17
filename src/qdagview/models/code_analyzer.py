
import ast
import copy


class CodeAnalyzer:
    """
    Analyzes Python code to identify unbound variables and perform transformations.
    
    This class provides efficient analysis by caching the parsed AST and reusing it
    for multiple operations on the same code.
    """
    
    def __init__(self, code: str = ""):
        """
        Initialize the analyzer with Python code.
        
        Args:
            code: Python code as a string
            
        Raises:
            SyntaxError: If the code contains invalid Python syntax
        """
        self._code = ""
        self._tree = None
        self._unbound_vars = None
        if code:
            self.set_code(code)
    
    def set_code(self, code: str) -> None:
        """
        Set new code and invalidate cached analysis.
        
        Args:
            code: Python code as a string
            
        Raises:
            SyntaxError: If the code contains invalid Python syntax
        """
        try:
            self._tree = ast.parse(code)
            self._code = code
            self._unbound_vars = None  # Invalidate cache
        except SyntaxError as e:
            raise SyntaxError(f"Invalid Python syntax: {e}")
    
    @property
    def code(self) -> str:
        """Get the current code."""
        return self._code
    
    def get_unbound_nodes(self) -> list[str]:
        """
        Get unbound variable names from the current code.
        
        Returns:
            List of unbound variable names in order of first appearance
        """
        if self._tree is None:
            raise ValueError("No code has been set")
        
        # Return cached result if available
        if self._unbound_vars is not None:
            return self._unbound_vars[:]  # Return a copy
        
        # Sets to store variable names
        assigned: set[str] = set()
        used: list[str] = []  # Changed to list to preserve order
        used_set: set[str] = set()  # Keep set for O(1) lookup

        # Recursive AST traversal to maintain order
        def visit_node(node):
            if isinstance(node, ast.Name):
                if isinstance(node.ctx, ast.Load):  # This is a variable being used
                    if node.id not in assigned and node.id not in used_set:
                        used.append(node.id)
                        used_set.add(node.id)
                        
                elif isinstance(node.ctx, ast.Store):  # This is a variable being assigned
                    assigned.add(node.id)
            
            # Handle comprehensions - variables bound in comprehensions are local
            elif isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
                # Save current assigned state
                old_assigned = assigned.copy()
                
                # Add comprehension variables to assigned set temporarily
                for generator in node.generators:
                    if isinstance(generator.target, ast.Name):
                        assigned.add(generator.target.id)
                    # Handle tuple unpacking in comprehensions
                    elif isinstance(generator.target, ast.Tuple):
                        for elt in generator.target.elts:
                            if isinstance(elt, ast.Name):
                                assigned.add(elt.id)
                
                # Visit child nodes
                for child in ast.iter_child_nodes(node):
                    visit_node(child)
                
                # Restore assigned state
                assigned.clear()
                assigned.update(old_assigned)
                return
            
            # Visit child nodes in order
            for child in ast.iter_child_nodes(node):
                visit_node(child)
        
        visit_node(self._tree)

        # Unbound variables are used variables that are not assigned
        unbound = [var for var in used if var not in assigned]
        
        # Cache the result
        self._unbound_vars = unbound
        return unbound[:]  # Return a copy
    
    def replace_unbound_nodes(self, new_names: dict[str, str]) -> str:
        """
        Replace unbound variable names in the current code with new names.
        
        Args:
            new_names: Dictionary mapping old variable names to new variable names
            
        Returns:
            The modified Python code with replaced variable names
        """
        if self._tree is None:
            raise ValueError("No code has been set")
        
        # Get the set of unbound variables
        unbound_vars = set(self.get_unbound_nodes())
        
        # Create a transformer to replace variable names
        class VariableReplacer(ast.NodeTransformer):
            def visit_Name(self, node):
                # Only replace if it's an unbound variable being loaded (used)
                if (isinstance(node.ctx, ast.Load) and 
                    node.id in unbound_vars and 
                    node.id in new_names):
                    # Create a new Name node with the replacement name
                    new_node = ast.Name(id=new_names[node.id], ctx=node.ctx)
                    return ast.copy_location(new_node, node)
                return node
        
        # Apply the transformation to a copy of the tree
        transformer = VariableReplacer()
        new_tree = transformer.visit(copy.deepcopy(self._tree))
        
        # Convert back to source code
        return ast.unparse(new_tree)