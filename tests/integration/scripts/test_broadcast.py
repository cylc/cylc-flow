# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from ansimarkup import strip as cstrip

from cylc.flow.network.client import WorkflowRuntimeClient
from cylc.flow.option_parsers import Options
from cylc.flow.rundb import CylcWorkflowDAO
from cylc.flow.scripts.broadcast import _main, get_option_parser
from cylc.flow.util import sstrip


BroadcastOptions = Options(get_option_parser())


async def test_broadcast_multi_workflow(
    one_conf,
    flow,
    scheduler,
    start,
    run_dir,
    test_dir,
    capsys,
):
    """Test a multi-workflow broadcast command."""
    # create three workflows
    one = scheduler(flow(one_conf))
    two = scheduler(flow(one_conf))
    thr = scheduler(flow(one_conf))

    # the ID under which all three are installed
    id_base = test_dir.relative_to(run_dir)

    async with start(one):
        async with start(two):
            async with start(thr):
                capsys.readouterr()

                # test a successful broadcast command
                rets = await _main(
                    BroadcastOptions(settings=['script=true']), f'{id_base}*'
                )

                # all three broadcasts should have succeeded
                assert list(rets.values()) == [True, True, True]

                out, err = capsys.readouterr()
                assert '[*/root] script=true' in out
                assert err == ''

                # test an unsuccessful broadcast command
                rets = await _main(
                    BroadcastOptions(
                        namespaces=['*'],
                        settings=['script=true'],
                    ),
                    f'{id_base}*',
                )

                # all three broadcasts should have failed
                assert list(rets.values()) == [False, False, False]

                out, err = capsys.readouterr()
                assert '[*/root] script=true' not in out
                assert (
                    # NOTE: for historical reasons this message goes to stdout
                    # not stderr
                    'Rejected broadcast:'
                    ' settings are not compatible with the workflow'
                ) in out
                assert err == ''


async def test_broadcast_multi_namespace(
    flow,
    scheduler,
    start,
    db_select,
):
    """Test a multi-namespace broadcast command.

    See https://github.com/cylc/cylc-flow/issues/6334
    """
    id_ = flow(
        {
            'scheduling': {
                'graph': {'R1': 'a & b & c & fin'},
            },
            'runtime': {
                'root': {'execution time limit': 'PT1S'},
                'VOWELS': {'execution time limit': 'PT2S'},
                'CONSONANTS': {'execution time limit': 'PT3S'},
                'a': {'inherit': 'VOWELS'},
                'b': {'inherit': 'CONSONANTS'},
                'c': {'inherit': 'CONSONANTS'},
            },
        }
    )
    schd = scheduler(id_)

    async with start(schd):
        # issue a broadcast to multiple namespaces
        rets = await _main(
            BroadcastOptions(
                settings=['execution time limit = PT5S'],
                namespaces=['root', 'VOWELS', 'CONSONANTS'],
            ),
            schd.workflow,
        )

        # the broadcast should succeed
        assert list(rets.values()) == [True]

        # the broadcast manager should store the "coerced" setting
        for task in ['a', 'b', 'c', 'fin']:
            assert schd.broadcast_mgr.get_broadcast(
                schd.tokens.duplicate(cycle='1', task=task)
            ) == {'execution time limit': 5.0}

        # the database should store the "raw" setting
        assert sorted(
            db_select(schd, True, CylcWorkflowDAO.TABLE_BROADCAST_STATES)
        ) == [
            ('*', 'CONSONANTS', 'execution time limit', 'PT5S'),
            ('*', 'VOWELS', 'execution time limit', 'PT5S'),
            ('*', 'root', 'execution time limit', 'PT5S'),
        ]


async def test_broadcast_truncated_datetime(flow, scheduler, start, capsys):
    """It should reject truncated datetime cycle points.

    See https://github.com/cylc/cylc-flow/issues/6407
    """
    id_ = flow({
        'scheduling': {
            'initial cycle point': '2000',
            'graph': {
                'R1': 'foo',
            },
        }
    })
    schd = scheduler(id_)
    async with start(schd):
        # attempt an invalid broadcast
        rets = await _main(
            BroadcastOptions(
                settings=['[environment]FOO=bar'],
                point_strings=['050101T0000Z'],  # <== truncated
            ),
            schd.workflow,
        )

        # the broadcast should fail
        assert list(rets.values()) == [False]

        # an error should be recorded
        _out, err = capsys.readouterr()
        assert (
            'Rejected broadcast:'
            ' settings are not compatible with the workflow'
        ) in err


