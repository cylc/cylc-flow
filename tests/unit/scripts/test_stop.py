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

"""Test logic in cylc-stop script."""

import pytest
from typing import TYPE_CHECKING, Optional, Tuple, Type

from cylc.flow.exceptions import InputError
from cylc.flow.option_parsers import Options
from cylc.flow.scripts.stop import get_option_parser, _validate


if TYPE_CHECKING:
    from optparse import Values


Opts = Options(get_option_parser())


@pytest.mark.parametrize(
    'options, stop_task, stop_cycle, globs, expected_err',
    [
        (
            Opts(),
            None,
            None,
            None,
            None,
        ),
        (
            Opts(kill=True),
            None,
            '10',
            None,
            (InputError, "--kill is not compatible with stop-cycle")
        ),
        (
            Opts(),
            '10/foo',
            '10',
            None,
            (InputError, "stop-task is not compatible with stop-cycle")
        ),
        (
            Opts(kill=True, now=True),
            None,
            None,
            None,
            (InputError, "--kill is not compatible with --now")
        ),
        (
            Opts(flow_num=2, max_polls=2),
            None,
            None,
            None,
            (InputError, "--flow is not compatible with --max-polls")
        ),
        (
            Opts(flow_num=2),
            None,
            None,
            '*',
            (InputError, "--flow is not compatible with task IDs")
        ),
    ]
)
def test_validate(
        options: 'Values',
        stop_task: str,
        stop_cycle: str,
        globs: str,
        expected_err: Optional[Tuple[Type[Exception], str]]):

    if expected_err:
        err, msg = expected_err
        with pytest.raises(err) as exc:
            _validate(options, stop_task, stop_cycle, globs)
        assert msg in str(exc.value)
    else:
        _validate(options, stop_task, stop_cycle, globs)
