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


def expand_tree(app, tree_node, id_, depth=5, node_types=None):
    """Expand the Tui tree to the desired level.

    Arguments:
        app:
            The Tui application instance.
        tree_node:
            The Tui widget representing the tree view.
        id_:
            If specified, we will look within the tree for a node matching
            this ID and the tree below this node will be expanded.
        depth:
            The max depth to expand nodes too.
        node_types:
            Whitelist of node types to expand, note "task", "job" and "spring"
            nodes are excluded by default.

    Returns:
        True, if the node was found in the tree, is loaded and has been
        expanded.

    Examples:
        # expand the top three levels of the tree
        compute_tree(app, node, None, 3)

        # expand the "root" node AND the top five levels of the tree under
        # ~user/workflow
        compute_tree(app, node, '~user/workflow')

    """
    if not node_types:
        # don't auto-expand job nodes by default
        node_types = {'root', 'workflow', 'cycle', 'family'}

    root_node = tree_node.get_root()
    requested_node = root_node

    # locate the "id_" within the tree if specified
    if id_:
        for node in walk_tree(root_node):
            key = app.get_node_id(node)
            if key == id_:
                requested_node = node
                child_keys = node.get_child_keys()
                if (
                    # if the node only has one child
                    len(child_keys) == 1
                    # and that child is a "#spring" node (i.e. a loading node)
                    and (
                        node.get_child_node(0).get_value()['type_']
                    ) == '#spring'
                ):
                    # then the content hasn't loaded yet so the node cannot be
                    # expanded
                    return False
                break
        else:
            # the requested node does not exist yet
            # it might still be loading
            return False

    # expand the specified nodes
    for node in (*walk_tree(requested_node, depth), root_node):
        if node.get_value()['type_'] not in node_types:
            continue
        widget = node.get_widget()
        widget.expanded = True
        widget.update_expanded_icon(False)

    return True


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
            # this node was present before
            # => translate its expansion to the new tree
            expanded = old_tree.get(key)
            widget = node.get_widget()
            if widget.expanded != expanded:
                widget.expanded = expanded
                widget.update_expanded_icon(False)
        else:
            # this node was not present before
            # => apply the standard expansion logic
            expand_tree(
                app,
                node,
                key,
                3,
                # don't auto-expand workflows, only cycles/families
                # and the root node to help expand the tree on startup
                node_types={'root', 'cycle', 'family'}
            )


def walk_tree(node, depth=None):
    """Yield nodes in order.

    Arguments:
        node (urwid.TreeNode):
            Yield this node and all nodes beneath it.
        depth:
            The maximum depth to walk to or None to walk all children.

    Yields:
        urwid.TreeNode

    """
    stack = [(node, 1)]
    while stack:
        node, _depth = stack.pop()
        yield node
        if depth is None or _depth < depth:
            stack.extend([
                (node.get_child_node(index), _depth + 1)
                for index in node.get_child_keys()
            ])
