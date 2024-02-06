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


import ast
from unittest.mock import Mock

import pytest
import urwid

from cylc.flow.tui.app import BINDINGS
import cylc.flow.tui.overlay
from cylc.flow.workflow_status import WorkflowStatus


@pytest.fixture
def overlay_functions():
    """List overlay all generator functions in cylc.flow.tui.overlay

    Uses ast to parse functions out of the module.

    """
    filepath = cylc.flow.tui.overlay.__file__
    with open(filepath, 'r') as source_file:
        tree = ast.parse(source_file.read(), filename=filepath)

    return [
        getattr(cylc.flow.tui.overlay, obj.name)
        for obj in tree.body
        if isinstance(obj, ast.FunctionDef)
        and not obj.name.startswith('_')
    ]


def test_interface(overlay_functions):
    """Ensure all overlay functions have the correct signature."""
    for function in overlay_functions:
        # mock up an app object to keep things working
        app = Mock(
            filters={'tasks': {}, 'workflows': {'id': '.*'}},
            bindings=BINDINGS,
            tree_walker=Mock(
                get_focus=Mock(
                    return_value=[
                        Mock(
                            get_node=Mock(
                                return_value=Mock(
                                    get_value=lambda: {
                                        'id_': '~u/a',
                                        'type_': 'workflow',
                                        'data': {
                                            'status': WorkflowStatus.RUNNING,
                                        },
                                    }
                                )
                            )
                        )
                    ]
                )
            )
        )

        widget, options = function(app)

        assert isinstance(widget, urwid.Widget)
        assert isinstance(options, dict)
        assert 'width' in options
        assert 'height' in options
