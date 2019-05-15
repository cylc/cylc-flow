#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
"""Cylc-modified xdot windows for the "cylc graph" command.

TODO - factor more commonality out of MyDotWindow, MyDotWindow2
"""


import gtk
import os
import re
import sys
import xdot

from cylc import LOG
from cylc.config import SuiteConfig
from cylc.cycling.loader import get_point
from cylc.graphing import CGraphPlain, CGraph, GHOST_TRANSP_HEX, gtk_rgb_to_hex
from cylc.gui import util
from cylc.task_id import TaskID


class MyOptions(object):
    """Object to hold options to pass to SuiteConfig."""

    def __init__(self, icp, collapsed, vis_initial, vis_final):
        self.icp = icp
        self.collapsed = collapsed
        self.vis_initial = vis_initial
        self.vis_final = vis_final


class CylcDotViewerCommon(xdot.DotWindow):

    def __init__(self, suite, suiterc, template_vars, orientation="TB",
                 should_hide=False, start_point_string=None,
                 stop_point_string=None, interactive=True):
        self.suite = suite
        self.suiterc = None
        self.template_vars = template_vars
        self.orientation = orientation
        self.should_hide = should_hide
        self.start_point_string = start_point_string
        self.stop_point_string = stop_point_string
        self.interactive = interactive

        self.outfile = None
        self.disable_output_image = False
        self.suitercfile = suiterc
        self.filter_recs = []

        util.setup_icons()
        gtk.Window.__init__(self)
        self.graph = xdot.Graph()
        self.set_icon(util.get_icon())
        self.set_default_size(512, 512)
        self.vbox = gtk.VBox()
        self.add(self.vbox)
        self.widget = xdot.DotWidget()

    def load_config(self):
        """Load the suite config."""
        if self.suiterc:
            is_reload = True
            collapsed = self.suiterc.closed_families
        else:
            is_reload = False
            collapsed = []
        try:
            self.suiterc = SuiteConfig(
                self.suite,
                self.suitercfile,
                MyOptions(
                    icp=self.start_point_string,
                    collapsed=collapsed,
                    vis_initial=self.start_point_string,
                    vis_final=self.stop_point_string,
                ),
                self.template_vars,
                is_reload=is_reload)
        except Exception as exc:
            msg = "Failed - parsing error?\n\n%s" % exc
            LOG.error(msg)
            if self.interactive:
                dia = gtk.MessageDialog(type=gtk.MESSAGE_ERROR,
                                        buttons=gtk.BUTTONS_OK,
                                        message_format=msg)
                dia.run()
                dia.destroy()
                return False
            sys.exit(1)
        self.inherit = self.suiterc.get_parent_lists()
        return True

    def on_refresh(self, w):
        """Re-load the suite config and refresh the graph."""
        if self.load_config():
            self.get_graph()
        else:
            self.set_dotcode('graph {}')

    def set_filter_graph_patterns(self, filter_patterns):
        """Set some regular expressions to filter out graph nodes."""
        self.filter_recs = [re.compile(_) for _ in filter_patterns]

    def filter_graph(self):
        """Apply any filter patterns to remove graph nodes."""
        if not self.filter_recs:
            return
        filter_nodes = set()
        for node in self.graph.nodes():
            for filter_rec in self.filter_recs:
                if filter_rec.search(node.get_name()):
                    filter_nodes.add(node)
        self.graph.cylc_remove_nodes_from(filter_nodes)


