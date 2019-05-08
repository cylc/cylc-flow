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
"""Suite status constants."""

# Keys for identify API call
KEY_GROUP = "group"
KEY_META = "meta"
KEY_NAME = "name"
KEY_OWNER = "owner"
KEY_STATES = "states"
KEY_TASKS_BY_STATE = "tasks-by-state"
KEY_UPDATE_TIME = "update-time"
KEY_VERSION = "version"

# Suite status strings.
SUITE_STATUS_HELD = "held"
SUITE_STATUS_RUNNING = "running"
SUITE_STATUS_STOPPING = "stopping"
SUITE_STATUS_RUNNING_TO_STOP = "running to stop at %s"
SUITE_STATUS_RUNNING_TO_HOLD = "running to hold at %s"

# Pseudo status strings for use by suite monitors.
#   Use before attempting to determine status:
SUITE_STATUS_NOT_CONNECTED = "not connected"
#   Use prior to first status update:
SUITE_STATUS_CONNECTED = "connected"
SUITE_STATUS_INITIALISING = "initialising"
#   Use when the suite is not running:
SUITE_STATUS_STOPPED = "stopped"
SUITE_STATUS_STOPPED_WITH = "stopped with '%s'"
