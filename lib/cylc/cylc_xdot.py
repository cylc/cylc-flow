#!/usr/bin/env

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import xdot
from gui import util
import subprocess
import gtk
import time
import gobject
import config
import os, sys
from graphing import CGraphPlain
import TaskID

"""
Cylc-modified xdot windows for the "cylc graph" command.
TODO - factor more commonality out of MyDotWindow, MyDotWindow2
"""

class CylcDotViewerCommon( xdot.DotWindow ):
    def load_config( self ):
        print 'loading the suite definition'
        if self.suiterc:
            is_reload = True
            collapsed = self.suiterc.closed_families
        else:
            is_reload = False
            collapsed = []
        try:
            self.suiterc = config.config( self.suite, self.file,
                    template_vars=self.template_vars,
                    template_vars_file=self.template_vars_file,
                    is_reload=is_reload, collapsed=collapsed )
        except Exception, x:
            print >> sys.stderr, "Failed - parsing error?"
            print >> sys.stderr, x
            return False
        self.inherit = self.suiterc.get_parent_lists()
        return True

class MyDotWindow2( CylcDotViewerCommon ):
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
            <toolitem action="Save"/>
        </toolbar>
    </ui>
    '''
    def __init__(self, suite, suiterc, template_vars,
            template_vars_file, watch, orientation="TB" ):
        self.outfile = None
        self.disable_output_image = False
        self.suite = suite
        self.file = suiterc
        self.suiterc = None
        self.watch = []
        self.orientation = orientation
        self.template_vars = template_vars
        self.template_vars_file = template_vars_file

        gtk.Window.__init__(self)

        self.graph = xdot.Graph()

        window = self

        window.set_title('Suite Runtime Namespace Graph Viewer')
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

        # Create actions
        actiongroup.add_actions((
            ('ZoomIn', gtk.STOCK_ZOOM_IN, None, None, 'Zoom In', self.widget.on_zoom_in),
            ('ZoomOut', gtk.STOCK_ZOOM_OUT, None, None, 'Zoom Out', self.widget.on_zoom_out),
            ('ZoomFit', gtk.STOCK_ZOOM_FIT, None, None, 'Zoom Fit', self.widget.on_zoom_fit),
            ('Zoom100', gtk.STOCK_ZOOM_100, None, None, 'Zoom 100', self.widget.on_zoom_100),
            ('Save', gtk.STOCK_SAVE_AS, None, None, 'Save', self.save_action ),
        ))
        actiongroup.add_toggle_actions((
            ('LeftToRight', gtk.STOCK_JUMP_TO, 'Left-to-Right',
             None, 'Left-to-right Graphing', self.on_left_to_right),
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

        #eb = gtk.EventBox()
        #eb.add( gtk.Label( "right-click on nodes to control family grouping" ) )
        #eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#8be' ) )
        #vbox.pack_start( eb, False )

        self.set_focus(self.widget)

        # find all suite.rc include-files
        self.rc_mtimes = {}
        self.rc_last_mtimes = {}
        for rc in watch:
            while True:
                try:
                    self.rc_last_mtimes[rc] = os.stat(rc).st_mtime
                except OSError:
                    # this happens occasionally when the file is being edited ...
                    print >> sys.stderr, "Failed to get rc file mod time, trying again in 1 second"
                    time.sleep(1)
                else:
                    #self.rc_mtimes[rc] = self.rc_last_mtimes[rc]
                    break

        self.show_all()
        while True:
            if self.load_config():
                break
            else:
                time.sleep(1)

    def get_graph( self ):
        title = self.suite + ' runtime namespace inheritance graph'
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

    def update(self):
        # if any suite config file has changed, reparse the graph
        reparse = False
        for rc in self.rc_last_mtimes:
            while True:
                try:
                    rct= os.stat(rc).st_mtime
                except OSError:
                    # this happens occasionally when the file is being edited ...
                    print "Failed to get rc file mod time, trying again in 1 second"
                    time.sleep(1)
                else:
                    if rct != self.rc_last_mtimes[rc]:
                        reparse = True
                        print 'FILE CHANGED:', rc
                        self.rc_last_mtimes[rc] = rct
                    break
        if reparse:
            while True:
                if self.load_config():
                    break
                else:
                    time.sleep(1)
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
            <toolitem action="IgnoreSuicide"/>
            <toolitem action="IgnoreColdStart"/>
            <separator expand="true"/>
            <toolitem action="Save"/>
        </toolbar>
    </ui>
    '''
    def __init__(self, suite, suiterc, template_vars,
                 template_vars_file,  watch, ctime, stop_after,
                 orientation="TB" ):
        self.outfile = None
        self.disable_output_image = False
        self.suite = suite
        self.file = suiterc
        self.suiterc = None
        self.ctime = ctime
        self.raw = False
        self.stop_after = stop_after
        self.watch = []
        self.orientation = orientation
        self.template_vars = template_vars
        self.template_vars_file = template_vars_file
        self.ignore_suicide = False

        gtk.Window.__init__(self)

        self.graph = xdot.Graph()

        window = self

        window.set_title('Suite Dependency Graph Viewer')
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

        # Create actions
        actiongroup.add_actions((
            ('ZoomIn', gtk.STOCK_ZOOM_IN, None,
             None, 'Zoom In', self.widget.on_zoom_in),
            ('ZoomOut', gtk.STOCK_ZOOM_OUT, None,
             None, 'Zoom Out', self.widget.on_zoom_out),
            ('ZoomFit', gtk.STOCK_ZOOM_FIT, None,
             None, 'Zoom Fit', self.widget.on_zoom_fit),
            ('Zoom100', gtk.STOCK_ZOOM_100, None,
             None, 'Zoom 100', self.widget.on_zoom_100),
            ('Group', 'group', 'Group',
             None, 'Group All Families', self.group_all),
            ('UnGroup', 'ungroup', 'Ungroup',
             None, 'Ungroup All Families', self.ungroup_all),
            ('Save', gtk.STOCK_SAVE_AS,
             'Save', None, 'Save', self.save_action ),
        ))
        actiongroup.add_toggle_actions((
            ('LeftToRight', gtk.STOCK_JUMP_TO, 'Left-to-Right',
             None, 'Left-to-right Graphing', self.on_left_to_right),
        ))
        actiongroup.add_toggle_actions((
            ('IgnoreSuicide', gtk.STOCK_CANCEL, 'Ignore Suicide Triggers',
             None, 'Ignore Suicide Triggers', self.on_igsui),
        ))
        actiongroup.add_toggle_actions((
            ('IgnoreColdStart', gtk.STOCK_YES, 'Ignore Cold Start Tasks',
             None, 'Ignore Cold Start Tasks', self.on_igcol),
        ))

        # Add the actiongroup to the uimanager
        uimanager.insert_action_group(actiongroup, 0)

        # Add a UI descrption
        uimanager.add_ui_from_string(self.ui)

        left_to_right_toolitem = uimanager.get_widget('/ToolBar/LeftToRight')
        left_to_right_toolitem.set_active(self.orientation == "LR")

        # Create a Toolbar

        toolbar = uimanager.get_widget('/ToolBar')
        vbox.pack_start(toolbar, False)
        vbox.pack_start(self.widget)

        eb = gtk.EventBox()
        eb.add( gtk.Label( "right-click on nodes to control family grouping" ) )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#8be' ) )
        vbox.pack_start( eb, False )

        self.set_focus(self.widget)

        # find all suite.rc include-files
        self.rc_mtimes = {}
        self.rc_last_mtimes = {}
        for rc in watch:
            while True:
                try:
                    self.rc_last_mtimes[rc] = os.stat(rc).st_mtime
                except OSError:
                    # this happens occasionally when the file is being edited ...
                    print >> sys.stderr, "Failed to get rc file mod time, trying again in 1 second"
                    time.sleep(1)
                else:
                    #self.rc_mtimes[rc] = self.rc_last_mtimes[rc]
                    break

        self.show_all()
        while True:
            if self.load_config():
                break
            else:
                time.sleep(1)

    def group_all( self, w ):
        self.get_graph( group_all=True )

    def ungroup_all( self, w ):
        self.get_graph( ungroup_all=True )

    def get_graph( self, group_nodes=[], ungroup_nodes=[],
            ungroup_recursive=False, ungroup_all=False, group_all=False ):
        family_nodes = self.suiterc.get_first_parent_descendants().keys()
        graphed_family_nodes = self.suiterc.triggering_families
        suite_polling_tasks = self.suiterc.suite_polling_tasks

        if self.ctime != None and self.stop_after != None:
            one = self.ctime
            two = self.stop_after
        else:
            one = str( self.suiterc.cfg['visualization']['initial cycle time'])
            two = str(self.suiterc.cfg['visualization']['final cycle time'])

        graph = self.suiterc.get_graph( one, two,
                raw=self.raw, group_nodes=group_nodes,
                ungroup_nodes=ungroup_nodes,
                ungroup_recursive=ungroup_recursive,
                group_all=group_all, ungroup_all=ungroup_all,
                ignore_suicide=self.ignore_suicide )

        graph.graph_attr['rankdir'] = self.orientation

        for node in graph.nodes():
            name, tag = TaskID.split( node.get_name() )
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

    def on_igsui( self, toolitem ):
        self.ignore_suicide = toolitem.get_active()
        self.get_graph()

    def on_igcol( self, toolitem ):
        self.raw = toolitem.get_active()
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

    def update(self):
        # if any suite config file has changed, reparse the graph
        reparse = False
        for rc in self.rc_last_mtimes:
            while True:
                try:
                    rct= os.stat(rc).st_mtime
                except OSError:
                    # this happens occasionally when the file is being edited ...
                    print "Failed to get rc file mod time, trying again in 1 second"
                    time.sleep(1)
                else:
                    if rct != self.rc_last_mtimes[rc]:
                        reparse = True
                        print 'FILE CHANGED:', rc
                        self.rc_last_mtimes[rc] = rct
                    break
        if reparse:
            while True:
                if self.load_config():
                    break
                else:
                    time.sleep(1)
            self.get_graph()
        return True


