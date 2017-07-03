#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import gobject
import gtk
from time import time, sleep
import os
import re
import threading

from cylc.gui.warning_dialog import warning_dialog, info_dialog
from cylc.gui.util import get_icon, EntryTempText, EntryDialog
from cylc.network.port_scan import scan_all
from cylc.suite_srv_files_mgr import SuiteSrvFilesManager
from cylc.run_get_stdout import run_get_stdout
from cylc.suite_host import is_remote_host, is_remote_user


class db_updater(threading.Thread):

    SCAN_INTERVAL = 60.0

    def __init__(self, regd_treestore, filtr=None, timeout=None):
        self.db = SuiteSrvFilesManager()
        self.quit = False
        if timeout:
            self.timeout = float(timeout)
        else:
            self.timeout = None

        self.regd_treestore = regd_treestore
        super(db_updater, self).__init__()

        self.next_scan_time = None
        self.running_choices = None
        self.newtree = {}

        self.regd_choices = self.db.list_suites(filtr)

    def construct_newtree(self):
        """construct self.newtree[one][two]...[nnn] = [auth, descr, dir ]"""
        regd_choices = {}
        for suite, suite_dir, descr in sorted(self.regd_choices):
            regd_choices[suite] = (suite, suite_dir, descr)

        self.newtree = {}

        for suite, auth in self.running_choices:
            if suite in regd_choices:
                if is_remote_host(auth.split(':', 1)[0]):
                    descr, suite_dir = (None, None)
                else:
                    # local suite
                    suite_dir, descr = regd_choices[suite][1:3]
                    del regd_choices[suite]
            nest2 = self.newtree
            regp = suite.split(SuiteSrvFilesManager.DELIM)
            for key in regp[:-1]:
                if key not in nest2:
                    nest2[key] = {}
                nest2 = nest2[key]
            nest2[(regp[-1], suite, auth)] = [auth, descr, suite_dir]

        for suite, suite_dir, descr in regd_choices.values():
            suite_dir = re.sub('^' + os.environ['HOME'], '~', suite_dir)
            nest2 = self.newtree
            regp = suite.split(SuiteSrvFilesManager.DELIM)
            for key in regp[:-1]:
                if key not in nest2:
                    nest2[key] = {}
                nest2 = nest2[key]
            nest2[(regp[-1], suite, '-')] = ['-', descr, suite_dir]

    def build_treestore(self, data, piter=None):
        for key, value in sorted(data.items()):
            if isinstance(key, tuple):
                item = key[0]
            else:
                item = key
            if isinstance(value, dict):
                # final three items are colours
                iter_ = self.regd_treestore.append(
                    piter, [item, None, None, None, None, None, None])
                self.build_treestore(value, iter_)
            else:
                state, descr, suite_dir = value
                self.regd_treestore.append(
                    piter, [item, state, descr, suite_dir, None, None, None])

    def update(self):
        """Update tree, if necessary."""
        if self.next_scan_time is not None and self.next_scan_time > time():
            return

        # Scan for running suites
        choices = []
        for host, port, suite_identity in scan_all(timeout=self.timeout):
            name = suite_identity['name']
            owner = suite_identity['owner']
            if is_remote_user(owner):
                continue  # current user only
            auth = "%s:%d" % (host, port)
            choices.append((name, auth))
        choices.sort()
        self.next_scan_time = time() + self.SCAN_INTERVAL
        if choices == self.running_choices:
            return

        # Update tree if running suites changed
        self.running_choices = choices
        self.construct_newtree()
        self.update_treestore(
            self.newtree, self.regd_treestore.get_iter_first())

    def update_treestore(self, new, iter_):
        # iter_ is None for an empty treestore (no suites registered)
        ts = self.regd_treestore
        if iter_:
            opath = ts.get_path(iter_)
            # get parent iter_ before pruning in case we prune last item at
            # this level
            piter = ts.iter_parent(iter_)
        else:
            opath = None
            piter = None

        def my_get_iter(item):
            # find the TreeIter pointing at item at this level
            if not opath:
                return None
            iter_ = ts.get_iter(opath)
            while iter_:
                val, = ts.get(iter_, 0)
                if val == item:
                    return iter_
                iter_ = ts.iter_next(iter_)
            return None

        # new items at this level
        new_items = new.keys()
        old_items = []

        while iter_:
            # iterate through old items at this level
            item, state = ts.get(iter_, 0, 1, 2, 3)[0:2]
            if item not in new_items:
                # old item is not in new - prune it
                res = ts.remove(iter_)
                if not res:  # Nec?
                    iter_ = None
            else:
                # old item is in new - update it in case it changed
                old_items.append(item)
                # update old items that do appear in new
                chiter = ts.iter_children(iter_)
                if not isinstance(new[item], dict):
                    # new item is not a group - update title etc.
                    state = new[item][0]
                    sc = self.statecol(state)
                    ni = new[item]
                    ts.set(iter_, 0, item, 1, ni[0], 2, ni[1], 3, ni[2],
                           4, sc[0], 5, sc[1], 6, sc[2])
                    if chiter:
                        # old item was a group - kill its children
                        while chiter:
                            res = ts.remove(chiter)
                            if not res:
                                chiter = None
                else:
                    # new item is a group
                    if not chiter:
                        # old item was not a group
                        ts.set(
                            iter_, 0, item, 1, None, 2, None, 3, None, 4,
                            None, 5, None, 6, None)
                        self.build_treestore(new[item], iter_)

                # continue
                iter_ = ts.iter_next(iter_)

        # return to original iter_
        if opath:
            try:
                iter_ = ts.get_iter(opath)
            except ValueError:
                # removed the item pointed to
                # TODO - NEED TO WORRY ABOUT OTHERS AT THIS LEVEL?
                iter_ = None
        else:
            iter_ = None

        # add new items at this level
        for key in sorted(new_items):
            if isinstance(key, tuple):
                item = key[0]
            else:
                item = key
            if item not in old_items:
                # new data wasn't in old - add it
                if isinstance(new[key], dict):
                    xiter = ts.append(
                        piter, [item] + [None, None, None, None, None, None])
                    self.build_treestore(new[key], xiter)
                else:
                    state = new[key][0]
                    ts.append(
                        piter, [item] + new[key] + list(self.statecol(state)))
            else:
                # new data was already in old
                if isinstance(new[key], dict):
                    # check lower levels
                    niter = my_get_iter(key)
                    if niter:
                        chiter = ts.iter_children(niter)
                        if chiter:
                            self.update_treestore(new[key], chiter)

    def run(self):
        """Main loop."""
        while not self.quit:
            gobject.idle_add(self.update)
            sleep(0.1)

    @staticmethod
    def statecol(state):
        bg_ = '#19ae0a'
        fg_ = '#030'
        if state == '-':
            return (None, None, None)
        else:
            return (fg_, bg_, bg_)

    def search_level(self, model, iter_, func, data):
        while iter_:
            if func(model, iter_, data):
                return iter_
            iter_ = model.iter_next(iter_)
        return None

    def search_treemodel(self, model, iter_, func, data):
        while iter_:
            if func(model, iter_, data):
                return iter_
            result = self.search_treemodel(
                model, model.iter_children(iter_), func, data)
            if result:
                return result
            iter_ = model.iter_next(iter_)
        return None

    def match_func(self, model, iter_, data):
        column, key = data
        value = model.get_value(iter_, column)
        return value == key


