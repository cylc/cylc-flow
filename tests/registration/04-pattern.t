#!/bin/bash
# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
# Test unregister suite with similar names.

. "$(dirname "$0")/test_header"
set_test_number 24

mkdir 'foo' 'bar' 'foobar' 'barfoo'
UUID="$(uuidgen)"
for NAME in 'foo' 'bar' 'foobar' 'barfoo'; do
    cat >"${NAME}/suite.rc" <<'__SUITERC__'
[scheduling]
    [[dependencies]]
        graph = t1
[runtime]
    [[t1]]
        script = true
__SUITERC__
    cylc register "${UUID}-${NAME}" "${PWD}/${NAME}" 1>'/dev/null'
    cylc register "${NAME}-${UUID}" "${PWD}/${NAME}" 1>'/dev/null'
done

for NAME in 'foo' 'bar' 'foobar' 'barfoo'; do
    run_ok "${TEST_NAME_BASE}-${UUID}-${NAME}" cylc unregister "${UUID}-${NAME}"
    cmp_ok "${TEST_NAME_BASE}-${UUID}-${NAME}.stdout" <<__OUT__
UNREGISTER ${UUID}-${NAME}:${PWD}/${NAME}
1 suite(s) unregistered.
__OUT__
    cmp_ok "${TEST_NAME_BASE}-${UUID}-${NAME}.stderr" <'/dev/null'

    run_ok "${TEST_NAME_BASE}-${NAME}-${UUID}" cylc unregister "${NAME}-${UUID}"
    cmp_ok "${TEST_NAME_BASE}-${NAME}-${UUID}.stdout" <<__OUT__
UNREGISTER ${NAME}-${UUID}:${PWD}/${NAME}
1 suite(s) unregistered.
__OUT__
    cmp_ok "${TEST_NAME_BASE}-${NAME}-${UUID}.stderr" <'/dev/null'
done

exit
