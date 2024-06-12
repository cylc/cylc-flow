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


import cylc.flow.tui.data
from cylc.flow.tui.data import generate_mutation


def test_generate_mutation(monkeypatch):
    """It should produce a GraphQL mutation with the args filled in."""
    arg_types = {
        'foo': 'String!',
        'bar': '[Int]'
    }
    monkeypatch.setattr(cylc.flow.tui.data, 'ARGUMENT_TYPES', arg_types)
    assert generate_mutation(
        'my_mutation',
        {'foo': 'foo', 'bar': 'bar', 'user': 'user'}
    ) == '''
        mutation($foo: String!, $bar: [Int]) {
            my_mutation (foos: $foo, bars: $bar) {
                result
            }
        }
    '''
