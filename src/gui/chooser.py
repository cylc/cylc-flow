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

    def __init__(self, owner, running_liststore, regd_liststore, host ):
        self.owner = owner
        self.quit = False
        self.host = host
        self.running_liststore = running_liststore
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
        # it is expected that choices will change infrequently,
        # so just clear and recreate the list, rather than 
        # adjusting element-by-element.
        ##print "Updating list of available suites"
        self.running_liststore.clear()
        for suite in self.running_choices:
            name, port = suite
            self.running_liststore.append( [name + ' (port ' + str(port) + ')' ] )

        self.regd_liststore.clear()
        for reg in self.regd_choices:
            name, suite_dir = reg
            self.regd_liststore.append( [name + ' (' + suite_dir + ')'] )

class chooser:
    def __init__(self, host, imagedir ):

        self.owner = os.environ['USER']

        gobject.threads_init()

        self.host = host
        self.imagedir = imagedir

        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_title("cylc gui" )
        window.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#ddd" ))
        window.set_size_request(800, 300)
        window.connect("delete_event", self.delete_event)

        running_treeview = gtk.TreeView()
        running_liststore = gtk.ListStore( str )
        running_treeview.set_model(running_liststore)

        regd_treeview = gtk.TreeView()
        regd_liststore = gtk.ListStore( str )
        regd_treeview.set_model(regd_liststore)

        running_ts = running_treeview.get_selection()
        running_ts.set_mode( gtk.SELECTION_SINGLE )
        running_ts.set_select_function( self.get_selected_running_suite, running_liststore )

        regd_ts = regd_treeview.get_selection()
        regd_ts.set_mode( gtk.SELECTION_SINGLE )
        regd_ts.set_select_function( self.get_selected_regd_suite, regd_liststore )

        tvc = gtk.TreeViewColumn( 'My Running Suites' )
        cr = gtk.CellRendererText()
        cr.set_property( 'cell-background', 'lightblue' )
        tvc.pack_start( cr, False )
        tvc.set_attributes( cr, text=0 )
        running_treeview.append_column( tvc )

        tvc = gtk.TreeViewColumn( 'My Registered Suites' )
        cr = gtk.CellRendererText()
        cr.set_property( 'cell-background', 'yellow' )
        tvc.pack_start( cr, False )
        tvc.set_attributes( cr, text=0 )
        regd_treeview.append_column( tvc )

        vbox = gtk.VBox()
        quit_button = gtk.Button( "Close" )
        quit_button.connect("clicked", self.delete_event, None, None )
        vbox.pack_start( running_treeview, True )
        vbox.pack_start( regd_treeview, True )
        vbox.pack_start( quit_button, False )
        window.add( vbox )
        window.show_all()

        self.viewer_list = []

        self.updater = chooser_updater( self.owner, running_liststore, regd_liststore, self.host )
        self.updater.start()

    def delete_event( self, w, e, data=None ):
        self.updater.quit = True
        for item in self.viewer_list:
            item.click_exit( None )
        gtk.main_quit()

    def get_selected_running_suite( self, selection, treemodel ):
        iter = treemodel.get_iter( selection )
        suite = treemodel.get_value( iter, 0 )
        m = re.match( '(\w+) \(port (\d+)\)', suite )
        if m:
            name, port = m.groups()
            tv = standalone_monitor(name, self.owner, self.host, port, self.imagedir )
            self.viewer_list.append( tv )
        return False

    def get_selected_regd_suite( self, selection, treemodel ):
        iter = treemodel.get_iter( selection )
        suite = treemodel.get_value( iter, 0 )
        m = re.match( '(\w+) \((.+)\)', suite )
        if m:
            name, suite_dir = m.groups()
            port = None
            # get suite logging directory
            rcfile = prefs( user=self.owner, silent=True )
            logging_dir = rcfile.get_suite_logging_dir( name )
            tv = standalone_monitor_preload(name, self.owner, self.host, port, suite_dir, logging_dir, self.imagedir )
            self.viewer_list.append( tv )
        return False
