def test_suite(make_flow, run_flow):
    foo = make_flow(
        'foo',
        {
            'scheduling': {
                'dependencies': {
                    'graph': 'foo'
                }
            }
        }
    )
    print('here we go')
    with run_flow(foo, hold_start=True, no_detach=True) as (proc, client):
        print('Attempting ping')
        ret = client('ping_suite')
        print(ret)
        assert ret is True
        print('Attempted ping')

        # from time import sleep
        # sleep(2)
        # assert False
