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

import pytest

from cylc.flow.network.client import WorkflowRuntimeClient


@pytest.fixture(scope='module')
async def harness(mod_flow, mod_scheduler, mod_run):
    id_ = mod_flow({
        'scheduling': {
            'graph': {
                'R1': '''
                    a
                    b
                ''',
            },
        },
        'runtime': {
            'A1': {
                'inherit': 'A2'
            },
            'A2': {
            },
            'a': {
                'inherit': 'A1'
            },
            'b': {},
        },
    })
    schd = mod_scheduler(id_)
    async with mod_run(schd):
        client = WorkflowRuntimeClient(id_)

        async def _query(query_string):
            nonlocal client
            return await client.async_request(
                'graphql',
                {
                    'request_string': 'query { %s } ' % query_string,
                }
            )
        yield schd, client, _query


async def test_workflows(harness):
    """It should return True if running."""
    schd, client, query = harness
    ret = await query('workflows(ids: ["%s"]) { id }' % schd.workflow)
    assert ret == {
        'workflows': [
            {'id': f'~{schd.owner}/{schd.workflow}'}
        ]
    }


async def test_jobs(harness):
    """It should return True if running."""
    schd, client, query = harness
    ret = await query('workflows(ids: ["%s"]) { id }' % schd.workflow)
    assert ret == {
        'workflows': [
            {'id': f'~{schd.owner}/{schd.workflow}'}
        ]
    }
