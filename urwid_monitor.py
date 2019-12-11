import urwid
import os
import json

from cylc.flow.exceptions import ClientError
from cylc.flow.network.client import SuiteRuntimeClient

urwid.set_encoding('utf8')  # required for unicode task icons


FORE = 'default'
BACK = 'default'


SUITE_COLOURS = {
    'running': ('light blue', BACK),
    'held': ('brown', BACK),
    'stopping': ('light magenta', BACK),
    'error': ('light red', BACK, 'bold')
}

TASK_ICONS = {
    'waiting': '\u25cb',
    'ready': '\u25cb',  # TODO: remove
    'submitted': '\u2299',
    'running': '\u2299',
    #'running:0': '\u2299',
    #'running:25': '\u25D4',
    #'running:50': '\u25D1',
    #'running:75': '\u25D5',
    'succeeded': '\u25CB',
    'failed': '\u2297'
}

JOB_ICON = '\u25A0'

JOB_COLOURS = {
    'submitted': 'dark cyan',
    'running': 'light blue',
    'succeeded': 'dark green',
    'failed': 'light red',
    'submit-failed': 'light magenta',
    'ready': 'brown'
}


class MonitorWidget(urwid.TreeWidget):
    """Display widget for leaf nodes."""

    def __init__(self, node, max_depth=2): 
        # NOTE: copy of urwid.TreeWidget.__init__, the only difference
        #       being the self.expanded logic
        self._node = node 
        self._innerwidget = None 
        self.is_leaf = not hasattr(node, 'get_first_child') 
        self.expanded = node.get_depth() < max_depth
        widget = self.get_indented_widget() 
        urwid.WidgetWrap.__init__(self, widget) 

    def get_display_text(self):
        """Compute the text to display for a given node.

        Returns:
            (object) - Text content for the urwid.Text widget,
            may be a string, tuple or list, see urwid docs.

        """
        node = self.get_node()
        value = node.get_value()
        type_ = value['type_']
        if type_ == 'task':
            # the task icon
            ret = [f'{TASK_ICONS[value["data"]["state"]]} ']
            # the most recent job status
            try:
                state = node.get_child_node(0).get_value()['data']['state']
                ret += [(f'job_{state}', f'{JOB_ICON} ')]
            except IndexError:
                pass
            # the task name
            ret += [f'{value["data"]["name"]}']
            return ret
        elif type_ == 'job':
            return [
                f'#{value["data"]["submitNum"]:02d} ',
                (f'job_{value["data"]["state"]}', f'{JOB_ICON}')
            ]
        else:
            return value['data']['id'].rsplit('|', 1)[-1]


class MonitorNode(urwid.TreeNode):
    """Data storage object for leaf nodes."""

    def load_widget(self):
        return MonitorWidget(self)


class MonitorParentNode(urwid.ParentNode):
    """Data storage object for interior/parent nodes."""

    def load_widget(self):
        return MonitorWidget(self)

    def load_child_keys(self):
        # Note: keys are really indices.
        data = self.get_value()
        return range(len(data['children']))

    def load_child_node(self, key):
        """Return either an MonitorNode or MonitorParentNode"""
        childdata = self.get_value()['children'][key]
        if 'children' in childdata:
            childclass = MonitorParentNode
        else:
            childclass = MonitorNode
        return childclass(
            childdata,
            parent=self,
            key=key,
            depth=self.get_depth() + 1
        )


