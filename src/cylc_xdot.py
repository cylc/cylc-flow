#!/usr/bin/env

from graphing import xdot
import gtk
import config
import os

class MyDotWindow( xdot.DotWindow ):
    """Override xdot to get rid of the Open and Refresh buttons"""

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
    def __init__(self, suite, ctime, stop_after, raw, outfile=None ):
        self.outfile = outfile
        self.disable_output_image = False
        self.suite = suite
        self.ctime = ctime
        self.raw = raw
        self.stop_after = stop_after

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

        self.show_all()

    def parse_graph( self ):
        #print 'ullo'
        # reparse the graph
        self.suiterc = config.config( self.suite )
        self.suitercfile = self.suiterc.get_filename()
        graph = self.suiterc.get_graph( self.ctime, self.stop_after, raw=self.raw )
        self.set_dotcode( graph.string() )
        if self.outfile and not self.disable_output_image:
            try:
                graph.draw( self.outfile, prog='dot' )
            except IOError, x:
                print x
                self.disable_output_image = True

    def update(self):
        # if suite config file has changed, reparse the graph
        if not hasattr(self, "last_mtime"):
            self.last_mtime = None

        while True:
            try:
                current_mtime = os.stat(self.suitercfile).st_mtime
            except OSError:
                # this happens occasionally when the file is being edited ... 
                print "Failed to get suite.rc file modification time, trying again in 1 second"
                sleep(1)
            else:
                break

        if current_mtime != self.last_mtime:
            self.last_mtime = current_mtime
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

        bbox = gtk.HButtonBox()
        #bbox.add( open_button )
        #bbox.add( reload_button )
        bbox.add( zoomin_button )
        bbox.add( zoomout_button )
        bbox.add( zoomfit_button )
        bbox.add( zoom100_button )
        #bbox.set_layout(gtk.BUTTONBOX_END)
        bbox.set_layout(gtk.BUTTONBOX_SPREAD)

        self.vbox.pack_start(bbox, False)
        self.vbox.pack_start(self.widget)

    def get( self ):
        return self.vbox

    def update(self, filename):
        import os
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
            self.widget.zoom_to_fit()

    def set_xdotcode(self, xdotcode, filename='<stdin>'):
        if self.widget.set_xdotcode(xdotcode):
            #self.set_title(os.path.basename(filename) + ' - Dot Viewer')
            self.widget.zoom_to_fit()

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


