#!/usr/bin/env python3
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
"""Tree utilities for Tui."""


def find_closest_focus(app, old_node, new_node):
    """Return the position of the old node in the new tree.

    1. Attempts to find the old node in the new tree.
    2. Otherwise it walks up the old tree until it
       finds a node which is present in the new tree.
    3. Otherwise it returns the root node of the new tree.

    Arguments:
        app (TuiApp):
            Tui app instance.
        old_node (MonitorNode):
            The in-focus node from the deceased tree.
        new_node (MonitorNode):
            The root node from the new tree.

    Returns
        MonitorNode - The closest node.

    """
    old_key = app.get_node_id(old_node)

    for node in walk_tree(new_node):
        if old_key == app.get_node_id(node):
            # (1)
            return node

    if not old_node._parent:
        # (3) reset focus
        return new_node

    # (2)
    return find_closest_focus(
        app,
        old_node._parent,
        new_node
    )


def translate_collapsing(app, old_node, new_node):
    """Transfer the collapse state from one tree to another.

    Arguments:
        app (TuiApp):
            Tui app instance.
        old_node (MonitorNode):
            Any node in the tree you want to copy the
            collapse/expand state from.
        new_node (MonitorNode):
            Any node in the tree you want to copy the
            collapse/expand state to.

    """
    old_root = old_node.get_root()
    new_root = new_node.get_root()

    old_tree = {
        app.get_node_id(node): node.get_widget().expanded
        for node in walk_tree(old_root)
    }

    for node in walk_tree(new_root):
        key = app.get_node_id(node)
        if key in old_tree:
            expanded = old_tree.get(key)
            widget = node.get_widget()
            if widget.expanded != expanded:
                widget.expanded = expanded
                widget.update_expanded_icon()


def walk_tree(node):
    """Yield nodes in order.

    Arguments:
        node (urwid.TreeNode):
            Yield this node and all nodes beneath it.

    Yields:
        urwid.TreeNode

    """
    stack = [node]
    while stack:
        node = stack.pop()
        yield node
        stack.extend([
            node.get_child_node(index)
            for index in node.get_child_keys()
        ])
