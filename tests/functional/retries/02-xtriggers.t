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
# Test kill running jobs only
. "$(dirname "$0")/test_header"
set_test_number 2
reftest

# install the cylc7 restart database
cp "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}/.service/db" \
    "${HOME}/cylc-run/${SUITE_NAME}/.service/db"

run_ok "${TEST_NAME_BASE}-run" cylc restart "${SUITE_NAME}"

FILE="$(cylc cat-log "${SUITE_NAME}" -m p)"
log_scan "${TEST_NAME_BASE}-retries" "${FILE}" 30 0.5 \
    '(upgrading retrying state for b.1)' \
    'xtrigger satisfied: cylc_retry_b.1' \
    '\[b.1\] -submit-num=02' \
    '\[b.1\] status=running: (received)failed/EXIT.*job(02)' \
    '\[b.1\] -job(02) failed, retrying in PT2S' \
    'xtrigger satisfied: cylc_retry_b.1' \
    '\[b.1\] -submit-num=03' \
    '\[b.1] status=running: (received)succeeded' \
    '\[c.1] status=running: (received)succeeded'

purge
exit
