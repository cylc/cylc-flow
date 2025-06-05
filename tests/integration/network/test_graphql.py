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

"""Test the top-level (root) GraphQL queries."""

from contextlib import suppress
import pytest
from typing import TYPE_CHECKING

from graphql import parse, MiddlewareManager

from cylc.flow.data_store_mgr import create_delta_store
from cylc.flow.id import Tokens
from cylc.flow.network.client import WorkflowRuntimeClient
from cylc.flow.network.schema import schema, SUB_RESOLVER_MAPPING
from cylc.flow.network.graphql import (
    CylcExecutionContext,
    IgnoreFieldMiddleware,
    instantiate_middleware,
)
from cylc.flow.network.graphql_subscribe import subscribe
from cylc.flow.workflow_status import get_workflow_status

if TYPE_CHECKING:
    from cylc.flow.scheduler import Scheduler


# NOTE: These tests mutate the data store, so running them in isolation may
# see failures when they actually pass if you run the whole file


def job_config(schd):
    return {
        'owner': schd.owner,
        'submit_num': 1,
        'task_id': '1/foo',
        'job_runner_name': 'background',
        'env-script': None,
        'err-script': None,
        'exit-script': None,
        'execution_time_limit': None,
        'init-script': None,
        'post-script': None,
        'pre-script': None,
        'script': 'sleep 5; echo "I come in peace"',
        'work_d': None,
        'directives': {},
        'environment': {},
        'param_var': {},
        'platform': {'name': 'platform'},
    }


def gather_subscription_args(schd, request_string):
    kwargs = {
        "variable_values": {},
        "operation_name": None,
        "context_value": {
            'op_id': 1,
            'resolvers': schd.server.resolvers,
            'meta': {},
        },
        "subscribe_resolver_map": SUB_RESOLVER_MAPPING,
        "middleware": MiddlewareManager(
            *list(
                instantiate_middleware(
                    [IgnoreFieldMiddleware]
                )
            )
        ),
        "execution_context_class": CylcExecutionContext,
    }
    document = parse(request_string)
    return (document, kwargs)


@pytest.fixture
def job_db_row():
    return [
        '1',
        'foo',
        'running',
        4,
        '2020-04-03T13:40:18+13:00',
        '2020-04-03T13:40:20+13:00',
        '2020-04-03T13:40:30+13:00',
        'background',
        '20542',
        'localhost',
    ]


@pytest.fixture(scope='module')
async def harness(mod_flow, mod_scheduler, mod_run):
    flow_def = {
        'scheduler': {
            'allow implicit tasks': True
        },
        'scheduling': {
            'graph': {
                'R1': 'a => b & c => d'
            }
        },
        'runtime': {
            'A': {
            },
            'B': {
                'inherit': 'A',
            },
            'b': {
                'inherit': 'B',
            },
        },
    }
    id_: str = mod_flow(flow_def)
    schd: 'Scheduler' = mod_scheduler(id_)
    async with mod_run(schd):
        client = WorkflowRuntimeClient(id_)
        schd.pool.hold_tasks(['*'])
        schd.resume_workflow()
        # Think this is needed to save the data state at first start (?)
        # Fails without it.. and a test needs to overwrite schd data with this.
        # data = schd.data_store_mgr.data[schd.data_store_mgr.workflow_id]

        workflow_tokens = Tokens(
            user=schd.owner,
            workflow=schd.workflow,
        )

        yield schd, client, workflow_tokens


async def test_workflows(harness):
    schd, client, w_tokens = harness
    ret = await client.async_request(
        'graphql',
        {'request_string': 'query { workflows { id } }'}
    )
    assert ret == {
        'workflows': [
            {
                'id': f'{w_tokens}'
            }
        ]
    }


