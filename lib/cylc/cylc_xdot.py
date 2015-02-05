#!/usr/bin/env

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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

import xdot
from gui import util
import subprocess
import gtk
import time
import gobject
import config
import os, sys
import re
from graphing import CGraphPlain
from cylc.task_id import TaskID

"""
Cylc-modified xdot windows for the "cylc graph" command.
TODO - factor more commonality out of MyDotWindow, MyDotWindow2
"""

class CylcDotViewerCommon(xdot.DotWindow):
    def load_config(self):
        if self.suiterc:
            is_reload = True
            collapsed = self.suiterc.closed_families
        else:
            is_reload = False
            collapsed = []
        try:
            self.suiterc = config.config(self.suite, self.file,
                    template_vars=self.template_vars,
                    template_vars_file=self.template_vars_file,
                    is_reload=is_reload, collapsed=collapsed,
                    vis_start_string=self.start_point_string,
                    vis_stop_string=self.stop_point_string)
        except Exception, x:
            print >> sys.stderr, "Failed - parsing error?"
            print >> sys.stderr, x
            return False
        self.inherit = self.suiterc.get_parent_lists()
        return True

class MyDotWindow2(CylcDotViewerCommon):
    """Override xdot to get rid of some buttons and parse graph from suite.rc"""
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
    def __init__(self, suite, suiterc, template_vars,
            template_vars_file, orientation="TB",
            should_hide=False):
        self.outfile = None
        self.disable_output_image = False
        self.suite = suite
        self.file = suiterc
        self.suiterc = None
        self.orientation = orientation
        self.template_vars = template_vars
        self.template_vars_file = template_vars_file
        self.start_point_string = None
        self.stop_point_string = None

        util.setup_icons()

        gtk.Window.__init__(self)

        self.graph = xdot.Graph()

        window = self

        window.set_title('Cylc Suite Runtime Inheritance Graph Viewer')
        window.set_default_size(512, 512)
        window.set_icon( util.get_icon() )

        vbox = gtk.VBox()
        window.add(vbox)

        self.widget = xdot.DotWidget()

        # Create a UIManager instance
        uimanager = self.uimanager = gtk.UIManager()

        # Add the accelerator group to the toplevel window
        accelgroup = uimanager.get_accel_group()
        window.add_accel_group(accelgroup)

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
        vbox.pack_start(toolbar, False)
        vbox.pack_start(self.widget)

        self.set_focus(self.widget)

        if not should_hide:
            self.show_all()
        self.load_config()

    def get_graph( self ):
        title = self.suite + ': runtime inheritance graph'
        graph = CGraphPlain( title )
        graph.graph_attr['rankdir'] = self.orientation
        for ns in self.inherit:
            for p in self.inherit[ns]:
                attr = {}
                attr['color'] = 'royalblue'
                graph.add_edge( p, ns, **attr )
                nl = graph.get_node( p )
                nr = graph.get_node( ns )
                for n in nl, nr:
                    n.attr['shape'] = 'box'
                    n.attr['style'] = 'filled'
                    n.attr['fillcolor'] = 'powderblue'
                    n.attr['color'] = 'royalblue'

        self.set_dotcode( graph.string() )
        self.graph = graph

    def on_left_to_right( self, toolitem ):
        if toolitem.get_active():
            self.set_orientation( "LR" )  # Left to right ordering of nodes
        else:
            self.set_orientation( "TB" )  # Top to bottom (default) ordering

    def save_action( self, toolitem ):
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
                    self.graph.draw( self.outfile, prog='dot' )
                except IOError, x:
                    msg = gtk.MessageDialog(type=gtk.MESSAGE_ERROR,
                                            buttons=gtk.BUTTONS_OK,
                                            message_format=str(x))
                    msg.run()
                    msg.destroy()
            chooser.destroy()
        else:
            chooser.destroy()

    def set_orientation( self, orientation="TB" ):
        """Set the orientation of the graph node ordering."""
        if orientation == self.orientation:
            return False
        self.orientation = orientation
        self.get_graph()

    def on_refresh(self, w):
        self.load_config()
        self.get_graph()
        return True


