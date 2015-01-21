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
# Test "cylc reregister" and passphrase creation.
# See https://github.com/cylc/cylc/pull/1009
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 1
#-------------------------------------------------------------------------------
SUITE_NAME=$(date -u +%Y%m%dT%H%M%SZ)-cylc-test-registration-01-reregister-passphrase
cp -r $TEST_SOURCE_DIR/basic/* .
cylc unregister "$SUITE_NAME-0" 1>/dev/null 2>&1 || true
cylc unregister "$SUITE_NAME-1" 1>/dev/null 2>&1 || true

cylc register "$SUITE_NAME-0" "$PWD"
cylc reregister "$SUITE_NAME-0" "$SUITE_NAME-1"

exists_ok passphrase

cylc unregister "$SUITE_NAME-0" 1>/dev/null 2>&1 || true
cylc unregister "$SUITE_NAME-1"
#-------------------------------------------------------------------------------
exit