async def test_tasks(harness):
    schd, client, w_tokens = harness

    # query "tasks"
    ret = await client.async_request(
        'graphql',
        {'request_string': 'query { tasks { id } }'}
    )
    ids = [
        w_tokens.duplicate(cycle=f'$namespace|{namespace}').id
        for namespace in ('a', 'b', 'c', 'd')
    ]
    ret['tasks'].sort(key=lambda x: x['id'])
    assert ret == {
        'tasks': [
            {'id': id_}
            for id_ in ids
        ]
    }

    # query "task"
    for id_ in ids:
        ret = await client.async_request(
            'graphql',
            {'request_string': 'query { task(id: "%s") { id } }' % id_}
        )
        assert ret == {
            'task': {'id': id_}
        }


async def test_families(harness):
    schd, client, w_tokens = harness

    # query "tasks"
    ret = await client.async_request(
        'graphql',
        {'request_string': 'query { families { id } }'}
    )
    ids = [
        w_tokens.duplicate(
            cycle=f'$namespace|{namespace}'
        ).id
        for namespace in ('A', 'B', 'root')
    ]
    ret['families'].sort(key=lambda x: x['id'])
    assert ret == {
        'families': [
            {'id': id_}
            for id_ in ids
        ]
    }

    # query "task"
    for id_ in ids:
        ret = await client.async_request(
            'graphql',
            {'request_string': 'query { family(id: "%s") { id } }' % id_}
        )
        assert ret == {
            'family': {'id': id_}
        }


async def test_task_proxies(harness):
    schd, client, w_tokens = harness

    # query "tasks"
    ret = await client.async_request(
        'graphql',
        {'request_string': 'query { taskProxies { id } }'}
    )
    ids = [
        w_tokens.duplicate(
            cycle='1',
            task=namespace,
        )
        # NOTE: task "d" is not in the n=1 window yet
        for namespace in ('a', 'b', 'c')
    ]
    ret['taskProxies'].sort(key=lambda x: x['id'])
    assert ret == {
        'taskProxies': [
            {'id': id_.id}
            for id_ in ids
        ]
    }

    # query "task"
    ret = await client.async_request(
        'graphql',
        {'request_string': 'query { taskProxy(id: "%s") { id } }' % ids[0].id}
    )
    assert ret == {
        'taskProxy': {'id': ids[0].id}
    }

    # query "taskProxies" fragment with null stripping
    ret = await client.async_request(
        'graphql',
        {
            'request_string': '''
                fragment wf on Workflow {
                    taskProxies (ids: ["%s"], stripNull: true) { id }
                }
                query { workflows (ids: ["%s"]) { ...wf } }
            ''' % (ids[0].relative_id, ids[0].workflow_id)
        }
    )
    assert ret == {'workflows': [{'taskProxies': [{'id': ids[0].id}]}]}


async def test_family_proxies(harness):
    schd, client, w_tokens = harness

    # query "familys"
    ret = await client.async_request(
        'graphql',
        {'request_string': 'query { familyProxies { id } }'}
    )
    ids = [
        w_tokens.duplicate(
            cycle='1',
            task=namespace,
        ).id
        # NOTE: family "d" is not in the n=1 window yet
        for namespace in ('A', 'B', 'root')
    ]
    ret['familyProxies'].sort(key=lambda x: x['id'])
    assert ret == {
        'familyProxies': [
            {'id': id_}
            for id_ in ids
        ]
    }

    # query "family"
    for id_ in ids:
        ret = await client.async_request(
            'graphql',
            {'request_string': 'query { familyProxy(id: "%s") { id } }' % id_}
        )
        assert ret == {
            'familyProxy': {'id': id_}
        }


