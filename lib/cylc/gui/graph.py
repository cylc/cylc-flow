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

import gobject
import gtk

from gcapture import gcapture, gcapture_tmpfile
from warning_dialog import warning_dialog


def graph_suite_popup(reg, cmd_help, defstartc, defstopc, graph_opts,
                      gcapture_windows, tmpdir, template_opts,
                      parent_window=None):
    """Popup a dialog to allow a user to configure their suite graphing."""
    try:
        import xdot
    except Exception, x:
        warning_dialog(str(x) + "\nGraphing disabled.", parent_window).warn()
        return False

    window = gtk.Window()
    window.set_border_width(5)
    window.set_title("cylc graph " + reg)
    window.set_transient_for(parent_window)
    window.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)

    vbox = gtk.VBox()

    label = gtk.Label("[START]: ")
    start_entry = gtk.Entry()
    start_entry.set_max_length(14)
    if defstartc:
        start_entry.set_text(str(defstartc))
    ic_hbox = gtk.HBox()
    ic_hbox.pack_start(label)
    ic_hbox.pack_start(start_entry, True)
    vbox.pack_start(ic_hbox)

    label = gtk.Label("[STOP]:")
    stop_entry = gtk.Entry()
    stop_entry.set_max_length(14)
    if defstopc:
        stop_entry.set_text(str(defstopc))
    fc_hbox = gtk.HBox()
    fc_hbox.pack_start(label)
    fc_hbox.pack_start(stop_entry, True)
    vbox.pack_start(fc_hbox, True)

    cancel_button = gtk.Button("_Close")
    cancel_button.connect("clicked", lambda x: window.destroy())
    ok_button = gtk.Button("_Graph")
    ok_button.connect("clicked", lambda w: graph_suite(
        reg,
        start_entry.get_text(),
        stop_entry.get_text(),
        graph_opts, gcapture_windows,
        tmpdir, template_opts, parent_window))

    help_button = gtk.Button("_Help")
    help_button.connect("clicked", cmd_help, 'prep', 'graph')

    hbox = gtk.HBox()
    hbox.pack_start(ok_button, False)
    hbox.pack_end(cancel_button, False)
    hbox.pack_end(help_button, False)
    vbox.pack_start(hbox)

    window.add(vbox)
    window.show_all()


def graph_suite(reg, start, stop, graph_opts,
                gcapture_windows, tmpdir, template_opts, window=None):
    """Launch the cylc graph command with some options."""
    options = graph_opts
    options += ' ' + reg + ' ' + start + ' ' + stop
    command = "cylc graph " + template_opts + " " + options
    foo = gcapture_tmpfile(command, tmpdir)
    gcapture_windows.append(foo)
    foo.run()
    return False
