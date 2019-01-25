#!/usr/bin/env python3

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

import sys

from cylc.cfgspec.glbl_cfg import glbl_cfg


def prompt(question, force=False, gui=False, no_force=False, no_abort=False,
           keep_above=True):
    """Interactive Yes/No prompt for cylc CLI scripts.

    For convenience, on No we just exit rather than return.
    If force is True don't prompt, just return immediately.

    """
    if (force or glbl_cfg().get(['disable interactive command prompts'])) and (
            not no_force):
        return True
    if gui:
        raise NotImplementedError
    else:
        cli_response = input('%s (y/n)? ' % question)
        response_no = (cli_response not in ['y', 'Y'])
    if response_no:
        if no_abort:
            return False
        else:
            sys.exit(0)
    else:
        return True