async def test_edges(harness):
    schd, client, w_tokens = harness

    t_tokens = [
        w_tokens.duplicate(
            cycle='1',
            task=namespace,
        )
        # NOTE: task "d" is not in the n=1 window yet
        for namespace in ('a', 'b', 'c')
    ]
    edges = [
        (t_tokens[0], t_tokens[1]),
        (t_tokens[0], t_tokens[2]),
    ]
    e_ids = sorted([
        w_tokens.duplicate(
            cycle=(
                '$edge'
                f'|{left.relative_id}'
                f'|{right.relative_id}'
            )
        ).id
        for left, right in edges
    ])

    # query "edges"
    ret = await client.async_request(
        'graphql',
        {'request_string': 'query { edges { id } }'}
    )
    ret['edges'].sort(key=lambda x: x['id'])
    assert ret == {
        'edges': [
            {'id': id_}
            for id_ in e_ids
        ]
    }

    # query "nodesEdges"
    ret = await client.async_request(
        'graphql',
        {'request_string': 'query { nodesEdges { nodes {id}\nedges {id} } }'}
    )
    ret['nodesEdges']['nodes'].sort(key=lambda x: x['id'])
    ret['nodesEdges']['edges'].sort(key=lambda x: x['id'])
    assert ret == {
        'nodesEdges': {
            'nodes': [
                {'id': tokens.id}
                for tokens in t_tokens
            ],
            'edges': [
                {'id': id_}
                for id_ in e_ids
            ],
        },
    }


async def test_jobs(harness):
    schd, client, w_tokens = harness

    # add a job
    schd.data_store_mgr.insert_job('a', '1', 'submitted', job_config(schd))
    schd.data_store_mgr.update_data_structure()
    j_tokens = w_tokens.duplicate(
        cycle='1',
        task='a',
        job='01',
    )
    j_id = j_tokens.id

    # query "jobs"
    ret = await client.async_request(
        'graphql',
        {'request_string': 'query { jobs { id } }'}
    )
    assert ret == {
        'jobs': [
            {'id': f'{j_id}'}
        ]
    }

    # query "job"
    ret = await client.async_request(
        'graphql',
        {'request_string': 'query { job(id: "%s") { id } }' % j_id}
    )
    assert ret == {
        'job': {'id': f'{j_id}'}
    }


# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~ #
# Test the GraphQL subscription infrastructure.
# (currently only used at UIS)
@pytest.mark.asyncio(loop_scope="module")
async def test_subscription_basic(harness):
    """Test a basic subscription that uses the resolver's sub_resolver code."""
    schd, _, w_tokens = harness
    document, kwargs = gather_subscription_args(
        schd,
        'subscription { workflows { id } }',
    )
    subscription = await subscribe(
        schema.graphql_schema,
        document,
        **kwargs
    )
    has_item = False
    with suppress(GeneratorExit):
        async for response in subscription:
            has_item = True
            assert response.data['workflows'][0]['id'] == w_tokens.id
            await subscription.aclose()
    assert has_item


@pytest.mark.asyncio(loop_scope="module")
async def test_subscription_deltas(one, start):
    """Test the full subscription with null-stripping and delta handling."""
    async with start(one):
        document, kwargs = gather_subscription_args(
            one,
            '''
                subscription {
                    deltas (stripNull: true) {
                        id
                        added {
                            workflow {
                                id
                                host
                                status
                            }
                        }
                        updated {
                            workflow {
                                id
                                host
                                status
                            }
                        }
                    }
                }
            ''',
        )
        subscription = await subscribe(
            schema.graphql_schema,
            document,
            **kwargs
        )
        aitem = await subscription.__anext__()
        assert aitem.data['deltas']['added']['workflow'] == {
            'id': one.id,
            'host': one.host,
            'status': 'running',
        }
        # Workflow one is paused on start, but this hasn't been processed yet.
        await one.update_data_structure()
        assert (
            one.data_store_mgr.data[one.id]['workflow'].status
            == get_workflow_status(one).value
        )
        # Get the all delta, process, then add it to the subscription queue.
        btopic, delta, _ = one.data_store_mgr.publish_deltas[-1]
        _, sub_queue = next(
            iter(one.data_store_mgr.delta_queues[one.id].items())
        )
        sub_queue.put(
            (
                one.id,
                btopic.decode('utf-8'),
                create_delta_store(delta, one.id)
            )
        )
        aitem = await subscription.__anext__()
        assert aitem.data['deltas']['updated']['workflow'] == {
            'id': one.id,
            'status': get_workflow_status(one).value,
        }
        with suppress(GeneratorExit):
            await subscription.aclose()