async def test_invalid(one, start, capsys, monkeypatch):
    """It should reject invalid broadcasts.

    * Broadcast operations may contain a mix of valid and invalid
      cycles/namespaces/settings.
    * Valid settings are applied and reported.
    * Invalid settings are rejected and reported.
    """
    # disable client side config validation so that we can see invalid
    # broadcast settings in the CLI output
    monkeypatch.setattr(
        'cylc.flow.scripts.broadcast.cylc_config_validate',
        lambda *args, **kwargs: True,
    )

    # 1) disable CLI colour output
    monkeypatch.setattr('cylc.flow.scripts.broadcast.cparse', cstrip)

    async with start(one):
        # test the GraphQL API
        client = WorkflowRuntimeClient(one.workflow)
        response = await client.async_request(
            'graphql',
            {
                'request_string': '''
                    mutation(
                        $workflows: [WorkflowID]!,
                        $cycles: [BroadcastCyclePoint],
                        $namespaces: [NamespaceName],
                        $settings: [BroadcastSetting]
                    ) {
                      broadcast(
                        mode: Set
                        workflows: $workflows
                        cyclePoints: $cycles
                        namespaces: $namespaces
                        settings: $settings
                      ) {
                        result
                      }
                    }
                ''',
                'variables': {
                    'workflows': [one.workflow],
                    # valid, invalid
                    'cycles': ['*', 'invalid'],
                    'namespaces': ['root', 'invalid'],
                    'settings': [{'script': 'true'}, {'invalid': 'false'}],
                }
            }
        )
        modified, rejected = response['broadcast']['result'][0]['response']

        assert modified == [
            [
                # cycle
                '*',
                # namespace
                'root',
                # settings
                {'script': 'true'},
            ]
        ]
        assert rejected == {
            'point_strings': ['invalid'],
            'namespaces': ['invalid'],
            'settings': [{'invalid': 'false'}],
        }

        # 2) test the CLI
        capsys.readouterr()  # flush out any stdout/err
        await _main(
            BroadcastOptions(
                point_strings=['*', 'invalid'],
                namespaces=['root', 'invalid'],
                settings=['script=true', 'invalid=false'],
            ),
            one.workflow,
        )
        out, err = capsys.readouterr()
        assert out == 'Broadcast set:\n+ [*/root] script=true\n'
        assert err == sstrip('''
    ERROR: Rejected broadcast: settings are not compatible with the workflow
      --namespace=invalid
      --point=invalid
      --set=invalid=false
        ''') + '\n'


async def test_internal_error(one, start, capsys, monkeypatch, log_filter):
    """It should handle internal code errors elegantly."""

    # simulate an internal error
    # Note: The broadcast "lock" mechanism is an example of how such an error
    # could arise
    def put_broadcast(*args, **kwargs):
        raise Exception('FooBar')

    async with start(one):
        # issue a broadcast
        one.broadcast_mgr.put_broadcast = put_broadcast
        client = WorkflowRuntimeClient(one.workflow)
        response = await client.async_request(
            'graphql',
            {
                'request_string': '''
                    mutation(
                        $workflows: [WorkflowID]!,
                        $cycles: [BroadcastCyclePoint],
                        $namespaces: [NamespaceName],
                        $settings: [BroadcastSetting]
                    ) {
                      broadcast(
                        mode: Set
                        workflows: $workflows
                        cyclePoints: $cycles
                        namespaces: $namespaces
                        settings: $settings
                      ) {
                        result
                      }
                    }
                ''',
                'variables': {
                    'workflows': [one.workflow],
                    'cycles': ['*'],
                    'namespaces': ['root'],
                    'settings': [{'script': 'true'}],
                }
            }
        )

        # check it comes back with an error code
        assert (
            response['broadcast']['result'][0]
        )['response']['error']['message'] == 'FooBar'

        # the error should be logged server-side too
        assert log_filter(contains='FooBar')
