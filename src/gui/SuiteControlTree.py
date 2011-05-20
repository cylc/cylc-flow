#!/usr/bin/env python

from SuiteControl import ControlAppBase
import gtk
import os, re
import gobject
from stateview import updater
import helpwindow

class ControlTree(ControlAppBase):
    """
Text treeview base GUI suite control interface.
    """
    def __init__(self, suite, owner, host, port, suite_dir, logging_dir,
            imagedir, readonly=False ):

        ControlAppBase.__init__(self, suite, owner, host, port,
                suite_dir, logging_dir, imagedir, readonly=False )

        self.userguide_item.connect( 'activate', helpwindow.userguide, False )

        self.tfilt = ''
        self.full_task_headings()
        self.t = updater( self.suite, self.owner, self.host, self.port,
                self.imagedir, self.led_treeview.get_model(),
                self.ttreeview, self.task_list, self.label_mode,
                self.label_status, self.label_time, self.label_block )
        self.t.start()

    def get_control_widgets( self ):
        # Load task list from suite config.
        ### TO DO: For suites that are already running, or for dynamically
        ### updating the viewed task list, we can retrieve the task list
        ### (etc.) from the suite's remote state summary object.
        self.task_list = self.suiterc.get_full_task_name_list()

        main_panes = gtk.VPaned()
        main_panes.set_position(200)
        main_panes.add1( self.ledview_widgets())
        main_panes.add2( self.treeview_widgets())
        return main_panes

    def visible_cb(self, model, iter ):
        # visibility determined by state matching active toggle buttons
        # set visible if model value NOT in filter_states
        state = model.get_value(iter, 1 ) 
        # strip formatting tags
        if state:
            state = re.sub( r'<.*?>', '', state )
            sres = state not in self.tfilter_states
            # AND if taskname matches filter entry text
            if self.tfilt == '':
                nres = True
            else:
                tname = model.get_value(iter, 0)
                tname = re.sub( r'<.*?>', '', tname )
                if re.search( self.tfilt, tname ):
                    nres = True
                else:
                    nres = False
        else:
            # this must be a cycle-time line (not state etc.)
            sres = True
            nres = True
        return sres and nres

    def check_tfilter_buttons(self, tb):
        del self.tfilter_states[:]
        for b in self.tfilterbox.get_children():
            if not b.get_active():
                # sub '_' from button label keyboard mnemonics
                self.tfilter_states.append( re.sub('_', '', b.get_label()))
        self.tmodelfilter.refilter()

    def check_filter_entry( self, e ):
        ftxt = self.filter_entry.get_text()
        if ftxt != '(task name filter)':
            self.tfilt = self.filter_entry.get_text()
        self.tmodelfilter.refilter()

    def delete_event(self, widget, event, data=None):
        self.t.quit = True
        return ControlAppBase.delete_event(self, widget, event, data )

    def click_exit( self, foo ):
        self.t.quit = True
        return ControlAppBase.click_exit(self, foo )

    def toggle_autoexpand( self, w ):
        self.t.autoexpand = not self.t.autoexpand

    def toggle_headings( self, w ):
        if self.task_headings_on:
            self.no_task_headings()
        else:
            self.full_task_headings()

    def no_task_headings( self ):
        self.task_headings_on = False
        self.led_headings = ['Cycle Time' ] + [''] * len( self.task_list )
        self.reset_led_headings()

    def full_task_headings( self ):
        self.task_headings_on = True
        self.led_headings = ['Cycle Time' ] + self.task_list
        self.reset_led_headings()

    def reset_led_headings( self ):
        tvcs = self.led_treeview.get_columns()
        for n in range( 1,1+len( self.task_list) ):
            heading = self.led_headings[n]
            # double on underscores or they get turned into underlines
            # (may be related to keyboard mnemonics for button labels?)
            heading = re.sub( '_', '__', heading )
            tvcs[n].set_title( heading )

    def ledview_widgets( self ):
        types = tuple( [gtk.gdk.Pixbuf]* (10 + len( self.task_list)))
        liststore = gtk.ListStore( *types )
        treeview = gtk.TreeView( liststore )
        treeview.get_selection().set_mode( gtk.SELECTION_NONE )

        # this is how to set background color of the entire treeview to black:
        #treeview.modify_base( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#000' ) ) 

        tvc = gtk.TreeViewColumn( 'Cycle Time' )
        for i in range(10):
            cr = gtk.CellRendererPixbuf()
            #cr.set_property( 'cell-background', 'black' )
            tvc.pack_start( cr, False )
            tvc.set_attributes( cr, pixbuf=i )
        treeview.append_column( tvc )

        # hardwired 10px lamp image width!
        lamp_width = 10

        for n in range( 10, 10+len( self.task_list )):
            cr = gtk.CellRendererPixbuf()
            #cr.set_property( 'cell_background', 'black' )
            cr.set_property( 'xalign', 0 )
            tvc = gtk.TreeViewColumn( ""  )
            tvc.set_min_width( lamp_width )  # WIDTH OF LED PIXBUFS
            tvc.pack_end( cr, True )
            tvc.set_attributes( cr, pixbuf=n )
            treeview.append_column( tvc )

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        self.led_treeview = treeview
        sw.add( treeview )
        return sw
    
    def treeview_widgets( self ):
        # Treeview of current suite state, with filtering and sorting.
        # sorting is handled somewhat manually because the simple method 
        # of interposing a TreeModelSort at the top:
        #   treestore = gtk.TreeStore(str, ...)
        #   tms = gtk.TreeModelSort( treestore )   #\ 
        #   tmf = tms.filter_new()                 #-- or other way round?
        #   tv = gtk.TreeView()
        #   tv.set_model(tms)
        # failed to produce correct results (the data displayed was not 
        # consistently what should have been displayed given the
        # filtering in use) although the exact same code worked for a
        # liststore.

        self.ttreestore = gtk.TreeStore(str, str, str, str, str, str, str )
        self.tmodelfilter = self.ttreestore.filter_new()
        self.tmodelfilter.set_visible_func(self.visible_cb)
        self.ttreeview = gtk.TreeView()
        self.ttreeview.set_model(self.tmodelfilter)

        ts = self.ttreeview.get_selection()
        ts.set_mode( gtk.SELECTION_SINGLE )

        self.ttreeview.connect( 'button_press_event', self.on_treeview_button_pressed )

        headings = ['task', 'state', 'message', 'Tsubmit', 'Tstart', 'mean dT', 'ETC' ]
        bkgcols  = [ None,  '#def',  '#fff',    '#def',    '#fff',   '#def',    '#fff']
        for n in range(len(headings)):
            cr = gtk.CellRendererText()
            cr.set_property( 'cell-background', bkgcols[n] )
            #tvc = gtk.TreeViewColumn( headings[n], cr, text=n )
            tvc = gtk.TreeViewColumn( headings[n], cr, markup=n )
            tvc.set_resizable(True)
            if n == 0:
                # allow click sorting only on first column (cycle time
                # and task name) as I don't understand the effect of
                # sorting on other columns in a treeview (it doesn't
                # seem to work as expected).
                tvc.set_clickable(True)
                tvc.connect("clicked", self.rearrange, n )
                tvc.set_sort_order(gtk.SORT_ASCENDING)
                tvc.set_sort_indicator(True)
                self.ttreestore.set_sort_column_id(n, gtk.SORT_ASCENDING ) 
            self.ttreeview.append_column(tvc)
 
        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )
        sw.add( self.ttreeview )

        self.tfilterbox = gtk.HBox()

        # allow filtering out of 'succeeded' and 'waiting'
        all_states = [ 'waiting', 'submitted', 'running', 'succeeded', 'failed', 'stopped' ]
        labels = {}
        labels[ 'waiting'   ] = '_waiting'
        labels[ 'submitted' ] = 's_ubmitted'
        labels[ 'running'   ] = '_running'
        labels[ 'succeeded'  ] = 'su_cceeded'
        labels[ 'failed'    ] = 'f_ailed'
        labels[ 'stopped'   ] = 'sto_pped'
 
        # initially filter out 'succeeded' and 'waiting' tasks
        self.tfilter_states = [ 'waiting', 'succeeded' ]

        for st in all_states:
            b = gtk.CheckButton( labels[st] )
            self.tfilterbox.pack_start(b)
            if st in self.tfilter_states:
                b.set_active(False)
            else:
                b.set_active(True)
            b.connect('toggled', self.check_tfilter_buttons)

        hbox = gtk.HBox()
        eb = gtk.EventBox()
        eb.add( gtk.Label( "BELOW: right-click on tasks to control or interrogate" ) )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#8be' ) ) 
        hbox.pack_start( eb, True )

        bbox = gtk.HButtonBox()
        expand_button = gtk.Button( "E_xpand" )
        expand_button.connect( 'clicked', lambda x: self.ttreeview.expand_all() )
        collapse_button = gtk.Button( "_Collapse" )
        collapse_button.connect( 'clicked', lambda x: self.ttreeview.collapse_all() )
     
        bbox.add( expand_button )
        bbox.add( collapse_button )
        bbox.set_layout( gtk.BUTTONBOX_START )

        self.filter_entry = gtk.Entry()
        self.filter_entry.set_text( '(task name filter)' )
        self.filter_entry.connect( "activate", self.check_filter_entry )

        ahbox = gtk.HBox()
        ahbox.pack_start( bbox, True )
        ahbox.pack_start( self.filter_entry, True )
        ahbox.pack_start( self.tfilterbox, True)

        vbox = gtk.VBox()
        vbox.pack_start( hbox, False )
        vbox.pack_start( sw, True )
        vbox.pack_end( ahbox, False )

        return vbox

    def on_treeview_button_pressed( self, treeview, event ):
        # DISPLAY MENU ONLY ON RIGHT CLICK ONLY
        if event.button != 3:
            return False

        # the following sets selection to the position at which the
        # right click was done (otherwise selection lags behind the
        # right click):
        x = int( event.x )
        y = int( event.y )
        time = event.time
        pth = treeview.get_path_at_pos(x,y)

        if pth is None:
            return False

        treeview.grab_focus()
        path, col, cellx, celly = pth
        treeview.set_cursor( path, col, 0 )

        selection = treeview.get_selection()
        treemodel, iter = selection.get_selected()
        name = treemodel.get_value( iter, 0 )
        iter2 = treemodel.iter_parent( iter )
        try:
            ctime = treemodel.get_value( iter2, 0 )
        except TypeError:
            # must have clicked on the top level ctime 
            return

        task_id = name + '%' + ctime

        self.right_click_menu( event, task_id )

    def right_click_menu( self, event, task_id ):
        menu = gtk.Menu()
        menu_root = gtk.MenuItem( task_id )
        menu_root.set_submenu( menu )

        title_item = gtk.MenuItem( 'Task: ' + task_id )
        title_item.set_sensitive(False)
        menu.append( title_item )
        menu.append( gtk.SeparatorMenuItem() )

        menu_items = self.get_right_click_menu_items( task_id )
        for item in menu_items:
            menu.append( item )

        menu.show_all()
        menu.popup( None, None, None, event.button, event.time )

        # TO DO: popup menus are not automatically destroyed and can be
        # reused if saved; however, we need to reconstruct or at least
        # alter ours dynamically => should destroy after each use to
        # prevent a memory leak? But I'm not sure how to do this as yet.)

        return True

    def rearrange( self, col, n ):
        cols = self.ttreeview.get_columns()
        for i_n in range(0,len(cols)):
            if i_n == n: 
                cols[i_n].set_sort_indicator(True)
            else:
                cols[i_n].set_sort_indicator(False)
        # col is cols[n]
        if col.get_sort_order() == gtk.SORT_ASCENDING:
            col.set_sort_order(gtk.SORT_DESCENDING)
        else:
            col.set_sort_order(gtk.SORT_ASCENDING)
        self.ttreestore.set_sort_column_id(n, col.get_sort_order()) 

    def on_popup_quit( self, b, lv, w ):
        lv.quit()
        self.quitters.remove( lv )
        w.destroy()

    def create_main_menu( self ):
        ControlAppBase.create_main_menu(self)

        names_item = gtk.MenuItem( '_Toggle Task Names (light panel)' )
        self.view_menu.append( names_item )
        names_item.connect( 'activate', self.toggle_headings )

        autoex_item = gtk.MenuItem( 'Toggle _Auto-Expand Tree' )
        self.view_menu.append( autoex_item )
        autoex_item.connect( 'activate', self.toggle_autoexpand )

class StandaloneControlTreeApp( ControlTree ):
    def __init__(self, suite, owner, host, port, suite_dir, logging_dir, imagedir, readonly=False ):
        gobject.threads_init()
        ControlTree.__init__(self, suite, owner, host, port, suite_dir, logging_dir, imagedir, readonly )
 
    def delete_event(self, widget, event, data=None):
        ControlTree.delete_event( self, widget, event, data )
        gtk.main_quit()

    def click_exit( self, foo ):
        ControlTree.click_exit( self, foo )
        gtk.main_quit()
