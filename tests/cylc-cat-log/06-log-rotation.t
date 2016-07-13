#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2016 NIWA
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
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 1
#-------------------------------------------------------------------------------
# Tests that cylc cat-log correctly handes log rotation.

# Create dummy suite.
TMP_DIR=$(mktemp -d)
SUITE_NAME="$(basename ${TMP_DIR})-cat-log"
echo '' >> $TMP_DIR/suite.rc
cylc register ${SUITE_NAME} ${TMP_DIR}

# Populate its cylc-run dir with empty log files.
LOG_DIR=$(dirname $(cylc cat-log ${SUITE_NAME} -l))
mkdir -p ${LOG_DIR}
touch $LOG_DIR/out.20000103T00Z
touch $LOG_DIR/out.20000102T00Z
touch $LOG_DIR/out.20000101T00Z
touch $LOG_DIR/out.0  # Back compatability to old log rotation system.
touch $LOG_DIR/out.1
touch $LOG_DIR/out.2

# Test log rotation.
cylc cat-log ${SUITE_NAME} -o -l -r 0 |xargs basename >> "$TMP_DIR/result"
cylc cat-log ${SUITE_NAME} -o -l -r 1 |xargs basename >> "$TMP_DIR/result"
cylc cat-log ${SUITE_NAME} -o -l -r 2 |xargs basename >> "$TMP_DIR/result"
cylc cat-log ${SUITE_NAME} -o -l -r 3 |xargs basename >> "$TMP_DIR/result"
cylc cat-log ${SUITE_NAME} -o -l -r 4 |xargs basename >> "$TMP_DIR/result"
cylc cat-log ${SUITE_NAME} -o -l -r 5 |xargs basename >> "$TMP_DIR/result"
cylc unregister ${SUITE_NAME}
cmp_ok "$TMP_DIR/result" <<__CMP__
out.20000103T00Z
out.20000102T00Z
out.20000101T00Z
out.0
out.1
out.2
__CMP__
#-------------------------------------------------------------------------------
# Tidy up.
#rm -rf $TMP_DIR
#rm -rf $LOG_DIR
echo $TMP_DIR
echo $LOG_DIR
#-------------------------------------------------------------------------------
