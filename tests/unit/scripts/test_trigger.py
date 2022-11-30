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

"""Test logic in cylc-trigger script."""

from optparse import Values
import pytest
from typing import Iterable, Optional, Tuple, Type

from cylc.flow.exceptions import InputError
from cylc.flow.option_parsers import Options
from cylc.flow.flow_mgr import FLOW_ALL, FLOW_NEW, FLOW_NONE
from cylc.flow.scripts.trigger import get_option_parser, _validate


Opts = Options(get_option_parser())


@pytest.mark.parametrize(
    'opts, expected_err',
    [
        (
            Opts(
                flow=[FLOW_ALL],
                flow_wait=False
            ),
            None
        ),
        (
            Opts(
                flow=[FLOW_NEW],
                flow_wait=False,
                flow_descr="Denial is a deep river"
            ),
            None
        ),
        (
            Opts(
                flow=[FLOW_ALL, "1"],
                flow_wait=False
            ),
            (
                InputError,
                "Multiple flow options must all be integer valued"
            )
        ),
        (
            Opts(
                flow=[FLOW_ALL],
                flow_wait=False,
                flow_descr="the quick brown fox"
            ),
            (
                InputError,
                "Metadata is only for new flows"
            )
        ),
        (
            Opts(
                flow=["cheese"],
                flow_wait=False
            ),
            (
                InputError,
                "Flow values must be integer, 'all', 'new', or 'none'"
            )
        ),
        (
            Opts(
                flow=[FLOW_NONE],
                flow_wait=True
            ),
            (
                InputError,
                "--wait is not compatible with --flow=new or --flow=none"
            )
        ),
        (
            Opts(
                flow=[FLOW_ALL, "1"],
                flow_wait=False
            ),
            (
                InputError,
                "Multiple flow options must all be integer valued"
            )
        ),
        (
            Opts(
                flow=[FLOW_ALL, "1"],
                flow_wait=False
            ),
            (
                InputError,
                "Multiple flow options must all be integer valued"
            )
        ),
    ]
)
def test_validate(
        opts: Values,
        expected_err: Optional[Tuple[Type[Exception], str]]):

    if expected_err:
        err, msg = expected_err
        with pytest.raises(err) as exc:
            _validate(opts)
        assert msg in str(exc.value)
    else:
        _validate(opts)
