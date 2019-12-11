import urwid
import os
import json

urwid.set_encoding('utf8')

FLOWS = json.load(open('data.json','r'))['data']['workflows']


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

    def __init__(self, node, max_depth=3): 
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
        self.header = urwid.Text( "" )
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
        self.loop.run()

    def get_snapshot(self):
        data = poll(self.client)
        return iter_flows(data)

    def find_closest_focus(self, old_focus, new_focus):
        _, old_node = old_focus
        xyz, new_node = new_focus

        def get_key(node):
            node_data = node.get_value()
            return (node_data['id_'], node_data['type_'])

        old_key = get_key(old_node)

        stack = [new_node]
        while stack:
            node = stack.pop()
            key = get_key(node)
            if key == old_key:
                return (xyz, node)
            else:
                stack.extend([
                    node.get_child_node(index)
                    for index in node.get_child_keys()
                ])

        if not old_node._parent:
            raise IndexError()

        return self.find_closest_focus(
            (xyz, old_node._parent),
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

    def update(self):
        snapshot = self.get_snapshot()
        self.topnode = ExampleParentNode(self.get_snapshot())
        old_focus = self.listbox._body.get_focus()
        self.listbox._set_body(urwid.TreeWalker(self.topnode))
        new_focus = self.listbox._body.get_focus()
        closest_focus = self.find_closest_focus(old_focus, new_focus)
        self.listbox._body.set_focus(closest_focus[1])

        self.translate_collapsing(
            old_focus[1],
            new_focus[1]
        )

    def unhandled_input(self, k):
        if k in ('q','Q'):
            raise urwid.ExitMainLoop()
        if k in ('u', 'U'):
            return self.update()


def get_example_tree():
    """ generate a quick 100 leaf tree for demo purposes """
    retval = {"name":"parent","children":[]}
    for i in range(10):
        retval['children'].append({"name":"child " + str(i)})
        retval['children'][i]['children']=[]
        for j in range(10):
            retval['children'][i]['children'].append({"name":"grandchild " +
                                                      str(i) + "." + str(j)})
    return retval

def get_example_tree2():
    ret = {
        'name': 'parent',
        'children': []
    }
    for flow in FLOWS:
        flow_node = {
            'name': flow['name'],
            'children': []
        }
        ret['children'].append(flow_node)
    return ret


def add_node(type_, id_, data, nodes):
    if (type_, id_) not in nodes:
        nodes[(type_, id_)] = {
            'children': [],
            'id_': id_,
            'data': data,
            'type_': type_
        }
    return nodes[(type_, id_)]


def iter_flows(data):
    root = {  # TODO: generate this via add_node
        'children': [],
        'type_': None,
        'id_': 'root',
        'data': {
            'id': 'Workflows'
        }
    }
    nodes = {}
    for flow in data:
        flow_node = add_node(
            'workflow', flow['id'], flow, nodes)
        # create nodes
        for family_ in flow['families']:
            for family in family_['proxies']:
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
                family_node = add_node(
                    'family', family['id'], None, nodes)
                first_parent = family['firstParent']
                if first_parent:
                    parent_node = add_node(
                        'family', first_parent['id'], None, nodes)
                    parent_node['children'].append(family_node)
                else:
                    cycle_node = add_node(
                        'cycle', family['cyclePoint'], None, nodes)
                    cycle_node['children'].append(family_node)
        # add leaves
        for task in flow['taskProxies']:
            parents = task['parents'] or [{'id': 'root'}]
            task_node = add_node(
                'task', task['id'], task, nodes)
            family_node = add_node(
                'family', parents[0]['id'], None, nodes)
            family_node['children'].append(task_node)
            for job in task['jobs']:
                job_node = add_node(
                    'job', job['id'], job, nodes)
                task_node['children'].append(job_node)

        root['children'].append(flow_node)

    return root


from cylc.flow.network.client import SuiteRuntimeClient

QUERY = open('query.ql', 'r').read()

def poll(client):
    return client(
        'graphql',
        {
            'request_string': QUERY,
            'variables': {}
        }
    )['workflows']


def main(suite):
    client = SuiteRuntimeClient(suite)
    ExampleTreeBrowser(client).main()


if __name__=="__main__":
    main('generic')
