#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
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
#-------------------------------------------------------------------------------
# Test "cylc cat-log" for viewing PBS runtime STDOUT/STDERR by a custom command
export REQUIRE_PLATFORM='runner:pbs'
. "$(dirname "$0")/test_header"

OUT_VIEWER="$(cylc get-global-config -i \
    "[platforms][$CYLC_TEST_PLATFORM]out viewer")"
ERR_VIEWER="$(cylc get-global-config -i \
    "[platforms][$CYLC_TEST_PLATFORM]err viewer")"
if [[ -z "${ERR_VIEWER}" || -z "${OUT_VIEWER}" ]]; then
    skip_all 'remote viewers not configured for this platform'
fi
set_test_number 2
reftest
purge
exit