class dbchooser(object):
    def __init__(self, title, parent, tmpdir, timeout):

        if timeout:
            self.timeout = float(timeout)
        else:
            self.timeout = None

        self.chosen = None

        self.updater = None
        self.tmpdir = tmpdir
        self.gcapture_windows = []

        gobject.threads_init()

        # self.window = gtk.Window(gtk.WINDOW_TOPLEVEL)
        self.window = gtk.Dialog(
            "Choose a suite",
            parent,
            gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
            (gtk.STOCK_CANCEL, gtk.RESPONSE_CANCEL, gtk.STOCK_OK,
             gtk.RESPONSE_OK))
        # self.window.set_modal(True)
        self.window.set_title(title)
        self.window.set_size_request(750, 400)
        # TODO: not needed for a dialog window?
        self.window.set_icon(get_icon())
        # self.window.set_border_width(5)

        self.window.connect("delete_event", self.delete_all_event)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)

        self.regd_treeview = gtk.TreeView()
        self.regd_treestore = gtk.TreeStore(str, str, str, str, str, str, str)
        self.regd_treeview.set_model(self.regd_treestore)
        self.regd_treeview.set_rules_hint(True)
        # search column zero (Ctrl-F)
        self.regd_treeview.connect('key_press_event', self.on_suite_select)
        self.regd_treeview.connect('button_press_event', self.on_suite_select)
        self.regd_treeview.set_search_column(0)

        regd_ts = self.regd_treeview.get_selection()
        regd_ts.set_mode(gtk.SELECTION_SINGLE)

        cr = gtk.CellRendererText()
        # cr.set_property('cell-background', '#def')
        tvc = gtk.TreeViewColumn(
            'Suite', cr, text=0, foreground=4, background=5)
        tvc.set_resizable(True)
        tvc.set_sort_column_id(0)
        self.regd_treeview.append_column(tvc)

        cr = gtk.CellRendererText()
        tvc = gtk.TreeViewColumn(
            'Host:Port', cr, text=1, foreground=4, background=5)
        tvc.set_resizable(True)
        # not sure how this sorting works
        # tvc.set_sort_column_id(1)
        self.regd_treeview.append_column(tvc)

        cr = gtk.CellRendererText()
        # cr.set_property('cell-background', '#def')
        tvc = gtk.TreeViewColumn(
            'Title', cr, markup=2, foreground=4, background=6)
        tvc.set_resizable(True)
        # vc.set_sort_column_id(2)
        self.regd_treeview.append_column(tvc)

        cr = gtk.CellRendererText()
        tvc = gtk.TreeViewColumn(
            'Location', cr, text=3, foreground=4, background=5)
        tvc.set_resizable(True)
        # vc.set_sort_column_id(3)
        self.regd_treeview.append_column(tvc)

        vbox = self.window.vbox

        sw.add(self.regd_treeview)

        vbox.pack_start(sw, True)

        self.selected_label_text = (
            '(double-click or OK to select; right-click for db options)')
        self.selected_label = gtk.Label(self.selected_label_text)

        filter_entry = EntryTempText()
        filter_entry.set_width_chars(7)  # Reduce width in toolbar
        filter_entry.connect("activate", self.filter)
        filter_entry.set_temp_text("filter")
        filter_toolitem = gtk.ToolItem()
        filter_toolitem.add(filter_entry)
        tooltip = gtk.Tooltips()
        tooltip.enable()
        tooltip.set_tip(
            filter_toolitem, "Filter suites \n(enter a sub-string or regex)")

        expand_button = gtk.ToolButton()
        image = gtk.image_new_from_stock(
            gtk.STOCK_ADD, gtk.ICON_SIZE_SMALL_TOOLBAR)
        expand_button.set_icon_widget(image)
        expand_button.connect(
            'clicked', lambda x: self.regd_treeview.expand_all())

        collapse_button = gtk.ToolButton()
        image = gtk.image_new_from_stock(
            gtk.STOCK_REMOVE, gtk.ICON_SIZE_SMALL_TOOLBAR)
        collapse_button.set_icon_widget(image)
        collapse_button.connect(
            'clicked', lambda x: self.regd_treeview.collapse_all())

        hbox = gtk.HBox()

        eb = gtk.EventBox()
        eb.add(self.selected_label)
        eb.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('#bbc'))
        hbox.pack_start(eb, True)
        hbox.pack_start(expand_button, False)
        hbox.pack_start(collapse_button, False)
        hbox.pack_start(filter_toolitem, False)

        vbox.pack_start(hbox, False)

        self.window.show_all()

        self.start_updater()

    def start_updater(self, filtr=None):
        if self.updater:
            self.updater.quit = True  # does this take effect?
        self.updater = db_updater(self.regd_treestore, filtr, self.timeout)
        self.updater.start()

    # TODO: a button to do this?
    # def reload(self, w):
    #    # tell updated to reconstruct the treeview from scratch
    #    self.updater.reload = True

    def filter(self, filtr_e):
        if filtr_e == "":
            # reset
            self.start_updater()
            return
        filtr = filtr_e.get_text()
        try:
            re.compile(filtr)
        except:
            warning_dialog(
                "Bad Regular Expression: " + filtr, self.window).warn()
            filtr_e.set_text("")
            self.start_updater()
            return
        self.start_updater(filtr)

    def delete_all_event(self, w, e):
        self.updater.quit = True
        # call quit on any remaining gcapture windows, which contain
        # Tailer threads that need to be stopped). Currently we maintain
        # a list of all gcapture windows opened
        # since start-up, hence the use of 'quit_already' to
        # avoid calling window.destroy() on gcapture windows that have
        # already been destroyed by the user closing them (although
        # a second call to destroy() may be safe anyway?)...
        for gwindow in self.gcapture_windows:
            if not gwindow.quit_already:
                gwindow.quit(None, None)

    def on_suite_select(self, treeview, event):
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
                path = treeview.get_cursor()[0]
                if not path:
                    # no selection (prob treeview heading selected)
                    return False
                if not treeview.row_expanded(path):
                    # row not expanded or not expandable
                    iter_ = self.regd_treestore.get_iter(path)
                    if self.regd_treestore.iter_children(iter_):
                        # has children so is expandable
                        treeview.expand_row(path, False)
                        return False
        else:
            # called by button click

            if event.button != 1 and event.button != 3:
                return False

            # the following sets selection to the position at which the
            # right click was done (otherwise selection lags behind the
            # right click):
            x = int(event.x)
            y = int(event.y)
            pth = treeview.get_path_at_pos(x, y)
            if pth is None:
                return False
            treeview.grab_focus()
            path, col = pth[0:2]
            treeview.set_cursor(path, col, 0)

        selection = treeview.get_selection()
        model, iter_ = selection.get_selected()
        item, auth, _, suite_dir = model.get(iter_, 0, 1, 2, 3)

        def get_reg(item, iter_):
            reg = item
            if iter_:
                par = model.iter_parent(iter_)
                if par:
                    val, = model.get(par, 0)
                    reg = get_reg(val, par) + SuiteSrvFilesManager.DELIM + reg
            return reg

        reg = get_reg(item, iter_)
        if reg and auth:
            self.chosen = (reg, auth)
            self.selected_label.set_text("%s @ %s" % (reg, auth))
        else:
            self.chosen = None
            self.selected_label.set_text(self.selected_label_text)

        if event.type == gtk.gdk._2BUTTON_PRESS:
            # double-click
            self.window.response(gtk.RESPONSE_OK)
            return True

        # return False so clicks still be handled for tree expand/collapse
        if event.button == 1:
            return False

        if suite_dir:
            menu = gtk.Menu()
            compare_item = gtk.MenuItem('C_ompare')
            menu.append(compare_item)
            compare_item.connect('activate', self.compare_popup, reg)

            menu.show_all()
            # button only:
            # menu.popup(None, None, None, event.button, event.time)
            # this seems to work with keypress and button:
            menu.popup(None, None, None, 0, event.time)

            # TODO - POPUP MENU MUST BE DESTROY()ED AFTER EVERY USE AS
            # POPPING DOWN DOES NOT DO THIS (=> MEMORY LEAK?)
            return False

    def compare_popup(self, w, reg):

        window = EntryDialog(
            parent=self.window,
            flags=0,
            type=gtk.MESSAGE_QUESTION,
            buttons=gtk.BUTTONS_OK_CANCEL,
            message_format="Compare Suite " + reg + " With")

        compare = window.run()
        window.destroy()
        if compare:
            command = "cylc diff " + reg + ' ' + compare
            res, out = run_get_stdout(command)
            if not res:
                warning_dialog('\n'.join(out), self.window).warn()
            else:
                # TODO: need a bigger scrollable window here!
                info_dialog('\n'.join(out), self.window).inform()
