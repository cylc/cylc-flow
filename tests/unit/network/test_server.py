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

from typing import Any, NoReturn
from unittest.mock import Mock

import pytest

from cylc.flow.network.server import WorkflowRuntimeServer


class CustomError(Exception):
    ...


def _raise_exc(*a, **k) -> NoReturn:
    raise CustomError("Mock error")


@pytest.mark.parametrize(
    'message, expected_method_args, expected_content, expected_err_msg',
    [
        pytest.param(
            {'command': 'some_method', 'args': {'foo': 1}, 'meta': 42},
            {'foo': 1, 'user': 'darmok', 'meta': 42},
            "Ok",
            None,
            id="Normal"
        ),
        pytest.param(
            {'command': 'non_exist', 'args': {}},
            None,
            None,
            "No method by the name",
            id="Method doesn't exist"
        ),
        pytest.param(
            {'args': {}},
            None,
            None,
            "Request missing required field",
            id="Missing command field"
        ),
        pytest.param(
            {'command': 'some_method'},
            None,
            None,
            "Request missing required field",
            id="Missing args field"
        ),
        pytest.param(
            {'command': 'raise_exc', 'args': {}},
            None,
            None,
            "Mock error",
            id="Exception in command method"
        ),
    ]
)
def test_receiver(
    message: dict,
    expected_method_args: dict,
    expected_content: Any,
    expected_err_msg: str
):
    """Test receiver."""
    user = 'darmok'
    _some_method = Mock(return_value="Ok")
    server = WorkflowRuntimeServer(Mock())
    server.some_method = _some_method  # type: ignore[attr-defined]
    server.raise_exc = _raise_exc  # type: ignore[attr-defined]

    result = server.receiver(message, user)
    if expected_method_args is not None:
        _some_method.assert_called_with(**expected_method_args)
    # Zeroth element of response tuple should be content
    assert result[0] == expected_content
    # Next should be error
    if expected_err_msg:
        assert isinstance(result[1], tuple)
        assert expected_err_msg in result[1][0]
    else:
        assert result[1] is None
        # Last is user
        assert result[2] == user
