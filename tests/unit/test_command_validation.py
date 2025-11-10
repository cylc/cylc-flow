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

import re

import pytest

from cylc.flow.command_validation import (
    ERR_OPT_FLOW_COMBINE,
    ERR_OPT_FLOW_VAL_INT_NEW_NONE,
    flow_opts,
    is_tasks,
)
from cylc.flow.cycling.loader import ISO8601_CYCLING_TYPE
from cylc.flow.exceptions import InputError
from cylc.flow.flow_mgr import FLOW_NEW, FLOW_NONE
from cylc.flow.id import TaskTokens


@pytest.mark.parametrize('flow_strs, expected_msg', [
    ([FLOW_NEW, '1'], ERR_OPT_FLOW_COMBINE.format(FLOW_NEW)),
    ([FLOW_NONE, '1'], ERR_OPT_FLOW_COMBINE.format(FLOW_NONE)),
    ([FLOW_NONE, FLOW_NEW], ERR_OPT_FLOW_COMBINE.format(FLOW_NONE)),
    (['a'], ERR_OPT_FLOW_VAL_INT_NEW_NONE),
    (['1', 'a'], ERR_OPT_FLOW_VAL_INT_NEW_NONE),
])
async def test_trigger_invalid(flow_strs, expected_msg):
    """Ensure invalid flow values are rejected during command validation."""
    with pytest.raises(InputError) as exc_info:
        flow_opts(flow_strs, False)
    assert str(exc_info.value) == expected_msg


async def test_is_tasks(set_cycling_type):
    set_cycling_type(ISO8601_CYCLING_TYPE)

    # tokens should be parsed
    assert is_tasks({'20000101T0000Z/a', '20010101T0000Z/b'}) == {
        TaskTokens('20000101T0000Z', 'a'),
        TaskTokens('20010101T0000Z', 'b'),
    }

    # cycle points should be standardised unless they are globs
    assert is_tasks({'2000/a', '20010101/b', '*/c', '[23]000/d'}) == {
        TaskTokens('20000101T0000Z', 'a'),
        TaskTokens('20010101T0000Z', 'b'),
        TaskTokens('*', 'c'),
        TaskTokens('[23]000', 'd'),
    }

    # the namespace should default to "root" unless provided
    assert is_tasks({'*', '2000'}) == {
        TaskTokens('*', 'root'),
        TaskTokens('20000101T0000Z', 'root'),
    }

    # invalid IDs result in errors
    with pytest.raises(InputError, match='Invalid ID: //, ///, ////'):
        is_tasks({'//', '///', '////', '2000/a'})  # last ID is valid

    # invalid cycle points result in errors
    with pytest.raises(
        InputError,
        match=re.escape('Invalid cycle point: (42)/answer, 2000Z, abc'),
    ):
        is_tasks({'(42)/answer', '2000Z', 'abc', '2000/a'})  # last ID is valid

    # job IDs reuslt in errors
    with pytest.raises(
        InputError,
        match=re.escape('This command does not take job IDs: */b/02, 1/a/01'),
    ):
        is_tasks({'1/a/01', '*/b/02'})

    # combinations of errors are reported
    with pytest.raises(
        InputError,
        match=(
            re.escape('Invalid ID: ///, ////')
            + re.escape('\nInvalid cycle point: 200Z, abc')
            + re.escape('\nThis command does not take job IDs: */b/02, 1/a/01')
        ),
    ):
        is_tasks({'///', '////', '200Z', 'abc', '1/a/01', '*/b/02'})
