# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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

from cylc.flow.cfgspec.globalcfg import SPEC
from cylc.flow.parsec.config import ParsecConfig
import cylc.flow.flags

# parse:
sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))
# cylc:
sys.path.append(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))

cylc.flow.flags.verbosity = 1


class Testcfg(ParsecConfig):

    def check(self, sparse):
        # TEMPORARY EXAMPLE
        if 'missing item' not in list(self.sparse):
            print("missing item is MISSING!!!!")


cfg = Testcfg(SPEC)
strict = False
cfg.loadcfg(os.path.join(os.path.dirname(__file__), 'site.cylc'))
cfg.loadcfg(os.path.join(os.path.dirname(__file__), 'user.cylc'))

cfg.dump()
cfg.dump(['list values'])
cfg.dump(['list values', 'integers'])
cfg.dump(['single values', 'strings with internal comments'])
