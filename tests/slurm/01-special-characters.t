#!/bin/bash
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
#-------------------------------------------------------------------------------
# Test that we can use valid characters in SLURM. Examples are task names,
# workflow names, xtriggers, etc.
# Ref:
#  - https://slurm.schedmd.com/sbatch.html#lbAH
#  - https://github.com/cylc/cylc-flow/pull/3531
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
if [[ -z "${CYLC_TEST_BATCH_SLURM+x}" || -z "${CYLC_TEST_BATCH_SLURM}" || "${CYLC_TEST_BATCH_SLURM}" == None ]]
then
    skip_all "no slurm installation"
fi
#-------------------------------------------------------------------------------
set_test_number 1
#-------------------------------------------------------------------------------
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
suite_run_ok "${TEST_NAME}" cylc run --no-detach "${SUITE_NAME}"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"

exit
