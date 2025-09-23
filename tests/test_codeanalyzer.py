import pytest
from qdagview.models.code_analyzer import CodeAnalyzer

def test_initial_expression():
    assert CodeAnalyzer("a+b").get_unbound_nodes()   == ["a", "b"]
    assert CodeAnalyzer("x*x").get_unbound_nodes()   == ["x"]
    assert CodeAnalyzer("a + b").get_unbound_nodes() == ["a", "b"]
    assert CodeAnalyzer("text").get_unbound_nodes()  == ["text"]
    assert CodeAnalyzer("x*y+a").get_unbound_nodes() == ["x", "y", "a"]
    assert CodeAnalyzer("a*x+a").get_unbound_nodes() == ["a", "x"]

def test_expression_with_values():
    assert CodeAnalyzer("None").get_unbound_nodes() == []
    assert CodeAnalyzer("5").get_unbound_nodes()   == []
    assert CodeAnalyzer("x + 5").get_unbound_nodes() == ["x"]
    assert CodeAnalyzer("5 + y").get_unbound_nodes() == ["y"]
    assert CodeAnalyzer("5 + 5").get_unbound_nodes() == []

if __name__ == "__main__":
    pytest.main([__file__, "-v"])