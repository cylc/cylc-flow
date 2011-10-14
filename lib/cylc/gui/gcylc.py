#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC FORECAST SUITE METASCHEDULER.
#C: Copyright (C) 2008-2011 Hilary Oliver, NIWA
#C:
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gobject
#import pygtk
#pygtk.require('2.0')
import gtk
import subprocess
import time, os, re
import threading
from cylc.cycle_time import ct, CycleTimeError
from cylc.config import config, SuiteConfigError
from cylc import cylc_pyro_client
from cylc.port_scan import scan, SuiteIdentificationError
from cylc.registration import delimiter, dbgetter, localdb, centraldb, RegistrationError
from warning_dialog import warning_dialog, info_dialog, question_dialog
import helpwindow
from gcapture import gcapture, gcapture_tmpfile
from cylc.mkdir_p import mkdir_p
from cylc_logviewer import cylc_logviewer

debug = False

# WHY LAUNCH CONTROL GUIS AS STANDALONE APPS (via gcapture) rather than
# as part of the main gcylc app: we can then capture out and err
# streams into suite-specific log files rather than have it all come
# out with the gcylc stdout and stderr streams.

class db_updater(threading.Thread):
    count = 0
    def __init__(self, owner, regd_treestore, db, is_cdb, host, filtr=None ):
        self.__class__.count += 1
        self.me = self.__class__.count
        self.filtr = filtr
        self.db = db
        self.is_cdb = is_cdb
        self.owner = owner
        self.quit = False
        self.host = host
        self.reload = False
        self.regd_treestore = regd_treestore
        super(db_updater, self).__init__()
        self.running_choices = []

        self.newtree = {}

        self.db.load_from_file()
        self.regd_choices = []
        self.regd_choices = self.db.get_list(filtr)

        # not needed:
        # self.build_treestore( self.newtree )
        self.construct_newtree()
        self.update()

    def construct_newtree( self ):
        # construct self.newtree[one][two]...[nnn] = [state, descr, dir ]
        self.running_choices_changed()
        ports = {}
        for suite in self.running_choices:
            reg, port = suite
            ports[ reg ] = port

        self.newtree = {}
        for reg in self.regd_choices:
            suite, suite_dir, descr = reg
            suite_dir = re.sub( '^' + os.environ['HOME'], '~', suite_dir )
            if suite in ports:
                state = str(ports[suite])
            else:
                state = '-'
            nest2 = self.newtree
            regpath = suite.split(delimiter)
            for key in regpath[:-1]:
                if key not in nest2:
                    nest2[key] = {}
                nest2 = nest2[key]
            nest2[regpath[-1]] = [ state, descr, suite_dir ]

    def build_treestore( self, data, piter=None ):
        items = data.keys()
        items.sort()
        for item in items:
            value = data[item]
            if isinstance( value, dict ):
                # final three items are colours
                iter = self.regd_treestore.append(piter, [item, None, None, None, None, None, None ] )
                self.build_treestore(value, iter)
            else:
                state, descr, dir = value
                iter = self.regd_treestore.append(piter, [item, state, descr, dir, None, None, None ] )

    def update( self ):
        #print "Updating list of available suites"
        self.construct_newtree()
        if self.reload:
            self.regd_treestore.clear()
            self.build_treestore( self.newtree )
            self.reload = False
        else:
            self.update_treestore( self.newtree, self.regd_treestore.get_iter_first() )

    def update_treestore( self, new, iter ):
        # iter is None for an empty treestore (no suites registered)
        ts = self.regd_treestore
        if iter:
            opath = ts.get_path(iter)
            # get parent iter before pruning in case we prune last item at this level
            piter = ts.iter_parent(iter)
        else:
            opath = None
            piter = None

        def my_get_iter( item ):
            # find the TreeIter pointing at item at this level
            if not opath:
                return None
            iter = ts.get_iter(opath)
            while iter:
                val, = ts.get( iter, 0 ) 
                if val == item:
                    return iter
                iter = ts.iter_next( iter )
            return None

        # new items at this level
        new_items = new.keys()
        old_items = []
        prune = []

        while iter:
            # iterate through old items at this level
            item, state, descr, dir = ts.get( iter, 0,1,2,3 )
            if item not in new_items:
                # old item is not in new - prune it
                res = ts.remove( iter )
                if not res: # Nec?
                    iter = None
            else:
                # old item is in new - update it in case it changed
                old_items.append(item)
                # update old items that do appear in new
                chiter = ts.iter_children(iter)
                if not isinstance( new[item], dict ):
                    # new item is not a group - update title etc.
                    state, descr, dir = new[item]
                    sc = self.statecol(state)
                    ni = new[item]
                    ts.set( iter, 0, item, 1, ni[0], 2, ni[1], 3, ni[2], 4, sc[0], 5, sc[1], 6, sc[2] )
                    if chiter:
                        # old item was a group - kill its children
                        while chiter:
                            res = ts.remove( chiter )
                            if not res:
                                chiter = None
                else:
                    # new item is a group
                    if not chiter:
                        # old item was not a group
                        ts.set( iter, 0, item, 1, None, 2, None, 3, None, 4, None, 5, None, 6, None )
                        self.build_treestore( new[item], iter )

                # continue
                iter = ts.iter_next( iter )

        # return to original iter
        if opath:
            try:
                iter = ts.get_iter(opath)
            except ValueError:
                # removed the item pointed to
                # TO DO: NEED TO WORRY ABOUT OTHERS AT THIS LEVEL?
                iter = None
        else:
            iter = None

        # add new items at this level
        for item in new_items:
            if item not in old_items:
                # new data wasn't in old - add it
                if isinstance( new[item], dict ):
                    xiter = ts.append(piter, [item] + [None, None, None, None, None, None] )
                    self.build_treestore( new[item], xiter )
                else:
                    state, descr, dir = new[item]
                    yiter = ts.append(piter, [item] + new[item] + list( self.statecol(state)))
            else:
                # new data was already in old
                if isinstance( new[item], dict ):
                    # check lower levels
                    niter = my_get_iter( item )
                    if niter:
                        chiter = ts.iter_children(niter)
                        if chiter:
                            self.update_treestore( new[item], chiter )

    def run( self ):
        global debug
        if debug:
            print '* thread', self.me, 'starting'
        while not self.quit:
            if self.running_choices_changed() or self.regd_choices_changed() or self.reload:
                gobject.idle_add( self.update )
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
        regs = self.db.get_list(self.filtr)
        if regs != self.regd_choices:
            self.regd_choices = regs
            return True
        else:
            return False

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
            self.window.set_title("Registered Suites (PRIVATE DATABASE; READONLY)" )
        else:
            self.window.set_title("Registered Suites (PRIVATE DATABASE)" )
        self.window.set_size_request(600, 300)
        #self.window.set_border_width( 5 )
        self.window.connect("delete_event", self.delete_all_event)

        sw = gtk.ScrolledWindow()
        sw.set_policy( gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC )

        self.regd_treeview = gtk.TreeView()
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

        self.reg_new_item = gtk.MenuItem( '_Register Existing Suite' )
        self.reg_new_item.connect( 'activate', self.newreg_popup )
        file_menu.append( self.reg_new_item )

        self.reg_new_item2 = gtk.MenuItem( '_Register A New Suite' )
        self.reg_new_item2.connect( 'activate', self.newreg2_popup )
        file_menu.append( self.reg_new_item2 )

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

        refresh_item = gtk.MenuItem( '_Refresh Titles' )
        view_menu.append( refresh_item )
        refresh_item.connect( 'activate', self.refresh )

        reload_item = gtk.MenuItem( '_Reload' )
        view_menu.append( reload_item )
        reload_item.connect( 'activate', self.reload )

        db_menu = gtk.Menu()
        db_menu_root = gtk.MenuItem( '_Database' )
        db_menu_root.set_submenu( db_menu )

        self.dblocal_item = gtk.MenuItem( '_Private' )
        db_menu.append( self.dblocal_item )
        self.dblocal_item.set_sensitive(False) # (already on local at startup)

        self.dbcentral_item = gtk.MenuItem( '_Central' )
        db_menu.append( self.dbcentral_item )
        self.dbcentral_item.set_sensitive(True) # (on local at startup)

        self.dblocal_item.connect( 'activate', self.localdb )
        self.dbcentral_item.connect( 'activate', self.centraldb )

        help_menu = gtk.Menu()
        help_menu_root = gtk.MenuItem( '_Help' )
        help_menu_root.set_submenu( help_menu )

        guide_item = gtk.MenuItem( '_GUI Quick Guide' )
        help_menu.append( guide_item )
        guide_item.connect( 'activate', helpwindow.main )

        chelp_menu = gtk.MenuItem( 'All Commands' )
        help_menu.append( chelp_menu )
        self.construct_command_menu( chelp_menu )

        cug_pdf_item = gtk.MenuItem( 'Cylc User Guide (_PDF)' )
        help_menu.append( cug_pdf_item )
        cug_pdf_item.connect( 'activate', self.launch_cug, True )
  
        cug_html_item = gtk.MenuItem( 'Cylc User Guide (_HTML)' )
        help_menu.append( cug_html_item )
        cug_html_item.connect( 'activate', self.launch_cug, False )

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
        self.dbopt = ''
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
        tvc = gtk.TreeViewColumn( 'Port', cr, text=1, foreground=4, background=5 )
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

    def construct_command_menu( self, menu ):
        cat_menu = gtk.Menu()
        menu.set_submenu( cat_menu )

        cylc_help_item = gtk.MenuItem( 'cylc' )
        cat_menu.append( cylc_help_item )
        cylc_help_item.connect( 'activate', self.command_help )

        cout = subprocess.Popen( ["cylc", "categories"], stdout=subprocess.PIPE ).communicate()[0]
        categories = cout.rstrip().split()
        for category in categories: 
            foo_item = gtk.MenuItem( category )
            cat_menu.append( foo_item )
            com_menu = gtk.Menu()
            foo_item.set_submenu( com_menu )
            cout = subprocess.Popen( ["cylc", "category="+category ], stdout=subprocess.PIPE ).communicate()[0]
            commands = cout.rstrip().split()
            for command in commands:
                bar_item = gtk.MenuItem( command )
                com_menu.append( bar_item )
                bar_item.connect( 'activate', self.command_help, category, command )

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
        #about.set_website( "http://www.niwa.co.nz" )
        about.set_logo( gtk.gdk.pixbuf_new_from_file( self.imagedir + "/logo.png" ))
        about.run()
        about.destroy()

    def command_help( self, w, cat='', com='' ):
        command = "cylc " + cat + " " + com + " help"
        foo = gcapture_tmpfile( command, self.tmpdir, 700, 600 )
        self.gcapture_windows.append(foo)
        foo.run()

    def expand_all( self, w, view ):
        view.expand_all()

    def collapse_all( self, w, view ):
        view.collapse_all()

    def start_updater(self, filtr=None ):
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
        self.updater = db_updater( self.owner, self.regd_treestore, db, self.cdb, self.host, filtr )
        self.updater.start()

    def newreg_popup( self, w ):
        dialog = gtk.FileChooserDialog(title='Register Existing Suite (choose a suite.rc file)',
                action=gtk.FILE_CHOOSER_ACTION_OPEN,
                buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OPEN,gtk.RESPONSE_OK))
        filtr = gtk.FileFilter()
        filtr.set_name("cylc suite.rc files")
        filtr.add_pattern("suite\.rc")
        dialog.add_filter( filtr )

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

        label = gtk.Label( 'PATH: ' + dir )
        vbox.pack_start( label, True )

        box = gtk.HBox()
        label = gtk.Label( 'SUITE:' )
        box.pack_start( label, True )
        as_entry = gtk.Entry()
        box.pack_start (as_entry, True)
        vbox.pack_start( box )

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        apply_button = gtk.Button( "_Register" )
        apply_button.connect("clicked", self.new_reg, window, dir, as_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, 'db', 'register' )

        hbox = gtk.HBox()
        hbox.pack_start( apply_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def newreg2_popup( self, w ):
        dialog = gtk.FileChooserDialog(title='Register New Suite (choose or create suite definition directory)',
                action=gtk.FILE_CHOOSER_ACTION_SELECT_FOLDER,
                buttons=(gtk.STOCK_CANCEL,gtk.RESPONSE_CANCEL,
                    gtk.STOCK_OPEN,gtk.RESPONSE_OK))

        response = dialog.run()
        if response != gtk.RESPONSE_OK:
            dialog.destroy()
            return False

        res = dialog.get_filename()
        dialog.destroy()

        if os.path.isdir( res ):
            suiterc = os.path.join( res, 'suite.rc' )
        else:
            warning_dialog( res + " is not a directory" ).warn()
            return False
            
        if not os.path.isfile( suiterc ):
            info_dialog( "creating empty suite.rc file: " + suiterc ).inform()
            os.system( 'touch ' + suiterc )

        dir = os.path.dirname( suiterc )

        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "New Suite" )

        vbox = gtk.VBox()

        label = gtk.Label( 'PATH: ' + dir )
        vbox.pack_start( label, True )

        box = gtk.HBox()
        label = gtk.Label( 'SUITE:' )
        box.pack_start( label, True )
        as_entry = gtk.Entry()
        box.pack_start (as_entry, True)
        vbox.pack_start( box )

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        apply_button = gtk.Button( "_Register" )
        apply_button.connect("clicked", self.new_reg, window, dir, as_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, 'db', 'register' )

        hbox = gtk.HBox()
        hbox.pack_start( apply_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def new_reg( self, b, w, dir, reg_e ):
        reg = reg_e.get_text()
        command = "cylc register --notify-completion " + reg + ' ' + dir
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
        w.destroy()

    def reload( self, w ):
        # tell updated to reconstruct the treeview from scratch
        self.updater.reload = True

    def refresh( self, w ):
        command = "cylc refresh " + self.dbopt + " --notify-completion"
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()

    def filter(self, w, filtr_e ):
        filtr = filtr_e.get_text()
        try:
            re.compile( filtr )
        except:
            warning_dialog( "Bad Expression: " + filt ).warn()
            self.filtr_reset( w, filtr_e )
            return
        self.start_updater( filtr )

    def filter_reset(self, w, filtr_e ):
        filtr_e.set_text('')
        self.start_updater()

    def filter_popup(self, w):
        self.filter_window = gtk.Window()
        self.filter_window.set_border_width(5)
        self.filter_window.set_title( "FILTER" )
        vbox = gtk.VBox()

        box = gtk.HBox()
        label = gtk.Label( 'Filter' )
        box.pack_start( label, True )
        filter_entry = gtk.Entry()
        box.pack_start (filter_entry, True)
        vbox.pack_start( box )

        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: self.filter_window.destroy() )

        apply_button = gtk.Button( "_Apply" )
        apply_button.connect("clicked", self.filter, filter_entry )

        reset_button = gtk.Button( "_Reset" )
        reset_button.connect("clicked", self.filter_reset, filter_entry )

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
        self.window.set_title("Registered Suites (PRIVATE DATABASE)" )
        w.set_sensitive(False)
        self.dbcentral_item.set_sensitive(True)
        self.cdb = False
        self.dbopt = ''
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
        self.dbopt = '--central'
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

        item, state, descr, suite_dir = model.get( iter, 0,1,2,3 )
        if not suite_dir:
            group_clicked = True
        else:
            group_clicked = False
 
        menu = gtk.Menu()

        menu_root = gtk.MenuItem( 'foo' )
        menu_root.set_submenu( menu )

        def get_reg( item, iter ):
            reg = item
            if iter:
                par = model.iter_parent( iter )
                if par:
                    val, = model.get(par, 0)
                    reg = get_reg( val, par ) + delimiter + reg
            return reg

        reg = get_reg( item, iter )
        if self.cdb:
            owner = reg.split(delimiter)[0]

        if group_clicked:
            group = reg
            # MENU OPTIONS FOR GROUPS
            if not self.cdb:
                copy_item = gtk.MenuItem( 'C_opy' )
                menu.append( copy_item )
                copy_item.connect( 'activate', self.copy_popup, group )

            if self.cdb:
                imp_item = gtk.MenuItem( 'I_mport' )
                menu.append( imp_item )
                imp_item.connect( 'activate', self.import_popup, group )
            else:
                exp_item = gtk.MenuItem( 'E_xport' )
                menu.append( exp_item )
                exp_item.connect( 'activate', self.export_popup, group )

            reregister_item = gtk.MenuItem( '_Reregister' )
            menu.append( reregister_item )
            reregister_item.connect( 'activate', self.reregister_popup, group)
            if self.cdb:
                if owner != self.owner:
                    reregister_item.set_sensitive( False )

            del_item = gtk.MenuItem( '_Unregister' )
            menu.append( del_item )
            del_item.connect( 'activate', self.unregister_popup, group )
            if self.cdb:
                if owner != self.owner:
                    del_item.set_sensitive( False )

        else:
            # MENU OPTIONS FOR SUITES
            if not self.cdb:
                con_item = gtk.MenuItem( '_Control GUI (tree)')
                menu.append( con_item )
                con_item.connect( 'activate', self.launch_controller, reg, state )

                cong_item = gtk.MenuItem( '_Control GUI (graph)')
                menu.append( cong_item )
                cong_item.connect( 'activate', self.launch_controller, reg, state, True )

                subm_item = gtk.MenuItem( '_Submit A Task')
                menu.append( subm_item )
                subm_item.connect( 'activate', self.submit_task_popup, reg )

                menu.append( gtk.SeparatorMenuItem() )

                out_item = gtk.MenuItem( 'Suite _Output')
                menu.append( out_item )
                out_item.connect( 'activate', self.view_output, reg, state )

                out_item = gtk.MenuItem( 'Suite _Log')
                menu.append( out_item )
                out_item.connect( 'activate', self.view_log, reg )

                if state != '-':
                    # suite is running
                    dump_item = gtk.MenuItem( 'D_ump Suite State' )
                    menu.append( dump_item )
                    dump_item.connect( 'activate', self.dump_suite, reg )

                menu.append( gtk.SeparatorMenuItem() )

            search_item = gtk.MenuItem( '_Description' )
            menu.append( search_item )
            search_item.connect( 'activate', self.describe_suite, reg )

            list_item = gtk.MenuItem( 'Task _List' )
            menu.append( list_item )
            list_item.connect( 'activate', self.list_suite, reg )

            tree_item = gtk.MenuItem( '_Namespaces' )
            menu.append( tree_item )
            # use "-tp" for unicode box-drawing characters (seems to be
            # OK in pygtk textview).
            tree_item.connect( 'activate', self.list_suite, reg, '-tp' )

            if not self.cdb:
                jobs_item = gtk.MenuItem( 'Get A _Job Script')
                menu.append( jobs_item )
                jobs_item.connect( 'activate', self.jobscript_popup, reg )
    
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
                copy_item.connect( 'activate', self.copy_popup, reg )

                alias_item = gtk.MenuItem( '_Alias' )
                menu.append( alias_item )
                alias_item.connect( 'activate', self.alias_popup, reg )
    
            if self.cdb:
                imp_item = gtk.MenuItem( 'I_mport' )
                menu.append( imp_item )
                imp_item.connect( 'activate', self.import_popup, reg )
            else:
                exp_item = gtk.MenuItem( 'E_xport' )
                menu.append( exp_item )
                exp_item.connect( 'activate', self.export_popup, reg )
    
            compare_item = gtk.MenuItem( 'Co_mpare' )
            menu.append( compare_item )
            compare_item.connect( 'activate', self.compare_popup, reg )
 
            reregister_item = gtk.MenuItem( '_Reregister' )
            menu.append( reregister_item )
            reregister_item.connect( 'activate', self.reregister_popup, reg )
            if self.cdb:
                if owner != self.owner:
                    reregister_item.set_sensitive( False )
    
            del_item = gtk.MenuItem( '_Unregister' )
            menu.append( del_item )
            del_item.connect( 'activate', self.unregister_popup, reg )
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


    def alias_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Alias A Suite")

        vbox = gtk.VBox()
        label = gtk.Label( "SUITE: " + reg )
        vbox.pack_start( label )

        box = gtk.HBox()
        label = gtk.Label( 'ALIAS:' )
        box.pack_start( label, True )
        alias_entry = gtk.Entry()
        alias_entry.set_text( self.ownerless(reg) )
        box.pack_start (alias_entry, True)
        vbox.pack_start(box)

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Alias" )
        ok_button.connect("clicked", self.alias_suite, window, reg, alias_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, 'db', 'alias' )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def alias_suite( self, b, w, reg, alias_entry ):
        command = "cylc alias --notify-completion " + reg + " " + alias_entry.get_text()
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
        w.destroy()

    def unregister_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Unregister Suite(s)")

        vbox = gtk.VBox()

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        oblit_cb = gtk.CheckButton( "_Delete suite definition directories" )
        oblit_cb.set_active(False)

        ok_button = gtk.Button( "_Unregister" )
        ok_button.connect("clicked", self.unregister_suites, window, reg, oblit_cb )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, 'db', 'unregister' )

        label = gtk.Label( "SUITE: " + reg )
        vbox.pack_start( label )
        vbox.pack_start( oblit_cb )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def unregister_suites( self, b, w, reg, oblit_cb ):
        options = ''
        if oblit_cb.get_active():
            res = question_dialog( "!DANGER! !DANGER! !DANGER! !DANGER! !DANGER! !DANGER!\n"
                    "?Do you REALLY want to delete the associated suite definitions?" ).ask()
            if res == gtk.RESPONSE_YES:
                options = '--delete '
            else:
                return False
 
        command = "cylc unregister " + self.dbopt + " --notify-completion --force " + options + reg
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
        w.destroy()

    def launch_cug( self, b, pdf ):
        fail = []
        cdir = None
        try:
            cdir = os.environ['CYLC_DIR']
        except KeyError:
            fail.append( "$CYLC_DIR is not defined" )
 
        if pdf:
            try:
                appl = os.environ['PDF_READER']
            except KeyError:
                fail.append( "$PDF_READER is not defined" )
        else:
            try:
                appl = os.environ['HTML_READER']
            except KeyError:
                fail.append( "$HTML_READER is not defined" )

        if cdir:
            if pdf:
                file = os.path.join( cdir, 'doc', 'CylcUserGuide.pdf' )
            else:
                file = os.path.join( cdir, 'doc', 'cug-html.html' )

            if not os.path.isfile( file ):
                fail.append( "File not found: " + file )

        if len(fail) > 0:
            warning_dialog( '\n'.join( fail ) ).warn()
            return

        command = appl + " " + file 
        foo = gcapture_tmpfile( command, self.tmpdir, 400 )
        self.gcapture_windows.append(foo)
        foo.run()
 
    def ownerless( self, creg ):
        # remove owner from a central suite registration
        return delimiter.join( creg.split(delimiter)[1:] )
 
    def import_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Import Suite(s)")

        vbox = gtk.VBox()
        label = gtk.Label( 'SOURCE: ' + reg )
        vbox.pack_start( label )

        box = gtk.HBox()
        label = gtk.Label( 'TARGET:' )
        box.pack_start( label, True )
        newreg_entry = gtk.Entry()
        newreg_entry.set_text( self.ownerless(reg) )
        box.pack_start (newreg_entry, True)
        vbox.pack_start(box)

        box = gtk.HBox()
        label = gtk.Label( 'TOPDIR' )
        box.pack_start( label, True )
        dir_entry = gtk.Entry()
        box.pack_start (dir_entry, True)
        vbox.pack_start(box)

        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Import" )
        ok_button.connect("clicked", self.import_suites, window, reg, newreg_entry, dir_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, 'db', 'import' )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def import_suites( self, b, w, reg, newreg_entry, dir_entry ):
        newreg  = newreg_entry.get_text()
        sdir = dir_entry.get_text()
        if not self.check_entries( [newreg, sdir] ):
            return False
        command = "cylc import --notify-completion " + reg + ' ' + newreg + ' ' + sdir
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
        w.destroy()
 
    def export_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Export Suite(s)")

        vbox = gtk.VBox()
        label = gtk.Label( 'SOURCE: ' + reg )
        vbox.pack_start( label )

        box = gtk.HBox()
        label = gtk.Label( 'TARGET:' )
        box.pack_start( label, True )
        newreg_entry = gtk.Entry()
        newreg_entry.set_text( reg )
        box.pack_start (newreg_entry, True)
        vbox.pack_start( box )

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Export" )
        ok_button.connect("clicked", self.export_suites, window, reg, newreg_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, 'db', 'export' )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def export_suites( self, b, w, reg, newreg_entry ):
        newreg  = newreg_entry.get_text()
        if not self.check_entries( [newreg] ):
            return False
        command = "cylc export --notify-completion " + reg + ' ' + newreg
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
        w.destroy()
 
    def toggle_entry_sensitivity( self, w, entry ):
        if entry.get_property( 'sensitive' ) == 0:
            entry.set_sensitive( True )
        else:
            entry.set_sensitive( False )

    def reregister_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Reregister Suite(s)" )

        vbox = gtk.VBox()

        label = gtk.Label("SOURCE: " + reg )
        vbox.pack_start( label )
 
        label = gtk.Label("TARGET: " )
        name_entry = gtk.Entry()
        name_entry.set_text( reg )
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(name_entry, True) 
        vbox.pack_start( hbox )

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Reregister" )
        ok_button.connect("clicked", self.reregister_suites, window, reg, name_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, 'db', 'reregister' )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def reregister_suites( self, b, w, reg, n_e ):
        newreg = n_e.get_text()
        command = "cylc reregister " + self.dbopt + " --notify-completion " + reg + ' ' + newreg
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
        w.destroy()

    def compare_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Compare")

        vbox = gtk.VBox()
        label = gtk.Label("SUITE1: " + reg)
        vbox.pack_start(label)

        label = gtk.Label("SUITE2:" )
        name_entry = gtk.Entry()
        name_entry.set_text( reg )
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(name_entry, True) 
        vbox.pack_start( hbox )

        nested_cb = gtk.CheckButton( "Nested section headings" )
        nested_cb.set_active(False)
        vbox.pack_start (nested_cb, True)

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "Co_mpare" )
        ok_button.connect("clicked", self.compare_suites, window, reg, name_entry, nested_cb )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, 'prep', 'compare'  )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def copy_popup( self, w, reg ):

        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Copy Suite(s)")

        vbox = gtk.VBox()

        label = gtk.Label("SOURCE: " + reg )
        vbox.pack_start( label )

        label = gtk.Label("TARGET" )
        name_entry = gtk.Entry()
        name_entry.set_text( reg )
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(name_entry, True) 
        vbox.pack_start( hbox )

        box = gtk.HBox()
        label = gtk.Label( 'TOPDIR' )
        box.pack_start( label, True )
        dir_entry = gtk.Entry()
        box.pack_start (dir_entry, True)
        vbox.pack_start(box)

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "Co_py" )
        ok_button.connect("clicked", self.copy_suites, window, reg, name_entry, dir_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, 'db', 'copy')

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def compare_suites( self, b, w, reg, name_entry, nested_cb ):
        name  = name_entry.get_text()
        chk = [ name ]
        opts = ''
        if nested_cb.get_active():
            opts = ' -n '
        if not self.check_entries( chk ):
            return False
        command = "cylc diff " + self.dbopt + " --notify-completion " + opts + reg + ' ' + name
        foo = gcapture_tmpfile( command, self.tmpdir, 800 )
        self.gcapture_windows.append(foo)
        foo.run()
        w.destroy()
 
    def copy_suites( self, b, w, reg, name_entry, dir_entry ):
        name  = name_entry.get_text()
        sdir  = dir_entry.get_text()
        chk = [ name, sdir ]
        if not self.check_entries( chk ):
            return False
        command = "cylc copy --notify-completion " + reg + ' ' + name + ' ' + sdir
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()
        w.destroy()
 
    def search_suite_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Suite Search" )

        vbox = gtk.VBox()

        label = gtk.Label("SUITE: " + reg )
        vbox.pack_start(label)

        label = gtk.Label("PATTERN" )
        pattern_entry = gtk.Entry()
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(pattern_entry, True) 
        vbox.pack_start( hbox )

        nobin_cb = gtk.CheckButton( "Don't search bin/ directory" )
        vbox.pack_start (nobin_cb, True)

        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Search" )
        ok_button.connect("clicked", self.search_suite, reg, nobin_cb, pattern_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, 'prep', 'search' )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def graph_suite_popup( self, w, reg, suite_dir ):
        try:
            from cylc.graphing import xdot
        except Exception, x:
            warning_dialog( str(x) + "\nGraphing disabled.").warn()
            return False

        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Plot Suite Dependency Graph")

        vbox = gtk.VBox()

        label = gtk.Label("SUITE: " + reg )

        label = gtk.Label("[output FILE]" )
        outputfile_entry = gtk.Entry()
        hbox = gtk.HBox()
        hbox.pack_start( label )
        hbox.pack_start(outputfile_entry, True) 
        vbox.pack_start( hbox )
 
        cold_rb = gtk.RadioButton( None, "Cold Start" )
        cold_rb.set_active( True )
        warm_rb = gtk.RadioButton( cold_rb, "Warm Start" )
        hbox = gtk.HBox()
        hbox.pack_start (cold_rb, True)
        hbox.pack_start (warm_rb, True)
        vbox.pack_start( hbox, True )

        suite, rcfile = dbgetter(self.cdb).get_suite(reg)
        try:
            suiterc = config( suite, rcfile )
        except SuiteConfigError, x:
            warning_dialog( str(x) + \
                    '\n\n Suite.rc parsing failed (needed\nfor default start and stop cycles.' ).warn()
            return
        defstartc = suiterc['visualization']['initial cycle time']
        defstopc  = suiterc['visualization']['final cycle time']
 
        label = gtk.Label("[START]: " )
        start_entry = gtk.Entry()
        start_entry.set_max_length(10)
        start_entry.set_text( str(defstartc) )
        ic_hbox = gtk.HBox()
        ic_hbox.pack_start( label )
        ic_hbox.pack_start(start_entry, True) 
        vbox.pack_start(ic_hbox)

        label = gtk.Label("[STOP]:" )
        stop_entry = gtk.Entry()
        stop_entry.set_max_length(10)
        stop_entry.set_text( str(defstopc) )
        fc_hbox = gtk.HBox()
        fc_hbox.pack_start( label )
        fc_hbox.pack_start(stop_entry, True) 
        vbox.pack_start (fc_hbox, True)

        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )
        ok_button = gtk.Button( "_Graph" )
        ok_button.connect("clicked", self.graph_suite, reg, suite_dir,
                warm_rb, outputfile_entry, start_entry, stop_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, 'prep', 'graph' )

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
        command = "cylc search " + self.dbopt + " --notify-completion " + options + ' ' + pattern + ' ' + reg 
        foo = gcapture_tmpfile( command, self.tmpdir, height=500 )
        self.gcapture_windows.append(foo)
        foo.run()

    def graph_suite( self, w, reg, suite_dir, warm_rb, outputfile_entry,
            start_entry, stop_entry ):

        options = ''
        ofile = outputfile_entry.get_text()
        if ofile != '':
            options += ' -o ' + ofile

        if True:
            start = start_entry.get_text()
            stop = stop_entry.get_text()
            if start != '':
                try:
                    ct(start)
                except CycleTimeError,x:
                    warning_dialog( str(x) ).warn()
                    return False
            if stop != '':
                if start == '':
                    warning_dialog( "You cannot override Final Cycle without overriding Initial Cycle.").warn()
                    return False

                try:
                    ct(stop)
                except CycleTimeError,x:
                    warning_dialog( str(x) ).warn()
                    return False

        if warm_rb.get_active():
            options += ' -w '
        options += ' ' + reg + ' ' + start + ' ' + stop

        command = "cylc graph " + self.dbopt + " --notify-completion " + options
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

        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )
        ok_button = gtk.Button( "_Edit" )
        ok_button.connect("clicked", self.edit_suite, window, reg, edit_rb,
                edit_inlined_rb, view_inlined_rb, mark_cb, label_cb, nojoin_cb, single_cb )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, 'prep', 'edit' )

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
            command = "cylc inline " + self.dbopt + " --notify-completion -g " + extra + ' ' + reg
            foo = gcapture_tmpfile( command, self.tmpdir )
            self.gcapture_windows.append(foo)
            foo.run()
        else:
            if edit_inlined_rb.get_active():
                extra = '-i '
            else:
                extra = ''
            command = "cylc edit " + self.dbopt + " --notify-completion -g " + extra + ' ' + reg
            foo = gcapture_tmpfile( command, self.tmpdir )
            self.gcapture_windows.append(foo)
            foo.run()
        return False

    def validate_suite( self, w, name ):
        command = "cylc validate -v " + self.dbopt + " --notify-completion " + name 
        foo = gcapture_tmpfile( command, self.tmpdir, 600 )
        self.gcapture_windows.append(foo)
        foo.run()

    def dump_suite( self, w, name ):
        command = "cylc dump --notify-completion " + name
        foo = gcapture_tmpfile( command, self.tmpdir, 400, 400 )
        self.gcapture_windows.append(foo)
        foo.run()

    def jobscript_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Generate A Task Job Script")

        vbox = gtk.VBox()
        label = gtk.Label("SUITE: " + reg )
        vbox.pack_start( label )

        label = gtk.Label("TASK: " )
        task_entry = gtk.Entry()
        hbox = gtk.HBox()
        hbox.pack_start( label, True )
        hbox.pack_start(task_entry, True) 
        vbox.pack_start( hbox )
 
        cancel_button = gtk.Button( "_Close" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Generate" )
        ok_button.connect("clicked", self.jobscript, reg, task_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, 'util', 'jobscript' )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def submit_task_popup( self, w, reg ):
        window = gtk.Window()
        window.set_border_width(5)
        window.set_title( "Submit A Single Task")

        vbox = gtk.VBox()
        label = gtk.Label("SUITE: " + reg )
        vbox.pack_start( label )
 
        label = gtk.Label("TASK" )
        task_entry = gtk.Entry()
        hbox = gtk.HBox()
        hbox.pack_start( label, True )
        hbox.pack_start(task_entry, True) 
        vbox.pack_start( hbox )
 
        cancel_button = gtk.Button( "_Cancel" )
        cancel_button.connect("clicked", lambda x: window.destroy() )

        ok_button = gtk.Button( "_Submit" )
        ok_button.connect("clicked", self.submit_task, reg, task_entry )

        help_button = gtk.Button( "_Help" )
        help_button.connect("clicked", self.command_help, 'task', 'submit' )

        hbox = gtk.HBox()
        hbox.pack_start( ok_button, False )
        hbox.pack_end( cancel_button, False )
        hbox.pack_end( help_button, False )
        vbox.pack_start( hbox )

        window.add( vbox )
        window.show_all()

    def submit_task( self, w, reg, task_entry ):
        command = "cylc submit --notify-completion " + reg + " " + task_entry.get_text()
        foo = gcapture_tmpfile( command, self.tmpdir, 500, 400 )
        self.gcapture_windows.append(foo)
        foo.run()

    def jobscript( self, w, reg, task_entry ):
        command = "cylc jobscript " + reg + " " + task_entry.get_text()
        foo = gcapture_tmpfile( command, self.tmpdir, 800, 800 )
        self.gcapture_windows.append(foo)
        foo.run()

    def describe_suite( self, w, name ):
        command = """echo '> TITLE:'; cylc get-config """ + self.dbopt + " " + name + """ title; echo
echo '> DESCRIPTION:'; cylc get-config """ + self.dbopt + " --notify-completion " + name + " description"
        foo = gcapture_tmpfile( command, self.tmpdir, 800, 400 )
        self.gcapture_windows.append(foo)
        foo.run()

    def list_suite( self, w, name, opt='' ):
        command = "cylc list " + self.dbopt + " " + opt + " --notify-completion " + name
        foo = gcapture_tmpfile( command, self.tmpdir, 600, 600 )
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
                    "the command line, so gcylc does not have access its stdout "
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
                        "Delete old CYLC OUTPUT from this suite?\n\n"
                        "  + " + stdoutf + "\n\n"
                        "(Deleting this file is safe - it only contains cylc stdout "
                        "and stderr messages from previous runs launched via gcylc. "
                        "Click 'Yes' to delete it and start anew, or 'No' to append "
                        "new output to the existing file)." ).ask()
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
            # connecting a controller to a running suite started by command line
            # so no point in connecting to the special stdout and stderr files.
            # User was informed of this already by a dialog above.
            if depgraph:
                command = "gcylc --graph " + name
            else:
                command = "gcylc " + name
            foo = gcapture_tmpfile( command, self.tmpdir, 400 )
            self.gcapture_windows.append(foo)
            foo.run()

    def close_log_window( self, w, e, window, clv ):
        window.destroy()
        clv.quit()

    def view_log( self, w, reg ):
        suite, rcfile = dbgetter(self.cdb).get_suite(reg)
        try:
            suiterc = config( suite, rcfile )
        except SuiteConfigError, x:
            warning_dialog( str(x) + \
                    '\n\n Suite.rc parsing failed (needed\nto determine the suite log path.' ).warn()
            return
        logdir = os.path.join( suiterc['cylc']['logging']['directory'] )
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
                    "the command line, so gcylc cannot access its cylc stdout/stderr file.").inform()
                return False
        else:
            # suite not running
            info_dialog( "This suite is not running, so "
                    "the suite output window will show stdout and stderr "
                    "messages captured the last time(s) the suite was started "
                    "from via the GUI (gcylc cannot access stdout "
                    "and stderr for suites started by the command line).").inform()

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
(if you start a suite on the command line stdout and stderr redirection is up to you).'''
            warning_dialog( str(x) + '\n' + msg ).warn()
            return False

        foo = gcapture( None, stdout, width=600, height=400, ignore_command=True )
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

