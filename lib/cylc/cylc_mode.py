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


class mode(object):
    def __init__(self):
        self.mode = 'raw'
        if 'CYLC_MODE' in os.environ:
            self.mode = os.environ['CYLC_MODE']
            # 'scheduler' or 'submit'

    def is_raw(self):
        return self.mode == 'raw'

    def is_scheduler(self):
        return self.mode == 'scheduler'

    def is_submit(self):
        return self.mode == 'submit'
