from cylc.flow.parsec.config import ConfigNode as Conf


with Conf('scheduling') as scheduling:
    with Conf('dependencies') as dependencies:
        graph = Conf('graph', default='')


def test_config_node():
    assert scheduling.name == 'scheduling'
    assert scheduling._parent is None
    assert scheduling._children == {'dependencies': dependencies}
    assert scheduling.name == 'scheduling'
    assert dependencies.name == 'dependencies'
    assert dependencies._parent == scheduling
    assert dependencies._children == {'graph': graph}
    assert graph.name == 'graph'
    assert graph._parent == dependencies
    assert graph._children is None


def test_config_str():
    assert str(scheduling) == '[scheduling]'
    assert str(dependencies) == '[dependencies]'
    assert str(graph) == 'graph'


def test_config_repr():
    assert repr(scheduling) == '[scheduling]'
    assert repr(dependencies) == '[scheduling][dependencies]'
    assert repr(graph) == '[scheduling][dependencies]graph'
