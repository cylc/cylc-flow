import gobject
import pygtk
####pygtk.require('2.0')
import gtk
import time, os, re
import threading
from config import config, SuiteConfigError
from port_scan import scan_my_suites
from registration import localdb, centraldb, regsplit, RegistrationError
from gtkmonitor import monitor
from color_rotator import rotator
from warning_dialog import warning_dialog, info_dialog
from subprocess import call
import helpwindow 

class chooser_updater(threading.Thread):
    def __init__(self, owner, regd_treestore, db, is_cdb, host, 
            ownerfilt=None, groupfilt=None, namefilt=None ):
        self.ownerfilt = ownerfilt
        self.groupfilt = groupfilt
        self.namefilt = namefilt
        self.db = db
        self.is_cdb = is_cdb
        self.owner = owner
        self.quit = False
        self.host = host
        self.regd_treestore = regd_treestore
        super(chooser_updater, self).__init__()
        self.running_choices = []
        self.line_colors = rotator([ '#ccc', '#aaa' ])
        self.line_colors_cdb = rotator([ '#cfc', '#ada' ])
        self.state_line_colors = rotator([ '#fcc', '#faa' ])

        self.db.load_from_file()
        self.regd_choices = []
        self.regd_choices = self.db.get_list( self.ownerfilt, self.groupfilt, self.namefilt ) 
    
    def run( self ):
        while not self.quit:
            if self.running_choices_changed() or self.regd_choices_changed():
                gobject.idle_add( self.update_liststore )
            time.sleep(1)
        else:
            pass
    
    def running_choices_changed( self ):
        # (name, owner, port)
        suites = scan_my_suites( self.host )
        if suites != self.running_choices:
            self.running_choices = suites
            return True
        else:
            return False

    def regd_choices_changed( self ):
        if not self.db.changed_on_disk():
            return False
        self.db.load_from_file()
        regs = self.db.get_list( self.ownerfilt, self.groupfilt, self.namefilt ) 
        if regs != self.regd_choices:
            self.regd_choices = regs
            return True
        else:
            return False

    def update_liststore( self ):
        # it is expected that a single user will not have a huge number
        # of suites, and registrations will change infrequently,
        # so just clear and recreate the list rather than 
        # adjusting element-by-element.
        ##print "Updating list of available suites"
        ports = {}
        for suite in self.running_choices:
            name, port = suite
            ports[ name ] = port

        # construct tree[owner][group][name] = [state, descr, dir ]
        tree = {}
        self.regd_treestore.clear()
        choices = self.regd_choices
        for reg in choices:
            suite, suite_dir, descr = reg
            suite_dir = re.sub( os.environ['HOME'], '~', suite_dir )
            if suite in ports:
                state = 'port ' + str(ports[name])
            else:
                state = 'dormant'
            if self.is_cdb:
                owner, group, name = re.split( ':', suite )
            else:
                owner = self.owner
                group, name = re.split( ':', suite )
            if owner not in tree:
                tree[owner] = {}
            if group not in tree[owner]:
                tree[owner][group] = {}
            if name not in tree[owner][group]:
                tree[owner][group][name] = {}
            tree[owner][group][name] = [ state, descr, suite_dir ]

        #grn = '#2f2'
        #grn2 = '#19ae0a'
        #red = '#ff1a45'
        #red = self.state_line_colors.get_color()
 
        # construct treestore
        if self.is_cdb:
            for owner in tree:
                o_iter = self.regd_treestore.append( None, [owner, None, None, None, 'white', 'white' ] )
                for group in tree[owner]:
                    g_iter = self.regd_treestore.append( o_iter, [ group, None, None, None, 'white', 'white' ] )
                    for name in tree[owner][group]:
                        col = self.line_colors_cdb.get_color()
                        state, descr, dir = tree[owner][group][name]
                        n_iter = self.regd_treestore.append( g_iter, [ name, state, descr, dir, col, col ] )
        else:
            owner = self.owner
            for group in tree[owner]:
                g_iter = self.regd_treestore.append( None, [ group, None, None, None, 'white', 'white' ] )
                for name in tree[owner][group]:
                    col = self.line_colors.get_color()
                    state, descr, dir = tree[owner][group][name]
                    n_iter = self.regd_treestore.append( g_iter, [ name, state, descr, dir, col, col ] )

