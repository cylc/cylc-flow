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

"""Integration tests for the "cylc completion-server command.

See also the more extensive unit tests for this module.
"""

from cylc.flow.scripts.completion_server import complete_cylc


def setify(coro):
    """Cast returned lists to sets for coroutines.

    Convenience function to use when you want to test output not order.
    """
    async def _coro(*args, **kwargs):
        nonlocal coro
        ret = await coro(*args, **kwargs)
        if isinstance(ret, list):
            return set(ret)
        return ret
    return _coro


async def test_list_prereqs_and_outputs(flow, scheduler, start):
    """Test the success cases for listing task prereqs/outputs.

    The error cases are tested in a unit test (doesn't require a running
    scheduler).
    """
    _complete_cylc = setify(complete_cylc)  # Note: results are un-ordered

    id_ = flow({
        'scheduler': {
            'allow implicit tasks': 'True',
        },
        'scheduling': {
            'initial cycle point': '1',
            'cycling mode': 'integer',
            'graph': {
                'P1': '''
                    a => b
                    c => d
                    b[-P1] => b
                '''
            },
        },
        'runtime': {
            'a': {},
            'b': {
                'outputs': {
                    'foo': 'abc def ghi',
                }
            }
        }
    })
    schd = scheduler(id_)
    async with start(schd):
        await schd.update_data_structure()
        b1 = schd.tokens.duplicate(cycle='1', task='b')
        d1 = schd.tokens.duplicate(cycle='1', task='d')
        e1 = schd.tokens.duplicate(cycle='1', task='e')  # does not exist

        # list prereqs (b1)
        assert await _complete_cylc('cylc', 'set', b1.id, '--pre', '') == {
            # keywords
            'all',
            # intra-cycle dependency
            '1/a:succeeded',
            # inter-cycle dependency
            '0/b:succeeded',
        }

        # list outputs (b1)
        assert await _complete_cylc('cylc', 'set', b1.id, '--out', '') == {
            # regular task outputs
            'expired',
            'failed',
            'started',
            'submit-failed',
            'submitted',
            'succeeded',
            # custom task outputs
            'foo',
        }

        # list prereqs (d1)
        assert await _complete_cylc('cylc', 'set', d1.id, '--pre', '') == {
            # keywords
            'all',
            # d1 prereqs
            '1/c:succeeded',
        }

        # list prereqs for multiple (b1, d1)
        assert await _complete_cylc(
            'cylc',
            'set',
            b1.id,
            d1.id,
            '--pre',
            '',
        ) == {
            # keywords
            'all',
            # b1 prereqs
            '1/a:succeeded',
            '0/b:succeeded',
            # d1 prereqs
            '1/c:succeeded',
        }

        # list prereqs for multiple (b1, d1) - alternative format
        assert await _complete_cylc(
            'cylc',
            'set',
            f'{schd.id}//',
            f'//{b1.relative_id}',
            f'//{d1.relative_id}',
            '--pre',
            '',
        ) == {
            # keywords
            'all',
            # b1 prereqs
            '1/a:succeeded',
            '0/b:succeeded',
            # d1 prereqs
            '1/c:succeeded',
        }

        # list outputs for a non-existant task
        assert await _complete_cylc('cylc', 'set', e1.id, '--out', '') == set()

        # list outputs for a non-existant workflow
        assert await _complete_cylc(
            'cylc',
            'set',
            # this invalid workflow shouldn't prevent it from returning values
            # for the valid one
            'no-such-workflow//',
            f'{schd.id}//',
            f'//{b1.relative_id}',
            f'//{d1.relative_id}',
            '--pre',
            '',
        ) == {
            # keywords
            'all',
            # b1 prereqs
            '1/a:succeeded',
            '0/b:succeeded',
            # d1 prereqs
            '1/c:succeeded',
        }

        # start a second workflow to test multi-workflow functionality
        id2 = flow({
            'scheduling': {
                'graph': {
                    'R1': '''
                        x => z
                    '''
                }
            },
            'runtime': {'x': {}, 'z': {}},
        })
        schd2 = scheduler(id2)
        async with start(schd2):
            await schd2.update_data_structure()
            z1 = schd2.tokens.duplicate(cycle='1', task='z')

            # list prereqs for multiple tasks in multiple workflows
            # (it should combine the results from both workflows)
            assert await _complete_cylc(
                'cylc',
                'set',
                b1.id,
                z1.id,
                '--pre',
                '',
            ) == {
                # keywords
                'all',
                # workflow1//1/b prereqs
                '0/b:succeeded',
                '1/a:succeeded',
                # workflow2//1/z prereqs
                '1/x:succeeded'
            }
