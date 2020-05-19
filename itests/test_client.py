from cylc.flow.network.server import PB_METHOD_MAP


def test_ping(simple_flow):
    """It should return True if running."""
    reg, _, client = simple_flow
    assert client('ping_suite')


def test_graphql(simple_flow):
    """It should return information about itself."""
    reg, _, client = simple_flow
    ret = client(
        'graphql',
        {'request_string': 'query { workflows { id } }'}
    )
    workflows = ret['workflows']
    assert len(workflows) == 1
    workflow = workflows[0]
    assert reg in workflow['id']


def test_protobuf(simple_flow):
    """It should return information about itself."""
    reg, _, client = simple_flow
    ret = client('pb_entire_workflow')
    pb_data = PB_METHOD_MAP['pb_entire_workflow']()
    pb_data.ParseFromString(ret)
    assert reg in pb_data.workflow.id
