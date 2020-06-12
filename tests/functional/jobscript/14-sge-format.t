#!/bin/bash
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
# Test that SGE directives are formatted correctly. GitHub #2215
. "$(dirname "${0}")/test_header"
#-------------------------------------------------------------------------------
set_test_number 6
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"
#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-script"
run_ok "${TEST_NAME}" cylc jobscript "${SUITE_NAME}" foo.1
grep_ok "^#\$ -l h_rt=0:10:00$" "${TEST_NAME}.stdout"
grep_ok "^#\$ -l s_vmem=1G,s_cpu=60$" "${TEST_NAME}.stdout"
grep_ok "^#\$ -V$" "${TEST_NAME}.stdout"
grep_ok "^#\$ -q queuename$" "${TEST_NAME}.stdout"
#-------------------------------------------------------------------------------
purge_suite "${SUITE_NAME}"
exit