class MonitorTreeBrowser:

    UPDATE_INTERVAL = 1

    palette = [
        ('body', FORE, BACK),
        ('foot', 'white', 'dark blue'),
        ('key', 'light cyan', 'dark blue'),
        ('title', FORE, BACK, 'bold'),
    ] + [
        (f'job_{status}', colour, BACK)
        for status, colour in JOB_COLOURS.items()
    ] + [
        (f'suite_{status}',) + spec
        for status, spec in SUITE_COLOURS.items()
    ]

    FOOTER_TEXT = [
        'navigation: ',
        ('key', 'UP'),
        ',',
        ('key', 'DOWN'),
        ',',
        ('key', 'LEFT'),
        ',',
        ('key', 'PAGE-UP'),
        ',',
        ('key', 'PAGE-DOWN'),
        ',',
        ('key', 'HOME'),
        ',',
        ('key', 'END'),
        ' ',
        '  expand: ',
        ('key', '+'),
        ',',
        ('key', '-'),
        '  exit: ',
        ('key', 'Q'),
    ]

    def __init__(self, client):
        # the cylc data client
        self.client = client

        # create the template
        topnode = MonitorParentNode(dummy_flow())
        self.listbox = urwid.TreeListBox(urwid.TreeWalker(topnode))
        header = urwid.Text("\n")
        footer = urwid.AttrWrap(
            urwid.Text(self.FOOTER_TEXT),
            'foot'
        )
        self.view = urwid.Frame(
            urwid.AttrWrap( self.listbox, 'body'),
            header=urwid.AttrWrap(header, 'head'),
            footer=footer
        )

    def main(self):
        """Start the event loop."""
        self.loop = urwid.MainLoop(
            self.view,
            self.palette,
            unhandled_input=self.unhandled_input
        )
        # schedule the first update
        self.loop.set_alarm_in(0, self.update)
        self.loop.run()

    def get_snapshot(self):
        """Contact the workflow, return a tree structure

        In the event of error contacting the suite the
        message is written to this Widget's header.

        Returns:
            dict if successful, else False

        """
        try:
            data = self.client(
                'graphql',
                {
                    'request_string': QUERY,
                    'variables': {}
                }
            )
        except ClientError as exc:
            # cannot get data - present exception to user
            self.set_header(('suite_error', str(exc)))
            return False

        assert len(data['workflows']) == 1
        return iter_flow(data['workflows'][0])

    def find_closest_focus(self, old_node, new_node):
        """Return the position of the old node in the new tree.

        1. Attempts to find the old node in the new tree.
        2. Otherwise it walks up the old tree until it
           finds a node which is present in the new tree.
        3. Otherwise it returns the root node of the new tree.

        Arguments:
            old_node (urwid.TreeNode):
                The in-focus node from the deceased tree.
            new_node (urwid.TreeNode):
                The root node from the new tree.

        Returns
            urwid.TreeNode - The closest node.

        """

        def get_key(node):
            # TODO: this
            node_data = node.get_value()
            return (node_data['id_'], node_data['type_'])

        old_key = get_key(old_node)

        stack = [new_node]
        while stack:
            node = stack.pop()
            key = get_key(node)
            if key == old_key:
                return node
            else:
                stack.extend([
                    node.get_child_node(index)
                    for index in node.get_child_keys()
                ])

        if not old_node._parent:
            # new tree is unrelated to the old one - reset focus
            return new_node

        return self.find_closest_focus(
            old_node._parent,
            new_node
        )

    @staticmethod
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

    def translate_collapsing(self, old_node, new_node):
        """Transfer the collapse state from one tree to another.

        Arguments:
            old_node (urwid.TreeNode):
                Any node in the tree you want to copy the
                collapse/expand state from.
            new_node (urwid.TreeNode):
                Any node in the tree you want to copy the
                collapse/expand state to.

        """
        def get_key(node):  # TODO: can just use the ID
            node_data = node.get_value()
            return (node_data['id_'], node_data['type_'])

        old_root = old_node.get_root()
        new_root = new_node.get_root()

        old_tree = {
            get_key(node): node.get_widget().expanded
            for node in self.walk_tree(old_root)
        }

        for node in self.walk_tree(new_root):
            key = get_key(node)
            if key in old_tree:
                expanded = old_tree.get(key)
                if node.get_widget().expanded != expanded:
                    node.get_widget().expanded = expanded
                    node.get_widget().update_expanded_icon()

    @staticmethod
    def get_status_str(flow):
        """Return a suite status string for the header.

        Arguments:
            flow (dict):
                GraphQL JSON response for this workflow.

        Returns:
            list - Text list for the urwid.Text widget.

        """
        status = flow['status']
        return [
            (
                'title',
                flow['name'],
            ),
            ' - ',
            (
                f'suite_{status}',
                status
            )
        ]

    def set_header(self, message):
        """Set the header message for this widget.

        Arguments:
            message (object):
                Text content for the urwid.Text widget,
                may be a string, tuple or list, see urwid docs.

        """
        # put in a one line gap
        if isinstance(message, list):
            message.append('\n')
        elif isinstance(message, tuple):
            message = (message[0], message[1] + '\n')
        else:
            message += '\n'
        self.view.header = urwid.Text(message)

    def update(self, *args):
        """Refresh the data and redraw this widget.

        Preserves the current focus and collapse/expand state.

        """
        # update the data store
        # TODO: this can be done incrementally using deltas
        #       once this interface is available
        snapshot = self.get_snapshot()
        if snapshot is False:
            return False

        # update the suite status message
        self.set_header(self.get_status_str(snapshot['data']))

        # global update - the nuclear option - slow but simple
        # TODO: this can be done incrementally by adding and
        #       removing nodes from the existing tree
        topnode = MonitorParentNode(snapshot)

        # NOTE: because we are nuking the tree we need to manually
        # preserve the focus and collapse status of tree nodes

        # record the old focus
        _, old_node = self.listbox._body.get_focus()

        # nuke the tree
        self.listbox._set_body(urwid.TreeWalker(topnode))

        # get the new focus
        _, new_node = self.listbox._body.get_focus()

        # preserve the focus or walk to the nearest parent
        closest_focus = self.find_closest_focus(old_node, new_node)
        self.listbox._body.set_focus(closest_focus)

        # preserve the collapse/expand status of all nodes
        self.translate_collapsing(old_node, new_node)

        # schedule the next run of this update method
        self.loop.set_alarm_in(self.UPDATE_INTERVAL, self.update)

        return True

    def unhandled_input(self, k):
        if k in ('q','Q'):
            raise urwid.ExitMainLoop()
        # manual update
        #if k in ('u', 'U'):
        #    return self.update()


