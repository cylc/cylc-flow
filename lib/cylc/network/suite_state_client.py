#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
"""Wrap communications daemon for a suite."""

from cylc.network.method import METHOD

if METHOD == "https" or "http":
    from cylc.network.https.suite_state_client import (
        StateSummaryClient, extract_group_state,
        get_id_summary, SUITE_STATUS_SPLIT_REC,
        SUITE_STATUS_NOT_CONNECTED, SUITE_STATUS_CONNECTED,
        SUITE_STATUS_INITIALISING, SUITE_STATUS_STOPPED, SUITE_STATUS_STOPPING,
        SUITE_STATUS_STOPPED_WITH
    )
