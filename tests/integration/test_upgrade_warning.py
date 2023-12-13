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

"""Test upgrade warnings make sense.
"""


def test_graph_upgrade_msg_default(flow, validate, caplog):
    """It lists Cycling definitions which need upgrading."""
    id_ = flow({
        'scheduler': {'allow implicit tasks': True},
        'scheduling': {
            'initial cycle point': 1042,
            'dependencies': {
                'R1': {'graph': 'foo'},
                'P1Y': {'graph': 'bar & baz'}
            }
        },
    })
    validate(id_)
    assert '[scheduling][dependencies][X]graph' in caplog.messages[0]
    assert 'for X in:\n       P1Y, R1' in caplog.messages[0]


def test_graph_upgrade_msg_graph_equals(flow, validate, caplog):
    """It gives a more useful message in special case where graph is
    key rather than section:

    [scheduling]
        [[dependencies]]
            graph = foo => bar
    """
    id_ = flow({
        'scheduler': {'allow implicit tasks': True},
        'scheduling': {'dependencies': {'graph': 'foo => bar'}},
    })
    validate(id_)
    expect = ('[scheduling][dependencies]graph -> [scheduling][graph]R1')
    assert expect in caplog.messages[0]
