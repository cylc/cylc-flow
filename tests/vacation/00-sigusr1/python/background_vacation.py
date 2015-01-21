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


from cylc.batch_sys_handlers.background import BgCommandHandler


class MyBgCommandHandler(BgCommandHandler):

    """Job submission class for use by test battery.

    Allow a background submission to have a job vacation signal.

    """

    VACATION_SIGNAL = "USR1"

    def get_vacation_signal(self, _):
        return self.VACATION_SIGNAL


BATCH_SYS_HANDLER = MyBgCommandHandler()
