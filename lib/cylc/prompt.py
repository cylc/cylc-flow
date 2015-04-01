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

import sys
import gtk

from cylc.cfgspec.globalcfg import GLOBAL_CFG
from cylc.gui.util import get_icon

def prompt(question, force=False, gui=False, no_force=False):
    """Interactive Yes/No prompt for cylc CLI scripts.

    For convenience, on No we just exit rather than return.
    If force is True don't prompt, just return immediately.
    
    """
    if (force or GLOBAL_CFG.get(['disable interactive command prompts'])) and (
            not no_force):
        return
    if gui:
        dialog = gtk.MessageDialog(
            None, gtk.DIALOG_DESTROY_WITH_PARENT,
            gtk.MESSAGE_QUESTION, gtk.BUTTONS_YES_NO,
            question
        )
        gui_response = dialog.run()
        response_no = (gui_response != gtk.RESPONSE_YES)
    else:
        cli_response = raw_input('%s (y/n)? ' % question)
        response_no = (cli_response not in ['y', 'Y'])
    if response_no:
        sys.exit(0)