class MyDotWindow2(CylcDotViewerCommon):
    """Override xdot to get rid of some buttons + parse graph from suite.rc"""
    # used by "cylc graph" to plot runtime namespace graphs

    ui = '''
    <ui>
        <toolbar name="ToolBar">
            <toolitem action="ZoomIn"/>
            <toolitem action="ZoomOut"/>
            <toolitem action="ZoomFit"/>
            <toolitem action="Zoom100"/>
            <separator name="LeftToRightSep"/>
            <toolitem action="LeftToRight"/>
            <separator expand="true"/>
            <toolitem action="Refresh"/>
            <toolitem action="Save"/>
        </toolbar>
    </ui>
    '''

    def __init__(self, *args, **kwargs):
        CylcDotViewerCommon.__init__(self, *args, **kwargs)

        self.set_title('Cylc Suite Runtime Inheritance Graph Viewer')

        # Create a UIManager instance
        uimanager = self.uimanager = gtk.UIManager()

        # Add the accelerator group to the toplevel window
        accelgroup = uimanager.get_accel_group()
        self.add_accel_group(accelgroup)

        # Create an ActionGroup
        actiongroup = gtk.ActionGroup('Actions')
        self.actiongroup = actiongroup
        actiongroup.add_actions((
            ('ZoomIn', gtk.STOCK_ZOOM_IN, None, None, 'Zoom In',
                self.widget.on_zoom_in),
            ('ZoomOut', gtk.STOCK_ZOOM_OUT, None, None, 'Zoom Out',
                self.widget.on_zoom_out),
            ('ZoomFit', gtk.STOCK_ZOOM_FIT, None, None, 'Zoom Fit',
                self.widget.on_zoom_fit),
            ('Zoom100', gtk.STOCK_ZOOM_100, None, None, 'Zoom 100',
                self.widget.on_zoom_100),
            ('Refresh', gtk.STOCK_REFRESH, None, None, 'Refresh',
                self.on_refresh),
            ('Save', gtk.STOCK_SAVE_AS, None, None, 'Save', self.save_action),
        ))
        actiongroup.add_toggle_actions((
            ('LeftToRight', 'transpose', 'Transpose',
             None, 'Transpose the graph', self.on_left_to_right),
        ))

        # Add the actiongroup to the uimanager
        uimanager.insert_action_group(actiongroup, 0)

        # Add a UI descrption
        uimanager.add_ui_from_string(self.ui)

        left_to_right_toolitem = uimanager.get_widget(
            '/ToolBar/LeftToRight')
        left_to_right_toolitem.set_active(self.orientation == "LR")

        # Create a Toolbar

        toolbar = uimanager.get_widget('/ToolBar')
        self.vbox.pack_start(toolbar, False)
        self.vbox.pack_start(self.widget)

        self.set_focus(self.widget)

        if not self.should_hide:
            self.show_all()
        self.load_config()

    def get_graph(self):
        title = self.suite + ': runtime inheritance graph'
        graph = CGraphPlain(title)
        graph.set_def_style(
            gtk_rgb_to_hex(
                getattr(self.style, 'fg', None)[gtk.STATE_NORMAL]),
            gtk_rgb_to_hex(
                getattr(self.style, 'bg', None)[gtk.STATE_NORMAL])
        )
        graph.graph_attr['rankdir'] = self.orientation
        for ns in self.inherit:
            for p in self.inherit[ns]:
                graph.add_edge(p, ns)
                graph.get_node(p).attr['shape'] = 'box'
                graph.get_node(ns).attr['shape'] = 'box'

        self.graph = graph
        self.filter_graph()
        self.set_dotcode(graph.string())

    def on_left_to_right(self, toolitem):
        if toolitem.get_active():
            self.set_orientation("LR")  # Left to right ordering of nodes
        else:
            self.set_orientation("TB")  # Top to bottom (default) ordering

    def save_action(self, toolitem):
        chooser = gtk.FileChooserDialog(title="Save Graph",
                                        action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                        buttons=(gtk.STOCK_CANCEL,
                                                 gtk.RESPONSE_CANCEL,
                                                 gtk.STOCK_SAVE,
                                                 gtk.RESPONSE_OK))

        chooser.set_default_response(gtk.RESPONSE_OK)
        if self.outfile:
            chooser.set_filename(self.outfile)
        if chooser.run() == gtk.RESPONSE_OK:
            self.outfile = chooser.get_filename()
            if self.outfile:
                try:
                    self.graph.draw(self.outfile, prog='dot')
                except IOError, x:
                    msg = gtk.MessageDialog(type=gtk.MESSAGE_ERROR,
                                            buttons=gtk.BUTTONS_OK,
                                            message_format=str(x))
                    msg.run()
                    msg.destroy()
            chooser.destroy()
        else:
            chooser.destroy()

    def set_orientation(self, orientation="TB"):
        """Set the orientation of the graph node ordering."""
        if orientation == self.orientation:
            return False
        self.orientation = orientation
        self.get_graph()


