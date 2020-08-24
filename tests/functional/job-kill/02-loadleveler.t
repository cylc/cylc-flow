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
# Test killing of jobs submitted to loadleveler, slurm, pbs...
# TODO Check this test on a dockerized system or VM.
BATCH_SYS_NAME="${TEST_NAME_BASE##}"
export REQUIRE_PLATFORM="batch:$BATCH_SYS_NAME comms:tcp"
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
set_test_number 2

create_test_global_config "" "
[platforms]
  [[${BATCH_SYS_NAME}-test-platform]]
    hosts = ${CYLC_TEST_BATCH_TASK_HOST}
    batch system = ${BATCH_SYS_NAME}
"

reftest
purge_remote_platform "${CYLC_TEST_PLATFORM}" "${SUITE_NAME}"
exit
