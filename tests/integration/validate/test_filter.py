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

from cylc.flow.parsec.exceptions import IllegalItemError


def test_filtered_keys_error(flow, validate):
    id_ = flow({
        'scheduling': {
            'graph': {
                'R1': 'foo',
            },
        },
        'runtime': {
            'foo': {
                'retry delays': 'PT1S'
            },
        },
    })
    with pytest.raises(IllegalItemError, match=(
        r'\[runtime\]\[foo\]retry delays.* did you '
        r'mean execution retry delays.*submission retry delays.*'
    )):
        validate(id_)
