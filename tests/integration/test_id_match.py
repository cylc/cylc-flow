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

from typing import Set, Tuple, cast, TYPE_CHECKING

from cylc.flow import commands
from cylc.flow.id import Tokens
from cylc.flow.scheduler import Scheduler

if TYPE_CHECKING:
    from cylc.flow.id import TaskTokens


async def test_id_match(flow, scheduler, start, caplog):
    id_ = flow({
        'scheduling': {
            'cycling mode': 'integer',
            'initial cycle point': '1',
            'final cycle point': '3',
            'graph': {
                'P2': '''
                    a1 => b1 => c1
                    a2 => b2 => c2

                    b1[-P1] => b1
                    b2[-P1] => b2
                ''',
            },
        },
        'runtime': {
            'a1, a2': {'inherit': 'A'},
            'A': {},
            'b1, b2': {'inherit': 'B'},
            'B': {},
            'c1, c2': {},
        },
    })
    schd: Scheduler = scheduler(id_)

    def match(*ids: str) -> Tuple[Set[str], Set[str]]:
        matched, unmatched = schd.pool.id_match(
            {cast('TaskTokens', Tokens(id_, relative=True)) for id_ in ids},
        )
        return {id_.relative_id for id_ in matched}, {
            id_.relative_id_with_selectors for id_ in unmatched
        }

    async with start(schd):
        await commands.run_cmd(
            commands.set_prereqs_and_outputs(
                schd, ['1/a2'], ['1'], ['succeeded'], None
            )
        )
        await commands.run_cmd(
            commands.set_prereqs_and_outputs(
                schd, ['1/b2'], ['1'], ['failed'], None
            )
        )

        # task pool state:
        # * cycle 1
        #   * n=0 a1 waiting
        #   * n=1 b1 waiting
        #   * n=2 c1 waiting
        #   * n=1 a2 succeeded
        #   * n=0 b2 failed
        #   * n=1 c2 waiting
        # * cycle 2
        #   * n=0 a1 waiting
        #   * n=1 b1 waiting
        #   * n=2 c1 waiting
        #   * n=0 a2 waiting
        #   * n=1 b2 waiting
        #   * n=2 c2 waiting

        # check the n=0 window matches expecations before proceeding
        assert {
            itask.tokens.relative_id for itask in schd.pool.get_tasks()
        } == {'1/a1', '1/b2', '3/a1', '3/a2'}

        # test active task selection: waiting selector
        assert (
            match('*:waiting')
            == match('*/root:waiting')
            == match('*/*:waiting')
            == match('*/A:waiting')
            == match('*/a*:waiting')
            == match('1/a1:waiting', '3/a1:waiting', '3/a2:waiting')
            == match('^/a1:waiting', '3/a1:waiting', '$/a2:waiting')
            == ({'1/a1', '3/a1', '3/a2'}, set())
        )

        # test active task selection: failed selector
        assert (
            match('*:failed')
            == match('*/root:failed')
            == match('*/*:failed')
            == match('*/B:failed')
            == match('*/b*:failed')
            == match('1/b2:failed')
            == match('^/b2:failed')
            == ({'1/b2'}, set())
        )

        # test active task selection: failed selector
        assert (
            match('1/b1:failed', '1/b2:failed')
            == match('1/B:failed', '1/b1:failed')
            == match('*:failed', '1/B:failed', '1/b1:failed')
            == ({'1/b2'}, {'1/b1:failed'})
        )

        # test active task selection: submit-failed selector
        assert match('*:submit-failed') == (set(), {'*:submit-failed'})

        # test globs, cycle and family matching
        assert (
            match('*')
            == match('*/*')
            == match('*/root')
            == match('*/A', '*/B', '*/c1', '*/c2')
            == match('*/a*', '*/b*', '*/c*')
            == (
                {
                    '1/a1',
                    '1/a2',
                    '1/b1',
                    '1/b2',
                    '1/c1',
                    '1/c2',
                    '3/a1',
                    '3/a2',
                    '3/b1',
                    '3/b2',
                    '3/c1',
                    '3/c2',
                },
                set(),
            )
        )

        # test globs, cycle and family matching
        assert (
            match('1/A')
            == match('1/a*')
            == match('^/a*')
            == match('1/a1', '1/a2')
            == ({'1/a1', '1/a2'}, set())
        )
        assert match('1/X') == (set(), {'1/X'})
        assert match('5:waiting') == (set(), {'5:waiting'})

        # test invalid IDs
        assert match('not-a-cycle/*', '*/not_a_task', '*:not-a-state') == (
            set(),
            {'not-a-cycle/*', '*/not_a_task', '*:not-a-state'},
        )
        # test invalid cycle point in combination with a selector
        assert match('x/y:succeeded') == (set(), {'x/y:succeeded'})

        # ensure that off-sequence IDs are filtered out
        # NOTE: cycle 2 is not on sequence for task a1
        assert match('1/a1', '2/a1', '3/a1') == ({'1/a1', '3/a1'}, {'2/a1'})

        # ensure warnings are raised for off-sequence tasks if the user
        # explcitly specified them
        # NOTE: 2/a1 should result in a warning (because the user asked for
        # this exact combination), however, "2/a*" should not (because there
        # may be a combination of tasks which are or are not valid at the given
        # cycle(s) which match the task name pattern)
        caplog.clear()
        assert match('2/a1', '2/a*') == (set(), {'2/a1', '2/a*'})
        assert caplog.messages == ['Invalid cycle point for task: a1, 2']


async def test_match_removed_task(flow, scheduler, run, complete):
    """It should match and operate on tasks no longer in the config."""
    config = {
        'scheduling': {
            'graph': {'R1': 'foo & bar'},
        },
    }
    id_ = flow(config)
    schd = scheduler(id_, paused_start=False)

    def list_tasks():
        return {
            itask.tokens.relative_id for itask in schd.pool.get_tasks()
        }

    async with run(schd):
        # workflow starts with "foo" and "bar" in the pool
        assert list_tasks() == {'1/foo', '1/bar'}

        # remove "bar" from the config and reload
        config['scheduling']['graph']['R1'] = 'x => foo'
        flow(config, name=id_)
        await commands.run_cmd(commands.reload_workflow(schd))

        # both "foo" and "bar" are still in the pool ("bar" is orphaned)
        assert list_tasks() == {'1/foo', '1/bar'}

        # remove all tasks from the workflow
        await commands.run_cmd(commands.remove_tasks(schd, {'*'}, ['1']))

        # this should match the orphaned task "bar"
        assert list_tasks() == set()
