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
# Test loadleveler directives
#     This test requires an e.g. [test battery][batch systems][loadleveler]host
#     entry in site/user config in order to run 'loadleveler' tests (same for
#     slurm, pbs, etc), otherwise it will be bypassed.
BATCH_SYS_NAME="$(sed 's/.*\/...\(.*\)\.t/\1/' <<< "$0")"
export REQUIRE_PLATFORM="batch:$BATCH_SYS_NAME comms:tcp"
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 2
reftest "${TEST_NAME_BASE}" "${BATCH_SYS_NAME}"
purge
exit
