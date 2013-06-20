#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2013 Hilary Oliver, NIWA
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
import time, os, re, sys
import threading
from util import EntryTempText, EntryDialog
from cylc.run_get_stdout import run_get_stdout

try:
    from cylc import cylc_pyro_client
except BaseException, x: # this catches SystemExit
    PyroInstalled = False
    print >> sys.stderr, "WARNING: Pyro is not installed."
else:
    PyroInstalled = True
    from cylc.port_scan import scan

from cylc.registration import localdb
from cylc.regpath import RegPath
from warning_dialog import warning_dialog, info_dialog, question_dialog
from util import get_icon
from gcapture import gcapture, gcapture_tmpfile

debug = False

class db_updater(threading.Thread):
    count = 0
    def __init__(self, regd_treestore, db, filtr=None, pyro_timeout=None ):
        self.__class__.count += 1
        self.me = self.__class__.count
        self.filtr = filtr
        self.db = db
        self.quit = False
        self.reload = False
        if pyro_timeout:
            self.pyro_timeout = float(pyro_timeout)
        else:
            self.pyro_timeout = None

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
            regp = suite.split(RegPath.delimiter)
            for key in regp[:-1]:
                if key not in nest2:
                    nest2[key] = {}
                nest2 = nest2[key]
            nest2[regp[-1]] = [ state, descr, suite_dir ]

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
                # TODO - NEED TO WORRY ABOUT OTHERS AT THIS LEVEL?
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
        if not PyroInstalled:
            return
        # (name, port)
        suites = scan( pyro_timeout=self.pyro_timeout, silent=True )
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

