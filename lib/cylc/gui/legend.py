#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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

from cylc.gui.dot_maker import DotMaker
from cylc.gui.util import get_icon
from cylc.task_state import TASK_STATUSES_ORDERED


class ThemeLegendWindow(gtk.Window):

    """This is a popup window displaying the theme state colors."""

    def __init__(self, parent_window, theme_map, dot_size='medium'):
        super(ThemeLegendWindow, self).__init__()
        self.set_border_width(5)
        self.set_title("")
        if parent_window is None:
            self.set_icon(get_icon())
        else:
            self.set_transient_for(parent_window)
        self.set_type_hint(gtk.gdk.WINDOW_TYPE_HINT_DIALOG)

        self._theme = theme_map
        self._dot_size = dot_size
        self._key_liststore = gtk.ListStore(str, gtk.gdk.Pixbuf)
        treeview = gtk.TreeView(self._key_liststore)
        treeview.set_headers_visible(False)
        treeview.get_selection().set_mode(gtk.SELECTION_NONE)
        tvc = gtk.TreeViewColumn(None)

        self.update()

        cellpb = gtk.CellRendererPixbuf()
        cell = gtk.CellRendererText()

        tvc.pack_start(cellpb, False)
        tvc.pack_start(cell, True)

        tvc.set_attributes(cellpb, pixbuf=1)
        tvc.set_attributes(cell, text=0)

        treeview.append_column(tvc)

        self.add(treeview)
        self.show_all()

    def update(self, new_theme=None, new_dot_size=None):
        """Update, optionally with a new theme."""
        if new_theme is not None:
            self._theme = new_theme
        if new_dot_size is not None:
            self._dot_size = new_dot_size
        self._set_key_liststore()

    def _set_key_liststore(self):
        dotm = DotMaker(self._theme, self._dot_size)
        self._key_liststore.clear()
        for state in TASK_STATUSES_ORDERED:
            dot = dotm.get_icon(state)
            self._key_liststore.append([state, dot])
