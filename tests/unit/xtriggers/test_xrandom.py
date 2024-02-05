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
from pytest import param

from cylc.flow.xtriggers.xrandom import validate
from cylc.flow.exceptions import WorkflowConfigError


def test_validate_good_path():
    assert validate([1], {'secs': 0, '_': 'HelloWorld'}, 'good_path') is None


@pytest.mark.parametrize(
    'args, kwargs, err', (
        param(['foo'], {}, r"'percent", id='percent-not-numeric'),
        param([101], {}, r"'percent", id='percent>100'),
        param([-1], {}, r"'percent", id='percent<0'),
        param([100], {'secs': 1.1}, r"'secs'", id='secs-not-int'),
    )
)
def test_validate_exceptions(args, kwargs, err):
    """Illegal args and kwargs cause a WorkflowConfigError raised."""
    with pytest.raises(WorkflowConfigError, match=f'^{err}'):
        validate(args, kwargs, 'blah')
