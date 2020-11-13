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

#------------------------------------------------------------------------------
# Test suite registration

export RND_SUITE_NAME
export RND_SUITE_SOURCE
export RND_SUITE_RUNDIR

function make_rnd_suite() {
    # Create a randomly-named suite source directory.
    # Define its run directory.
    RND_SUITE_NAME=x$(< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c6)
    RND_SUITE_SOURCE="$PWD/${RND_SUITE_NAME}"
    mkdir -p "${RND_SUITE_SOURCE}"
    touch "${RND_SUITE_SOURCE}/flow.cylc"
    RND_SUITE_RUNDIR="${RUN_DIR}/${RND_SUITE_NAME}"
}

function purge_rnd_suite() {
    # Remove the suite source created by make_rnd_suite().
    # And remove its run-directory too.
    RND_SUITE_SOURCE=${1:-$RND_SUITE_SOURCE}
    RND_SUITE_RUNDIR=${2:-$RND_SUITE_RUNDIR}
    rm -rf "${RND_SUITE_SOURCE}"
    rm -rf "${RND_SUITE_RUNDIR}"
}

. "$(dirname "$0")/test_header"
set_test_number 24

# Use $SUITE_NAME and $SUITE_RUN_DIR defined by test_header

#------------------------------
# Test fail no suite source dir
TEST_NAME="${TEST_NAME_BASE}-nodir"
make_rnd_suite
rm -rf "${RND_SUITE_SOURCE}"
run_fail "${TEST_NAME}" cylc register "${RND_SUITE_NAME}" "${RND_SUITE_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
SuiteServiceFileError: no flow.cylc or suite.rc in ${RND_SUITE_SOURCE}
__ERR__
purge_rnd_suite

#---------------------------
# Test fail no flow.cylc file
TEST_NAME="${TEST_NAME_BASE}-nodir"
make_rnd_suite
rm -f "${RND_SUITE_SOURCE}/flow.cylc"
run_fail "${TEST_NAME}" cylc register "${RND_SUITE_NAME}" "${RND_SUITE_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
SuiteServiceFileError: no flow.cylc or suite.rc in ${RND_SUITE_SOURCE}
__ERR__
purge_rnd_suite

#-------------------------------------------------------
# Test default name: "cylc reg" (suite in $PWD, no args)
TEST_NAME="${TEST_NAME_BASE}-pwd1"
make_rnd_suite
pushd "${RND_SUITE_SOURCE}" || exit 1
run_ok "${TEST_NAME}" cylc register
contains_ok "${TEST_NAME}.stdout" <<__OUT__
REGISTERED $RND_SUITE_NAME -> ${RND_SUITE_SOURCE}
__OUT__
popd || exit 1
purge_rnd_suite

#--------------------------------------------------
# Test default path: "cylc reg REG" (suite in $PWD)
TEST_NAME="${TEST_NAME_BASE}-pwd2"
make_rnd_suite
pushd "${RND_SUITE_SOURCE}" || exit 1
run_ok "${TEST_NAME}" cylc register "${RND_SUITE_NAME}"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
REGISTERED ${RND_SUITE_NAME} -> ${RND_SUITE_SOURCE}
__OUT__
popd || exit 1
purge_rnd_suite

#-------------------------
# Test "cylc reg REG PATH"
TEST_NAME="${TEST_NAME_BASE}-normal"
make_rnd_suite
run_ok "${TEST_NAME}" cylc register "${RND_SUITE_NAME}" "${RND_SUITE_SOURCE}"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
REGISTERED ${RND_SUITE_NAME} -> ${RND_SUITE_SOURCE}
__OUT__
purge_rnd_suite

#--------------------------------------------------------------------
# Test register existing run directory: "cylc reg REG ~/cylc-run/REG"
TEST_NAME="${TEST_NAME_BASE}-reg-run-dir"
make_rnd_suite
mkdir -p "${RND_SUITE_RUNDIR}"
cp "${RND_SUITE_SOURCE}/flow.cylc" "${RND_SUITE_RUNDIR}"
run_ok "${TEST_NAME}" cylc register "${RND_SUITE_NAME}" "${RND_SUITE_RUNDIR}"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
REGISTERED ${RND_SUITE_NAME} -> ${RND_SUITE_RUNDIR}
__OUT__
SOURCE="$(readlink "${RND_SUITE_RUNDIR}/.service/source")"
run_ok "${TEST_NAME}-source" test '..' = "${SOURCE}"
# Run it twice
run_ok "${TEST_NAME}-2" cylc register "${RND_SUITE_NAME}" "${RND_SUITE_RUNDIR}"
contains_ok "${TEST_NAME}-2.stdout" <<__OUT__
REGISTERED ${RND_SUITE_NAME} -> ${RND_SUITE_RUNDIR}
__OUT__
SOURCE="$(readlink "${RND_SUITE_RUNDIR}/.service/source")"
run_ok "${TEST_NAME}-source" test '..' = "${SOURCE}"
purge_rnd_suite

#----------------------------------------------------------------
# Test fail "cylc reg REG PATH" where REG already points to PATH2
TEST_NAME="${TEST_NAME_BASE}-dup1"
make_rnd_suite
run_ok "${TEST_NAME}" cylc register "${RND_SUITE_NAME}" "${RND_SUITE_SOURCE}"
RND_SUITE_NAME1="${RND_SUITE_NAME}"
RND_SUITE_SOURCE1="${RND_SUITE_SOURCE}"
RND_SUITE_RUNDIR1="${RND_SUITE_RUNDIR}"
make_rnd_suite
TEST_NAME="${TEST_NAME_BASE}-dup2"
run_fail "${TEST_NAME}" cylc register "${RND_SUITE_NAME1}" "${RND_SUITE_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
SuiteServiceFileError: the name '${RND_SUITE_NAME1}' already points to ${RND_SUITE_SOURCE1}.
Use --redirect to re-use an existing name and run directory.
__ERR__
# Now force it
TEST_NAME="${TEST_NAME_BASE}-dup3"
run_ok "${TEST_NAME}" cylc register --redirect "${RND_SUITE_NAME1}" "${RND_SUITE_SOURCE}"
sed -i 's/^\t//; s/^.* WARNING - /WARNING - /' "${TEST_NAME}.stderr"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
WARNING - the name '${RND_SUITE_NAME1}' points to ${RND_SUITE_SOURCE1}.
It will now be redirected to ${RND_SUITE_SOURCE}.
Files in the existing ${RND_SUITE_NAME1} run directory will be overwritten.
__ERR__
contains_ok "${TEST_NAME}.stdout" <<__OUT__
REGISTERED ${RND_SUITE_NAME1} -> ${RND_SUITE_SOURCE}
__OUT__

TEST_NAME="${TEST_NAME_BASE}-get-dir"
run_ok "${TEST_NAME}" cylc get-directory "${RND_SUITE_NAME1}"
contains_ok "${TEST_NAME}.stdout" <<__ERR__
${RND_SUITE_SOURCE}
__ERR__

purge_rnd_suite
purge_rnd_suite "${RND_SUITE_SOURCE1}" "${RND_SUITE_RUNDIR1}"

exit
