#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2012 Hilary Oliver, NIWA
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
    icon_path = os.path.join(get_image_dir(), "icon.png")
    return gtk.gdk.pixbuf_new_from_file(icon_path)


def get_logo():
    """Return the gcylc logo as a gtk.gdk.Pixbuf."""
    logo_path = os.path.join(get_image_dir(), "logo.png")
    return gtk.gdk.pixbuf_new_from_file(logo_path)