class chooser(object):
    def __init__(self, host, imagedir, readonly=False ):
        self.updater = None
        self.filter_window = None
        self.owner = os.environ['USER']
        self.readonly = readonly

        gobject.threads_init()

        self.host = host
        self.imagedir = imagedir

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        if self.readonly:
            self.window.set_title("Registered Suites (READONLY)" )
        else:
            self.window.set_title("Registered Suites" )
        self.window.set_size_request(800, 200)
        self.window.set_border_width( 5 )
        self.window.connect("delete_event", self.delete_all_event)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        regd_treeview = gtk.TreeView()
        # [owner>]group>name, state, title, dir, color1, color2
        self.regd_treestore = gtk.TreeStore( str, str, str, str, str, str, )
        regd_treeview.set_model(self.regd_treestore)
        regd_treeview.connect( 'button_press_event', self.on_suite_select )

        newreg_button = gtk.Button( "_Register Another Suite" )
        newreg_button.connect("clicked", self.newreg_popup )

        self.db_button = gtk.Button( "_Local/Central DB" )
        self.db_button.connect("clicked", self.switchdb, newreg_button )
        self.main_label = gtk.Label( "Local Suite Registrations" )

        # Start updating the liststore now, as we need values in it
        # immediately below (it may be possible to delay this till the
        # end of __init___() but it doesn't really matter.
        self.cdb = False # start with local reg db
        self.start_updater()

        regd_ts = regd_treeview.get_selection()
        regd_ts.set_mode( gtk.SELECTION_SINGLE )

        cr = gtk.CellRendererText()
        tvc = gtk.TreeViewColumn( 'Suite', cr, text=0, background=4 )
        regd_treeview.append_column( tvc )

        #cr = gtk.CellRendererText()
        #tvc = gtk.TreeViewColumn( 'Group', cr, text=1, background=6 )
        #regd_treeview.append_column( tvc )

        #cr = gtk.CellRendererText()
        #tvc = gtk.TreeViewColumn( 'Name', cr, text=2, background=6)
        #regd_treeview.append_column( tvc )

        cr = gtk.CellRendererText()
        tvc = gtk.TreeViewColumn( 'State', cr, text=1, background=5 )
        regd_treeview.append_column( tvc ) 

        cr = gtk.CellRendererText()
        tvc = gtk.TreeViewColumn( 'Title', cr, text=2, background=4 )
        regd_treeview.append_column( tvc )

        cr = gtk.CellRendererText()
        tvc = gtk.TreeViewColumn( 'Suite Definition Directory', cr, text=3, background=4 )
        regd_treeview.append_column( tvc )

        # NOTE THAT WE CANNOT LEAVE ANY SUITE CONTROL WINDOWS OPEN WHEN
        # WE CLOSE THE CHOOSER WINDOW: when launched by the chooser 
        # they are all under the same gtk main loop (?) and do not
        # call gtk_main.quit() unless launched as standalone viewers.
        quit_all_button = gtk.Button( "_Quit" )
        quit_all_button.connect("clicked", self.delete_all_event, None, None )

        filter_button = gtk.Button( "_Filter" )
        filter_button.connect("clicked", self.filter_popup, None, None )

        expand_button = gtk.Button( "_Expand/Collapse")
        expand_button.connect( 'clicked', self.toggle_expand, regd_treeview )
    
        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.main )

        vbox = gtk.VBox()
        hbox = gtk.HBox()
        hbox.pack_start( self.main_label )
        vbox.pack_start( hbox, False )

        sw.add( regd_treeview )
        vbox.pack_start( sw, True )

        hbox = gtk.HBox()
        hbox_l = gtk.HBox()
        hbox_r = gtk.HBox()
        hbox_r.pack_start( help_button, False )
        hbox_r.pack_start( quit_all_button, False )
        hbox_l.pack_start( filter_button, False )
        hbox_l.pack_start( expand_button, False )
        hbox_l.pack_start( self.db_button, False )
        hbox_l.pack_start( newreg_button, False )
        hbox.pack_start( hbox_l, False )
        hbox.pack_end( hbox_r, False )

        vbox.pack_start( hbox, False )

        self.window.add(vbox)
        self.window.show_all()

        self.viewer_list = []

    def toggle_expand( self, widget, view ):
        if view.row_expanded(0):
            view.collapse_all()
        else:
            view.expand_all()

    def start_updater(self, ownerfilt=None, groupfilt=None, namefilt=None):
        if self.cdb:
            db = centraldb()
            self.db_button.set_label( "_Local/Central DB" )
            self.main_label.set_text( "Central Suite Registrations" )
        else:
            db = localdb()
            self.db_button.set_label( "_Local/Central DB" )
            self.main_label.set_text( "Local Suite Registrations" )
        if self.updater:
            self.updater.quit = True # does this take effect?
        self.updater = chooser_updater( self.owner, self.regd_treestore, 
                db, self.cdb, self.host, ownerfilt, groupfilt, namefilt )
        self.updater.update_liststore()
        self.updater.start()

    def newreg_popup( self, w ):
        dialog = gtk.FileChooserDialog(title='Add A Suite',
                action=gtk.FILE_CHOOSER_ACTION_OPEN,
                buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OPEN,gtk.RESPONSE_OK))
        filter = gtk.FileFilter()
        filter.set_name("cylc suite.rc files")
        filter.add_pattern("suite\.rc")
        dialog.add_filter( filter )

        response = dialog.run()
        if response != gtk.RESPONSE_OK:
            dialog.destroy()
            return False

        suiterc = dialog.get_filename()
        dialog.destroy()
        dir = os.path.dirname( suiterc )
        
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Add A Suite" )

        vbox = gtk.VBox()

        label = gtk.Label( dir )
        vbox.pack_start( label, True )
        label = gtk.Label( 'Register As:' )
        vbox.pack_start( label, True )

        box = gtk.HBox()
        label = gtk.Label( 'Group' )
        box.pack_start( label, True )
        group_entry = gtk.Entry()
        box.pack_start (group_entry, True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Name' )
        box.pack_start( label, True )
        name_entry = gtk.Entry()
        box.pack_start (name_entry, True)
        vbox.pack_start(box)

        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        apply_button = gtk.Button( "_Register" )
        apply_button.connect("clicked", self.new_reg, window, dir, group_entry, name_entry )

        #help_button = gtk.Button( "_Help" )
        #help_button.connect("clicked", self.filter_guide )

        hbox = gtk.HBox()
        hbox.pack_start( apply_button, False )
        hbox.pack_start( cancel_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def new_reg( self, b, w, dir, group_e, name_e ):
        group = group_e.get_text()
        name = name_e.get_text()
        reg = group + ':' + name
        call( 'capture "cylc register ' + reg + ' ' + dir + '" --width=600 &', shell=True )
        w.destroy()

    def filter(self, w, owner_e, group_e, name_e ):
        ownerfilt = owner_e.get_text()
        groupfilt = group_e.get_text()
        namefilt = name_e.get_text()
        for filt in ownerfilt, groupfilt, namefilt:
            try:
                re.compile( filt )
            except:
                warning_dialog( "Bad Expression: " + filt ).warn()
                self.filter_reset( w, owner_e, group_e, name_e )
                return
        self.start_updater( ownerfilt, groupfilt, namefilt )

    def filter_reset(self, w, owner_e, group_e, name_e ):
        if self.cdb:
            owner_e.set_text('')
        group_e.set_text('')
        name_e.set_text('')
        self.start_updater()

    def filter_popup(self, w, e, data=None):
        self.filter_window = gtk.Window()
        self.filter_window.set_border_width(5)
        self.filter_window.set_title( "Filter" )
        vbox = gtk.VBox()

        box = gtk.HBox()
        label = gtk.Label( 'Owner' )
        box.pack_start( label, True )
        owner_entry = gtk.Entry()
        if not self.cdb:
            owner_entry.set_text( self.owner )
            owner_entry.set_sensitive( False )
        box.pack_start (owner_entry, True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Group' )
        box.pack_start( label, True )
        group_entry = gtk.Entry()
        box.pack_start (group_entry, True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Name' )
        box.pack_start( label, True )
        name_entry = gtk.Entry()
        box.pack_start (name_entry, True)
        vbox.pack_start(box)

        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: self.filter_window.destroy() )

        apply_button = gtk.Button( "_Apply" )
        apply_button.connect("clicked", self.filter, owner_entry, group_entry, name_entry )

        reset_button = gtk.Button( "_Reset" )
        reset_button.connect("clicked", self.filter_reset, owner_entry, group_entry, name_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.filter )

        hbox = gtk.HBox()
        hbox.pack_start( apply_button, False )
        hbox.pack_start( reset_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        self.filter_window.add( vbox )
        self.filter_window.show_all()

    def switchdb( self, w, newreg ):
        if self.filter_window:
            self.filter_window.destroy()
        self.cdb = not self.cdb
        if self.cdb:
            newreg.set_sensitive( False )
        else:
            newreg.set_sensitive( True )
        self.start_updater()

    def delete_all_event( self, w, e, data=None ):
        self.updater.quit = True
        for item in self.viewer_list:
            item.click_exit( None )
        gtk.main_quit()

    def on_suite_select( self, treeview, event ):
        # DISPLAY MENU ON RIGHT CLICK ONLY
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

        model, iter = selection.get_selected()

        # assume right-click on lowest level
        group_clicked = False

        if self.cdb:
            one = model.get_value( iter, 0 )
            try:
                iter2 = model.iter_parent( iter )
                two = model.get_value( iter2, 0 )
            except TypeError:
                # no parent => clicked on owner; do nothing
                return
            else:
                # parent exists => clicked on name or group
                try:
                    iter3 = model.iter_parent(iter2)
                    three = model.get_value( iter3, 0 )
                except TypeError:
                    # no grandparent => clicked on group
                    group_clicked = True
                    group = one
                    owner = two
                else:
                    # grandparent exists => clicked on name
                    name = one
                    group = two
                    owner = three
        else:
            owner = self.owner
            one = model.get_value( iter, 0 )
            try:
                iter2 = model.iter_parent( iter )
                two = model.get_value( iter2, 0 )
            except TypeError:
                # no parent => clicked on group
                group_clicked = True
                group = one
            else:
                # parent exists => clicked on name
                name = one
                group = two
 
        state = model.get_value( iter, 1 ) 
        descr = model.get_value( iter, 2 )
        suite_dir = model.get_value( iter, 3 )

        menu = gtk.Menu()

        menu_root = gtk.MenuItem( 'foo' )
        menu_root.set_submenu( menu )

        if group_clicked:
            # MENU OPTIONS FOR GROUPS
            if not self.cdb:
                copy_item = gtk.MenuItem( 'Copy' )
                menu.append( copy_item )
                copy_item.connect( 'activate', self.copy_group_popup, group )

            if self.cdb:
                imp_item = gtk.MenuItem( 'Import' )
                menu.append( imp_item )
                imp_item.connect( 'activate', self.import_group_popup, owner, group )
            else:
                exp_item = gtk.MenuItem( 'Export' )
                menu.append( exp_item )
                exp_item.connect( 'activate', self.export_group_popup, group )

            reregister_item = gtk.MenuItem( 'Reregister' )
            menu.append( reregister_item )
            reregister_item.connect( 'activate', self.reregister_group_popup, group)
            if self.cdb:
                if owner != self.owner:
                    reregister_item.set_sensitive( False )

            del_item = gtk.MenuItem( 'Unregister' )
            menu.append( del_item )
            del_item.connect( 'activate', self.unregister_group_popup, group )
            if self.cdb:
                if owner != self.owner:
                    del_item.set_sensitive( False )

        else:
            # MENU OPTIONS FOR SUITES
            if self.cdb:
                reg = owner + ':' + group + ':' + name
            else:
                reg = group + ':' + name
            if not self.cdb:
                #if state == 'dormant':
                title = 'Control'
                #else:
                #    title = 'Connect'
                con_item = gtk.MenuItem( title )
                menu.append( con_item )
                con_item.connect( 'activate', self.launch_controller, reg, state, suite_dir )
    
                menu.append( gtk.SeparatorMenuItem() )
    
            edit_item = gtk.MenuItem( 'Edit' )
            menu.append( edit_item )
            edit_item.connect( 'activate', self.edit_suite_popup, reg )
    
            graph_item = gtk.MenuItem( 'Graph' )
            menu.append( graph_item )
            graph_item.connect( 'activate', self.graph_suite_popup, reg )
    
            search_item = gtk.MenuItem( 'Search' )
            menu.append( search_item )
            search_item.connect( 'activate', self.search_suite_popup, reg )

            val_item = gtk.MenuItem( 'Validate' )
            menu.append( val_item )
            val_item.connect( 'activate', self.validate_suite, reg )
    
            menu.append( gtk.SeparatorMenuItem() )
    
            if not self.cdb:
                copy_item = gtk.MenuItem( 'Copy' )
                menu.append( copy_item )
                copy_item.connect( 'activate', self.copy_suite_popup, reg )
    
            reregister_item = gtk.MenuItem( 'Reregister' )
            menu.append( reregister_item )
            reregister_item.connect( 'activate', self.reregister_suite_popup, reg )
            if self.cdb:
                if owner != self.owner:
                    reregister_item.set_sensitive( False )
    
            if self.cdb:
                imp_item = gtk.MenuItem( 'Import' )
                menu.append( imp_item )
                imp_item.connect( 'activate', self.import_suite_popup, reg )
            else:
                exp_item = gtk.MenuItem( 'Export' )
                menu.append( exp_item )
                exp_item.connect( 'activate', self.export_suite_popup, reg )
    
            del_item = gtk.MenuItem( 'Unregister' )
            menu.append( del_item )
            del_item.connect( 'activate', self.unregister_suite_popup, reg )
            if self.cdb:
                if owner != self.owner:
                    del_item.set_sensitive( False )

        menu.show_all()
        menu.popup( None, None, None, event.button, event.time )
        # TO DO: POPUP MENU MUST BE DESTROY()ED AFTER EVERY USE AS
        # POPPING DOWN DOES NOT DO THIS (=> MEMORY LEAK?)
        return True

    def unregister_group_popup( self, w, group ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Unregister '" + group + "'")

        vbox = gtk.VBox()

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Unregister" )
        ok_button.connect("clicked", self.unregister_group, window, group )

        #help_button = gtk.Button( "_Help" )
        #help_button.connect("clicked", self.stop_guide )

        label = gtk.Label( "Unregister the entire " + group + " group?" + """
Note that this will not delete any suite definition directories.""" )
        vbox.pack_start( label )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( ok_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def unregister_group( self, b, w, group ):
        call( 'capture "cylc unregister ' + group + ': " --width=600 &', shell=True )
        w.destroy()

    def unregister_suite_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Unregister '" + reg + "'")

        vbox = gtk.VBox()

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Unregister" )
        ok_button.connect("clicked", self.unregister_suite, window, reg )

        #help_button = gtk.Button( "_Help" )
        #help_button.connect("clicked", self.stop_guide )

        label = gtk.Label( "Unregister suite " + reg + "?" + """
Note that this will not delete the suite definition directory.""" )
        vbox.pack_start( label )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( ok_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def unregister_suite( self, b, w, reg ):
        call( 'capture "cylc unregister ' + reg + '" --width=600 &', shell=True )
        w.destroy()

    def import_group_popup( self, w, owner, group ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Import '" + group )

        vbox = gtk.VBox()

        box = gtk.HBox()
        label = gtk.Label( 'Group' )
        box.pack_start( label, True )
        group_entry = gtk.Entry()
        group_entry.set_text( group )
        box.pack_start (group_entry, True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Directory' )
        box.pack_start( label, True )
        def_entry = gtk.Entry()
        box.pack_start (def_entry, True)
        vbox.pack_start(box)

        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Import" )
        ok_button.connect("clicked", self.import_group, window, owner, group, group_entry, def_entry )

        #help_button = gtk.Button( "_Help" )
        #help_button.connect("clicked", self.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( ok_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def import_group( self, b, w, fowner, fgroup, group_entry, def_entry ):
        group = group_entry.get_text()
        dir = def_entry.get_text()
        if not self.check_entries( [group, dir] ):
            return False
        call( 'capture "cylc import ' + fowner + ':' + fgroup + ': ' + group + ': ' + dir + '" --width=600 &', shell=True )
        w.destroy()
 
    def import_suite_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Import '" + reg + "' from central database")

        vbox = gtk.VBox()
        #label = gtk.Label( 'Import ' + reg + ' as:' )

        owner = self.owner
        cowner, cgroup, cname = re.split( ':', reg )

        box = gtk.HBox()
        label = gtk.Label( 'Group' )
        box.pack_start( label, True )
        group_entry = gtk.Entry()
        group_entry.set_text( cgroup )
        box.pack_start (group_entry, True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Name' )
        box.pack_start( label, True )
        name_entry = gtk.Entry()
        name_entry.set_text( cname )
        box.pack_start (name_entry, True)
        vbox.pack_start(box)

        box = gtk.HBox()
        label = gtk.Label( 'Directory' )
        box.pack_start( label, True )
        def_entry = gtk.Entry()
        box.pack_start (def_entry, True)
        vbox.pack_start(box)

        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Import" )
        ok_button.connect("clicked", self.import_suite, window, reg, group_entry, name_entry, def_entry )

        #help_button = gtk.Button( "_Help" )
        #help_button.connect("clicked", self.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( ok_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def import_suite( self, b, w, reg, group_entry, name_entry, def_entry ):
        group = group_entry.get_text()
        name  = name_entry.get_text()
        dir = def_entry.get_text()
        if not self.check_entries( [group, name, dir] ):
            return False
        call( 'capture "cylc import ' + reg + ' ' + group + ':' + name + ' ' + dir + '" --width=600 &', shell=True )
        w.destroy()
 
    def export_suite_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Export '" + reg + "' to central database")

        vbox = gtk.VBox()
        #label = gtk.Label( 'Export ' + reg + ' as:' )

        owner = self.owner
        junk, group, name = regsplit( reg ).get()

        box = gtk.HBox()
        label = gtk.Label( 'Group' )
        box.pack_start( label, True )
        group_entry = gtk.Entry()
        group_entry.set_text( group )
        box.pack_start (group_entry, True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Name' )
        box.pack_start( label, True )
        name_entry = gtk.Entry()
        name_entry.set_text( name )
        box.pack_start (name_entry, True)
        vbox.pack_start(box)

        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Export" )
        ok_button.connect("clicked", self.export_suite, window, reg, group_entry, name_entry )

        #help_button = gtk.Button( "_Help" )
        #help_button.connect("clicked", self.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( ok_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def export_suite( self, b, w, reg, group_entry, name_entry ):
        group = group_entry.get_text()
        name  = name_entry.get_text()
        if not self.check_entries( [group, name] ):
            return False
        call( 'capture "cylc export ' + reg + ' ' + group + ':' + name + '" --width=600 &', shell=True )
        w.destroy()
 
    def toggle_entry_sensitivity( self, w, entry ):
        if entry.get_property( 'sensitive' ) == 0:
            entry.set_sensitive( True )
        else:
            entry.set_sensitive( False )

    def reregister_suite_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Reregister '" + reg + "'")

        vbox = gtk.VBox()

        reg_owner, reg_group, reg_name = regsplit( reg ).get() 
 
        label = gtk.Label("Group" )
        group_entry = gtk.Entry()
        group_entry.set_text( reg_group )
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(group_entry, True) 
        vbox.pack_start( hbox )
 
        label = gtk.Label("Name" )
        name_entry = gtk.Entry()
        name_entry.set_text( reg_name )
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(name_entry, True) 
        vbox.pack_start( hbox )

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Reregister" )
        ok_button.connect("clicked", self.reregister_suite, window, reg, group_entry, name_entry )

        #help_button = gtk.Button( "_Help" )
        #help_button.connect("clicked", self.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( ok_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def reregister_suite( self, b, w, reg, g_e, n_e ):
        g = g_e.get_text()
        n = n_e.get_text()
        reg_owner, reg_group, reg_name = regsplit( reg ).get() 
        tto = g + ':' + n
        if self.cdb:
            tto = reg_owner + ':' + tto
        call( 'capture "cylc reregister ' + reg + ' ' + tto + '" --width=600 &', shell=True )
        w.destroy()

    def reregister_group_popup( self, w, group ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "reregister Group'" + group + "'")

        vbox = gtk.VBox()

        label = gtk.Label("New Group Name" )
        new_group_entry = gtk.Entry()
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(new_group_entry, True) 
        vbox.pack_start( hbox )
 
        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_reregister" )
        ok_button.connect("clicked", self.reregister_group, window, group, new_group_entry )

        #help_button = gtk.Button( "_Help" )
        #help_button.connect("clicked", self.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( ok_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def reregister_group( self, b, w, g_from, g_to_e ):
        g_to = g_to_e.get_text()
        if self.cdb:
            g_from = self.owner + ':' + g_from
            g_to = self.owner + ':' + g_to
        call( 'capture "cylc reregister ' + g_from + ': ' + g_to + ':" --width=600 &', shell=True )
        w.destroy()

    def export_group_popup( self, w, group ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Export '" + group )

        vbox = gtk.VBox()

        box = gtk.HBox()
        label = gtk.Label( 'Group' )
        box.pack_start( label, True )
        group_entry = gtk.Entry()
        group_entry.set_text( group )
        box.pack_start (group_entry, True)
        vbox.pack_start( box )

        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Export" )
        ok_button.connect("clicked", self.export_group, window, group, group_entry )

        #help_button = gtk.Button( "_Help" )
        #help_button.connect("clicked", self.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( ok_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def export_group( self, b, w, lgroup, group_entry ):
        group = group_entry.get_text()
        if not self.check_entries( [group] ):
            return False
        call( 'capture "cylc export ' + lgroup + ': ' + group + ':" --width=600 &', shell=True )
        w.destroy()
 
    def copy_group_popup( self, w, group ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Copy Group'" + group + "'")

        vbox = gtk.VBox()

        label = gtk.Label("To Group" )
        group_entry = gtk.Entry()
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(group_entry, True) 
        vbox.pack_start( hbox )
 
        box = gtk.HBox()
        label = gtk.Label( 'Directory' )
        box.pack_start( label, True )
        def_entry = gtk.Entry()
        box.pack_start (def_entry, True)
        vbox.pack_start(box)

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Copy" )
        ok_button.connect("clicked", self.copy_group, window, group, group_entry, def_entry )

        #help_button = gtk.Button( "_Help" )
        #help_button.connect("clicked", self.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( ok_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def copy_group( self, b, w, g_from, g_to_entry, dir_entry ):
        g_to = g_to_entry.get_text()
        g_to += ':'
        g_from += ':'
        dir = dir_entry.get_text()
        call( 'capture "cylc copy ' + g_from + ' ' + g_to + ' ' + dir + '" --width=600 &', shell=True )
        w.destroy()

    def copy_suite_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Copy '" + reg + "'")

        vbox = gtk.VBox()

        label = gtk.Label("Group" )
        group_entry = gtk.Entry()
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(group_entry, True) 
        vbox.pack_start( hbox )
 
        label = gtk.Label("Name" )
        name_entry = gtk.Entry()
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(name_entry, True) 
        vbox.pack_start( hbox )

        box = gtk.HBox()
        label = gtk.Label( 'Directory' )
        box.pack_start( label, True )
        def_entry = gtk.Entry()
        box.pack_start (def_entry, True)
        vbox.pack_start(box)

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Copy" )
        ok_button.connect("clicked", self.copy_suite, window, reg, group_entry, name_entry, def_entry )

        #help_button = gtk.Button( "_Help" )
        #help_button.connect("clicked", self.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( ok_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def copy_suite( self, b, w, reg, group_entry, name_entry, def_entry ):
        junk, reg_group, junk = regsplit( reg ).get() 
        group = group_entry.get_text()
        name  = name_entry.get_text()
        dir = def_entry.get_text()
        if not self.check_entries( [group, name, dir] ):
            return False
        call( 'capture "cylc copy ' + reg + ' ' + group + ':' + name + ' ' + dir + '" --width=600 &', shell=True )
        w.destroy()
 
    def search_suite_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Suite Search Options for '" + reg + "'")

        vbox = gtk.VBox()

        nobin_cb = gtk.CheckButton( "Don't Search Suite bin Directory" )
        vbox.pack_start (nobin_cb, True)

        label = gtk.Label("Search Pattern" )
        pattern_entry = gtk.Entry()
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(pattern_entry, True) 
        vbox.pack_start( hbox )
 
        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Search" )
        ok_button.connect("clicked", self.search_suite, reg, nobin_cb, pattern_entry )

        #help_button = gtk.Button( "_Help" )
        #help_button.connect("clicked", self.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( ok_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()


    def graph_suite_popup( self, w, reg ):
        try:
            from graphing import xdot
        except:
            warning_dialog( "Graphing is not available;\nplease install graphviz\nand pygraphviz.").warn()
            return False

        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Suite Graph Options for '" + reg + "'")

        vbox = gtk.VBox()

        warm_cb = gtk.CheckButton( "Warm Start" )
        #runtime_cb = gtk.CheckButton( "Runtime Graph" )
        vbox.pack_start (warm_cb, True)

        label = gtk.Label("Output File" )
        outputfile_entry = gtk.Entry()
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(outputfile_entry, True) 
        vbox.pack_start( hbox )
 
        label = gtk.Label("Start Hour" )
        start_entry = gtk.Entry()
        start_entry.set_text( '0' )
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(start_entry, True) 
        vbox.pack_start(hbox)

        label = gtk.Label("Stop Hour" )
        stop_entry = gtk.Entry()
        stop_entry.set_text( '6' )
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(stop_entry, True) 
        vbox.pack_start (hbox, True)
  
        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )
        ok_button = gtk.Button( "_Graph" )
        ok_button.connect("clicked", self.graph_suite, reg,
                warm_cb, outputfile_entry, start_entry, stop_entry )

        #help_button = gtk.Button( "_Help" )
        #help_button.connect("clicked", self.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( ok_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def search_suite( self, w, reg, nobin_cb, pattern_entry ):
        pattern = pattern_entry.get_text()
        options = ''
        if nobin_cb.get_active():
            options += ' -x '

        if self.cdb:
            options += ' -c '

        # TO DO 1/ use non-shell non-blocking launch here?
        # TO DO 2/ instead of external process make part of chooser app?
        # Would have to launch in own thread as xdot is interactive?
        # Probably not necessary ... same goes for controller actually?
        call( 'capture "cylc search ' + options + ' ' + pattern + ' ' + reg + ' ' + '" --height=500 &', shell=True )

    def graph_suite( self, w, reg, warm_cb, outputfile_entry, start_entry, stop_entry ):
        start = start_entry.get_text()
        stop = stop_entry.get_text()
        for h in start, stop:
            try:
                int(h)
            except:
                warning_dialog( "Hour must convert to integer: " + h ).warn()
                return False

        options = ''

        ofile = outputfile_entry.get_text()
        if ofile != '':
            options += ' -o ' + ofile

        if warm_cb.get_active():
            options += ' -w '

        if self.cdb:
            options += ' -c '

        # TO DO 1/ use non-shell non-blocking launch here?
        # TO DO 2/ instead of external process make part of chooser app?
        # Would have to launch in own thread as xdot is interactive?
        # Probably not necessary ... same goes for controller actually?
        call( 'capture "cylc graph ' + options + ' ' + reg + ' ' + start + ' ' + stop + '" &', shell=True )

    def view_inlined_toggled( self, w, rb, cbs ):
        cbs.set_sensitive( rb.get_active() )

    def edit_suite_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Suite Editing Options for '" + reg + "'")

        vbox = gtk.VBox()
        box = gtk.HBox()

        edit_rb = gtk.RadioButton( None, "Edit" )
        box.pack_start (edit_rb, True)
        edit_inlined_rb = gtk.RadioButton( edit_rb, "Edit Inlined" )
        box.pack_start (edit_inlined_rb, True)
        view_inlined_rb = gtk.RadioButton( edit_rb, "View Inlined" )
        box.pack_start (view_inlined_rb, True)
        edit_rb.set_active(True)
        vbox.pack_start( box )

        hbox = gtk.HBox()
        mark_cb = gtk.CheckButton( "Marked" )
        label_cb = gtk.CheckButton( "Labeled" )
        nojoin_cb = gtk.CheckButton( "Unjoined" )
        single_cb = gtk.CheckButton( "Singled" )
        
        hbox.pack_start (mark_cb, True)
        hbox.pack_start (label_cb, True)
        hbox.pack_start (nojoin_cb, True)
        hbox.pack_start (single_cb, True)
        vbox.pack_start( hbox )
        hbox.set_sensitive(False)

        view_inlined_rb.connect( "toggled", self.view_inlined_toggled, view_inlined_rb, hbox )

        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )
        ok_button = gtk.Button( "_Edit" )
        ok_button.connect("clicked", self.edit_suite, reg, edit_rb,
                edit_inlined_rb, view_inlined_rb, mark_cb, label_cb, nojoin_cb, single_cb )

        #help_button = gtk.Button( "_Help" )
        #help_button.connect("clicked", self.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( ok_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def edit_suite( self, w, reg, edit_rb, edit_inlined_rb,
            view_inlined_rb, markcb, lblcb, nojcb, sngcb ):

        if view_inlined_rb.get_active():
            extra = ''
            if self.cdb:
                extra += '-c '
            if markcb.get_active():
                extra += ' -m'
            if nojcb.get_active():
                extra += ' -n'
            if lblcb.get_active():
                extra += ' -l'
            if sngcb.get_active():
                extra += ' -s'
            call( 'capture "cylc inline ' + extra + ' ' + reg + '" &', shell=True  )
        else:
            if edit_inlined_rb.get_active():
                extra = '-i '
            else:
                extra = ''
            if self.cdb:
                extra += '-c '
            call( 'capture "cylc edit ' + extra + ' ' + reg + '" &', shell=True  )
        return False


    def validate_suite( self, w, name ):
        # the following requires gui capture of stdout and stderr somehow:
        #try:
        #    conf = config( name )
        #    conf.load_tasks()
        #except SuiteConfigError,x:
        #    warning_dialog( str(x) ).warn()
        #    return False
        #except:
        #    raise
        #else:
        #    info_dialog( "Suite " + name + " validates OK." ).inform()

        # for now, launch external process via the cylc capture command:
        options = ''
        if self.cdb:
            options += ' -c '
        call( 'capture "cylc validate ' + options + name  + '" &', shell=True )

    def launch_controller( self, w, name, state, suite_dir ):
        m = re.match( 'RUNNING \(port (\d+)\)', state )
        port = None
        if m:
            port = m.groups()[0]
        # get suite logging directory
        # logging_dir = os.path.join( config(name)['top level logging directory'], name ) 
        # TO LAUNCH A CONTROL GUI AS PART OF THIS APP:
        #tv = monitor(name, self.owner, self.host, port, suite_dir,
        #    logging_dir, self.imagedir, self.readonly )
        #self.viewer_list.append( tv )
        #return False
        call( 'capture "gcylc ' + name  + '" --width=700 &', shell=True )

    def check_entries( self, entries ):
        # note this check retrieved entry values
        bad = False
        for entry in entries:
            if entry == '':
                bad = True
        if bad:
            warning_dialog( "Complete all text entry panels" ).warn()
            return False
        else:
            return True

