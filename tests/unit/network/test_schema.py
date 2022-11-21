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

from dataclasses import dataclass
from inspect import isclass

import pytest

from cylc.flow.cfgspec.workflow import SPEC as WORKFLOW_SPEC
from cylc.flow.network.schema import (
    RUNTIME_FIELD_TO_CFG_MAP,
    Runtime,
    sort_elements,
    SortArgs,
)


@dataclass
class DummyObject:
    value: int


@pytest.mark.parametrize(
    'elements,sort_args,expected_result',
    [
        # sort asc by key
        (
            [DummyObject(1), DummyObject(3), DummyObject(2)],
            {
                'keys': ['value'],
                'reverse': False  # NOTE: GraphQL ensures reverse is not None!
            },
            [DummyObject(1), DummyObject(2), DummyObject(3)]
        ),
        # sort desc by key
        (
            [DummyObject(1), DummyObject(3), DummyObject(2)],
            {
                'keys': ['value'],
                'reverse': True
            },
            [DummyObject(3), DummyObject(2), DummyObject(1)]
        ),
        # raise error when no keys given
        (
            [DummyObject(1), DummyObject(3), DummyObject(2)],
            {
                'keys': [],
                'reverse': True
            },
            ValueError
        ),
        # raise error when any of the keys given are not in the schema
        (
            [DummyObject(1), DummyObject(3), DummyObject(2)],
            {
                'keys': ['value', 'river_name'],
                'reverse': True
            },
            ValueError
        )
    ]
)
def test_sort_args(elements, sort_args, expected_result):
    """Test the sorting function used by the schema."""
    sort = SortArgs()
    sort.keys = sort_args['keys']
    sort.reverse = sort_args['reverse']
    args = {
        'sort': sort
    }
    if isclass(expected_result):
        with pytest.raises(expected_result):
            sort_elements(elements, args)
    else:
        sort_elements(elements, args)
        assert elements == expected_result


@pytest.mark.parametrize(
    'field_name', RUNTIME_FIELD_TO_CFG_MAP.keys()
)
def test_runtime_field_to_cfg_map(field_name: str):
    """Ensure the Runtime type's fields can be mapped back to the workflow
    config."""
    cfg_name = RUNTIME_FIELD_TO_CFG_MAP[field_name]
    assert field_name in Runtime.__dict__
    assert WORKFLOW_SPEC.get('runtime', '__MANY__', cfg_name)