class MyDotWindow( CylcDotViewerCommon ):
    """Override xdot to get rid of some buttons and parse graph from suite.rc"""
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
    def __init__(self, suite, suiterc, start_point_string, stop_point_string,
            template_vars, template_vars_file, orientation="TB",
            subgraphs_on=False, should_hide=False):
        self.outfile = None
        self.disable_output_image = False
        self.suite = suite
        self.file = suiterc
        self.suiterc = None
        self.orientation = orientation
        self.subgraphs_on = subgraphs_on
        self.template_vars = template_vars
        self.template_vars_file = template_vars_file
        self.ignore_suicide = False
        self.start_point_string = start_point_string
        self.stop_point_string = stop_point_string

        util.setup_icons()

        gtk.Window.__init__(self)

        self.graph = xdot.Graph()

        window = self

        window.set_title('Cylc Suite Dependency Graph Viewer')
        window.set_default_size(512, 512)
        window.set_icon( util.get_icon() )
        vbox = gtk.VBox()
        window.add(vbox)

        self.widget = xdot.DotWidget()

        # Create a UIManager instance
        uimanager = self.uimanager = gtk.UIManager()

        # Add the accelerator group to the toplevel window
        accelgroup = uimanager.get_accel_group()
        window.add_accel_group(accelgroup)

        # Create an ActionGroup
        actiongroup = gtk.ActionGroup('Actions')
        self.actiongroup = actiongroup

        # create new stock icons for group and ungroup actions
        imagedir = os.environ[ 'CYLC_DIR' ] + '/images/icons'
        factory = gtk.IconFactory()
        for i in [ 'group', 'ungroup' ]:
            pixbuf = gtk.gdk.pixbuf_new_from_file( imagedir + '/' + i + '.png' )
            iconset = gtk.IconSet(pixbuf)
            factory.add( i, iconset )
        factory.add_default()

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

        # Add a UI descrption
        uimanager.add_ui_from_string(self.ui)

        left_to_right_toolitem = uimanager.get_widget('/ToolBar/LeftToRight')
        left_to_right_toolitem.set_active(self.orientation == "LR")

        subgraphs_toolitem = uimanager.get_widget(
            '/ToolBar/Subgraphs')
        subgraphs_toolitem.set_active(self.subgraphs_on)

        # Create a Toolbar

        toolbar = uimanager.get_widget('/ToolBar')
        vbox.pack_start(toolbar, False)
        vbox.pack_start(self.widget)

        eb = gtk.EventBox()
        eb.add( gtk.Label( "right-click on nodes to control family grouping" ) )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#8be' ) )
        vbox.pack_start( eb, False )

        self.set_focus(self.widget)

        if not should_hide:
            self.show_all()
        self.load_config()

    def group_all( self, w ):
        self.get_graph( group_all=True )

    def ungroup_all( self, w ):
        self.get_graph( ungroup_all=True )

    def get_graph( self, group_nodes=[], ungroup_nodes=[],
            ungroup_recursive=False, ungroup_all=False, group_all=False ):
        family_nodes = self.suiterc.get_first_parent_descendants().keys()
        graphed_family_nodes = self.suiterc.triggering_families
        suite_polling_tasks = self.suiterc.suite_polling_tasks
        # Note this is used by "cylc graph" but not gcylc.
        # self.start_ and self.stop_point_string come from CLI.
        graph = self.suiterc.get_graph(
                group_nodes=group_nodes,
                ungroup_nodes=ungroup_nodes,
                ungroup_recursive=ungroup_recursive,
                group_all=group_all, ungroup_all=ungroup_all,
                ignore_suicide=self.ignore_suicide,
                subgraphs_on=self.subgraphs_on )

        graph.graph_attr['rankdir'] = self.orientation

        for node in graph.nodes():
            name, point_string = TaskID.split(node.get_name())
            if name in family_nodes:
                if name in graphed_family_nodes:
                    node.attr['shape'] = 'doubleoctagon'
                else:
                    node.attr['shape'] = 'tripleoctagon'

        self.set_dotcode( graph.string() )
        self.graph = graph

    def on_left_to_right( self, toolitem ):
        if toolitem.get_active():
            self.set_orientation( "LR" )  # Left to right ordering of nodes
        else:
            self.set_orientation( "TB" )  # Top to bottom (default) ordering

    def on_subgraphs( self, toolitem ):
        self.subgraphs_on = toolitem.get_active()
        self.get_graph()
 
    def on_igsui( self, toolitem ):
        self.ignore_suicide = toolitem.get_active()
        self.get_graph()

    def save_action( self, toolitem ):
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
                    self.graph.draw( self.outfile, prog='dot' )
                except IOError, x:
                    msg = gtk.MessageDialog(type=gtk.MESSAGE_ERROR,
                                            buttons=gtk.BUTTONS_OK,
                                            message_format=str(x))
                    msg.run()
                    msg.destroy()
            chooser.destroy()
        else:
            chooser.destroy()

    def set_orientation( self, orientation="TB" ):
        """Set the orientation of the graph node ordering."""
        if orientation == self.orientation:
            return False
        self.orientation = orientation
        self.get_graph()

    def on_refresh(self, w):
        self.load_config()
        self.get_graph()
        return True


