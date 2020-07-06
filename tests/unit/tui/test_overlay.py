import ast
from unittest.mock import Mock

import pytest
import urwid

import cylc.flow.tui.overlay


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
    ]


def test_interface(overlay_functions):
    """Ensure all overlay functions have the correct signature."""
    for function in overlay_functions:
        # mock up an app object to keep things working
        app = Mock(
            filter_states={},
            tree_walker=Mock(
                get_focus=Mock(
                    return_value=[
                        Mock(
                            get_node=Mock(
                                return_value=Mock(
                                    get_value=lambda: {'id_': 'a'}
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
