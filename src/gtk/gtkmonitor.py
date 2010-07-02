#!/usr/bin/env python

# example basictreeview.py

import pango
from stateview import updater
from combo_logviewer import combo_logviewer
from cylc_logviewer import cylc_logviewer
from warning_dialog import warning_dialog

import gobject
import pygtk
####pygtk.require('2.0')
import gtk
import time, os, re, sys
from CylcOptionParsers import NoPromptOptionParser_u
from connector import connector
import pyrex
from cycle_time import _rt_to_dt, is_valid

class color_rotator:
    def __init__( self ):
        self.colors = [ '#ed9638', '#dbd40a', '#a7c339', '#6ab7b4' ]
        self.current_color = 0
 
    def get_color( self ):
        index = self.current_color
        if index == len( self.colors ) - 1:
            index = 0
        else:
            index += 1

        self.current_color = index
        return self.colors[ index ]

class monitor:
    # visibility determined by state matching active toggle buttons
    def visible_cb(self, model, iter, col ):
        # set visible if model value NOT in filter_states
        # TO DO: WHY IS STATE SOMETIMES NONE?
        state = model.get_value(iter, col) 
        #print '-->', model.get_value( iter, 0 ), model.get_value( iter, 1 ), state, model.get_value( iter, 3 )
        if state:
            p = re.compile( r'<.*?>')
            state = re.sub( r'<.*?>', '', state )

        return state not in self.filter_states

    def check_filter_buttons(self, tb):
        del self.filter_states[:]
        for b in self.filter_buttonbox.get_children():
            if not b.get_active():
                self.filter_states.append(b.get_label())

        self.modelfilter.refilter()
        return

    # close the window and quit
    def delete_event(self, widget, event, data=None):
        self.lvp.quit()
        self.t.quit = True

        for q in self.quitters:
            #print "calling quit on ", q
            q.quit()

        #print "BYE from main thread"
        return False

    def about( self, bt ):
        about = gtk.AboutDialog()
        if gtk.gtk_version[0] ==2:
            if gtk.gtk_version[1] >= 12:
                # set_program_name() was added in PyGTK 2.12
                about.set_program_name( "cylc" )
        cylc_version = 'THIS IS NOT A VERSIONED RELEASE'
        about.set_version( cylc_version )
        about.set_copyright( "(c) Hilary Oliver, NIWA" )
        about.set_comments( 
"""
Cylc View is a real time system monitor for Cylc.
""" )
        about.set_website( "http://www.niwa.co.nz" )
        about.set_logo( gtk.gdk.pixbuf_new_from_file( self.imagedir + "/dew.jpg" ))
        about.run()
        about.destroy()

    def click_exit( self, foo ):
        self.lvp.quit()
        self.t.quit = True
        for q in self.quitters:
            #print "calling quit on ", q
            q.quit()

        #print "BYE from main thread"
        self.window.destroy()
        return False

    def expand_all( self, widget, view ):
        view.expand_all()
 
    def collapse_all( self, widget, view ):
        view.collapse_all()

    def no_task_headings( self, w ):
        self.led_headings = ['Cycle Time' ] + ['-'] * len( self.task_list )
        self.reset_led_headings()

    def short_task_headings( self, w ):
        self.led_headings = ['Cycle Time' ] + self.task_list_shortnames
        self.reset_led_headings()

    def full_task_headings( self, w ):
        self.led_headings = ['Cycle Time' ] + self.task_list
        self.reset_led_headings()

    def reset_led_headings( self ):
        tvcs = self.led_treeview.get_columns()
        for n in range( 1,1+len( self.task_list) ):
            heading = self.led_headings[n]
            # underscores treated as underlines markup?
            #heading = re.sub( '_', ' ', heading )
            tvcs[n].set_title( heading )

    def create_led_panel( self ):
        types = tuple( [gtk.gdk.Pixbuf]* (10 + len( self.task_list)))
        liststore = gtk.ListStore( *types )
        treeview = gtk.TreeView( liststore )
        treeview.get_selection().set_mode( gtk.SELECTION_NONE )

        tvc = gtk.TreeViewColumn( 'Cycle Time' )
        for i in range(10):
            cr = gtk.CellRendererPixbuf()
            cr.set_property( 'cell-background', 'black' )
            tvc.pack_start( cr, False )
            tvc.set_attributes( cr, pixbuf=i )
        treeview.append_column( tvc )

        for n in range( 10, 10+len( self.task_list )):
            cr = gtk.CellRendererPixbuf()
            cr.set_property( 'cell_background', 'black' )
            cr.set_property( 'xalign', 0 )
            tvc = gtk.TreeViewColumn( "-"  )
            tvc.set_min_width( 20 )  # WIDTH OF LED PIXBUFS
            tvc.pack_end( cr, True )
            tvc.set_attributes( cr, pixbuf=n )
            treeview.append_column( tvc )

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        self.led_treeview = treeview
        sw.add( treeview )

        return sw
    
    def create_tree_panel( self ):
        self.ttreestore = gtk.TreeStore(str, str, str )
        tms = gtk.TreeModelSort( self.ttreestore )
        tms.set_sort_column_id(0, gtk.SORT_ASCENDING)
        treeview = gtk.TreeView()
        treeview.set_model(tms)
        ts = treeview.get_selection()
        ts.set_mode( gtk.SELECTION_SINGLE )
        ts.set_select_function( self.get_selected_task_from_tree, tms )

        headings = ['task', 'state', 'latest message' ]
        for n in range(len(headings)):
            cr = gtk.CellRendererText()
            tvc = gtk.TreeViewColumn( headings[n], cr, markup=n )
            #tvc = gtk.TreeViewColumn( headings[n], cr, text=n )
            treeview.append_column(tvc)
            tvc.set_sort_column_id(n)
 
        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )
        sw.add( treeview )

        hbox = gtk.HBox()
        eb = gtk.EventBox()
        eb.add( gtk.Label( "Click headings to sort") )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#a7c339' ) ) 
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( gtk.Label( "Click rows for Task Info" ))
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#ed9638' ) ) 
        hbox.pack_start( eb, True )
 
        bbox = gtk.HButtonBox()
        expand_button = gtk.Button( "Expand" )
        expand_button.connect( 'clicked', self.expand_all, treeview )
    
        collapse_button = gtk.Button( "Collapse" )
        collapse_button.connect( 'clicked', self.collapse_all, treeview )

        bbox.add( expand_button )
        bbox.add( collapse_button )
        bbox.set_layout( gtk.BUTTONBOX_END )

        vbox = gtk.VBox()
        vbox.pack_start( hbox, False )
        vbox.pack_start( sw, True )
        vbox.pack_start( bbox, False )

        return vbox

    def get_selected_task_from_tree( self, selection, treemodel ):
        if len( selection ) == 1:
            # top level, just ctime
            return False

        c_iter = treemodel.get_iter( selection )
        name = treemodel.get_value( c_iter, 0 )
 
        iter = treemodel.iter_parent( c_iter )
        ctime = treemodel.get_value( iter, 0 )
        task_id = name + '%' + ctime

        self.show_log( task_id )
        return False


    def show_log( self, task_id ):

        [ glbl, states ] = self.get_pyro( 'state_summary').get_state_summary()

        view = True
        reasons = []

        logfiles = states[ task_id ][ 'logfiles' ]

        if len(logfiles) == 0:
            view = False
            reasons.append( task_id + ' has no associated log files' )

        if states[ task_id ][ 'state' ] == 'waiting':
            view = False
            reasons.append( task_id + ' has not started' )

        if not view:
            warning_dialog( '\n'.join( reasons ) ).warn()
            self.popup_requisites( None, task_id )
        else:
            self.popup_logview( task_id, logfiles )

        return False

    def get_selected_task_from_list( self, selection, treemodel ):
        #print selection, treeview
        iter = treemodel.get_iter( selection )
        ctime = treemodel.get_value( iter, 0 )
        name = treemodel.get_value( iter, 1 )
        task_id = name + '%' + ctime

        self.show_log( task_id )
        return False

    def create_flatlist_panel( self ):
        self.fl_liststore = gtk.ListStore(str, str, str, str)
        self.modelfilter = self.fl_liststore.filter_new()
        self.modelfilter.set_visible_func(self.visible_cb, 2)
        tms = gtk.TreeModelSort( self.modelfilter )
        tms.set_sort_column_id(0, gtk.SORT_ASCENDING)
        treeview = gtk.TreeView()
        treeview.set_model(tms)

        ts = treeview.get_selection()
        ts.set_mode( gtk.SELECTION_SINGLE )
        ts.set_select_function( self.get_selected_task_from_list, tms )

        headings = ['cycle', 'name', 'state', 'latest message' ]
        bkgcols = ['#def', '#fff', '#fff', '#fff' ]

        # create the TreeViewColumn to display the data
        for n in range(len(headings)):
            # add columns to treeview
            cr = gtk.CellRendererText()
            cr.set_property( 'cell-background', bkgcols[ n] )
            tvc = gtk.TreeViewColumn( headings[n], cr, markup=n )
            #tvc = gtk.TreeViewColumn( headings[n], cr, text=n )
            tvc.set_sort_column_id(n)
            treeview.append_column(tvc)

        treeview.set_search_column(1)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )
        sw.add( treeview )

        self.filter_buttonbox = gtk.HButtonBox()

        # allow filtering out of 'finished' and 'waiting'
        all_states = [ 'waiting', 'submitted', 'running', 'finished', 'failed' ]
        # initially filter out only 'finished' tasks
        self.filter_states = [ 'finished' ]

        for st in all_states:
            b = gtk.ToggleButton( st )
            self.filter_buttonbox.pack_start(b)
            if st in self.filter_states:
                b.set_active(False)
            else:
                b.set_active(True)
            b.connect('toggled', self.check_filter_buttons)

        self.filter_buttonbox.set_layout( gtk.BUTTONBOX_END )

        hbox = gtk.HBox()
        eb = gtk.EventBox()
        eb.add( gtk.Label( "Click headings to sort") )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#dbd40a' ) ) 
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( gtk.Label( "Click rows for Task Info" ) )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#a7c339' ) ) 
        hbox.pack_start( eb, True )

        vbox = gtk.VBox()
        vbox.pack_start( hbox, False )
        vbox.pack_start( sw, True )
        vbox.pack_start( self.filter_buttonbox, False )

        return vbox

    def update_tb( self, tb, line, tags = None ):
        if tags:
            tb.insert_with_tags( tb.get_end_iter(), line, *tags )
        else:
            tb.insert( tb.get_end_iter(), line )

    def popup_requisites( self, w, task_id ):
        window = gtk.Window()
        #window.set_border_width( 10 )
        window.set_title( task_id + ": Prerequisites and Outputs" )
        #window.modify_bg( gtk.STATE_NORMAL, 
        #       gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_size_request(400, 300)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        vbox = gtk.VBox()
        quit_button = gtk.Button( "Close" )
        quit_button.connect("clicked", lambda x: window.destroy() )
        vbox.pack_start( sw )
        vbox.pack_start( quit_button, False )

        textview = gtk.TextView()
        textview.set_border_width(5)
        textview.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#fff" ))
        textview.set_editable( False )
        sw.add( textview )
        window.add( vbox )
        tb = textview.get_buffer()

        blue = tb.create_tag( None, foreground = "blue" )
        red = tb.create_tag( None, foreground = "red" )
        bold = tb.create_tag( None, weight = pango.WEIGHT_BOLD )
 
        rem = self.get_pyro( 'remote' )
        result = rem.get_task_requisites( [ task_id ] )

        if task_id not in result:
            warning_dialog( 
                    "Task proxy " + task_id + " not found in " + self.system_name + \
                 ".\nTasks are removed once they are no longer needed.").warn()
            return
        
        #self.update_tb( tb, 'Task ' + task_id + ' in ' +  self.system_name + '\n\n', [bold])
        self.update_tb( tb, 'TASK ', [bold] )
        self.update_tb( tb, task_id, [bold, blue])
        self.update_tb( tb, ' in SYSTEM ', [bold] )
        self.update_tb( tb, self.system_name + '\n\n', [bold, blue])

        [ pre, out, extra_info ] = result[ task_id ]

        self.update_tb( tb, 'Prerequisites', [bold])
        #self.update_tb( tb, ' blue => satisfied,', [blue] )
        self.update_tb( tb, ' (' )
        self.update_tb( tb, 'red', [red] )
        self.update_tb( tb, '=> NOT satisfied)\n') 

        if len( pre ) == 0:
            self.update_tb( tb, ' - (None)\n' )
        for item in pre:
            [ msg, state ] = item
            if state:
                tags = None
            else:
                tags = [red]
            self.update_tb( tb, ' - ' + msg + '\n', tags )

        self.update_tb( tb, '\nOutputs', [bold] )
        self.update_tb( tb, ' (' )
        self.update_tb( tb, 'red', [red] )
        self.update_tb( tb, '=> NOT completed)\n') 


        if len( out ) == 0:
            self.update_tb( tb, ' - (None)\n')
        for item in out:
            [ msg, state ] = item
            if state:
                tags = []
            else:
                tags = [red]
            self.update_tb( tb, ' - ' + msg + '\n', tags )

        if len( extra_info.keys() ) > 0:
            self.update_tb( tb, '\nOther\n', [bold] )
            for item in extra_info:
                self.update_tb( tb, ' - ' + item + ': ' + str( extra_info[ item ] ) + '\n' )

        #window.connect("delete_event", lv.quit_w_e)
        window.show_all()

    def on_popup_quit( self, b, lv, w ):
        lv.quit()
        self.quitters.remove( lv )
        w.destroy()

    def popup_logview( self, task_id, logfiles ):
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL, 
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title( task_id + ": Task Information Viewer" )
        window.set_size_request(800, 300)

        lv = combo_logviewer( task_id, logfiles )
        #print "ADDING to quitters: ", lv
        self.quitters.append( lv )

        window.add( lv.get_widget() )

        state_button = gtk.Button( "Interrogate" )
        state_button.connect("clicked", self.popup_requisites, task_id )
 
        quit_button = gtk.Button( "Close" )
        quit_button.connect("clicked", self.on_popup_quit, lv, window )
        
        lv.hbox.pack_start( quit_button )
        lv.hbox.pack_start( state_button )

        window.connect("delete_event", lv.quit_w_e)
        window.show_all()


    def create_menu( self ):

        file_menu = gtk.Menu()
        file_menu_root = gtk.MenuItem( 'File' )
        file_menu_root.set_submenu( file_menu )
        exit_item = gtk.MenuItem( 'Exit Cylc View' )
        exit_item.connect( 'activate', self.click_exit )
        file_menu.append( exit_item )

        help_menu = gtk.Menu()
        help_menu_root = gtk.MenuItem( 'Help' )
        help_menu_root.set_submenu( help_menu )
        about_item = gtk.MenuItem( 'About' )
        help_menu.append( about_item )
        about_item.connect( 'activate', self.about )

        view_menu = gtk.Menu()
        view_menu_root = gtk.MenuItem( 'View' )
        view_menu_root.set_submenu( view_menu )

        heading_none_item = gtk.MenuItem( 'No Task Names' )
        view_menu.append( heading_none_item )
        heading_none_item.connect( 'activate', self.no_task_headings )

        heading_short_item = gtk.MenuItem( 'Short Task Names' )
        view_menu.append( heading_short_item )
        heading_short_item.connect( 'activate', self.short_task_headings )

        heading_full_item = gtk.MenuItem( 'Full Task Names' )
        view_menu.append( heading_full_item )
        heading_full_item.connect( 'activate', self.full_task_headings )
       
        self.menu_bar = gtk.MenuBar()
        self.menu_bar.append( file_menu_root )
        self.menu_bar.append( view_menu_root )
        self.menu_bar.append( help_menu_root )

    def create_info_bar( self ):
        root, user, name = self.groupname.split('.')

        self.label_status = gtk.Label( "status..." )
        self.label_mode = gtk.Label( "mode..." )
        self.label_time = gtk.Label( "time..." )
        self.label_sysname = gtk.Label( name )

        hbox = gtk.HBox()

        eb = gtk.EventBox()
        eb.add( self.label_sysname )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#ed9638' ) )
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( self.label_mode )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#dbd40a' ) )
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( self.label_status )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#a7c339' ) )
        hbox.pack_start( eb, True )

        eb = gtk.EventBox()
        eb.add( self.label_time )
        #eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#6ab7b4' ) ) 
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#fa87a4' ) ) 
        hbox.pack_start( eb, True )

        return hbox

    def translate_task_names( self, shortnames ):
        temp = {}
        for t in range( len( self.task_list )):
            temp[ self.task_list[ t ] ] = shortnames[ t ]

        self.task_list.sort()
        self.task_list_shortnames = []
        for task in self.task_list:
            self.task_list_shortnames.append( temp[ task ] )
 
    def check_connection( self ):
        # called on a timeout in the gtk main loop, tell the log viewer
        # to reload if the connection has been lost and re-established,
        # which probably means the cylc system was shutdown and
        # restarted.
        try:
            connector( self.pns_host, self.groupname, 'minimal', silent=True ).get()
        except:
            #print "NO CONNECTION"
            self.connection_lost = True
        else:
            #print "CONNECTED"
            if self.connection_lost:
                #print "------>INITIAL RECON"
                self.connection_lost = False
                self.lvp.clear_and_reconnect()
        # always return True so that we keep getting called
        return True

    def get_pyro( self, object ):
        foo = connector( self.pns_host, self.groupname, object, check=False )
        bar = foo.get()
        return bar
 
    def block_till_connected( self ):
        warned = False
        while True:
            try:
                self.get_pyro( 'minimal' )
            except:
                if not warned:
                    print "waiting for system " + self.system_name + ".",
                    warned = True
                else:
                    print '.',
                    sys.stdout.flush()
            else:
                print '.'
                sys.stdout.flush()
                time.sleep(1) # wait for system to start
                break
            time.sleep(1)

    def load_task_list( self ):
        self.block_till_connected()
        ss = self.get_pyro( 'state_summary' )
        self.logdir = ss.get_config( 'logging_dir' ) 
        self.task_list = ss.get_config( 'task_list' )
        self.shortnames = ss.get_config( 'task_list_shortnames' )

    def __init__(self, groupname, system_name, pns_host, imagedir ):
        self.system_name = system_name
        self.groupname = groupname
        self.pns_host = pns_host
        self.imagedir = imagedir
        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        #self.window.set_border_width( 5 )
        self.window.set_title("cylc view <" + self.groupname + ">" )
        self.window.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#ddd" ))
        self.window.set_size_request(600, 500)
        self.window.connect("delete_event", self.delete_event)

        self.log_colors = color_rotator()

        # Get list of tasks in the system
        self.load_task_list()

        self.translate_task_names( self.shortnames )

        notebook = gtk.Notebook()
        notebook.set_tab_pos(gtk.POS_TOP)
        notebook.append_page( self.create_flatlist_panel(), gtk.Label("Filtered List") )
        notebook.append_page( self.create_tree_panel(), gtk.Label("Expanding Tree") )

        main_panes = gtk.VPaned()
        main_panes.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#d91212' ))
        main_panes.add1( self.create_led_panel())
        main_panes.add2( notebook )

        self.logfile = 'main'
        cylc_log = self.logdir + '/' + self.logfile 
        self.lvp = cylc_logviewer( 'main', self.logdir, self.logfile, self.task_list )
        notebook.append_page( self.lvp.get_widget(), gtk.Label("Scheduler Log Files"))

        self.create_menu()

        self.led_headings = None 
        self.short_task_headings( None )

        bigbox = gtk.VBox()
        bigbox.pack_start( self.menu_bar, False )
        bigbox.pack_start( self.create_info_bar(), False )
        bigbox.pack_start( main_panes, True )
        self.window.add( bigbox )

        self.window.show_all()

        self.quitters = []

        self.connection_lost = False
        gobject.timeout_add( 1000, self.check_connection )

        self.t = updater( self.pns_host, self.groupname, self.imagedir, 
                self.led_treeview.get_model(), self.fl_liststore,
                self.ttreestore, self.task_list, self.label_mode, 
                self.label_status, self.label_time )

        #print "Starting task state info thread"
        self.t.start()

class standalone_monitor( monitor ):
    def __init__(self, groupname, system_name, pns_host, imagedir ):
        gobject.threads_init()
        monitor.__init__(self, groupname, system_name, pns_host, imagedir)
 
    def delete_event(self, widget, event, data=None):
        monitor.delete_event( self, widget, event, data )
        gtk.main_quit()

    def click_exit( self, foo ):
        monitor.click_exit( self, foo )
        gtk.main_quit()


class standalone_monitor_preload( standalone_monitor ):
    def __init__(self, groupname, system_name, system_dir, logging_dir, pns_host, imagedir ):
        self.logdir = logging_dir
        self.system_dir = system_dir
        standalone_monitor.__init__(self, groupname, system_name, pns_host, imagedir)
 
    def load_task_list( self ):
        sys.path.append( self.system_dir )
        import task_list
        self.task_list = task_list.task_list
        self.shortnames = task_list.task_list_shortnames