def add_node(type_, id_, data, nodes):
    if (type_, id_) not in nodes:
        nodes[(type_, id_)] = {
            'children': [],
            'id_': id_,
            'data': data,
            'type_': type_
        }
    return nodes[(type_, id_)]


def dummy_flow():
    return add_node(
        'worflow',
        '',
        {
            'id': 'Loading...'
        },
        {}
    )


def iter_flow(flow):
    nodes = {}
    flow_node = add_node(
        'workflow', flow['id'], flow, nodes)

    # create nodes
    for family_ in flow['families']:
        for family in family_['proxies']:
            if family['name'] != 'root':
                cycle_data = {
                    'name': family['cyclePoint'],
                    'id': f"{flow['id']}|{family['cyclePoint']}"
                }
                cycle_node = add_node(
                    'cycle', family['cyclePoint'], cycle_data, nodes)
                if cycle_node not in flow_node['children']:
                    flow_node['children'].append(cycle_node)
                family_node = add_node('family', family['id'], family, nodes)
    # create cycle/family tree
    for family_ in flow['families']:
        for family in family_['proxies']:
            if family['name'] != 'root':
                family_node = add_node(
                    'family', family['id'], None, nodes)
                first_parent = family['firstParent']
                if (
                    first_parent
                    and first_parent['name'] != 'root'
                ):
                    parent_node = add_node(
                        'family', first_parent['id'], None, nodes)
                    parent_node['children'].append(family_node)
                else:
                    cycle_node = add_node(
                        'cycle', family['cyclePoint'], None, nodes)
                    cycle_node['children'].append(family_node)
    # add leaves
    for task in flow['taskProxies']:
        parents = task['parents']
        task_node = add_node(
            'task', task['id'], task, nodes)
        if parents[0]['name'] == 'root':
            family_node = add_node(
                'cycle', task['cyclePoint'], None, nodes)
        else:
            family_node = add_node(
                'family', parents[0]['id'], None, nodes)
        family_node['children'].append(task_node)
        for job in task['jobs']:
            job_node = add_node(
                'job', job['id'], job, nodes)
            task_node['children'].append(job_node)

    return flow_node


QUERY = open('query.ql', 'r').read()


def main(suite):
    client = SuiteRuntimeClient(suite)
    MonitorTreeBrowser(client).main()


if __name__=="__main__":
    main('generic')
