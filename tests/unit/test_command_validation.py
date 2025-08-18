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

from cylc.flow.command_validation import (
    ERR_OPT_FLOW_COMBINE,
    ERR_OPT_FLOW_VAL_INT_NEW_NONE,
    flow_opts,
)
from cylc.flow.exceptions import InputError
from cylc.flow.flow_mgr import FLOW_NEW, FLOW_NONE


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
