import gobject
#import pygtk
#pygtk.require('2.0')
import gtk
import time, os, re
import threading
import cycle_time
from config import config, SuiteConfigError
import cylc_pyro_client
from port_scan import scan, SuiteIdentificationError
from registration import localdb, centraldb, regsplit, RegistrationError
from warning_dialog import warning_dialog, info_dialog, question_dialog
from subprocess import call
import helpwindow 
from gcapture import gcapture, gcapture_tmpfile
from mkdir_p import mkdir_p
from cylc_logviewer import cylc_logviewer
from option_group import option_group, controlled_option_group
from color_rotator import rotator

#debug = True
debug = False

# NOTE, WHY WE LAUNCH CONTROL GUIS AS STANDALONE APPS (via gcapture)
# instead of as part of the gcylc app: we can then capture out and err
# streams into suite-specific log files rather than have it all come
# out with the gcylc stdout and stderr streams.

class db_updater(threading.Thread):
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
        super(db_updater, self).__init__()
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
        # (name, port)
        suites = scan( self.host, mine=True, silent=True )
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
                    res = ts.remove(oiter)
                    if not ts.iter_is_valid(oiter):
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
                            res = ts.remove(giter)
                            if not ts.iter_is_valid(giter):
                                giter = None
                        else:
                            # group still exists, check it
                            niter = ts.iter_children(giter)
                            while niter:
                                # get name
                                chch_row = []
                                for col in range( ts.get_n_columns()):
                                    chch_row.append( ts.get_value(niter,col))
                                [name, state, descr, dir, junk, junk, junk ] = chch_row
                                oldtree[owner][group][name] = [state, descr, dir ]
                                #print '    REG', name, state, descr, dir

                                if name not in newtree[owner][group]:
                                    # remove name
                                    #print '    removing reg ', name
                                    res = ts.remove(niter)
                                    if not ts.iter_is_valid(niter):
                                        niter = None
                                elif oldtree[owner][group][name] != newtree[owner][group][name]:
                                    # data changed
                                    # print '    changing reg ', name
                                    state, descr, dir = newtree[owner][group][name]
                                    col1, col2, col3  = self.statecol( state )
                                    foo = ts.prepend( giter, [ name ] + [ state, '<i>' + descr + '</i>', dir, col1, col2, col3  ] )
                                    res = ts.remove(niter)
                                    if not ts.iter_is_valid(niter):
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
                       res = ts.remove(giter)
                       if not ts.iter_is_valid(giter):
                           giter = None
                   else:
                       # group still exists, check it
                       niter = ts.iter_children(giter)
                       while niter:
                           # get name
                           chch_row = []
                           for col in range( ts.get_n_columns()):
                               chch_row.append( ts.get_value(niter,col))
                           [name, state, descr, dir, junk, junk, junk ] = chch_row
                           oldtree[owner][group][name] = [state, descr, dir ]
                           #print '    REG', name, state, descr, dir

                           if name not in newtree[owner][group]:
                               # remove name
                               #print '    removing reg ', name
                               res = ts.remove(niter)
                               if not ts.iter_is_valid(niter):
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
                               foo = ts.prepend( giter, [ name ] + [ state, '<i>' + descr + '</i>', dir, col1, col2, col3  ] )
                               res = ts.remove(niter)
                               if not ts.iter_is_valid(niter):
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
                            niter = ts.append( giter, [name] + [state, '<i>' + descr + '</i>', dir, col1, col2, col3 ])
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
                            niter = ts.append( giter, [name] + [state, '<i>' + descr +'</i>', dir, col1, col2, col3 ])
                        continue

                    # group already in the treemodel, find it
                    giter = self.search_level( ts, ts.iter_children(oiter), self.match_func, (0, group))

                    for name in newtree[owner][group]:
                        if name not in oldtree[owner][group]:
                            # new name, insert it and its data
                            state, descr, dir = newtree[owner][group][name]
                            col1, col2, col3  = self.statecol( state )
                            niter = ts.append( giter, [name] + [ state, '<i>' + descr + '</i>', dir, col1, col2, col3 ])
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
                            niter = ts.append( giter, [name] + [state, '<i>' + descr + '</i>', dir, col1, col2, col3 ])
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
                            niter = ts.append( giter, [name] + [state, '<i>' + descr + '</i>', dir, col1, col2, col3  ])
                        continue

                    # group already in the treemodel, find it
                    giter = self.search_level( ts, ts.get_iter_first(), self.match_func, (0, group))
    
                    for name in newtree[owner][group]:
                        if name not in oldtree[owner][group]:
                            # new name, insert it and its data
                            state, descr, dir = newtree[owner][group][name]
                            col1, col2, col3  = self.statecol( state )
                            niter = ts.append( giter, [name] + [ state, '<i>' + descr + '</i>', dir, col1, col2, col3  ])
                            continue
    
    def statecol( self, state ):
        grnbg = '#19ae0a'
        grnfg = '#030'
        #red = '#ff1a45'
        red = '#845'
        white = '#fff'
        black='#000'
        hilight = '#faf'
        hilight2 = '#f98e3a'
        if state == '-':
            #return (black, None, hilight)
            return (None, None, None)
        else:
            #return (grnfg, grnbg, hilight2 )
            return (grnfg, grnbg, grnbg )

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

