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
from warning_dialog import warning_dialog, info_dialog
from subprocess import call
import helpwindow 

#debug = True
debug = False

class chooser_updater(threading.Thread):
    count = 0
    def __init__(self, owner, regd_treestore, db, is_cdb, host, 
            ownerfilt=None, groupfilt=None, namefilt=None ):
        self.__class__.count += 1
        self.me = self.__class__.count
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

        self.db.load_from_file()
        self.regd_choices = []
        self.regd_choices = self.db.get_list( self.ownerfilt, self.groupfilt, self.namefilt ) 
    
    def run( self ):
        global debug
        if debug:
            print '* thread', self.me, 'starting'
        while not self.quit:
            if self.running_choices_changed() or self.regd_choices_changed():
                gobject.idle_add( self.update_liststore )
            time.sleep(1)
        else:
            if debug:
                print '* thread', self.me, 'quitting'
            self.__class__.count -= 1
    
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
            reg, port = suite
            ports[ reg ] = port

        # construct newtree[owner][group][name] = [state, descr, dir ]
        newtree = {}
        for reg in self.regd_choices:
            suite, suite_dir, descr = reg
            suite_dir = re.sub( os.environ['HOME'], '~', suite_dir )
            if suite in ports:
                state = 'port ' + str(ports[suite])
            else:
                state = '-'
            if self.is_cdb:
                owner, group, name = re.split( ':', suite )
            else:
                owner = self.owner
                group, name = re.split( ':', suite )
            if owner not in newtree:
                newtree[owner] = {}
            if group not in newtree[owner]:
                newtree[owner][group] = {}
            if name not in newtree[owner][group]:
                newtree[owner][group][name] = {}
            newtree[owner][group][name] = [ state, descr, suite_dir ]

        # construct tree of the old data, 
        # remove any old data not found in the new data.
        # change any old data that is different in the new data
        # (later we'll add any new data not found in the old data)
        if self.is_cdb:
            oldtree = {}
            ts = self.regd_treestore
            oiter = ts.get_iter_first()
            while oiter:
                # get owner
                row = []
                for col in range( ts.get_n_columns() ):
                    row.append( ts.get_value( oiter, col))
                owner = row[0]
                #print 'OWNER', owner
                oldtree[owner] = {}
                if owner not in newtree:
                    # remove owner
                    #print 'removing owner ', owner
                    result = ts.remove(oiter)
                    if not result:
                        oiter = None
                else:
                    # owner still exists, check it
                    giter = ts.iter_children(oiter)
                    while giter:
                        # get group
                        ch_row = []
                        for col in range( ts.get_n_columns()):
                            ch_row.append( ts.get_value(giter,col))
                        group = ch_row[0]
                        #print '  GROUP', group

                        oldtree[owner][group] = {}
                        if group not in newtree[owner]:
                            # remove group
                            #print '  removing group ', group
                            result = ts.remove(giter)
                            if not result:
                                giter = None
                        else:
                            # group still exists, check it
                            niter = ts.iter_children(giter)
                            while niter:
                                # get name
                                chch_row = []
                                for col in range( ts.get_n_columns()):
                                    chch_row.append( ts.get_value(niter,col))
                                [name, state, descr, dir, junk, junk ] = chch_row
                                oldtree[owner][group][name] = [state, descr, dir ]
                                #print '    REG', name, state, descr, dir

                                if name not in newtree[owner][group]:
                                    # remove name
                                    #print '    removing reg ', name
                                    result = ts.remove(niter)
                                    if not result:
                                        niter = None
                                elif oldtree[owner][group][name] != newtree[owner][group][name]:
                                    # data changed
                                    # print '    changing reg ', name
                                    state, descr, dir = newtree[owner][group][name]
                                    col1, col2, col3  = self.statecol( state )
                                    foo = ts.prepend( giter, [ name ] + [ state, descr, dir, col1, col2, col3  ] )
                                    result = ts.remove(niter)
                                    if not result:
                                        niter = None
                                else:
                                    niter = ts.iter_next( niter )
                            giter = ts.iter_next( giter )
                    oiter = ts.iter_next(oiter)  


        else:
            owner = self.owner
            oldtree = {}
            oldtree[owner] = {}
            ts = self.regd_treestore
            giter = ts.get_iter_first()
            while giter:
                # get group
                while giter:
                   # get group
                   ch_row = []
                   for col in range( ts.get_n_columns()):
                       ch_row.append( ts.get_value(giter,col))
                   group = ch_row[0]
                   #print '  GROUP', group

                   oldtree[owner][group] = {}
                   if owner not in newtree or group not in newtree[owner]:
                       # remove group
                       #print '  removing group ', group
                       result = ts.remove(giter)
                       if not result:
                           giter = None
                   else:
                       # group still exists, check it
                       niter = ts.iter_children(giter)
                       while niter:
                           # get name
                           chch_row = []
                           for col in range( ts.get_n_columns()):
                               chch_row.append( ts.get_value(niter,col))
                           [name, state, descr, dir, junk, junk ] = chch_row
                           oldtree[owner][group][name] = [state, descr, dir ]
                           #print '    REG', name, state, descr, dir

                           if name not in newtree[owner][group]:
                               # remove name
                               #print '    removing reg ', name
                               result = ts.remove(niter)
                               if not result:
                                   niter = None
                           elif oldtree[owner][group][name] != newtree[owner][group][name]:
                               # data changed
                               #print '    changing reg ', name
                               state, descr, dir = newtree[owner][group][name]
                               col1, col2, col3  = self.statecol( state )
                               if state != '-':
                                   ts.set_value( giter,4,col2)
                               else:
                                   ts.set_value( giter,4,None)
                               foo = ts.prepend( giter, [ name ] + [ state, descr, dir, col1, col2, col3  ] )
                               result = ts.remove(niter)
                               if not result:
                                   niter = None
                           else:
                               niter = ts.iter_next( niter )
                       giter = ts.iter_next( giter )

        if self.is_cdb:
            for owner in newtree:
                if owner not in oldtree:
                    # new owner: insert all of its data
                    oiter = ts.append( None, [owner, None, None, None, None, None, None ] )
                    for group in newtree[owner]:
                        giter = ts.append( oiter, [group, None, None, None, None, None, None ] )
                        for name in newtree[owner][group]:
                            state, descr, dir = newtree[owner][group][name]
                            col1, col2, col3 = self.statecol( state )
                            niter = ts.append( giter, [name] + [state, descr, dir, col1, col2, col3 ])
                    continue

                # owner already in the treemodel, find it
                oiter = self.search_level( ts, ts.get_iter_first(), self.match_func, (0, owner ))

                for group in newtree[owner]:
                    if group not in oldtree[owner]:
                        # new group: insert all of its data
                        giter = ts.append( oiter, [ group, None, None, None, None, None, None ] )
                        for name in newtree[owner][group]:
                            state, descr, dir = newtree[owner][group][name]
                            col1, col2, col3 = self.statecol( state )
                            niter = ts.append( giter, [name] + [state, descr, dir, col1, col2, col3 ])
                        continue

                    # group already in the treemodel, find it
                    giter = self.search_level( ts, ts.iter_children(oiter), self.match_func, (0, group))

                    for name in newtree[owner][group]:
                        if name not in oldtree[owner][group]:
                            # new name, insert it and its data
                            state, descr, dir = newtree[owner][group][name]
                            col1, col2, col3  = self.statecol( state )
                            niter = ts.append( giter, [name] + [ state, descr, dir, col1, col2, col3 ])
                            continue

        else:
            for owner in newtree:
                if owner not in oldtree:
                    # new owner: insert all of its data
                    for group in newtree[owner]:
                        giter = ts.append( None, [group, None, None, None, None, None, None ] )
                        for name in newtree[owner][group]:
                            state, descr, dir = newtree[owner][group][name]
                            col1, col2, col3 = self.statecol( state )
                            niter = ts.append( giter, [name] + [state, descr, dir, col1, col2, col3 ])
                    continue

                # owner already in the treemodel, find it
                #oiter = self.search_level( ts, ts.get_iter_first(), self.match_func, (0, owner ))
                oiter = ts.get_iter_first()

                for group in newtree[owner]:
                    if owner not in oldtree or group not in oldtree[owner]:
                        # new group: insert all of its data
                        giter = ts.append( None, [ group, None, None, None, None, None, None ] )
                        for name in newtree[owner][group]:
                            state, descr, dir = newtree[owner][group][name]
                            col1, col2, col3  = self.statecol( state )
                            niter = ts.append( giter, [name] + [state, descr, dir, col1, col2, col3  ])
                        continue

                    # group already in the treemodel, find it
                    giter = self.search_level( ts, ts.get_iter_first(), self.match_func, (0, group))
    
                    for name in newtree[owner][group]:
                        if name not in oldtree[owner][group]:
                            # new name, insert it and its data
                            state, descr, dir = newtree[owner][group][name]
                            col1, col2, col3  = self.statecol( state )
                            niter = ts.append( giter, [name] + [ state, descr, dir, col1, col2, col3  ])
                            continue
    
    def statecol( self, state ):
        grnbg = '#19ae0a'
        grnfg = '#030'
        #red = '#ff1a45'
        red = '#845'
        white = '#fff'
        black='#000'
        hilight = '#faf'
        if state == '-':
            return (black, None, hilight)
        else:
            return (grnfg, grnbg)

    def search_level( self, model, iter, func, data ):
        while iter:
            if func( model, iter, data):
                return iter
            iter = model.iter_next(iter)
        return None

    def search_treemodel( self, model, iter, func, data ):
        while iter:
            if func( model, iter, data):
                return iter
            result = self.search_treemodel( model, model.iter_children(iter), func, data)
            if result:
                return result
            iter = model.iter_next(iter)
        return None

    def match_func( self, model, iter, data ):
        column, key = data
        value = model.get_value( iter, column )
        return value == key

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
        self.window.set_size_request(600, 400)
        #self.window.set_border_width( 5 )
        self.window.connect("delete_event", self.delete_all_event)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        self.regd_treeview = gtk.TreeView()
        # [owner>]group>name, state, title, dir, color1, color2, color3
        self.regd_treestore = gtk.TreeStore( str, str, str, str, str, str, str )
        self.regd_treeview.set_model(self.regd_treestore)
        self.regd_treeview.set_rules_hint(True)
        # search column zero (Ctrl-F)
        self.regd_treeview.connect( 'key_press_event', self.on_suite_select )
        self.regd_treeview.connect( 'button_press_event', self.on_suite_select )
        self.regd_treeview.set_search_column(0)

        file_menu = gtk.Menu()
        file_menu_root = gtk.MenuItem( '_File' )
        file_menu_root.set_submenu( file_menu )

        new_item = gtk.MenuItem( '_New' )
        new_item.connect( 'activate', self.newreg_popup )
        file_menu.append( new_item )

        exit_item = gtk.MenuItem( 'E_xit' )
        exit_item.connect( 'activate', self.delete_all_event )
        file_menu.append( exit_item )

        view_menu = gtk.Menu()
        view_menu_root = gtk.MenuItem( '_View' )
        view_menu_root.set_submenu( view_menu )

        filter_item = gtk.MenuItem( '_Filter' )
        view_menu.append( filter_item )
        filter_item.connect( 'activate', self.filter_popup )

        expand_item = gtk.MenuItem( 'E_xpand' )
        view_menu.append( expand_item )
        expand_item.connect( 'activate', self.expand_all, self.regd_treeview )

        collapse_item = gtk.MenuItem( 'C_ollapse' )
        view_menu.append( collapse_item )
        collapse_item.connect( 'activate', self.collapse_all, self.regd_treeview )

        local_item = gtk.MenuItem( '_LocalDB' )
        view_menu.append( local_item )

        central_item = gtk.MenuItem( '_CentralDB' )
        view_menu.append( central_item )

        local_item.connect( 'activate', self.localdb, new_item, central_item )
        central_item.connect( 'activate', self.centraldb, new_item, local_item )

        help_menu = gtk.Menu()
        help_menu_root = gtk.MenuItem( '_Help' )
        help_menu_root.set_submenu( help_menu )

        guide_item = gtk.MenuItem( '_Quick Guide' )
        help_menu.append( guide_item )
        guide_item.connect( 'activate', helpwindow.main )
 
        about_item = gtk.MenuItem( '_About' )
        help_menu.append( about_item )
        about_item.connect( 'activate', self.about )
 
        self.menu_bar = gtk.MenuBar()
        self.menu_bar.append( file_menu_root )
        self.menu_bar.append( view_menu_root )
        self.menu_bar.append( help_menu_root )

        # Start updating the liststore now, as we need values in it
        # immediately below (it may be possible to delay this till the
        # end of __init___() but it doesn't really matter.
        self.cdb = False # start with local reg db
        self.start_updater()

        regd_ts = self.regd_treeview.get_selection()
        regd_ts.set_mode( gtk.SELECTION_SINGLE )

        cr = gtk.CellRendererText()
        tvc = gtk.TreeViewColumn( 'Suite', cr, text=0, foreground=4, background=5 )
        tvc.set_resizable(True)
        tvc.set_sort_column_id(0)
        self.regd_treeview.append_column( tvc )

        cr = gtk.CellRendererText()
        tvc = gtk.TreeViewColumn( 'State', cr, text=1, foreground=4, background=5 )
        tvc.set_resizable(True)
        # not sure how this sorting works
        #tvc.set_sort_column_id(1)
        self.regd_treeview.append_column( tvc ) 

        cr = gtk.CellRendererText()
        tvc = gtk.TreeViewColumn( 'Title', cr, text=2, foreground=4, background=6 )
        tvc.set_resizable(True)
        #vc.set_sort_column_id(2)
        self.regd_treeview.append_column( tvc )

        cr = gtk.CellRendererText()
        tvc = gtk.TreeViewColumn( 'Suite Definition', cr, text=3, foreground=4, background=5 )
        tvc.set_resizable(True)
        #vc.set_sort_column_id(3)
        self.regd_treeview.append_column( tvc )

        vbox = gtk.VBox()
        hbox = gtk.HBox()
        #hbox.pack_start( self.main_label )
        vbox.pack_start( hbox, False )

        sw.add( self.regd_treeview )

        vbox.pack_start( self.menu_bar, False )
        vbox.pack_start( sw, True )

        self.window.add(vbox)
        self.window.show_all()

        #self.regd_treeview.modify_base( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#f00" ))

    def about( self, bt ):
        about = gtk.AboutDialog()
        if gtk.gtk_version[0] ==2:
            if gtk.gtk_version[1] >= 12:
                # set_program_name() was added in PyGTK 2.12
                about.set_program_name( "cylc" )
        cylc_version = 'THIS IS NOT A VERSIONED RELEASE'
        about.set_version( cylc_version )
        about.set_copyright( "(c) Hilary Oliver, NIWA, 2008-2011" )
        about.set_comments( 
"""
The cylc forecast suite metascheduler.
""" )
        about.set_website( "http://www.niwa.co.nz" )
        about.set_logo( gtk.gdk.pixbuf_new_from_file( self.imagedir + "/dew.jpg" ))
        about.run()
        about.destroy()


    def expand_all( self, w, view ):
        view.expand_all()
    def collapse_all( self, w, view ):
        view.collapse_all()

    def start_updater(self, ownerfilt=None, groupfilt=None, namefilt=None):
        if self.cdb:
            db = centraldb()
            #self.db_button.set_label( "_Local/Central DB" )
            #self.main_label.set_text( "Central Suite Registrations" )
        else:
            db = localdb()
            #self.db_button.set_label( "_Local/Central DB" )
            #self.main_label.set_text( "Local Suite Registrations" )
        if self.updater:
            self.updater.quit = True # does this take effect?
        #not necessary: self.regd_treestore.clear()
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

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.register )

        hbox = gtk.HBox()
        hbox.pack_start( apply_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
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

    def filter_popup(self, w):
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

    def localdb( self, w, new_menu_item, other_w ):
        if not self.cdb:
            return
        w.set_sensitive(False)
        other_w.set_sensitive(True)
        self.cdb = False
        if self.filter_window:
            self.filter_window.destroy()
        # setting base color to None should return it to the default
        self.regd_treeview.modify_base( gtk.STATE_NORMAL, None)
        new_menu_item.set_sensitive( True )
        self.start_updater()

    def centraldb( self, w, new_menu_item, other_w ):
        if self.cdb:
            return
        w.set_sensitive(False)
        other_w.set_sensitive(True)
        self.cdb = True
        if self.filter_window:
            self.filter_window.destroy()
        # note treeview.modify_base() doesn't have same effect on all
        # installations ... it either colours the full background or
        # just inside the expander triangles!
        self.regd_treeview.modify_base( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#bdf" ))
        new_menu_item.set_sensitive( False )
        self.start_updater()

    def delete_all_event( self, w ):
        self.updater.quit = True
        gtk.main_quit()      
        # Uncommenting the following makes the window stay around until
        # all updater threads have exited (put a 5s sleep in scan_my_ports
        # to slow them down so you can see this). Otherwise, the window
        # and threads seem to be killed instantly when this method
        # returns.
        #while True:
        #    print  self.updater.__class__.count
        #    if self.updater.__class__.count == 0:
        #        break
        #    time.sleep(1)
        #print 'BYE'

    def on_suite_select( self, treeview, event ):
        # popup menu on right click or 'Return' key only
        try:
            event.button
        except AttributeError:
            # not called by button click
            try:
                event.keyval
            except AttributeError:
                # not called by key press
                pass
            else:
                # called by key press
                keyname = gtk.gdk.keyval_name(event.keyval)
                if keyname != 'Return':
                    return False
                path, focus_col = treeview.get_cursor()
                if not path:
                    # no selection (prob treeview heading selected)
                    return False
                if not treeview.row_expanded(path):
                    # row not expanded or not expandable
                    iter = self.regd_treestore.get_iter(path)
                    if self.regd_treestore.iter_children(iter):
                        # has children so is expandable
                        treeview.expand_row(path, False )
                        return False
        else:
            # called by button click
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
                copy_item = gtk.MenuItem( 'C_opy' )
                menu.append( copy_item )
                copy_item.connect( 'activate', self.copy_group_popup, group )

            if self.cdb:
                imp_item = gtk.MenuItem( 'I_mport' )
                menu.append( imp_item )
                imp_item.connect( 'activate', self.import_group_popup, owner, group )
            else:
                exp_item = gtk.MenuItem( 'E_xport' )
                menu.append( exp_item )
                exp_item.connect( 'activate', self.export_group_popup, group )

            reregister_item = gtk.MenuItem( '_Reregister' )
            menu.append( reregister_item )
            reregister_item.connect( 'activate', self.reregister_group_popup, group)
            if self.cdb:
                if owner != self.owner:
                    reregister_item.set_sensitive( False )

            del_item = gtk.MenuItem( '_Unregister' )
            menu.append( del_item )
            del_item.connect( 'activate', self.unregister_group_popup, owner, group )
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
                #if state == '-':
                title = '_Control'
                #else:
                #    title = 'Connect'
                con_item = gtk.MenuItem( title )
                menu.append( con_item )
                con_item.connect( 'activate', self.launch_controller, reg, state, suite_dir )
    
                menu.append( gtk.SeparatorMenuItem() )
    
            edit_item = gtk.MenuItem( '_Edit' )
            menu.append( edit_item )
            edit_item.connect( 'activate', self.edit_suite_popup, reg )
    
            graph_item = gtk.MenuItem( '_Graph' )
            menu.append( graph_item )
            graph_item.connect( 'activate', self.graph_suite_popup, reg )
    
            search_item = gtk.MenuItem( '_Search' )
            menu.append( search_item )
            search_item.connect( 'activate', self.search_suite_popup, reg )

            val_item = gtk.MenuItem( '_Validate' )
            menu.append( val_item )
            val_item.connect( 'activate', self.validate_suite, reg )
    
            menu.append( gtk.SeparatorMenuItem() )
    
            if not self.cdb:
                copy_item = gtk.MenuItem( 'Co_py' )
                menu.append( copy_item )
                copy_item.connect( 'activate', self.copy_suite_popup, reg )
    
            if self.cdb:
                imp_item = gtk.MenuItem( 'I_mport' )
                menu.append( imp_item )
                imp_item.connect( 'activate', self.import_suite_popup, reg )
            else:
                exp_item = gtk.MenuItem( 'E_xport' )
                menu.append( exp_item )
                exp_item.connect( 'activate', self.export_suite_popup, reg )
    
            reregister_item = gtk.MenuItem( '_Reregister' )
            menu.append( reregister_item )
            reregister_item.connect( 'activate', self.reregister_suite_popup, reg )
            if self.cdb:
                if owner != self.owner:
                    reregister_item.set_sensitive( False )
    
            del_item = gtk.MenuItem( '_Unregister' )
            menu.append( del_item )
            del_item.connect( 'activate', self.unregister_suite_popup, reg )
            if self.cdb:
                if owner != self.owner:
                    del_item.set_sensitive( False )

        menu.show_all()
        # button only:
        #menu.popup( None, None, None, event.button, event.time )
        # this seems to work with keypress and button:
        menu.popup( None, None, None, 0, event.time )

        # TO DO: POPUP MENU MUST BE DESTROY()ED AFTER EVERY USE AS
        # POPPING DOWN DOES NOT DO THIS (=> MEMORY LEAK?)
        return True

    def unregister_group_popup( self, w, owner, group ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Unregister '" + owner + ':' + group + "'")

        vbox = gtk.VBox()

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Unregister" )
        ok_button.connect("clicked", self.unregister_group, window, owner, group )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.unregister )

        label = gtk.Label( "Unregister the entire " + group + " group?" + """
Note that this will not delete any suite definition directories.""" )
        vbox.pack_start( label )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def unregister_group( self, b, w, owner, group ):
        if self.cdb:
            group = owner + ':' + group
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

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.unregister )

        label = gtk.Label( "Unregister suite " + reg + "?" + """
Note that this will not delete the suite definition directory.""" )
        vbox.pack_start( label )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
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
        label = gtk.Label( 'Target Group' )
        box.pack_start( label, True )
        group_entry = gtk.Entry()
        group_entry.set_text( group )
        box.pack_start (group_entry, True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Target Directory' )
        box.pack_start( label, True )
        def_entry = gtk.Entry()
        box.pack_start (def_entry, True)
        vbox.pack_start(box)

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Import" )
        ok_button.connect("clicked", self.import_group, window, owner, group, group_entry, def_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.importx )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
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
        label = gtk.Label( 'Target Group' )
        box.pack_start( label, True )
        group_entry = gtk.Entry()
        group_entry.set_text( cgroup )
        box.pack_start (group_entry, True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Target Name' )
        box.pack_start( label, True )
        name_entry = gtk.Entry()
        name_entry.set_text( cname )
        box.pack_start (name_entry, True)
        vbox.pack_start(box)

        box = gtk.HBox()
        label = gtk.Label( 'Target Directory' )
        box.pack_start( label, True )
        def_entry = gtk.Entry()
        box.pack_start (def_entry, True)
        vbox.pack_start(box)

        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Import" )
        ok_button.connect("clicked", self.import_suite, window, reg, group_entry, name_entry, def_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.importx )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
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
        label = gtk.Label( 'Target Group' )
        box.pack_start( label, True )
        group_entry = gtk.Entry()
        group_entry.set_text( group )
        box.pack_start (group_entry, True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Target Name' )
        box.pack_start( label, True )
        name_entry = gtk.Entry()
        name_entry.set_text( name )
        box.pack_start (name_entry, True)
        vbox.pack_start(box)

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Export" )
        ok_button.connect("clicked", self.export_suite, window, reg, group_entry, name_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.export )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
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
 
        label = gtk.Label("Target Group" )
        group_entry = gtk.Entry()
        group_entry.set_text( reg_group )
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(group_entry, True) 
        vbox.pack_start( hbox )
 
        label = gtk.Label("Target Name" )
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

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.reregister )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
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
        window.set_title( "Reregister Group'" + group + "'")

        vbox = gtk.VBox()

        label = gtk.Label("New Group" )
        new_group_entry = gtk.Entry()
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(new_group_entry, True) 
        vbox.pack_start( hbox )
 
        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Reregister" )
        ok_button.connect("clicked", self.reregister_group, window, group, new_group_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.reregister )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
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
        label = gtk.Label( 'Target Group' )
        box.pack_start( label, True )
        group_entry = gtk.Entry()
        group_entry.set_text( group )
        box.pack_start (group_entry, True)
        vbox.pack_start( box )

        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Export" )
        ok_button.connect("clicked", self.export_group, window, group, group_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.export )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
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

        label = gtk.Label("Target Group" )
        group_entry = gtk.Entry()
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(group_entry, True) 
        vbox.pack_start( hbox )
 
        box = gtk.HBox()
        label = gtk.Label( 'Target Directory' )
        box.pack_start( label, True )
        def_entry = gtk.Entry()
        box.pack_start (def_entry, True)
        vbox.pack_start(box)

        refonly_cb = gtk.CheckButton( "Reference Only" )
        refonly_cb.set_active(False)
        vbox.pack_start (refonly_cb, True)
        refonly_cb.connect( "toggled", self.refonly_toggled, def_entry )

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "Co_py" )
        ok_button.connect("clicked", self.copy_group, window, group, group_entry, refonly_cb, def_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.copy_group )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def copy_group( self, b, w, g_from, g_to_entry, refonly_cb, dir_entry ):
        g_to = g_to_entry.get_text()
        chk = [g_to]
        if not refonly_cb.get_active():
            dir = dir_entry.get_text()
            chk.append( dir )
        else:
            dir = ''
        if not self.check_entries( chk ):
            return False
        g_to += ':'
        g_from += ':'
        call( 'capture "cylc copy ' + g_from + ' ' + g_to + ' ' + dir + '" --width=600 &', shell=True )
        w.destroy()

    def copy_suite_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Copy '" + reg + "'")

        vbox = gtk.VBox()

        reg_owner, reg_group, reg_name = regsplit( reg ).get() 

        label = gtk.Label("Target Group" )
        group_entry = gtk.Entry()
        group_entry.set_text( reg_group )
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(group_entry, True) 
        vbox.pack_start( hbox )
 
        label = gtk.Label("Target Name" )
        name_entry = gtk.Entry()
        name_entry.set_text( reg_name )
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(name_entry, True) 
        vbox.pack_start( hbox )

        box = gtk.HBox()
        label = gtk.Label( 'Target Directory' )
        box.pack_start( label, True )
        def_entry = gtk.Entry()
        box.pack_start (def_entry, True)
        vbox.pack_start(box)

        refonly_cb = gtk.CheckButton( "Reference Only" )
        refonly_cb.set_active(False)
        vbox.pack_start (refonly_cb, True)
        refonly_cb.connect( "toggled", self.refonly_toggled, def_entry )

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "Co_py" )
        ok_button.connect("clicked", self.copy_suite, window, reg, group_entry, name_entry, refonly_cb, def_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.copy )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def refonly_toggled( self, w, entry ):
        if w.get_active():
            entry.set_sensitive( False )
        else:
            entry.set_sensitive( True )

    def copy_suite( self, b, w, reg, group_entry, name_entry, refonly_cb, def_entry ):
        group = group_entry.get_text()
        name  = name_entry.get_text()
        chk = [ group, name ]
        if not refonly_cb.get_active():
            dir = def_entry.get_text()
            chk.append( dir )
        else:
            dir = ''
        if not self.check_entries( chk ):
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

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.search )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
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
        window.set_title( "Dependency Graph '" + reg + "'")

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

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.graph )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def search_suite( self, w, reg, nobin_cb, pattern_entry ):
        pattern = pattern_entry.get_text()
        options = ''
        if nobin_cb.get_active():
            options += ' -x '

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
        window.set_title( "Edit '" + reg + "'")

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

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.edit )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def edit_suite( self, w, reg, edit_rb, edit_inlined_rb,
            view_inlined_rb, markcb, lblcb, nojcb, sngcb ):

        if view_inlined_rb.get_active():
            extra = ''
            if markcb.get_active():
                extra += ' -m'
            if nojcb.get_active():
                extra += ' -n'
            if lblcb.get_active():
                extra += ' -l'
            if sngcb.get_active():
                extra += ' -s'
            call( 'capture "cylc inline -g ' + extra + ' ' + reg + '" &', shell=True  )
        else:
            if edit_inlined_rb.get_active():
                extra = '-i '
            else:
                extra = ''
            call( 'capture "cylc edit -g ' + extra + ' ' + reg + '" &', shell=True  )
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
        call( 'capture "cylc validate ' + options + name  + '" &', shell=True )

    def launch_controller( self, w, name, state, suite_dir ):
        m = re.match( 'RUNNING \(port (\d+)\)', state )
        port = None
        if m:
            port = m.groups()[0]
        # get suite logging directory
        # logging_dir = os.path.join( config(name)['top level logging directory'], name ) 
        #return False
        call( 'capture "gcylc ' + name  + '" --width=800 --height=400 &', shell=True )

    def check_entries( self, entries ):
        # note this check retrieved entry values
        bad = False
        for entry in entries:
            if entry == '':
                bad = True
        if bad:
            warning_dialog( "Please complete all required text entry panels!" ).warn()
            return False
        else:
            return True

