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

class chooser_updater(threading.Thread):
    def __init__(self, owner, regd_liststore, db, is_cdb, host, 
            ownerfilt=None, groupfilt=None, namefilt=None ):
        self.ownerfilt = ownerfilt
        self.groupfilt = groupfilt
        self.namefilt = namefilt
        self.db = db
        self.is_cdb = is_cdb
        self.owner = owner
        self.quit = False
        self.host = host
        self.regd_liststore = regd_liststore
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

        self.regd_liststore.clear()
        choices = self.regd_choices
        for reg in choices:
            col = self.line_colors.get_color()
            col_cdb = self.line_colors_cdb.get_color()
            grn = '#2f2'
            #red = '#ff1a45'
            red = self.state_line_colors.get_color()
            name, suite_dir, descr = reg
            suite_dir = re.sub( os.environ['HOME'], '~', suite_dir )
            if self.is_cdb:
                self.regd_liststore.append( [name, col_cdb, '(cdb)', col_cdb, suite_dir, col_cdb, descr, col_cdb ] )
            else:
                if name in ports:
                    self.regd_liststore.append( [name, grn, 'port ' + str(ports[name]), '#19ae0a', suite_dir, grn, descr, grn ] )
                else:
                    self.regd_liststore.append( [name, col, 'dormant', red, suite_dir, col, descr, col ] )

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
        self.window.set_size_request(600, 200)
        self.window.set_border_width( 5 )
        self.window.connect("delete_event", self.delete_all_event)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        regd_treeview = gtk.TreeView()
        # suite, state, title, colors...
        self.regd_liststore = gtk.ListStore( str, str, str, str, str, str, str, str, )
        regd_treeview.set_model(self.regd_liststore)
        regd_treeview.connect( 'button_press_event', self.on_suite_select )

        newreg_button = gtk.Button( "New" )
        newreg_button.connect("clicked", self.newreg_popup )

        self.db_button = gtk.Button( "Central DB" )
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
        tvc = gtk.TreeViewColumn( 'Suite', cr, text=0, background=1 )
        regd_treeview.append_column( tvc )

        cr = gtk.CellRendererText()
        # use text from col 2, background color stored in col 3:
        tvc = gtk.TreeViewColumn( 'State', cr, text=2, background=3 )
        regd_treeview.append_column( tvc ) 

        cr = gtk.CellRendererText()
        tvc = gtk.TreeViewColumn( 'Title', cr, text=6, background=5 )
        regd_treeview.append_column( tvc )

        cr = gtk.CellRendererText()
        tvc = gtk.TreeViewColumn( 'Definition', cr, text=4, background=7 )
        regd_treeview.append_column( tvc )

        # NOTE THAT WE CANNOT LEAVE ANY SUITE CONTROL WINDOWS OPEN WHEN
        # WE CLOSE THE CHOOSER WINDOW: when launched by the chooser 
        # they are all under the same gtk main loop (?) and do not
        # call gtk_main.quit() unless launched as standalone viewers.
        quit_all_button = gtk.Button( " Quit " )
        quit_all_button.connect("clicked", self.delete_all_event, None, None )

        filter_button = gtk.Button( "Filter" )
        filter_button.connect("clicked", self.filter_popup, None, None )

        label = gtk.Label( " Right Click for Menu" )

        vbox = gtk.VBox()
        hbox = gtk.HBox()
        hbox.pack_start( self.main_label )
        vbox.pack_start( hbox, False )

        sw.add( regd_treeview )
        vbox.pack_start( sw, True )

        hbox = gtk.HBox()
        hbox.pack_start( quit_all_button, False )
        hbox.pack_start( self.db_button, False )
        hbox.pack_start( filter_button, False )
        hbox.pack_start( newreg_button, False )
        hbox.pack_start( label, False )

        vbox.pack_start( hbox, False )

        self.window.add(vbox)
        self.window.show_all()

        self.viewer_list = []

    def start_updater(self, ownerfilt=None, groupfilt=None, namefilt=None):
        if self.cdb:
            db = centraldb()
            self.db_button.set_label( "Local DB" )
            self.main_label.set_text( "Central Suite Registrations" )
        else:
            db = localdb()
            self.db_button.set_label( "Central DB" )
            self.main_label.set_text( "Local Suite Registrations" )
        if self.updater:
            self.updater.quit = True # does this take effect?
        self.updater = chooser_updater( self.owner, self.regd_liststore, 
                db, self.cdb, self.host, ownerfilt, groupfilt, namefilt )
        self.updater.update_liststore()
        self.updater.start()

    def newreg_popup( self, w ):
        dialog = gtk.FileChooserDialog(title='New Registration',
                action=gtk.FILE_CHOOSER_ACTION_OPEN,
                buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OPEN,gtk.RESPONSE_OK))
        filter = gtk.FileFilter()
        filter.set_name("cylc suite definitions")
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
        window.set_title( "New Registration" )

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

        cancel_button = gtk.Button( "Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        apply_button = gtk.Button( "OK" )
        apply_button.connect("clicked", self.new_reg, dir, group_entry, name_entry )

        #help_button = gtk.Button( "Help" )
        #help_button.connect("clicked", self.filter_guide )

        hbox = gtk.HBox()
        hbox.pack_start( apply_button, False )
        hbox.pack_start( cancel_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def new_reg( self, w, dir, group_e, name_e ):
        group = group_e.get_text()
        name = name_e.get_text()
        reg = group + ':' + name
        call( 'capture "_create ' + reg + ' ' + dir + '" &', shell=True )

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
        self.filter_window.set_title( "DB Filter" )

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

        cancel_button = gtk.Button( "Close" )
        cancel_button.connect("clicked", lambda x: self.filter_window.destroy() )

        apply_button = gtk.Button( "Apply" )
        apply_button.connect("clicked", self.filter, owner_entry, group_entry, name_entry )

        reset_button = gtk.Button( "Reset" )
        reset_button.connect("clicked", self.filter_reset, owner_entry, group_entry, name_entry )

        #help_button = gtk.Button( "Help" )
        #help_button.connect("clicked", self.filter_guide )

        hbox = gtk.HBox()
        hbox.pack_start( apply_button, False )
        hbox.pack_start( reset_button, False )
        hbox.pack_start( cancel_button, False )
        #hbox.pack_start( help_button, False )
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
        name = model.get_value( iter, 0 )
        suite_dir = model.get_value( iter, 1 )
        state = model.get_value( iter, 2 ) 
        descr = model.get_value( iter, 6 )

        m = re.match( 'RUNNING \(port (\d+)\)', state )
        port = None
        if m:
            port = m.groups()[0]

        menu = gtk.Menu()

        menu_root = gtk.MenuItem( name )
        menu_root.set_submenu( menu )

        rename_item = gtk.MenuItem( 'Rename' )
        menu.append( rename_item )
        rename_item.connect( 'activate', self.rename_suite_popup, name )
        if self.cdb:
            owner, group, sname = re.split(':', name )
            if owner != self.owner:
                rename_item.set_sensitive( False )

        val_item = gtk.MenuItem( 'Validate' )
        menu.append( val_item )
        val_item.connect( 'activate', self.validate_suite, name )

        graph_item = gtk.MenuItem( 'Graph' )
        menu.append( graph_item )
        graph_item.connect( 'activate', self.graph_suite_popup, name )

        search_item = gtk.MenuItem( 'Search' )
        menu.append( search_item )
        search_item.connect( 'activate', self.search_suite_popup, name )

        edit_item = gtk.MenuItem( 'Edit' )
        menu.append( edit_item )
        edit_item.connect( 'activate', self.edit_suite_popup, name )

        edit_item = gtk.MenuItem( 'Inline' )
        menu.append( edit_item )
        edit_item.connect( 'activate', self.inline_suite_popup, name )

        if self.cdb:
            imp_item = gtk.MenuItem( 'Import' )
            menu.append( imp_item )
            imp_item.connect( 'activate', self.import_suite_popup, name, suite_dir, descr )
        else:
            if state == 'dormant':
                title = 'Start'
            else:
                title = 'Connect'
            title = 'Control'
            con_item = gtk.MenuItem( title )
            menu.append( con_item )
            con_item.connect( 'activate', self.launch_controller, name, port, suite_dir )

            exp_item = gtk.MenuItem( 'Export' )
            menu.append( exp_item )
            exp_item.connect( 'activate', self.export_suite_popup, name, suite_dir, descr )

        del_item = gtk.MenuItem( 'Delete' )
        menu.append( del_item )
        del_item.connect( 'activate', self.delete_suite_popup, name )
        if self.cdb:
            owner, group, sname = re.split(':', name )
            if owner != self.owner:
                del_item.set_sensitive( False )

        menu.show_all()
        menu.popup( None, None, None, event.button, event.time )
        # TO DO: POPUP MENU MUST BE DESTROY()ED AFTER EVERY USE AS
        # POPPING DOWN DOES NOT DO THIS (=> MEMORY LEAK?)
        return True

    def delete_suite_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Delete '" + reg + "'")

        vbox = gtk.VBox()

        wholegroup_cb = gtk.CheckButton( "Delete Parent Group" )
        vbox.pack_start (wholegroup_cb, True)

        cancel_button = gtk.Button( "Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "Delete" )
        ok_button.connect("clicked", self.delete_suite, window, reg, wholegroup_cb )

        #help_button = gtk.Button( "Help" )
        #help_button.connect("clicked", self.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( ok_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def delete_suite( self, b, w, reg, wholegroup_cb ):
        wholegroup = wholegroup_cb.get_active()
        items = re.split(':', reg)
        if len(items) == 3:
            fo, fg, fn = items
        elif len(items) == 2:
            fg, fn = items
            fo = self.owner
        elif len(items) == 1:
            fo = self.owner
            fn = items[0]
            fg = 'default'

        options = ''
        if self.cdb:
            options += ' -c '

        options += " -g '^" + fg + "$' "
        if not wholegroup:
            options += " -n '^" + fn + "$' "

        call( 'capture "_delete ' + options + '" &', shell=True )
        w.destroy()

    def import_suite_popup( self, w, reg, dir, descr ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Import '" + reg + "' from central database")

        vbox = gtk.VBox()
        label = gtk.Label( 'Import ' + reg + ' as:' )

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
        label = gtk.Label( 'New Suite Definition Directory' )
        box.pack_start( label, True )
        def_entry = gtk.Entry()
        box.pack_start (def_entry, True)
        vbox.pack_start(box)

        cancel_button = gtk.Button( "Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "Import" )
        ok_button.connect("clicked", self.import_suite, window, reg, def_entry, group_entry, name_entry )

        #help_button = gtk.Button( "Help" )
        #help_button.connect("clicked", self.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( ok_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def import_suite( self, b, w, reg, def_entry, group_entry, name_entry ):
        group = group_entry.get_text()
        name  = name_entry.get_text()
        dir = def_entry.get_text()
        call( 'capture "_import ' + reg + ' ' + group + ':' + name + ' ' + dir + '" &', shell=True )
        w.destroy()
 
    def export_suite_popup( self, w, reg, dir, descr ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Export '" + reg + "' to central database")

        vbox = gtk.VBox()
        label = gtk.Label( 'Export ' + reg + ' as:' )

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

        #box = gtk.HBox()
        #label = gtk.Label( 'Description' )
        #box.pack_start( label, True )
        #descr_entry = gtk.Entry()
        #descr_entry.set_text( descr )
        #box.pack_start (descr_entry, True)
        #vbox.pack_start(box)

        cancel_button = gtk.Button( "Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "Export" )
        ok_button.connect("clicked", self.export_suite, window, reg, group_entry, name_entry )

        #help_button = gtk.Button( "Help" )
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
        call( 'capture "_export ' + reg + ' ' + group + ':' + name + '" &', shell=True )
        w.destroy()
 
    def toggle_entry_sensitivity( self, w, entry ):
        if entry.get_property( 'sensitive' ) == 0:
            entry.set_sensitive( True )
        else:
            entry.set_sensitive( False )

    def rename_suite_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Rename '" + reg + "'")

        vbox = gtk.VBox()

        wholegroup_cb = gtk.CheckButton( "Rename the group" )
        vbox.pack_start (wholegroup_cb, True)

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

        wholegroup_cb.connect( "toggled", self.toggle_entry_sensitivity, name_entry )
 
        cancel_button = gtk.Button( "Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "Rename" )
        ok_button.connect("clicked", self.rename_suite, window, reg, group_entry, name_entry, wholegroup_cb )

        #help_button = gtk.Button( "Help" )
        #help_button.connect("clicked", self.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( ok_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def rename_suite( self, b, w, ffrom, g_e, n_e, wholegroup_cb ):
        g = g_e.get_text()
        n = n_e.get_text()
        options = ''
        ffroms = re.split(':', ffrom)
        if len(ffroms) == 3:
            fo, fg, fn = ffroms
        elif len(ffroms) == 2:
            fg, fn = ffroms
            fo = self.owner
        elif len(ffroms) == 1:
            fn = ffroms
            fg = 'default'

        if g == '':
            g = 'default'
        if wholegroup_cb.get_active():
            options += ' -g '
            tto = g
            ffrom = fg
        else: 
            tto = g + ':' + n
        if self.cdb:
            options += ' -c '

        call( 'capture "_rename ' + options + ' ' + ffrom + ' ' + tto + '" &', shell=True )
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
 
        cancel_button = gtk.Button( "Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "Search" )
        ok_button.connect("clicked", self.search_suite, reg, nobin_cb, pattern_entry )

        #help_button = gtk.Button( "Help" )
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
  
        cancel_button = gtk.Button( "Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )
        ok_button = gtk.Button( "Graph" )
        ok_button.connect("clicked", self.graph_suite, reg,
                warm_cb, outputfile_entry, start_entry, stop_entry )

        #help_button = gtk.Button( "Help" )
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
        call( 'capture "_grep ' + options + ' ' + pattern + ' ' + reg + ' ' + '" &', shell=True )

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
        call( 'capture "_graph ' + options + ' ' + reg + ' ' + start + ' ' + stop + '" &', shell=True )

    def inline_suite_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Inlining Options for '" + reg + "'")

        vbox = gtk.VBox()
        box = gtk.HBox()

        mark_cb = gtk.CheckButton( "Marked" )
        label_cb = gtk.CheckButton( "Labeled" )
        nojoin_cb = gtk.CheckButton( "Unjoined" )
        single_cb = gtk.CheckButton( "Singled" )
        
        box.pack_start (mark_cb, True)
        box.pack_start (label_cb, True)
        box.pack_start (nojoin_cb, True)
        box.pack_start (single_cb, True)
        vbox.pack_start( box )

        cancel_button = gtk.Button( "Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )
        ok_button = gtk.Button( "Launch Editor" )
        ok_button.connect("clicked", self.inline_suite, reg,
                mark_cb, label_cb, nojoin_cb, single_cb  )

        #help_button = gtk.Button( "Help" )
        #help_button.connect("clicked", self.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( ok_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def edit_suite_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Suite Editing Options for '" + reg + "'")

        vbox = gtk.VBox()
        box = gtk.HBox()

        inlined_cb = gtk.CheckButton( "Inlined" )
        box.pack_start (inlined_cb, True)
        vbox.pack_start( box )

        cancel_button = gtk.Button( "Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )
        ok_button = gtk.Button( "Launch Editor" )
        ok_button.connect("clicked", self.edit_suite, reg, inlined_cb  )

        #help_button = gtk.Button( "Help" )
        #help_button.connect("clicked", self.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( cancel_button, False )
        hbox.pack_start( ok_button, False )
        #hbox.pack_start( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def edit_suite( self, w, reg, inlined_cb ):
        inlined = inlined_cb.get_active()
        if inlined:
            extra = '-i '
        else:
            extra = ''
        if self.cdb:
            extra += '-c '
        call( 'capture "_edit ' + extra + ' ' + reg + '" &', shell=True  )
        return False

    def inline_suite( self, w, reg, markcb, lblcb, nojcb, sngcb ):
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
        call( 'capture "_inline ' + extra + ' ' + reg + '" &', shell=True  )
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
        call( 'capture "_validate ' + options + name  + '" &', shell=True )

    def launch_controller( self, w, name, port, suite_dir ):
        # get suite logging directory
        # logging_dir = os.path.join( config(name)['top level logging directory'], name ) 
        # TO LAUNCH A CONTROL GUI AS PART OF THIS APP:
        #tv = monitor(name, self.owner, self.host, port, suite_dir,
        #    logging_dir, self.imagedir, self.readonly )
        #self.viewer_list.append( tv )
        #return False
        call( 'capture "gcylc ' + name  + '" &', shell=True )


