#!/usr/bin/env python

#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
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

import gtk
import pygtk
####pygtk.require('2.0')
from util import get_icon

class warning_dialog(object):
    def __init__( self, msg, parent=None ):
        self.dialog = gtk.MessageDialog( parent,
                gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_WARNING,
                gtk.BUTTONS_CLOSE, msg )
        self.dialog.set_icon(get_icon())

    def warn( self ):
        self.dialog.run()
        self.dialog.destroy()

class info_dialog(object):
    def __init__( self, msg, parent=None ):
        self.dialog = gtk.MessageDialog( parent,
                gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_INFO,
                gtk.BUTTONS_OK, msg )
        self.dialog.set_icon(get_icon())

    def inform( self ):
        self.dialog.run()
        self.dialog.destroy()

class question_dialog(object):
    def __init__( self, msg, parent=None ):
        self.dialog = gtk.MessageDialog( parent,
                gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_QUESTION,
                gtk.BUTTONS_YES_NO, msg )
        self.dialog.set_icon(get_icon())

    def ask( self ):
        response = self.dialog.run()
        self.dialog.destroy()
        return response


