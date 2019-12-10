import urwid
import os
import json

urwid.set_encoding('utf8')

FLOWS = json.load(open('data.json','r'))['data']['workflows']


TASK_ICONS = {
    'waiting': '\u25cb',
    'submitted': '\u2299',
    'running:0': '\u2299',
    'running:25': '\u25D4',
    'running:50': '\u25D1',
    'running:75': '\u25D5',
    'succeeded': '\u25CB',
    'failed': '\u2297'
}

JOB_ICON = '\u25A0'

JOB_COLOURS = {
    'submitted': '7DCFD4',
    'submitted': '8DD',
    'running': '6AA4F1',
    'running': '7AF',
    'succeeded': '51AF51',
    'succeeded': '5B5',
    'failed': 'CF4848',
    'failed': 'D55',
    'submit-failed': 'BE6AC0',
    'submit-failed': 'C7C'
}



class ExampleTreeWidget(urwid.TreeWidget):
    """ Display widget for leaf nodes """

    def get_display_text(self):
        #return self.get_node().get_value()['name']
        # return self.get_node().get_value()['data']['id'].rsplit('|', 1)[-1]
        node = self.get_node().get_value()
        type_ = node['type_']
        if type_ == 'task':
            return (
                f'{TASK_ICONS[node["data"]["state"]]}'
                ' '
                f'{node["data"]["name"]}'
            )
        elif type_ == 'job':
            return (
                f'#{node["data"]["submitNum"]:02d}'
                ' '
                f'{JOB_ICON}'
            )
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


class ExampleTreeBrowser:
    palette = [
        ('body', 'black', 'light gray'),
        ('focus', 'light gray', 'dark blue', 'standout'),
        ('head', 'yellow', 'black', 'standout'),
        ('foot', 'light gray', 'black'),
        ('key', 'light cyan', 'black', 'underline'),
        ('title', 'white', 'black', 'bold'),
        ('flag', 'dark gray', 'light gray'),
        ('error', 'dark red', 'light gray')
    ] + [
        (f'job_{state}', '', '', '', f'#{colour}', '')
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

    def __init__(self, data=None):
        self.topnode = ExampleParentNode(data)
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

        self.loop = urwid.MainLoop(self.view, self.palette,
            unhandled_input=self.unhandled_input)
        self.loop.run()

    def unhandled_input(self, k):
        if k in ('q','Q'):
            raise urwid.ExitMainLoop()


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
            'data': data,
            'type_': type_
        }
    return nodes[(type_, id_)]


def iter_flows():
    root = {
        'children': [],
        'type_': None,
        'data': {
            'id': 'Workflows'
        }
    }
    nodes = {}
    for flow in FLOWS:
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

def main():
    #for node in iter_flows():
    #    import pdb; pdb.set_trace()
    #sample = get_example_tree()
    sample = iter_flows()
    ExampleTreeBrowser(sample).main()


if __name__=="__main__":
    main()