class DotTipWidget(xdot.DotWidget):

    """Subclass that allows connection of 'motion-notify-event'."""

    def on_area_motion_notify(self, area, event):
        """This returns False, instead of True as in the base class."""
        self.drag_action.on_motion_notify(event)
        return False


class xdot_widgets(object):
    def __init__(self):
        self.graph = xdot.Graph()

        self.vbox = gtk.VBox()

        self.widget = DotTipWidget()

        #open_button = gtk.Button( stock=gtk.STOCK_OPEN )
        #open_button.connect( 'clicked', self.on_open)
        #reload_button = gtk.Button( stock=gtk.STOCK_REFRESH )
        #reload_button.connect('clicked', self.on_reload),
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
        #bbox.add( open_button )
        #bbox.add( reload_button )
        bbox.add( zoomin_button )
        bbox.add( zoomout_button )
        bbox.add( zoomfit_button )
        bbox.add( zoom100_button )
        bbox.add( self.graph_disconnect_button )
        bbox.add( self.graph_update_button )
        #bbox.set_layout(gtk.BUTTONBOX_END)
        bbox.set_layout(gtk.BUTTONBOX_SPREAD)

        self.vbox.pack_start(self.widget)
        self.vbox.pack_start(bbox, False)

    def get( self ):
        return self.vbox

    def update(self, filename):
        if not hasattr(self, "last_mtime"):
            self.last_mtime = None

        current_mtime = os.stat(filename).st_mtime
        if current_mtime != self.last_mtime:
            self.last_mtime = current_mtime
            self.open_file(filename)

        return True

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

    def open_file(self, filename):
        try:
            fp = file(filename, 'rt')
            self.set_dotcode(fp.read(), filename)
            fp.close()
        except IOError, ex:
            dlg = gtk.MessageDialog(type=gtk.MESSAGE_ERROR,
                                    message_format=str(ex),
                                    buttons=gtk.BUTTONS_OK)
            dlg.set_title('Dot Viewer')
            dlg.run()
            dlg.destroy()

    def on_open(self, action):
        chooser = gtk.FileChooserDialog(title="Open dot File",
                                        action=gtk.FILE_CHOOSER_ACTION_OPEN,
                                        buttons=(gtk.STOCK_CANCEL,
                                                 gtk.RESPONSE_CANCEL,
                                                 gtk.STOCK_OPEN,
                                                 gtk.RESPONSE_OK))
        chooser.set_default_response(gtk.RESPONSE_OK)
        filter = gtk.FileFilter()
        filter.set_name("Graphviz dot files")
        filter.add_pattern("*.dot")
        chooser.add_filter(filter)
        filter = gtk.FileFilter()
        filter.set_name("All files")
        filter.add_pattern("*")
        chooser.add_filter(filter)
        if chooser.run() == gtk.RESPONSE_OK:
            filename = chooser.get_filename()
            chooser.destroy()
            self.open_file(filename)
        else:
            chooser.destroy()

    def on_reload(self, action):
        self.widget.reload()

