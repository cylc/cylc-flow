#!/bin/bash
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
#-------------------------------------------------------------------------------
# Test "cylc refresh" on a running suite, with "title" changed in "suite.rc".
# It used to nuke the passphrase before https://github.com/cylc/cylc/pull/1774
# which would cause all subsequent clients (that require authentication) to
# fail. This test ensures that the problem will not happen again.
. "$(dirname "$0")/test_header"

set_test_number 3
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}"
run_ok "${TEST_NAME_BASE}" cylc run --reference-test --debug "${SUITE_NAME}"

cmp_ok "${HOME}/.cylc/REGDB/${SUITE_NAME}" <<__REG__
path=${TEST_DIR}/${SUITE_NAME}
title=Modified Title
__REG__

purge_suite "${SUITE_NAME}"
exit
