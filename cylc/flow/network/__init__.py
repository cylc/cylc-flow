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

"""Cylc networking code.

Contains:
* Server code (hosted by the scheduler process).
* Client implementations (used to communicate with the scheduler).
* Workflow scanning logic.
* Schema and interface definitions.
"""

# Cylc API version.
# This is the Cylc protocol version number that determines whether a client can
# communicate with a server. This should be changed when breaking changes are
# made for which backwards compatibility can not be provided.
API = 5