class dbchooser(object):
    def __init__(self, parent, db, db_owner, tmpdir, pyro_timeout ):

        self.db = db
        self.db_owner = db_owner
        if pyro_timeout:
            self.pyro_timeout = float(pyro_timeout)
        else:
            self.pyro_timeout = None

        self.regname = None

        self.updater = None
        self.tmpdir = tmpdir
        self.gcapture_windows = []

        gobject.threads_init()

        #self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window = gtk.Dialog( "Choose a suite", parent, gtk.DIALOG_MODAL|gtk.DIALOG_DESTROY_WITH_PARENT, (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK, gtk.RESPONSE_OK))
        #self.window.set_modal(True)
        self.window.set_title("Suite Chooser" )
        self.window.set_size_request(750, 400)
        self.window.set_icon(get_icon()) # TODO: not needed for a dialog window?
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

        # Start updating the liststore now, as we need values in it
        # immediately below (it may be possible to delay this till the
        # end of __init___() but it doesn't really matter.
        if self.db:
            self.dbopt = '--db='+self.db
        else:
            self.dbopt = ''

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
        tvc = gtk.TreeViewColumn( 'Location', cr, text=3, foreground=4, background=5 )
        tvc.set_resizable(True)
        #vc.set_sort_column_id(3)
        self.regd_treeview.append_column( tvc )

        vbox = self.window.vbox

        sw.add( self.regd_treeview )

        vbox.pack_start( sw, True )

        self.selected_label_text = '(double-click or OK to select; right-click for db options)'
        self.selected_label = gtk.Label( self.selected_label_text )

        filter_entry = EntryTempText()
        filter_entry.set_width_chars( 7 )  # Reduce width in toolbar
        filter_entry.connect( "activate", self.filter )
        filter_entry.set_temp_text( "filter" )
        filter_toolitem = gtk.ToolItem()
        filter_toolitem.add(filter_entry)
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(filter_toolitem, "Filter suites \n(enter a sub-string or regex)")

        expand_button = gtk.ToolButton()
        image = gtk.image_new_from_stock( gtk.STOCK_ADD, gtk.ICON_SIZE_SMALL_TOOLBAR )
        expand_button.set_icon_widget( image )
        expand_button.connect( 'clicked', lambda x: self.regd_treeview.expand_all() )

        collapse_button = gtk.ToolButton()
        image = gtk.image_new_from_stock( gtk.STOCK_REMOVE, gtk.ICON_SIZE_SMALL_TOOLBAR )
        collapse_button.set_icon_widget( image )        
        collapse_button.connect( 'clicked', lambda x: self.regd_treeview.collapse_all() )

        hbox = gtk.HBox()

        eb = gtk.EventBox()
        eb.add( self.selected_label )
        eb.modify_bg( gtk.STATE_NORMAL, gtk.gdk.color_parse( '#bbc' ) ) 
        hbox.pack_start( eb, True )
        hbox.pack_start( expand_button, False )
        hbox.pack_start( collapse_button, False )
        hbox.pack_start (filter_toolitem, False)
 
        vbox.pack_start( hbox, False )

        self.window.show_all()

        self.start_updater()

    def start_updater(self, filtr=None ):
        db = localdb(self.db)
        #self.db_button.set_label( "_Local/Central DB" )
        if self.updater:
            self.updater.quit = True # does this take effect?
        self.updater = db_updater( self.regd_treestore, db, filtr, self.pyro_timeout )
        self.updater.start()

    # TODO: a button to do this?
    #def reload( self, w ):
    #    # tell updated to reconstruct the treeview from scratch
    #    self.updater.reload = True

    def filter(self, filtr_e ):
        if filtr_e == "":
            # reset
            self.start_updater()
            return
        filtr = filtr_e.get_text()
        try:
            re.compile( filtr )
        except:
            warning_dialog( "Bad Regular Expression: " + filtr, self.window ).warn()
            filtr_e.set_text("")
            self.start_updater()
            return
        self.start_updater( filtr )

    def delete_all_event( self, w, e ):
        self.updater.quit = True
        # call quit on any remaining gcapture windows, which contain
        # tailer threads that need to be stopped). Currently we maintain
        # a list of all gcapture windows opened
        # since start-up, hence the use of 'quit_already' to
        # avoid calling window.destroy() on gcapture windows that have
        # already been destroyed by the user closing them (although
        # a second call to destroy() may be safe anyway?)...
        for gwindow in self.gcapture_windows:
            if not gwindow.quit_already:
                gwindow.quit( None, None )

    def on_suite_select( self, treeview, event ):
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

            if event.button != 1 and event.button != 3:
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
 
        def get_reg( item, iter ):
            reg = item
            if iter:
                par = model.iter_parent( iter )
                if par:
                    val, = model.get(par, 0)
                    reg = get_reg( val, par ) + RegPath.delimiter + reg
            return reg

        reg = get_reg( item, iter )
        if not group_clicked:
            self.regname = reg
            self.selected_label.set_text( reg )
        else:
            self.regname = None
            self.selected_label.set_text( self.selected_label_text )

        if event.type == gtk.gdk._2BUTTON_PRESS:
            # double-click
            self.window.response(gtk.RESPONSE_OK)
            return True

        # return False so clicks still be handled for tree expand/collapse
        if event.button == 1:
            return False

        menu = gtk.Menu()

        if group_clicked:
            group = reg
            # MENU OPTIONS FOR GROUPS
            copy_item = gtk.MenuItem( 'C_opy' )
            menu.append( copy_item )
            copy_item.connect( 'activate', self.copy_popup, group, True )

            reregister_item = gtk.MenuItem( '_Reregister' )
            menu.append( reregister_item )
            reregister_item.connect( 'activate', self.reregister_popup, group, True )

            del_item = gtk.MenuItem( '_Unregister' )
            menu.append( del_item )
            del_item.connect( 'activate', self.unregister_popup, group, True )

        else:
            copy_item = gtk.MenuItem( '_Copy' )
            menu.append( copy_item )
            copy_item.connect( 'activate', self.copy_popup, reg )

            alias_item = gtk.MenuItem( '_Alias' )
            menu.append( alias_item )
            alias_item.connect( 'activate', self.alias_popup, reg )
    
            reregister_item = gtk.MenuItem( '_Reregister' )
            menu.append( reregister_item )
            reregister_item.connect( 'activate', self.reregister_popup, reg )
    
            del_item = gtk.MenuItem( '_Unregister' )
            menu.append( del_item )
            del_item.connect( 'activate', self.unregister_popup, reg )

            compare_item = gtk.MenuItem( 'C_ompare' )
            menu.append( compare_item )
            compare_item.connect( 'activate', self.compare_popup, reg )

        menu.show_all()
        # button only:
        #menu.popup( None, None, None, event.button, event.time )
        # this seems to work with keypress and button:
        menu.popup( None, None, None, 0, event.time )

        # TODO - POPUP MENU MUST BE DESTROY()ED AFTER EVERY USE AS
        # POPPING DOWN DOES NOT DO THIS (=> MEMORY LEAK?)
        return False

    def alias_popup( self, w, reg ):

        window = EntryDialog( parent=self.window,
                flags=0,
                type=gtk.MESSAGE_QUESTION,
                buttons=gtk.BUTTONS_OK_CANCEL,
                message_format="Alias Suite Name " + reg )

        alias = window.run()
        window.destroy()
        if alias:
            command = "cylc alias " + reg + ' ' + alias
            res, out = run_get_stdout( command )
            if not res:
                warning_dialog( '\n'.join(out), self.window ).warn()

    def unregister_popup( self, w, reg, is_group=False ):

        window = gtk.MessageDialog( parent=self.window,
                flags=0,
                type=gtk.MESSAGE_QUESTION,
                buttons=gtk.BUTTONS_NONE,
                message_format="Unregistering Suite " + reg + """
\nDelete suite definition directory too? (DANGEROUS!)""")

        window.add_button( gtk.STOCK_YES, gtk.RESPONSE_YES )
        window.add_button( gtk.STOCK_NO, gtk.RESPONSE_NO )
        window.add_button( gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL )
        response = window.run()
        window.destroy()

        if is_group:
            reg = '^' + reg + '\..*$'
        else:
            reg = '^' + reg + '$'

        if response == gtk.RESPONSE_YES:
            command = "cylc unregister -f -d " + reg
        elif response == gtk.RESPONSE_NO:
            command = "cylc unregister " + reg
        else:
            command = None
        if command:
            res, out = run_get_stdout( command )
            if not res:
                warning_dialog( '\n'.join(out), self.window ).warn()

    def reregister_popup( self, w, reg, is_group=False ):

        window = EntryDialog( parent=self.window,
                flags=0,
                type=gtk.MESSAGE_QUESTION,
                buttons=gtk.BUTTONS_OK_CANCEL,
                message_format="Reregister Suite " + reg + " As")

        rereg = window.run()
        window.destroy()
        if rereg:
            command = "cylc reregister " + reg + ' ' + rereg
            res, out = run_get_stdout( command )
            if not res:
                warning_dialog( '\n'.join(out), self.window ).warn()

    def compare_popup( self, w, reg ):

        window = EntryDialog( parent=self.window,
                flags=0,
                type=gtk.MESSAGE_QUESTION,
                buttons=gtk.BUTTONS_OK_CANCEL,
                message_format="Compare Suite " + reg + " With")

        compare = window.run()
        window.destroy()
        if compare:
            command = "cylc diff " + reg + ' ' + compare
            res, out = run_get_stdout( command )
            if not res:
                warning_dialog( '\n'.join(out), self.window ).warn()
            else:
                # TODO: need a bigger scrollable window here!
                info_dialog( '\n'.join(out), self.window ).inform()

    def copy_popup( self, w, reg, is_group=False ):

        window = EntryDialog( parent=self.window,
                flags=0,
                type=gtk.MESSAGE_QUESTION,
                buttons=gtk.BUTTONS_OK_CANCEL,
                message_format="Copy Suite " + reg + """To
NAME,TOP_DIRECTORY""")

        out = window.run()
        window.destroy()
        if out:
            try:
                name, topdir = re.split(' *, *', out )
            except Exception, e:
                warning_dialog( str(e), self.window ).warn()
            else:
                print name, topdir
                topdir = os.path.expanduser( os.path.expandvars( topdir ))
                print name, topdir
                command = "cylc cp " + reg + ' ' + name + ' ' + topdir
                print command
                res, out = run_get_stdout( command )
                if not res:
                    warning_dialog( '\n'.join(out), self.window ).warn()
                elif out:
                    info_dialog( '\n'.join(out), self.window ).inform()


