#!/usr/bin/env bash
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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

#------------------------------------------------------------------------------
# Test workflow installation
. "$(dirname "$0")/test_header"
set_test_number 7

cat > flow.cylc <<__HEREDOC__
[scheduler]
    allow implicit tasks = true
[scheduling]
    [[graph]]
        R1 = foo
__HEREDOC__

run_ok "$TEST_NAME_BASE" cylc validate "$PWD"/flow.cylc

UUID=$(uuidgen)

cylc install -C "$PWD" --flow-name "${UUID}/1"
run_fail "${TEST_NAME_BASE}-child" cylc install -C "$PWD" --flow-name "${UUID}/1/child"
# TODO check log message

cylc install -C "$PWD" --flow-name "${UUID}/1/child"
run_fail "${TEST_NAME_BASE}-parent" cylc install -C "$PWD" --flow-name "${UUID}/1/"
# TODO check log message

cylc install -C "$PWD" --flow-name "${UUID}/2"
run_fail "${TEST_NAME_BASE}-grandchild" cylc install -C "$PWD" --flow-name "${UUID}/2/child/grandchild"
# TODO check log message

cylc install -C "$PWD" --flow-name "${UUID}/2/child/grandchild"
run_fail "${TEST_NAME_BASE}-grandparent" cylc install -C "$PWD" --flow-name "${UUID}2/"
# TODO check log message

cylc install -C "$PWD" --flow-name "${UUID}/3"
run_fail "${TEST_NAME_BASE}-Nth-child" cylc install -C "$PWD" --flow-name "${UUID}/3/i/cant/believe/how/deep/this/path/is"
# TODO check log message

cylc install -C "$PWD" --flow-name "${UUID}/3/i/cant/believe/how/deep/this/path/is"
run_fail "${TEST_NAME_BASE}-Nth-parent" cylc install -C "$PWD" --flow-name "${UUID}/3"
# TODO check log message



tree "$RUN_DIR/${UUID}/top" >&2

rm -fr "${RUN_DIR}/${UUID}"

exit
