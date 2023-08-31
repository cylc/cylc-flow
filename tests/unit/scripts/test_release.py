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

"""Test logic in cylc-release script."""

from optparse import Values
import pytest
from typing import Iterable, Optional, Tuple, Type

from cylc.flow.exceptions import InputError
from cylc.flow.option_parsers import Options
from cylc.flow.scripts.release import get_option_parser, _validate


Opts = Options(get_option_parser())


@pytest.mark.parametrize(
    'opts, task_globs, expected_err',
    [
        (Opts(), ['*'], None),
        (Opts(release_all=True), [], None),
        (Opts(flow_num=None), ['*'], None),
        (Opts(flow_num=2), ['*'], None),
        (
            Opts(flow_num='cat'),
            ['*'],
            (InputError, "--flow=cat: value must be integer")
        ),
        (
            Opts(release_all=True),
            ['*'],
            (InputError, "Cannot combine --all with Cycle/Task IDs")
        ),
        (
            Opts(),
            [],
            (InputError, "Must define Cycles/Tasks")
        ),
    ]
)
def test_validate(
        opts: Values,
        task_globs: Iterable[str],
        expected_err: Optional[Tuple[Type[Exception], str]]):

    if expected_err:
        err, msg = expected_err
        with pytest.raises(err) as exc:
            _validate(opts, *task_globs)
        assert msg in str(exc.value)
    else:
        _validate(opts, *task_globs)
