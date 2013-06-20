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

import os

import gtk


class EntryTempText( gtk.Entry ):

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
            if not hasattr(self, "original colour"):
                self.original_colour = self.style.text[gtk.STATE_NORMAL]
            self.modify_text(gtk.STATE_NORMAL, self.temp_colour)
        else:
            self.modify_text(gtk.STATE_NORMAL, self.original_colour)
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

