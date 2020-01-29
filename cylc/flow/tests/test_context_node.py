from textwrap import dedent

import pytest

from cylc.flow.context_node import ContextNode


with ContextNode('a') as a:
    with ContextNode('b') as b:
        c = ContextNode('c')
    d = ContextNode('d')


def test_context_node_tree():
    """Ensure parents and children are correctly organised."""
    assert a.name == 'a'
    assert a._parent == None
    assert a._children == {'b': b, 'd': d}
    assert b.name == 'b'
    assert b._parent == a
    assert b._children == {'c': c}
    assert c.name == 'c'
    assert c._parent == b
    assert c._children == None


def test_data_state():
    """Ensure the in-class state remains intact."""
    # DATA should start clean
    assert ContextNode.DATA == {}

    # nodes add themselves to DATA then remove themselves from it
    with ContextNode('foo'):
        pass

    # so DATA should end clean
    assert ContextNode.DATA == {}

    # however erroneously creating leaf-nodes outside of a context
    # will make a mess
    a = ContextNode('a')
    assert ContextNode.DATA == {a: set()}

    # just to make sure this doesn't result in hard-to-debug errors
    # we make sure this doesn't prevent us creating new trees
    with ContextNode('foo') as foo:
        bar = ContextNode('bar')
    assert ContextNode.DATA == {a: set(), foo: {a}}
    assert list(foo.walk()) == [(0, foo), (1, bar)]

    # finally clean up for niceness 
    del ContextNode.DATA[a]
    del ContextNode.DATA[foo]


def test_context_iter():
    """Test iterating over child nodes."""
    assert list(a) == [b, d]
    assert list(b) == [c]
    assert list(c) == []


def test_context_contains():
    """Test `node.__contains__`."""
    assert 'b' in a
    assert 'c' in b
    assert not 'c' in a


def test_context_getitem():
    """Test `node.__getitem__`."""
    assert a['b'] == b
    assert b['c'] == c
    with pytest.raises(KeyError):
        assert b['d']
    with pytest.raises(TypeError):
        assert c['b']


def test_context_str():
    """Test the string representation of a node."""
    assert str(a) == 'a'
    assert str(b) == 'b'
    assert str(c) == 'c'


def test_context_repr():
    """Test the Python representation of a node."""
    assert repr(a) == 'a'
    assert repr(b) == 'a/b'
    assert repr(c) == 'a/b/c'


def test_context_walk():
    """Test walking the tree."""
    assert list(a.walk()) == [
        (0, a),
        (1, b),
        (2, c),
        (1, d)
    ]
    assert list(b.walk()) == [
        (0, b),
        (1, c),
    ]
    assert list(c.walk()) == [
        (0, c)
    ]


def test_context_walk_depth():
    assert list(a.walk(depth=1)) == [
        (0, a),
        (1, b),
        (1, d)
    ]


def test_context_tree():
    """Test the string representation of the tree."""
    assert a.tree() == dedent('''
        a
            b
                c
            d
    ''').strip()
    assert b.tree() == dedent('''
        b
            c
    ''').strip()
    assert c.tree() == dedent('''
        c
    ''').strip()


def test_context_is_root():
    """Test root node detection."""
    assert a.is_root()
    assert not b.is_root()
    assert not c.is_root()


def test_context_is_leaf():
    """Test leaf node detection."""
    assert not a.is_leaf()
    assert not b.is_leaf()
    assert c.is_leaf()


def test_context_parents():
    """Test linearised ancestry."""
    assert list(a.parents()) == []
    assert list(b.parents()) == [a]
    assert list(c.parents()) == [b, a]
