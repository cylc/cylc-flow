import gobject
import pygtk
####pygtk.require('2.0')
import gtk
import time, os, re
import threading
from port_scan import scan_my_suites

from gtkmonitor import monitor

class chooser_updater(threading.Thread):

    def __init__(self, liststore, host ):
        self.quit = False
        self.host = host
        self.liststore = liststore
        super(chooser_updater, self).__init__()
        self.choices = []
    
    def run( self ):
        while not self.quit:
            if self.choices_changed():
                gobject.idle_add( self.update_gui )
            time.sleep(1)
        else:
            pass
    
    def choices_changed( self ):
        # (name, port)
        suites = scan_my_suites( self.host )
        if suites != self.choices:
            self.choices = suites
            return True
        else:
            return False

    def update_gui( self ):
        # it is expected that choices will change infrequently,
        # so just clear and recreate the list, rather than 
        # adjusting element-by-element.
        ##print "Updating list of available suites"
        self.liststore.clear()
        for suite in self.choices:
            name, port = suite
            self.liststore.append( [name + ' (port ' + str(port) + ')' ] )

class chooser:
    def __init__(self, host, imagedir ):

        self.owner = os.environ['USER']

        gobject.threads_init()

        self.host = host
        self.imagedir = imagedir

        window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        window.set_title("cylc view chooser" )
        window.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#ddd" ))
        window.set_size_request(400, 150)
        window.connect("delete_event", self.delete_event)

        liststore = gtk.ListStore( str )
        treeview = gtk.TreeView()

        ts = treeview.get_selection()
        ts.set_mode( gtk.SELECTION_SINGLE )
        ts.set_select_function( self.get_selected_suite, liststore )

        tvc = gtk.TreeViewColumn( 'My Suites' )
        cr = gtk.CellRendererText()
        cr.set_property( 'cell-background', 'lightblue' )
        tvc.pack_start( cr, False )
        tvc.set_attributes( cr, text=0 )
 
        treeview.set_model(liststore)
        treeview.append_column( tvc )

        vbox = gtk.VBox()
        quit_button = gtk.Button( "Close" )
        quit_button.connect("clicked", self.delete_event, None, None )
        vbox.pack_start( treeview, True )
        vbox.pack_start( quit_button, False )
        window.add( vbox )
        window.show_all()

        self.viewer_list = []

        self.updater = chooser_updater( liststore, self.host )
        self.updater.start()

    def launch_viewer( self, suite, port ):
        tv = monitor(suite, self.owner, self.host, port, self.imagedir )
        self.viewer_list.append( tv )

    def delete_event( self, w, e, data=None ):
        self.updater.quit = True
        for item in self.viewer_list:
            item.click_exit( None )
        gtk.main_quit()

    def get_selected_suite( self, selection, treemodel ):
        iter = treemodel.get_iter( selection )
        suite = treemodel.get_value( iter, 0 )
        m = re.match( '(\w+) \(port (\d+)\)', suite )
        if m:
            name, port = m.groups()
            self.launch_viewer( name, port )
        return False

