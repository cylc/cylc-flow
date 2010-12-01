import gobject
import pygtk
####pygtk.require('2.0')
import gtk
import time, os, re
import threading
from port_scan import scan_my_suites
from registration import registrations
from preferences import prefs
from gtkmonitor import standalone_monitor, standalone_monitor_preload

class chooser_updater(threading.Thread):

    def __init__(self, owner, regd_liststore, host ):
        self.owner = owner
        self.quit = False
        self.host = host
        self.regd_liststore = regd_liststore
        super(chooser_updater, self).__init__()
        self.running_choices = []
        self.regd_choices = []
    
    def run( self ):
        while not self.quit:
            if self.running_choices_changed() or self.regd_choices_changed():
                gobject.idle_add( self.update_gui )
            time.sleep(1)
        else:
            pass
    
    def running_choices_changed( self ):
        # (name, port)
        suites = scan_my_suites( self.host )
        if suites != self.running_choices:
            self.running_choices = suites
            return True
        else:
            return False

    def regd_choices_changed( self ):
        regs = registrations( self.owner ).get_list() 
        if regs != self.regd_choices:
            self.regd_choices = regs
            return True
        else:
            return False

    def update_gui( self ):
        # it is expected that a single user will not have a huge number
        # of suites, and registrations will change infrequently,
        # so just clear and recreate the list rather than 
        # adjusting element-by-element.
        ##print "Updating list of available suites"
        ports = {}
        for suite in self.running_choices:
            name, port = suite
            ports[ name ] = port

        self.regd_liststore.clear()
        for reg in self.regd_choices:
            name, suite_dir = reg
            if name in ports:
                self.regd_liststore.append( [name, suite_dir, 'RUNNING (port ' + str( ports[name] ) + ')'] )
            else:
                self.regd_liststore.append( [name, suite_dir, 'not running'] )

class chooser:
    def __init__(self, host, imagedir ):

        self.owner = os.environ['USER']

        gobject.threads_init()

        self.host = host
        self.imagedir = imagedir

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window.set_title("cylc gui" )
        self.window.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#ddd" ))
        self.window.set_size_request(600, 200)
        #self.window.set_size_request(400, 100)
        self.window.connect("delete_event", self.delete_event)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        regd_treeview = gtk.TreeView()
        regd_liststore = gtk.ListStore( str, str, str )
        regd_treeview.set_model(regd_liststore)

        regd_ts = regd_treeview.get_selection()
        regd_ts.set_mode( gtk.SELECTION_SINGLE )
        regd_ts.set_select_function( self.get_selected_suite, regd_liststore )

        tvc = gtk.TreeViewColumn( 'Name' )
        cr = gtk.CellRendererText()
        cr.set_property( 'cell-background', 'lightblue' )
        tvc.pack_start( cr, False )
        tvc.set_attributes( cr, text=0 )
        regd_treeview.append_column( tvc )

        tvc = gtk.TreeViewColumn( 'Definition' )
        cr = gtk.CellRendererText()
        cr.set_property( 'cell-background', 'orange' )
        tvc.pack_start( cr, False )
        tvc.set_attributes( cr, text=1 )
        regd_treeview.append_column( tvc )

        tvc = gtk.TreeViewColumn( 'State' )
        cr = gtk.CellRendererText()
        cr.set_property( 'cell-background', 'red' )
        tvc.pack_start( cr, False )
        tvc.set_attributes( cr, text=2 )
        regd_treeview.append_column( tvc )

        quit_button = gtk.Button( "Close" )
        quit_button.connect("clicked", self.delete_event, None, None )

        quit_all_button = gtk.Button( "Close All" )
        quit_all_button.connect("clicked", self.delete_all_event, None, None )

        vbox = gtk.VBox()
        sw.add( regd_treeview )
        vbox.pack_start( sw, True )

        hbox = gtk.HBox()
        hbox.pack_start( quit_button, False )
        hbox.pack_start( quit_all_button, False )

        vbox.pack_start( hbox, False )

        self.window.add(vbox)
        self.window.show_all()

        self.viewer_list = []

        self.updater = chooser_updater( self.owner, regd_liststore, self.host )
        self.updater.start()

    def delete_all_event( self, w, e, data=None ):
        self.updater.quit = True
        for item in self.viewer_list:
            item.click_exit( None )
        gtk.main_quit()

    def delete_event( self, w, e, data=None ):
        self.updater.quit = True
        self.window.destroy()
        #gtk.main_quit()

    def get_selected_suite( self, selection, treemodel ):
        iter = treemodel.get_iter( selection )

        name = treemodel.get_value( iter, 0 )
        suite_dir = treemodel.get_value( iter, 1 )
        state = treemodel.get_value( iter, 2 ) 

        m = re.match( 'RUNNING \(port (\d+)\)', state )
        if m:
            port = m.groups()[0]
            tv = standalone_monitor(name, self.owner, self.host, port, self.imagedir )
        else:
            port = None
            # get suite logging directory
            rcfile = prefs( user=self.owner, silent=True )
            logging_dir = rcfile.get_suite_logging_dir( name )
            tv = standalone_monitor_preload(name, self.owner, self.host, port, suite_dir, logging_dir, self.imagedir )
        self.viewer_list.append( tv )
        return False
