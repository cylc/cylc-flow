#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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

import gtk
import pygtk
import os
from cylc.gui.tailer import Tailer
from cylc.gui.warning_dialog import warning_dialog
import pango


class logviewer(object):
    def __init__(self, name, dirname, filename):
        self.name = name
        self.dirname = dirname
        self.filename = filename
        self.t = None

        self.find_current = None
        self.find_current_iter = None
        self.search_warning_done = False

        self.create_gui_panel()
        self.logview.get_buffer()

        self.connect()

    def clear_and_reconnect(self):
        self.t.stop()
        self.clear()
        self.connect()

    def clear(self):
        logbuffer = self.logview.get_buffer()
        s, e = logbuffer.get_bounds()
        logbuffer.delete(s, e)

    def path(self):
        if self.dirname and not os.path.isabs(self.filename):
            return os.path.join(self.dirname, self.filename)
        else:
            return self.filename

    def connect(self):
        self.t = Tailer(self.logview, self.path())
        self.t.start()

    def quit_w_e(self, w, e):
        self.t.stop()

    def quit(self):
        self.t.stop()

    def get_widget(self):
        return self.vbox

    def reset_logbuffer(self):
        # clear log buffer iters and tags
        logbuffer = self.logview.get_buffer()
        s, e = logbuffer.get_bounds()
        logbuffer.remove_all_tags(s, e)
        self.find_current_iter = None
        self.find_current = None

    def enter_clicked(self, e, tv):
        self.on_find_clicked(tv, e)

    def on_find_clicked(self, tv, e):
        needle = e.get_text()
        if not needle:
            return

        self.t.freeze = True
        self.freeze_button.set_active(True)
        self.freeze_button.set_label('Reconnect')
        if not self.search_warning_done:
            warning_dialog(
                "Find Next disconnects the live feed;" +
                " click Reconnect when you're done").warn()
            self.search_warning_done = True

        tb = tv.get_buffer()

        if needle == self.find_current:
            s = self.find_current_iter
        else:
            s, e = tb.get_bounds()
            tb.remove_all_tags(s, e)
            s = tb.get_end_iter()
            tv.scroll_to_iter(s, 0)
        try:
            f, l = s.backward_search(needle, gtk.TEXT_SEARCH_TEXT_ONLY)
        except:
            warning_dialog('"' + needle + '"' + " not found").warn()
        else:
            tag = tb.create_tag(None, background="#70FFA9")
            tb.apply_tag(tag, f, l)
            self.find_current_iter = f
            self.find_current = needle
            tv.scroll_to_iter(f, 0)

    def freeze_log(self, b):
        # TODO - HANDLE MORE STUFF IN THREADS LIKE THIS, RATHER THAN
        # PASSING IN ARGUMENTS?
        if b.get_active():
            self.t.freeze = True
            b.set_label('Re_connect')
            self.reset_logbuffer()
        else:
            self.t.freeze = False
            b.set_label('Dis_connect')

        return False

    def create_gui_panel(self):
        self.logview = gtk.TextView()
        self.logview.set_editable(False)
        # Use a monospace font. This is safe - by testing - setting an
        # illegal font description has no effect.
        self.logview.modify_font(pango.FontDescription("monospace"))

        searchbox = gtk.HBox()
        entry = gtk.Entry()
        entry.connect("activate", self.enter_clicked, self.logview)
        searchbox.pack_start(entry, True)
        b = gtk.Button("Find Next")
        b.connect_object('clicked', self.on_find_clicked, self.logview, entry)
        searchbox.pack_start(b, False)

        self.hbox = gtk.HBox()

        self.freeze_button = gtk.ToggleButton("Dis_connect")
        self.freeze_button.set_active(False)
        self.freeze_button.connect("toggled", self.freeze_log)

        searchbox.pack_end(self.freeze_button, False)

        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        sw.add(self.logview)
        self.logview.set_border_width(5)
        self.logview.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#fff"))

        self.vbox = gtk.VBox()

        self.log_label = gtk.Label(self.path())
        self.log_label.modify_fg(gtk.STATE_NORMAL, gtk.gdk.color_parse("#00a"))
        self.vbox.pack_start(self.log_label, False)

        self.vbox.pack_start(sw, True)
        self.vbox.pack_start(searchbox, False)
        self.vbox.pack_start(self.hbox, False)