class DotTipWidget(xdot.DotWidget):

    """Subclass that allows connection of 'motion-notify-event'."""

    def on_area_motion_notify(self, area, event):
        """This returns False, instead of True as in the base class."""
        self.drag_action.on_motion_notify(event)
        return False


class xdot_widgets(object):
    """Used only by the GUI graph view."""

    def __init__(self):
        self.graph = xdot.Graph()

        self.vbox = gtk.VBox()

        self.widget = DotTipWidget()

        zoomin_button = gtk.Button( stock=gtk.STOCK_ZOOM_IN )
        zoomin_button.connect('clicked', self.widget.on_zoom_in)
        zoomout_button = gtk.Button( stock=gtk.STOCK_ZOOM_OUT )
        zoomout_button.connect('clicked', self.widget.on_zoom_out)
        zoomfit_button = gtk.Button( stock=gtk.STOCK_ZOOM_FIT )
        zoomfit_button.connect('clicked', self.widget.on_zoom_fit)
        zoom100_button = gtk.Button( stock=gtk.STOCK_ZOOM_100 )
        zoom100_button.connect('clicked', self.widget.on_zoom_100)

        self.graph_disconnect_button = gtk.ToggleButton( '_DISconnect' )
        self.graph_disconnect_button.set_active(False)
        self.graph_update_button = gtk.Button( '_Update' )
        self.graph_update_button.set_sensitive(False)

        bbox = gtk.HButtonBox()
        bbox.add( zoomin_button )
        bbox.add( zoomout_button )
        bbox.add( zoomfit_button )
        bbox.add( zoom100_button )
        bbox.add( self.graph_disconnect_button )
        bbox.add( self.graph_update_button )
        bbox.set_layout(gtk.BUTTONBOX_SPREAD)

        self.vbox.pack_start(self.widget)
        self.vbox.pack_start(bbox, False)

    def get( self ):
        return self.vbox

    def set_filter(self, filter):
        self.widget.set_filter(filter)

    def set_dotcode(self, dotcode, filename='<stdin>', no_zoom=False):
        if no_zoom:
            old_zoom_func = self.widget.zoom_image
            self.widget.zoom_image = lambda *a, **b: self.widget.queue_draw()
        if self.widget.set_dotcode(dotcode, filename):
            #self.set_title(os.path.basename(filename) + ' - Dot Viewer')
            # disable automatic zoom-to-fit on update
            #self.widget.zoom_to_fit()
            pass
        if no_zoom:
            self.widget.zoom_image = old_zoom_func

    def set_xdotcode(self, xdotcode, filename='<stdin>'):
        if self.widget.set_xdotcode(xdotcode):
            #self.set_title(os.path.basename(filename) + ' - Dot Viewer')
            # disable automatic zoom-to-fit on update
            #self.widget.zoom_to_fit()
            pass

    def on_reload(self, action):
        self.widget.reload()


def get_reference_from_plain_format(plain_text):
    """Return a stripped text format for 'plain' graphviz output.

    Strip graph coordinates, extra spaces, and sort based on numeric
    content.

    """
    indexed_lines = []
    for line in plain_text.splitlines(True):
        # Remove spaces followed by numbers.
        line = re.sub(r"\s+[+-]?\d+(?:\.\d+)?(?:e[+-][.\d]+)?\b", "", line)
        # Get rid of extra spaces.
        line = re.sub("^((?:node|edge).*)\s+\w+", r"\1", line)
        # Create a numeric content index.
        line_items = re.split("(\d+)", line)
        for i, item in enumerate(line_items):
            try:
                line_items[i] = int(item)
            except (TypeError, ValueError):
                pass
        indexed_lines.append((line_items, line))
    indexed_lines.sort()
    return "".join([l[1] for l in indexed_lines])
