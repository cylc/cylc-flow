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

"""Tests for the "[scheduler]task match limit" global config setting.

Commands which can act on tasks outside of the task pool (set, trigger,
remove, hold) are refused if the task IDs match more tasks than the limit.

See https://github.com/cylc/cylc-flow/issues/4357
"""

import pytest

from cylc.flow.option_parsers import Options
from cylc.flow.scripts.set import get_option_parser as set_gop
from cylc.flow.scripts.set import run as set_run


N_TASKS = 20


@pytest.fixture
def match_limit(mock_glbl_cfg):
    """Set the task match limit as seen by the commands module."""
    def _match_limit(limit: int) -> None:
        mock_glbl_cfg(
            'cylc.flow.commands.glbl_cfg',
            f'''
                [scheduler]
                    task match limit = {limit}
            ''',
        )
    return _match_limit


@pytest.fixture
def id_(flow):
    """A cycling workflow with N_TASKS + 1 tasks per cycle."""
    return flow({
        'scheduling': {
            'initial cycle point': '1',
            'cycling mode': 'integer',
            'runahead limit': 'P0',
            'graph': {
                'P1': 'a[-P1] => a => b<m>',
            },
        },
        'task parameters': {
            'm': f'1..{N_TASKS}',
        },
    })


@pytest.mark.parametrize(
    'command, kwargs',
    [
        pytest.param('set', {'flow': []}, id='set'),
        pytest.param('force_trigger_tasks', {'flow': []}, id='trigger'),
        pytest.param('remove_tasks', {'flow': []}, id='remove'),
        pytest.param('hold', {}, id='hold'),
    ],
)
async def test_match_limit(
    id_, scheduler, start, match_limit, command, kwargs
):
    """Commands are refused if they match more tasks than the limit."""
    match_limit(10)
    schd = scheduler(id_)
    async with start(schd):
        # (the data store is updated in the main loop which is not running)
        await schd.update_data_structure()
        mapper = schd.server.resolvers._mutation_mapper

        # a glob in the task name matches every task in the workflow
        # (N_TASKS + 1 > limit)
        ok, msg = await mapper(command, {**kwargs, 'tasks': ['1/*']}, {})
        assert ok is False
        assert f'This would act on {N_TASKS + 1} tasks' in msg
        assert f'({N_TASKS} not in the task pool)' in msg
        assert 'more than the task match limit (10)' in msg
        assert '--yes' in msg

        # the limit can be overridden
        ok, _ = await mapper(
            command,
            {**kwargs, 'tasks': ['1/*'], 'ignore_match_limit': True},
            {},
        )
        assert ok is True

        # commands which match fewer tasks than the limit are not affected
        ok, _ = await mapper(
            command, {**kwargs, 'tasks': ['1/a', '1/b_m01']}, {}
        )
        assert ok is True


async def test_match_limit_zero(id_, scheduler, start, match_limit):
    """Setting the limit to 0 turns the check off."""
    match_limit(0)
    schd = scheduler(id_)
    async with start(schd):
        # (the data store is updated in the main loop which is not running)
        await schd.update_data_structure()
        ok, _ = await schd.server.resolvers._mutation_mapper(
            'set', {'flow': [], 'tasks': ['1/*']}, {}
        )
        assert ok is True


async def test_match_limit_cycle_glob(id_, scheduler, start, match_limit):
    """Cycle point globs match cycle points in the task pool.

    The limit applies to the total number of tasks across all matched
    cycle points.
    """
    match_limit(N_TASKS + 1)
    schd = scheduler(id_)
    async with start(schd):
        # (the data store is updated in the main loop which is not running)
        await schd.update_data_structure()
        # only cycle 1 is in the task pool, so this is within the limit
        ok, msg = await schd.server.resolvers._mutation_mapper(
            'set', {'flow': [], 'tasks': ['*/*']}, {}
        )
        assert ok is True, msg

        # add the next cycle to the task pool
        schd.pool.set_prereqs_and_outputs(
            {schd.tokens.duplicate(cycle='1', task='a')},
            ['succeeded'], [], ['1'],
        )
        await schd.update_data_structure()

        ok, msg = await schd.server.resolvers._mutation_mapper(
            'set', {'flow': [], 'tasks': ['*/*']}, {}
        )
        assert ok is False
        assert 'across 2 cycle point(s)' in msg


@pytest.mark.parametrize(
    'scheduler_version, yes, expected',
    [
        pytest.param('8.8.0', True, True, id='new-scheduler'),
        pytest.param('8.8.0', False, False, id='no-yes'),
        pytest.param('8.7.0', True, False, id='old-scheduler'),
    ],
)
async def test_cli_yes(
    monkeypatch, scheduler_version, yes, expected
):
    """The --yes option sends ignoreMatchLimit to new schedulers only."""
    requests = []

    class MockClient:
        def __init__(self, *args, **kwargs):
            self.scheduler_version = scheduler_version

        async def async_request(self, _command, kwargs):
            requests.append(kwargs)

    monkeypatch.setattr('cylc.flow.scripts.set.get_client', MockClient)
    opts = Options(set_gop())(ignore_match_limit=yes)
    await set_run(opts, 'wid', *[])

    (request,) = requests
    assert (
        'ignoreMatchLimit: $ignoreMatchLimit' in request['request_string']
    ) is expected
    assert ('ignoreMatchLimit' in request['variables']) is expected
