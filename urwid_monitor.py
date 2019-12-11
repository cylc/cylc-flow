import urwid
import os
import json

from cylc.flow.exceptions import ClientError
from cylc.flow.network.client import SuiteRuntimeClient

urwid.set_encoding('utf8')  # required for unicode task icons


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


class ExampleTreeWidget(urwid.TreeWidget):
    """ Display widget for leaf nodes """

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
        node = self.get_node().get_value()
        type_ = node['type_']
        if type_ == 'task':
            ret = [f'{TASK_ICONS[node["data"]["state"]]} ']

            try:
                state = self.get_node().get_child_node(0).get_value()['data']['state']
                ret += [(f'job_{state}', f'{JOB_ICON} ')]
            except IndexError:
                pass

            ret += [f'{node["data"]["name"]}']
            return ret
        elif type_ == 'job':
            return [
                f'#{node["data"]["submitNum"]:02d} ',
                (f'job_{node["data"]["state"]}', f'{JOB_ICON}')
            ]
        else:
            return node['data']['id'].rsplit('|', 1)[-1]


class ExampleNode(urwid.TreeNode):
    """ Data storage object for leaf nodes """

    def load_widget(self):
        return ExampleTreeWidget(self)


class ExampleParentNode(urwid.ParentNode):
    """ Data storage object for interior/parent nodes """

    def load_widget(self):
        return ExampleTreeWidget(self)

    def load_child_keys(self):
        data = self.get_value()
        return range(len(data['children']))

    def load_child_node(self, key):
        """Return either an ExampleNode or ExampleParentNode"""
        childdata = self.get_value()['children'][key]
        childdepth = self.get_depth() + 1
        if 'children' in childdata:
            childclass = ExampleParentNode
        else:
            childclass = ExampleNode
        return childclass(childdata, parent=self, key=key, depth=childdepth)


FORE = 'default'
BACK = 'default'


class ExampleTreeBrowser:

    UPDATE_INTERVAL = 1

    palette = [
        ('body', FORE, BACK),
        ('focus', BACK, 'dark blue', 'standout'),
        ('head', 'yellow', FORE, 'standout'),
        ('foot', BACK, FORE),
        ('key', 'dark cyan', FORE, 'underline'),
        ('title', FORE, BACK, 'bold'),
    ] + [
        (f'job_{state}', colour, BACK)
        for state, colour in JOB_COLOURS.items()
    ]

    footer_text = [
        ('title', "Example Data Browser"), "    ",
        ('key', "UP"), ",", ('key', "DOWN"), ",",
        ('key', "PAGE UP"), ",", ('key', "PAGE DOWN"),
        "  ",
        ('key', "+"), ",",
        ('key', "-"), "  ",
        ('key', "LEFT"), "  ",
        ('key', "HOME"), "  ",
        ('key', "END"), "  ",
        ('key', "Q"),
        ]

    def __init__(self, client):
        self.client = client
        self.topnode = ExampleParentNode(self.get_snapshot())
        self.listbox = urwid.TreeListBox(urwid.TreeWalker(self.topnode))
        self.listbox.offset_rows = 1
        self.header = urwid.Text( "header" )
        self.footer = urwid.AttrWrap( urwid.Text( self.footer_text ),
            'foot')
        self.view = urwid.Frame(
            urwid.AttrWrap( self.listbox, 'body' ),
            header=urwid.AttrWrap(self.header, 'head' ),
            footer=self.footer )

    def main(self):
        """Run the program."""
        self.loop = urwid.MainLoop(
            self.view,
            self.palette,
            unhandled_input=self.unhandled_input
        )
        self.loop.set_alarm_in(self.UPDATE_INTERVAL, self.update)
        self.loop.run()

    def get_snapshot(self):
        try:
            data = self.client(
                'graphql',
                {
                    'request_string': QUERY,
                    'variables': {}
                }
            )
        except ClientError:
            pass
            # TODO: raise warning
        assert len(data['workflows']) == 1
        return iter_flow(data['workflows'][0])

    def find_closest_focus(self, old_node, new_node):

        def get_key(node):
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
            raise IndexError()

        return self.find_closest_focus(
            old_node._parent,
            new_focus
        )

    @staticmethod
    def walk_tree(node):
        stack = [node]
        while stack:
            node = stack.pop()
            yield node
            stack.extend([
                node.get_child_node(index)
                for index in node.get_child_keys()
            ])

    def translate_collapsing(self, old_node, new_node):
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

    def set_header(self, message):
        self.view.header = urwid.Text(message)

    def update(self, *args):
        # update the data store
        # TODO: this can be done incrementally using deltas
        #       once this interface is available
        snapshot = self.get_snapshot()

        # global update - the nuclear option - slow but simple
        # TODO: this can be done incrementally by adding and
        #       removing nodes from the existing tree
        self.topnode = ExampleParentNode(snapshot)

        # NOTE: because we are nuking the tree we need to manually
        # preserve the focus and collapse status of tree nodes

        # record the old focus
        _, old_node = self.listbox._body.get_focus()

        # nuke the tree
        self.listbox._set_body(urwid.TreeWalker(self.topnode))

        # get the new focus
        _, new_node = self.listbox._body.get_focus()

        # preserve the focus or walk to the nearest parent
        closest_focus = self.find_closest_focus(old_node, new_node)
        self.listbox._body.set_focus(closest_focus)

        # preserve the collapse/expand status of all nodes
        self.translate_collapsing(old_node, new_node)

        # schedule the next run of this update method
        self.loop.set_alarm_in(self.UPDATE_INTERVAL, self.update)

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
    ExampleTreeBrowser(client).main()


if __name__=="__main__":
    main('generic')
