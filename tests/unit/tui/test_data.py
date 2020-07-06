import cylc.flow.tui.data
from cylc.flow.tui.data import generate_mutation


def test_generate_mutation(monkeypatch):
    """It should produce a GraphQL mutation with the args filled in."""
    arg_types = {
        'foo': 'String!',
        'bar': '[Int]'
    }
    monkeypatch.setattr(cylc.flow.tui.data, 'ARGUMENT_TYPES', arg_types)
    assert generate_mutation(
        'my_mutation',
        ['foo', 'bar']
    ) == '''
        mutation($foo: String!, $bar: [Int]) {
            my_mutation (foos: $foo, bars: $bar) {
                result
            }
        }
    '''