class MyDotWindow(CylcDotViewerCommon):
    """Override xdot to get rid of some buttons + parse graph from suite.rc"""
    # used by "cylc graph" to plot dependency graphs

    ui = '''
    <ui>
        <toolbar name="ToolBar">
            <toolitem action="ZoomIn"/>
            <toolitem action="ZoomOut"/>
            <toolitem action="ZoomFit"/>
            <toolitem action="Zoom100"/>
            <toolitem action="Group"/>
            <toolitem action="UnGroup"/>
            <separator name="LeftToRightSep"/>
            <toolitem action="LeftToRight"/>
            <toolitem action="Subgraphs"/>
            <toolitem action="IgnoreSuicide"/>
            <separator expand="true"/>
            <toolitem action="Refresh"/>
            <toolitem action="Save"/>
        </toolbar>
    </ui>
    '''

    def __init__(self, suite, suiterc, template_vars,
                 start_point_string, stop_point_string, **kwargs):
        self.subgraphs_on = kwargs.get('subgraphs_on', False)
        self.ignore_suicide = kwargs.get('ignore_suicide', True)
        for kwarg in ['subgraphs_on', 'ignore_suicide']:
            try:
                del kwargs[kwarg]
            except KeyError:
                pass
        CylcDotViewerCommon.__init__(
            self, suite, suiterc, template_vars,
            start_point_string=start_point_string,
            stop_point_string=stop_point_string, **kwargs)

        self.set_title('Cylc Suite Dependency Graph Viewer')

        # Create a UIManager instance
        uimanager = self.uimanager = gtk.UIManager()

        # Add the accelerator group to the toplevel window
        accelgroup = uimanager.get_accel_group()
        self.add_accel_group(accelgroup)

        # create new stock icons for group and ungroup actions
        imagedir = util.get_image_dir() + '/icons'
        factory = gtk.IconFactory()
        for i in ['group', 'ungroup']:
            pixbuf = gtk.gdk.pixbuf_new_from_file(imagedir + '/' + i + '.png')
            iconset = gtk.IconSet(pixbuf)
            factory.add(i, iconset)
        factory.add_default()

        # Create an ActionGroup
        actiongroup = gtk.ActionGroup('Actions')
        self.actiongroup = actiongroup
        actiongroup.add_actions((
            ('ZoomIn', gtk.STOCK_ZOOM_IN, None, None, 'Zoom In',
                self.widget.on_zoom_in),
            ('ZoomOut', gtk.STOCK_ZOOM_OUT, None, None, 'Zoom Out',
                self.widget.on_zoom_out),
            ('ZoomFit', gtk.STOCK_ZOOM_FIT, None, None, 'Zoom Fit',
                self.widget.on_zoom_fit),
            ('Zoom100', gtk.STOCK_ZOOM_100, None, None, 'Zoom 100',
                self.widget.on_zoom_100),
            ('Group', 'group', 'Group', None, 'Group All Families',
                self.group_all),
            ('UnGroup', 'ungroup', 'Ungroup', None, 'Ungroup All Families',
                self.ungroup_all),
            ('Refresh', gtk.STOCK_REFRESH, None, None, 'Refresh',
                self.on_refresh),
            ('Save', gtk.STOCK_SAVE_AS, None, None, 'Save', self.save_action),
        ))
        actiongroup.add_toggle_actions((
            ('LeftToRight', 'transpose', 'Transpose',
             None, 'Transpose the graph', self.on_left_to_right),
        ))
        actiongroup.add_toggle_actions((
            ('Subgraphs', gtk.STOCK_LEAVE_FULLSCREEN, 'Cycle Point Subgraphs',
             None, 'Organise by cycle point', self.on_subgraphs),
        ))
        actiongroup.add_toggle_actions((
            ('IgnoreSuicide', gtk.STOCK_CANCEL, 'Ignore Suicide Triggers',
             None, 'Ignore Suicide Triggers', self.on_igsui),
        ))

        # Add the actiongroup to the uimanager
        uimanager.insert_action_group(actiongroup, 0)

        # Add a UI description
        uimanager.add_ui_from_string(self.ui)

        left_to_right_toolitem = uimanager.get_widget('/ToolBar/LeftToRight')
        left_to_right_toolitem.set_active(self.orientation == "LR")

        subgraphs_toolitem = uimanager.get_widget(
            '/ToolBar/Subgraphs')
        subgraphs_toolitem.set_active(self.subgraphs_on)

        igsui_toolitem = uimanager.get_widget(
            '/ToolBar/IgnoreSuicide')
        igsui_toolitem.set_active(self.ignore_suicide)

        # Create a Toolbar

        toolbar = uimanager.get_widget('/ToolBar')
        self.vbox.pack_start(toolbar, False)
        self.vbox.pack_start(self.widget)

        eb = gtk.EventBox()
        eb.add(gtk.Label("right-click on nodes to control family grouping"))
        eb.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('#8be'))
        self.vbox.pack_start(eb, False)

        self.set_focus(self.widget)

        if not self.should_hide:
            self.show_all()
        self.load_config()

    def group_all(self, w):
        self.get_graph(group_all=True)

    def ungroup_all(self, w):
        self.get_graph(ungroup_all=True)

    def is_off_sequence(self, name, point, cache=None):
        """Return True if task <name> at point <point> is off-sequence.

        (This implies inter-cycle dependence on a task that will not be
        instantiated at run time).
        """
        try:
            sequences = self.suiterc.taskdefs[name].sequences
        except KeyError:
            # Handle tasks not used in the graph.
            return False
        if not sequences:
            return False
        for sequence in sequences:
            p_str = str(point)
            if (cache and sequence in cache and p_str in cache[sequence]):
                if cache[sequence][p_str]:
                    return False
            else:
                temp = sequence.is_on_sequence(get_point(point))
                if cache is not None:
                    cache.setdefault(sequence, {})[p_str] = temp
                if temp:
                    return False
        return True

    def get_graph(self, group_nodes=None, ungroup_nodes=None,
                  ungroup_recursive=False, ungroup_all=False, group_all=False):
        if not self.suiterc:
            return
        family_nodes = self.suiterc.get_first_parent_descendants()
        # Note this is used by "cylc graph" but not gcylc.
        # self.start_ and self.stop_point_string come from CLI.
        bg_color = gtk_rgb_to_hex(
            getattr(self.style, 'bg', None)[gtk.STATE_NORMAL])
        fg_color = gtk_rgb_to_hex(
            getattr(self.style, 'fg', None)[gtk.STATE_NORMAL])
        graph = CGraph.get_graph(
            self.suiterc,
            group_nodes=group_nodes,
            ungroup_nodes=ungroup_nodes,
            ungroup_recursive=ungroup_recursive,
            group_all=group_all, ungroup_all=ungroup_all,
            ignore_suicide=self.ignore_suicide,
            subgraphs_on=self.subgraphs_on,
            bgcolor=bg_color, fgcolor=fg_color)

        graph.graph_attr['rankdir'] = self.orientation

        # Style nodes.
        cache = {}  # For caching is_on_sequence() calls.
        fg_ghost = "%s%s" % (fg_color, GHOST_TRANSP_HEX)
        for node in graph.iternodes():
            name, point = TaskID.split(node.get_name())
            if name.startswith('@'):
                # Style action trigger nodes.
                node.attr['shape'] = 'none'
            elif name in family_nodes:
                # Style family nodes.
                node.attr['shape'] = 'doubleoctagon'
                # Detecting ghost families would involve analysing triggers
                # in the suite's graphing.
            elif self.is_off_sequence(name, point, cache=cache):
                node.attr['style'] = 'dotted'
                node.attr['color'] = fg_ghost
                node.attr['fontcolor'] = fg_ghost

        self.graph = graph
        self.filter_graph()
        self.set_dotcode(graph.string())

    def on_left_to_right(self, toolitem):
        if toolitem.get_active():
            self.set_orientation("LR")  # Left to right ordering of nodes
        else:
            self.set_orientation("TB")  # Top to bottom (default) ordering

    def on_subgraphs(self, toolitem):
        self.subgraphs_on = toolitem.get_active()
        self.get_graph()

    def on_igsui(self, toolitem):
        self.ignore_suicide = toolitem.get_active()
        self.get_graph()

    def save_action(self, toolitem):
        chooser = gtk.FileChooserDialog(title="Save Graph",
                                        action=gtk.FILE_CHOOSER_ACTION_SAVE,
                                        buttons=(gtk.STOCK_CANCEL,
                                                 gtk.RESPONSE_CANCEL,
                                                 gtk.STOCK_SAVE,
                                                 gtk.RESPONSE_OK))

        chooser.set_default_response(gtk.RESPONSE_OK)
        if self.outfile:
            chooser.set_filename(self.outfile)
        if chooser.run() == gtk.RESPONSE_OK:
            self.outfile = chooser.get_filename()
            if self.outfile:
                try:
                    self.graph.draw(self.outfile, prog='dot')
                except IOError, x:
                    msg = gtk.MessageDialog(type=gtk.MESSAGE_ERROR,
                                            buttons=gtk.BUTTONS_OK,
                                            message_format=str(x))
                    msg.run()
                    msg.destroy()
            chooser.destroy()
        else:
            chooser.destroy()

    def set_orientation(self, orientation="TB"):
        """Set the orientation of the graph node ordering."""
        if orientation == self.orientation:
            return False
        self.orientation = orientation
        self.get_graph()


def get_reference_from_plain_format(plain_text):
    """Return a stripped text format for 'plain' graphviz output.

    Strip graph coordinates, extra spaces, and sort based on numeric
    content.

    """
    indexed_lines = []
    for line in plain_text.splitlines(True):
        # Remove spaces followed by numbers.
        line = re.sub(r"\s+[+-]?\d+(?:\.\d+)?(?:e[+-][.\d]+)?\b", r"", line)
        # Get rid of extra spaces.
        line = re.sub(r"^((?:node|edge).*)\s+\w+", r"\1", line)
        # Create a numeric content index.
        line_items = re.split(r"(\d+)", line)
        for i, item in enumerate(line_items):
            try:
                line_items[i] = int(item)
            except (TypeError, ValueError):
                pass
        indexed_lines.append((line_items, line))
    indexed_lines.sort()
    # Strip node styling info (may depend on desktop theme).
    lines = "".join(l[1] for l in indexed_lines)
    stripped_lines = []
    for line in lines.split("\n"):
        line_items = line.split(' ')
        stripped_lines.append(' '.join(line_items[0:3]))
    return '\n'.join(stripped_lines)