class MainApp(object):
    def __init__(self, host, tmpdir, imagedir, readonly=False ):
        self.updater = None
        self.tmpdir = tmpdir
        self.filter_window = None
        self.owner = os.environ['USER']
        self.readonly = readonly
        self.gcapture_windows = []

        gobject.threads_init()

        self.host = host
        self.imagedir = imagedir

        self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        if self.readonly:
            # TO DO: READONLY IS NO LONGER USED?
            self.window.set_title("Registered Suites (LOCAL DATABASE; READONLY)" )
        else:
            self.window.set_title("Registered Suites (LOCAL DATABASE)" )
        self.window.set_size_request(600, 300)
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

        self.reg_new_item = gtk.MenuItem( '_New Suite Registration' )
        self.reg_new_item.connect( 'activate', self.newreg_popup )
        file_menu.append( self.reg_new_item )

        exit_item = gtk.MenuItem( 'E_xit gcylc' )
        exit_item.connect( 'activate', self.delete_all_event, None )
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

        collapse_item = gtk.MenuItem( '_Collapse' )
        view_menu.append( collapse_item )
        collapse_item.connect( 'activate', self.collapse_all, self.regd_treeview )

        refresh_item = gtk.MenuItem( '_Refresh' )
        view_menu.append( refresh_item )
        refresh_item.connect( 'activate', self.refresh )

        db_menu = gtk.Menu()
        db_menu_root = gtk.MenuItem( '_Database' )
        db_menu_root.set_submenu( db_menu )

        self.dblocal_item = gtk.MenuItem( '_LocalDB' )
        db_menu.append( self.dblocal_item )
        self.dblocal_item.set_sensitive(False) # (already on local at startup)

        self.dbcentral_item = gtk.MenuItem( '_CentralDB' )
        db_menu.append( self.dbcentral_item )
        self.dbcentral_item.set_sensitive(True) # (on local at startup)

        self.dblocal_item.connect( 'activate', self.localdb )
        self.dbcentral_item.connect( 'activate', self.centraldb )

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
        self.menu_bar.append( db_menu_root )
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
        #cr.set_property( 'cell-background', '#def' )
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
        #cr.set_property( 'cell-background', '#def' )
        tvc = gtk.TreeViewColumn( 'Title', cr, markup=2, foreground=4, background=6 )
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

        eb = gtk.EventBox()
        eb.add( gtk.Label( "right-click on suites or groups for options" ) )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#8be' ) ) 
        vbox.pack_start( eb, False )

        self.window.add(vbox)
        self.window.show_all()

        self.log_colors = rotator()

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
        self.updater = db_updater( self.owner, self.regd_treestore, 
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
        command = "cylc register " + reg + ' ' + dir
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
        w.destroy()

    def refresh( self, w ):
        if self.cdb:
            options = '-c'
        else:
            options = ''
        command = "cylc refresh " + options
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()

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

    def localdb( self, w ):
        if not self.cdb:
            return
        self.window.set_title("Registered Suites (LOCAL DATABASE)" )
        w.set_sensitive(False)
        self.dbcentral_item.set_sensitive(True)
        self.cdb = False
        if self.filter_window:
            self.filter_window.destroy()
        # setting base color to None should return it to the default
        self.regd_treeview.modify_base( gtk.STATE_NORMAL, None)
        self.reg_new_item.set_sensitive( True )
        self.start_updater()

    def centraldb( self, w ):
        if self.cdb:
            return
        self.window.set_title("Registered Suites (CENTRAL DATABASE)" )
        w.set_sensitive(False)
        self.dblocal_item.set_sensitive(True)
        self.cdb = True
        if self.filter_window:
            self.filter_window.destroy()
        # note treeview.modify_base() doesn't seem to have same effect
        # on all platforms. It either colours the full background or
        # just inside (behind the treeeview?) the expander triangles.
        self.regd_treeview.modify_base( gtk.STATE_NORMAL, gtk.gdk.color_parse( "#bdf" ))
        self.reg_new_item.set_sensitive( False )
        self.start_updater()

    def delete_all_event( self, w, e ):
        self.updater.quit = True
        # call quit on any remaining gcapture windows, which contain
        # tailer threads that need to be stopped). Currently we maintain
        # a list of all gcapture windows opened
        # since gcylc started up, hence the use of 'quit_already' to
        # avoid calling window.destroy() on gcapture windows that have
        # already been destroyed by the user closing them (although
        # a second call to destroy() may be safe anyway?)...
        for gwindow in self.gcapture_windows:
            if not gwindow.quit_already:
                gwindow.quit( None, None )

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
                con_item = gtk.MenuItem( '_Control (traditional)')
                menu.append( con_item )
                con_item.connect( 'activate', self.launch_controller, reg, state )

                cong_item = gtk.MenuItem( '_Control (graph based)')
                menu.append( cong_item )
                cong_item.connect( 'activate', self.launch_controller, reg, state, True )

                subm_item = gtk.MenuItem( '_Submit (single task)')
                menu.append( subm_item )
                subm_item.connect( 'activate', self.submit_task_popup, reg )

                out_item = gtk.MenuItem( 'View _Output')
                menu.append( out_item )
                out_item.connect( 'activate', self.view_output, reg, state )

                out_item = gtk.MenuItem( 'View _Log')
                menu.append( out_item )
                out_item.connect( 'activate', self.view_log, reg )

                if state != '-':
                    # suite is running
                    dump_item = gtk.MenuItem( 'D_ump' )
                    menu.append( dump_item )
                    dump_item.connect( 'activate', self.dump_suite, reg )

                    stop_item = gtk.MenuItem( 'Sto_p' )
                    menu.append( stop_item )
                    stop_item.connect( 'activate', self.stopsuite_popup, reg )
     
                menu.append( gtk.SeparatorMenuItem() )

            search_item = gtk.MenuItem( '_Describe' )
            menu.append( search_item )
            search_item.connect( 'activate', self.describe_suite, reg )

            search_item = gtk.MenuItem( '_List Tasks' )
            menu.append( search_item )
            search_item.connect( 'activate', self.list_suite, reg )

            menu.append( gtk.SeparatorMenuItem() )
    
            edit_item = gtk.MenuItem( '_Edit' )
            menu.append( edit_item )
            edit_item.connect( 'activate', self.edit_suite_popup, reg )
    
            graph_item = gtk.MenuItem( '_Graph' )
            menu.append( graph_item )
            graph_item.connect( 'activate', self.graph_suite_popup, reg, suite_dir )

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
            del_item.connect( 'activate', self.unregister_suite_popup, reg, suite_dir )
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

        oblit_cb = gtk.CheckButton( "_Delete suite definition directories" )
        oblit_cb.set_active(False)

        ok_button = gtk.Button( "_Unregister" )
        ok_button.connect("clicked", self.unregister_group, window, owner, group, oblit_cb )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.unregister )

        label = gtk.Label( "Unregister the entire " + group + " group?" )
        vbox.pack_start( label )
        vbox.pack_start( oblit_cb )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def unregister_group( self, b, w, owner, group, oblit_cb ):
        if self.cdb:
            group = owner + ':' + group
        options = ''
        if oblit_cb.get_active():
            res = question_dialog( "!DANGER! !DANGER! !DANGER! !DANGER! !DANGER! !DANGER!\n"
                    "?Do you REALLY want to delete ALL suite definition directories in group '" + group + "'?").ask()
            if res == gtk.RESPONSE_YES:
                options = '--obliterate '
            else:
                return False
        command = "cylc unregister --gcylc " + options + group + ":"
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
        w.destroy()

    def unregister_suite_popup( self, w, reg, dir ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Unregister '" + reg + "'")

        vbox = gtk.VBox()

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        oblit_cb = gtk.CheckButton( "_Delete suite definition directory" )
        oblit_cb.set_active(False)

        ok_button = gtk.Button( "_Unregister" )
        ok_button.connect("clicked", self.unregister_suite, window, reg, dir, oblit_cb )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.unregister )

        label = gtk.Label( "Unregister suite " + reg + "?" )
        vbox.pack_start( label )
        vbox.pack_start( oblit_cb )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def unregister_suite( self, b, w, reg, dir, oblit_cb ):
        options = ''
        if oblit_cb.get_active():
            res = question_dialog( "!DANGER! !DANGER! !DANGER! !DANGER! !DANGER! !DANGER!\n"
                    "?Do you REALLY want to delete " + dir + '?').ask()
            if res == gtk.RESPONSE_YES:
                options = '--obliterate '
            else:
                return False
 
        command = "cylc unregister --gcylc " + options + reg
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
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
        command = "cylc import " + fowner + ':' + fgroup + ': ' + group + ': ' + dir
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
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
        command = "cylc import " + reg + ' ' + group + ':' + name + ' ' + dir
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
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

        copy_cb = gtk.CheckButton( "Copy the suite definition directory" )
        copy_cb.set_active(False)
        vbox.pack_start(copy_cb)

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Export" )
        ok_button.connect("clicked", self.export_suite, window, reg, group_entry, name_entry, copy_cb )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.export )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def export_suite( self, b, w, reg, group_entry, name_entry, copy_cb ):
        group = group_entry.get_text()
        name  = name_entry.get_text()
        if not self.check_entries( [group, name] ):
            return False
        options = ''
        if copy_cb.get_active():
            options = '--copy '
        command = "cylc export " + options + reg + ' ' + group + ':' + name
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
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
        command = "cylc reregister " + reg + ' ' + tto
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
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
        command = "cylc reregister " + g_from + ': ' + g_to + ":"
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
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

        copy_cb = gtk.CheckButton( "Copy the suite definition directories" )
        copy_cb.set_active(False)
        vbox.pack_start(copy_cb)

        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Export" )
        ok_button.connect("clicked", self.export_group, window, group, group_entry, copy_cb )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.export )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def export_group( self, b, w, lgroup, group_entry, copy_cb ):
        group = group_entry.get_text()
        if not self.check_entries( [group] ):
            return False
        options = ''
        if copy_cb.get_active():
            options = '--copy '
        command = "cylc export " + options + lgroup + ': ' + group + ":"
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
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
        command = "cylc copy " + g_from + ' ' + g_to + ' ' + dir
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
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
        command = "cylc copy " + reg + ' ' + group + ':' + name + ' ' + dir
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
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

    def graph_suite_popup( self, w, reg, suite_dir ):
        try:
            from graphing import xdot
        except Exception, x:
            warning_dialog( str(x) + "\nGraphing disabled.").warn()
            return False

        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Dependency Graph '" + reg + "'")

        box = gtk.HBox()
        
        suiterc_rb = gtk.RadioButton( None, "suite.rc" )
        box.pack_start (suiterc_rb, True)
        runtime_rb = gtk.RadioButton( suiterc_rb, "runtime" )
        box.pack_start (runtime_rb, True)
        suiterc_rb.set_active(True)
 
        vbox = gtk.VBox()
        vbox.pack_start(box, True)

        label = gtk.Label("Optional Output File" )
        outputfile_entry = gtk.Entry()
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(outputfile_entry, True) 
        vbox.pack_start( hbox )
 
        warm_cb = gtk.CheckButton( "Warm Start" )
        vbox.pack_start (warm_cb, True)

        label = gtk.Label("Start Cycle Time" )
        start_entry = gtk.Entry()
        start_entry.set_max_length(10)
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(start_entry, True) 
        vbox.pack_start(hbox)

        label = gtk.Label("Stop Cycle Time" )
        stop_entry = gtk.Entry()
        stop_entry.set_max_length(10)
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(stop_entry, True) 
        vbox.pack_start (hbox, True)
  
        suiterc_rb.connect( "toggled", self.graph_type, "suiterc", 
                warm_cb, start_entry, stop_entry )
        runtime_rb.connect( "toggled", self.graph_type, "runtime", 
                warm_cb, start_entry, stop_entry )
 
        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )
        ok_button = gtk.Button( "_Graph" )
        ok_button.connect("clicked", self.graph_suite, reg, suite_dir,
                suiterc_rb, runtime_rb, 
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

    def graph_type( self, w, typ, warm_cb, start_ent, stop_ent ):
        if typ == "suiterc" and w.get_active():
            sensitive = True
        else:
            sensitive = False
        warm_cb.set_sensitive(sensitive)
        start_ent.set_sensitive(sensitive)
        stop_ent.set_sensitive(sensitive)

    def search_suite( self, w, reg, nobin_cb, pattern_entry ):
        pattern = pattern_entry.get_text()
        options = ''
        if nobin_cb.get_active():
            options += ' -x '
        command = "cylc search " + options + ' ' + pattern + ' ' + reg 
        foo = gcapture_tmpfile( command, self.tmpdir, height=500 )
        self.gcapture_windows.append(foo)
        foo.run()

    def graph_suite( self, w, reg, suite_dir, suiterc_rb, runtime_rb, 
            warm_cb, outputfile_entry, start_entry, stop_entry ):

        options = ''
        ofile = outputfile_entry.get_text()
        if ofile != '':
            options += ' -o ' + ofile

        if suiterc_rb.get_active():
            start = start_entry.get_text()
            stop = stop_entry.get_text()
            for ct in start, stop:
                if not cycle_time.is_valid( ct ):
                    warning_dialog( "Invalid cycle time (YYYYMMDDHH) " + ct ).warn()
                    return False
            if warm_cb.get_active():
                options += ' -w '
            options += ' ' + reg + ' ' + start + ' ' + stop

        elif runtime_rb.get_active():
            options += ' -r ' + reg

        command = "cylc graph " + options
        foo = gcapture_tmpfile( command, self.tmpdir )
        self.gcapture_windows.append(foo)
        foo.run()

    def graph_suite_runtime( self, w, reg, outputfile_entry ):
        options = ''
        ofile = outputfile_entry.get_text()
        if ofile != '':
            options += ' -o ' + ofile
        command = "cylc graph -r " + options + ' ' + reg
        foo = gcapture_tmpfile( command, self.tmpdir )
        self.gcapture_windows.append(foo)
        foo.run()

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

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )
        ok_button = gtk.Button( "_Edit" )
        ok_button.connect("clicked", self.edit_suite, window, reg, edit_rb,
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

    def edit_suite( self, w, window, reg, edit_rb, edit_inlined_rb,
            view_inlined_rb, markcb, lblcb, nojcb, sngcb ):
        window.destroy()
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
            command = "cylc inline -g " + extra + ' ' + reg
            foo = gcapture_tmpfile( command, self.tmpdir )
            self.gcapture_windows.append(foo)
            foo.run()
        else:
            if edit_inlined_rb.get_active():
                extra = '-i '
            else:
                extra = ''
            command = "cylc edit -g " + extra + ' ' + reg
            foo = gcapture_tmpfile( command, self.tmpdir )
            self.gcapture_windows.append(foo)
            foo.run()
        return False

    def validate_suite( self, w, name ):
        command = "cylc validate " + name 
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()

    def dump_suite( self, w, name ):
        command = "cylc dump " + name
        foo = gcapture_tmpfile( command, self.tmpdir, 400, 400 )
        self.gcapture_windows.append(foo)
        foo.run()

    def stop_method( self, b, meth, stoptime_entry ):
        if meth == 'stop' or meth == 'stopnow':
            stoptime_entry.set_sensitive( False )
        else:
            stoptime_entry.set_sensitive( True )

    def stopsuite_popup( self, b, suite ):
        window = gtk.Window()
        window.modify_bg( gtk.STATE_NORMAL, 
                gtk.gdk.color_parse( self.log_colors.get_color()))
        window.set_border_width(5)
        window.set_title( "Stop Suite '" + suite + "'")

        vbox = gtk.VBox()

        box = gtk.HBox()
        stop_rb = gtk.RadioButton( None, "Stop" )
        box.pack_start (stop_rb, True)
        stopat_rb = gtk.RadioButton( stop_rb, "Stop At" )
        box.pack_start (stopat_rb, True)
        stopnow_rb = gtk.RadioButton( stop_rb, "Stop NOW" )
        box.pack_start (stopnow_rb, True)
        stop_rb.set_active(True)
        vbox.pack_start( box )

        box = gtk.HBox()
        label = gtk.Label( 'Stop At (YYYYMMDDHH)' )
        box.pack_start( label, True )
        stoptime_entry = gtk.Entry()
        stoptime_entry.set_max_length(10)
        stoptime_entry.set_sensitive(False)
        box.pack_start (stoptime_entry, True)
        vbox.pack_start( box )

        stop_rb.connect( "toggled", self.stop_method, "stop", stoptime_entry )
        stopat_rb.connect( "toggled", self.stop_method, "stopat", stoptime_entry )
        stopnow_rb.connect(   "toggled", self.stop_method, "stopnow", stoptime_entry )

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        stop_button = gtk.Button( "_Stop" )
        stop_button.connect("clicked", self.stopsuite, 
                window, suite, stop_rb, stopat_rb, stopnow_rb,
                stoptime_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.stop_guide )

        hbox = gtk.HBox()
        hbox.pack_start( stop_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def stopsuite( self, bt, window, suite, stop_rb, stopat_rb, stopnow_rb, stoptime_entry ):
        stop = False
        stopat = False
        stopnow = False
        if stop_rb.get_active():
            stop = True
        elif stopat_rb.get_active():
            stopat = True
            stoptime = stoptime_entry.get_text()
            if stoptime == '':
                warning_dialog( "No stop time entered" ).warn()
                return
            if not cycle_time.is_valid( stoptime ):
                warning_dialog( "Invalid stop time: " + stoptime ).warn()
                return
        elif stopnow_rb.get_active():
            stopnow = True

        window.destroy()

        try:
            god = cylc_pyro_client.client( suite ).get_proxy( 'remote' )
            if stop:
                result = god.shutdown()
            elif stopat:
                result = god.set_stop_time( stoptime )
            elif stopnow:
                result = god.shutdown_now()
        except SuiteIdentificationError, x:
            warning_dialog( x.__str__() ).warn()
        else:
            if result.success:
                info_dialog( result.reason ).inform()
            else:
                warning_dialog( result.reason ).warn()

    def submit_task_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Submit Task from Suite '" + reg + "'")

        vbox = gtk.VBox()

        dryrun_cb = gtk.CheckButton( "Dry Run (just generate the job script)" )
        vbox.pack_start (dryrun_cb, True)

        label = gtk.Label("Task ID (NAME%YYYYMMDDHH)" )
        task_entry = gtk.Entry()
        hbox = gtk.HBox()
        hbox.pack_start( label, True )
        hbox.pack_start(task_entry, True) 
        vbox.pack_start( hbox )
 
        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Submit" )
        ok_button.connect("clicked", self.submit_task, reg, dryrun_cb, task_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", helpwindow.submit )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def submit_task( self, w, reg, dryrun_cb, task_entry ):
        options = ''
        if dryrun_cb.get_active():
            options = '--dry-run'
        command = "cylc submit " + options + " " + reg + " " + task_entry.get_text()
        foo = gcapture_tmpfile( command, self.tmpdir, 500, 400 )
        self.gcapture_windows.append(foo)
        foo.run()

    def describe_suite( self, w, name ):
        command = "cylc describe " + name  
        foo = gcapture_tmpfile( command, self.tmpdir, 500, 400 )
        self.gcapture_windows.append(foo)
        foo.run()

    def list_suite( self, w, name ):
        command = "cylc list " + name
        foo = gcapture_tmpfile( command, self.tmpdir, 300, 400 )
        self.gcapture_windows.append(foo)
        foo.run()

    def launch_controller( self, w, name, state, depgraph=False ):
        running_already = False
        if state != '-':
            # suite running
            running_already = True
            # was it started by gcylc?
            try:
                ssproxy = cylc_pyro_client.client( name ).get_proxy( 'state_summary' )
            except SuiteIdentificationError, x:
                warning_dialog( str(x) ).warn()
                return False
            [ glbl, states] = ssproxy.get_state_summary()
            if glbl['started by gcylc']:
                started_by_gcylc = True
                #info_dialog( "This suite is running already. It was started by "
                #    "gcylc, which redirects suite stdout and stderr to special files "
                #    "so we can connect a new output capture window to those files.").inform()
            else:
                started_by_gcylc = False
                info_dialog( "This suite is running but it was started from "
                    "the commandline, so gcylc does not have access its stdout "
                    "and stderr streams.").inform()

        if running_already and started_by_gcylc or not running_already:
            # Use suite-specific special stdout and stderr files.

            # TO DO: MAKE PREFIX THIS PART OF USER GLOBAL PREFS?
            # a hard-wired prefix makes it possible for us to 
            # reconnect to the output of a running suite. Some
            # non-fatal textbuffer insertion warnings may occur if several
            # control guis are open at once both trying to write to it.
            prefix = os.path.join( '$HOME', '.cylc', name )

            # environment variables allowed
            prefix = os.path.expandvars( prefix )
            # make parent directory if necessary
            pdir = os.path.dirname( prefix )
            try:
                mkdir_p( pdir )
            except Exception, x:
                warning_dialog( str(x) ).warn()
                return False

            stdoutf = prefix + '.out'

            if not running_already:
                # ask whether or not to delete existing output
                stdout_exists = False
                if os.path.exists( stdoutf ):
                    stdout_exists = True
                if stdout_exists:
                    response = question_dialog( 
                        "Delete old output (stdout and stderr) for this suite?\n\n"
                        "Output capture files exist from previous runs "
                        "launched via gcylc; click Yes to delete them and start anew "
                        "(Otherwise new output will be appended to the existing files)." ).ask()
                    if response == gtk.RESPONSE_YES:
                        try:
                            if stdout_exists:
                                os.unlink( stdoutf )
                        except OSError, x:
                            warning_dialog( str(x) ).warn()
                            return False
            try:
                # open in append mode 'ab' (write mode 'wb' nukes the files
                # with  each new open, which isn't good when multiple
                # controllers are opened).
                stdout = open( stdoutf, 'ab' )
            except IOError,x:
                warning_dialog( str(x) ).warn()
                return False

            if depgraph:
                command = "gcylc --graph " + name
            else:
                command = "gcylc " + name
            foo = gcapture( command, stdout, 800, 400 )
            self.gcapture_windows.append(foo)
            foo.run()

        else:
            # connecting a controller to a running suite started by commandline
            # so no point in connecting to the special stdout and stderr files.
            # User was informed of this already by a dialog above.
            command = "gcylc " + name
            foo = gcapture_tmpfile( command, self.tmpdir, 400 )
            self.gcapture_windows.append(foo)
            foo.run()

    def close_log_window( self, w, e, window, clv ):
        window.destroy()
        clv.quit()

    def view_log( self, w, suite ):
        try:
            suiterc = config( suite )
        except SuiteConfigError, x:
            warning_dialog( str(x) + \
                    '\n\nThe suite.rc file must be parsed\n'
                    ' to determine the suite log path.' ).warn()
            return
        logdir = os.path.join( suiterc['top level logging directory'], suite )
        cylc_logviewer( 'log', logdir, suiterc.get_task_name_list() )

    def view_output( self, w, name, state ):
        running_already = False
        if state != '-':
            # suite running
            running_already = True
            # was it started by gcylc?
            try:
                ssproxy = cylc_pyro_client.client( name ).get_proxy( 'state_summary' )
            except SuiteIdentificationError, x:
                warning_dialog( str(x) ).warn()
                return False
            [ glbl, states] = ssproxy.get_state_summary()
            if glbl['started by gcylc']:
                started_by_gcylc = True
                # suite is running already, started by gcylc, which
                # redirects output to a special file that we can
                # reconnect to.
            else:
                started_by_gcylc = False
                info_dialog( "This suite is running, but it was started from "
                    "the commandline, so gcylc does not have access its output "
                    "file.").inform()
                return False
        else:
            # suite not running
            info_dialog( "This suite is not running, so "
                    "the output capture window will show output (stdout and "
                    "stderr) from the previous time(s) that the suite was started "
                    "from via the gcylc app (gcylc cannot access stdout "
                    "and stderr for suites launched from the commandline).").inform()

        # TO DO: MAKE PREFIX THIS PART OF USER GLOBAL PREFS?
        # a hard-wired prefix makes it possible for us to 
        # reconnect to the output of a running suite. Some
        # non-fatal textbuffer insertion warnings may occur if several
        # control guis are open at once both trying to write to it.
        prefix = os.path.join( '$HOME', '.cylc', name )

        # environment variables allowed
        prefix = os.path.expandvars( prefix )

        try:
            # open existing out and err files
            stdout = open( prefix + '.out', 'rb' )
        except IOError,x:
            msg = '''This probably means the suite has not yet been started via gcylc
(if you start a suite on the commandline stdout and stderr redirection is up to you).'''
            warning_dialog( str(x) + '\n' + msg ).warn()
            return False

        foo = gcapture( None, stdout, width=800, height=400, ignore_command=True )
        self.gcapture_windows.append(foo)
        foo.run()

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

