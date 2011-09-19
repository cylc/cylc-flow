#!/usr/bin/env

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
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

from graphing import xdot
import gtk
import time
import gobject
import config
import os
from cycle_time import ct

class MyDotWindow( xdot.DotWindow ):
    """Override xdot to get rid of some buttons and parse graph from suite.rc"""

    ui = '''
    <ui>
        <toolbar name="ToolBar">
            <toolitem action="ZoomIn"/>
            <toolitem action="ZoomOut"/>
            <toolitem action="ZoomFit"/>
            <toolitem action="Zoom100"/>
        </toolbar>
    </ui>
    '''
    def __init__(self, suite, suiterc, watch, ctime, stop_after, raw, outfile=None ):
        self.outfile = outfile
        self.disable_output_image = False
        self.suite = suite
        self.file = suiterc
        self.ctime = ctime
        self.raw = raw
        self.stop_after = stop_after
        self.watch = []

        gtk.Window.__init__(self)

        self.graph = xdot.Graph()

        window = self

        window.set_title('Suite Dependency Graph Viewer')
        window.set_default_size(512, 512)
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

        # Create actions
        actiongroup.add_actions((
            ('ZoomIn', gtk.STOCK_ZOOM_IN, None, None, None, self.widget.on_zoom_in),
            ('ZoomOut', gtk.STOCK_ZOOM_OUT, None, None, None, self.widget.on_zoom_out),
            ('ZoomFit', gtk.STOCK_ZOOM_FIT, None, None, None, self.widget.on_zoom_fit),
            ('Zoom100', gtk.STOCK_ZOOM_100, None, None, None, self.widget.on_zoom_100),
        ))

        # Add the actiongroup to the uimanager
        uimanager.insert_action_group(actiongroup, 0)

        # Add a UI descrption
        uimanager.add_ui_from_string(self.ui)

        # Create a Toolbar
        toolbar = uimanager.get_widget('/ToolBar')
        vbox.pack_start(toolbar, False)

        vbox.pack_start(self.widget)

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
                    print "Failed to get rc file mod time, trying again in 1 second"
                    time.sleep(1)
                else:
                    #self.rc_mtimes[rc] = self.rc_last_mtimes[rc]
                    break

        self.show_all()

    def parse_graph( self ):
        # reparse the graph
        self.suiterc = config.config( self.suite, self.file )
        family_nodes = self.suiterc.members.keys()
        graphed_family_nodes = self.suiterc.families_used_in_graph
        if self.ctime != None and self.stop_after != None:
            graph = self.suiterc.get_graph( self.ctime, self.stop_after, raw=self.raw )
        else:
            one = str( self.suiterc['visualization']['initial cycle time'])
            two = str(self.suiterc['visualization']['final cycle time'])
            stop_delta = ct(two).subtract( ct(one) )
            # timedelta: days, seconds, microseconds; ignoring microseconds
            stop = stop_delta.days * 24 + stop_delta.seconds / 3600
            graph = self.suiterc.get_graph( one, stop, raw=self.raw )

        for node in graph.nodes():
            name, tag = node.get_name().split('%')
            if name in family_nodes:
                if name in graphed_family_nodes:
                    node.attr['shape'] = 'doubleoctagon'
                else:
                    node.attr['shape'] = 'doublecircle'

        self.set_dotcode( graph.string() )
        if self.outfile and not self.disable_output_image:
            try:
                graph.draw( self.outfile, prog='dot' )
            except IOError, x:
                print x
                self.disable_output_image = True

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
            print 'Reparsing graph'
            self.parse_graph()
        return True


class xdot_widgets(object):
    def __init__(self):
        self.graph = xdot.Graph()

        self.vbox = gtk.VBox()

        self.widget = xdot.DotWidget()

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
        eb = gtk.EventBox()
        eb.add( gtk.Label( "ABOVE: right-click on tasks to control or interrogate" ) )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#8be' ) ) 
        self.vbox.pack_start(eb, False)
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

    def set_dotcode(self, dotcode, filename='<stdin>'):
        if self.widget.set_dotcode(dotcode, filename):
            #self.set_title(os.path.basename(filename) + ' - Dot Viewer')
            # disable automatic zoom-to-fit on update
            #self.widget.zoom_to_fit()
            pass

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


