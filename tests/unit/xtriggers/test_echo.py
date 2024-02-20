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

from cylc.flow.exceptions import WorkflowConfigError
from cylc.flow.xtriggers.echo import validate
import pytest
from pytest import param


def test_validate_good():
    validate({
        'args': (),
        'kwargs': {'succeed': False, 'egg': 'fried', 'potato': 'baked'}
    })


@pytest.mark.parametrize(
    'all_args', (
        param({'args': (False,), 'kwargs': {}}, id='no-kwarg'),
        param({'args': (), 'kwargs': {'spud': 'mashed'}}, id='no-succeed-kwarg'),
    )
)
def test_validate_exceptions(all_args):
    with pytest.raises(WorkflowConfigError, match='^Requires'):
        validate(all_args)
