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

import os
import sys
import traceback

import gtk


class EntryTempText(gtk.Entry):
    """Class to add temporary text to an entry that vanishes on focus."""

    temp_colour = gtk.gdk.color_parse("grey")
    temp_text = "temp"

    def clear_temp_text(self, *args):
        """Clear the temporary text so the user can enter new stuff."""
        if super(EntryTempText, self).get_text() == self.temp_text:
            self.set_text("")

    def set_temp_text(self, temp_text):
        """Set the temporary text that will disappear on focus."""
        self.temp_text = temp_text
        self.set_text(temp_text)
        self.connect("focus-in-event", self.clear_temp_text)

    def set_text(self, text):
        """Wrapper for standard set_text - control colour."""
        if text == self.temp_text:
            self.modify_text(gtk.STATE_NORMAL, self.temp_colour)
        else:
            self.modify_text(gtk.STATE_NORMAL, None)
        super(EntryTempText, self).set_text(text)

    def get_text(self):
        """Wrapper for standard get_text - don't return temp text."""
        text = super(EntryTempText, self).get_text()
        if text == self.temp_text:
            return ""
        return text

class EntryDialog(gtk.MessageDialog):
    def __init__(self, *args, **kwargs):
        '''
        Creates a new EntryDialog. Takes all the arguments of the usual
        MessageDialog constructor plus one optional named argument
        "default_value" to specify the initial contents of the entry.
        '''
        if 'default_value' in kwargs:
            default_value = kwargs['default_value']
            del kwargs['default_value']
        else:
            default_value = ''
        super(EntryDialog, self).__init__(*args, **kwargs)
        entry = gtk.Entry()
        entry.set_text(str(default_value))
        entry.connect("activate",
                lambda ent, dlg, resp: dlg.response(resp),
                self, gtk.RESPONSE_OK)
        self.vbox.pack_end(entry, True, True, 0)
        self.vbox.show_all()
        self.entry = entry
    def set_value(self, text):
        self.entry.set_text(text)
    def run(self):
        result = super(EntryDialog, self).run()
        if result == gtk.RESPONSE_OK:
            text = self.entry.get_text()
        else:
            text = None
        return text


def get_image_dir():
    """Return the root directory for cylc images."""
    try:
        cylc_dir = os.environ['CYLC_DIR']
    except KeyError:
        # This should not happen (unecessary)
        raise SystemExit("ERROR: $CYLC_DIR is not defined!")
    return os.path.join(cylc_dir, "images")


def get_icon():
    """Return the gcylc icon as a gtk.gdk.Pixbuf."""
    try:
        icon_path = os.path.join(get_image_dir(), "icon.svg")
        icon      = gtk.gdk.pixbuf_new_from_file(icon_path)
    except:
        # SVG error? Try loading it the old way.
        icon_path = os.path.join(get_image_dir(), "icon.png")
        icon      = gtk.gdk.pixbuf_new_from_file(icon_path)
    return icon


def get_logo():
    """Return the gcylc logo as a gtk.gdk.Pixbuf."""
    logo_path = os.path.join(get_image_dir(), "logo.png")
    return gtk.gdk.pixbuf_new_from_file(logo_path)


def _launch_exception_hook_dialog(e_type, e_value, e_traceback,
                                  old_hook=None, program_name=None):
    if program_name is None:
        program_name = "This program"
    exc_lines = traceback.format_exception(e_type, e_value, e_traceback)
    exc_text = "".join(exc_lines)
    info = "%s has a problem.\n\n%s" % (program_name, exc_text)
    dialog = gtk.MessageDialog(type=gtk.MESSAGE_ERROR,
                               message_format=info.rstrip())
    dialog.set_icon(get_icon())
    dialog.add_button(gtk.STOCK_OK, gtk.RESPONSE_CLOSE)
    dialog.run()
    dialog.destroy()
    if old_hook is not None:
        old_hook(e_type, e_value, e_traceback)


def set_exception_hook_dialog(program_name=None):
    """Set a custom uncaught exception hook for launching an error dialog."""
    old_hook = sys.excepthook
    sys.excepthook = lambda *a: _launch_exception_hook_dialog(
                                                  *a, old_hook=old_hook,
                                                  program_name=program_name)


def setup_icons():
    """Set up some extra stock icons for better PyGTK compatibility."""
    # create a new stock icon for the 'group' and 'transpose' actions
    root_img_dir = get_image_dir()
    pixbuf = get_icon()
    gcylc_iconset = gtk.IconSet(pixbuf)
    pixbuf = gtk.gdk.pixbuf_new_from_file( root_img_dir + '/icons/group.png' )
    grp_iconset = gtk.IconSet(pixbuf)
    pixbuf = gtk.gdk.pixbuf_new_from_file( root_img_dir + '/icons/ungroup.png' )
    ungrp_iconset = gtk.IconSet(pixbuf)
    pixbuf = gtk.gdk.pixbuf_new_from_file( root_img_dir + '/icons/transpose.png' )
    transpose_iconset = gtk.IconSet(pixbuf)
    factory = gtk.IconFactory()
    factory.add( 'gcylc', gcylc_iconset )
    factory.add( 'group', grp_iconset )
    factory.add( 'ungroup', ungrp_iconset )
    factory.add( 'transpose', transpose_iconset )
    factory.add_default()
