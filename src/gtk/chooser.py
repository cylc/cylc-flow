import gobject
import pygtk
####pygtk.require('2.0')
import gtk
import time, os, re
import threading

from gtkmonitor import monitor
from pyrex import discover

class chooser_updater(threading.Thread):

    def __init__(self, liststore, pns_host ):
        self.quit = False
        self.pns_host = pns_host
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
        # renew the connection each time
        # (if a single proxy is established in __init__() then Pyro 3.7 (old!) 
        # complains that sharing a proxy between threads is not allowed).
        groups = discover( self.pns_host ).get_groups()
        choices = []
        for group in groups:
            choices.append( group )
        choices.sort()
        if choices != self.choices:
            self.choices = choices
            return True
        return False

    def update_gui( self ):
        # it is expected that choices will change infrequently,
        # so just clear and recreate the list, rather than 
        # adjusting element-by-element.
        print "Updating list of available systems"
        self.liststore.clear()
        for group in self.choices:
            self.liststore.append( [group] )

class chooser:
    def __init__(self, pns_host, imagedir ):

        gobject.threads_init()

        self.pns_host = pns_host
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
        ts.set_select_function( self.get_selected_system, liststore )

        tvc = gtk.TreeViewColumn( 'Viewable Systems' )
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

        self.updater = chooser_updater( liststore, self.pns_host )
        self.updater.start()

    def launch_viewer( self, group ):
        root, user, system = group.split( '.' ) 
        tv = monitor(group, system, self.pns_host, self.imagedir)
        self.viewer_list.append( tv )

    def delete_event( self, w, e, data=None ):
        self.updater.quit = True
        for item in self.viewer_list:
            item.click_exit( None )
        gtk.main_quit()

    def get_selected_system( self, selection, treemodel ):
        iter = treemodel.get_iter( selection )
        system = treemodel.get_value( iter, 0 )
        #self.show_log( task_id )
        self.launch_viewer( system )

        return False

