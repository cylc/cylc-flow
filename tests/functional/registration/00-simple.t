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
export CYLC_RUN_DIR

CYLC_RUN_DIR="$(cylc get-global-config --print-run-dir)"

function make_rnd_suite() {
    # Create a randomly-named suite source directory.
    # Define its run directory.
    RND_SUITE_NAME=x$(< /dev/urandom tr -dc _A-Z-a-z-0-9 | head -c6)
    RND_SUITE_SOURCE="$PWD/${RND_SUITE_NAME}"
    mkdir -p "${RND_SUITE_SOURCE}"
    touch "${RND_SUITE_SOURCE}/suite.rc"
    RND_SUITE_RUNDIR="${CYLC_RUN_DIR}/${RND_SUITE_NAME}"
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
set_test_number 37

# Use $SUITE_NAME and $SUITE_RUN_DIR defined by test_header

#------------------------------
# Test fail no suite source dir
TEST_NAME="${TEST_NAME_BASE}-nodir"
make_rnd_suite
rm -rf "${RND_SUITE_SOURCE}"
run_fail "${TEST_NAME}" cylc register "${RND_SUITE_NAME}" "${RND_SUITE_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
SuiteServiceFileError: no suite.rc in ${RND_SUITE_SOURCE}
__ERR__
purge_rnd_suite

#---------------------------
# Test fail no suite.rc file
TEST_NAME="${TEST_NAME_BASE}-nodir"
make_rnd_suite
rm -f "${RND_SUITE_SOURCE}/suite.rc"
run_fail "${TEST_NAME}" cylc register "${RND_SUITE_NAME}" "${RND_SUITE_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
SuiteServiceFileError: no suite.rc in ${RND_SUITE_SOURCE}
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
cp "${RND_SUITE_SOURCE}/suite.rc" "${RND_SUITE_RUNDIR}"
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

#-----------------------
# Test alternate run dir
# 1. Normal case.
TEST_NAME="${TEST_NAME_BASE}-alt-run-dir"
make_rnd_suite
ALT_RUN_DIR="${PWD}/alt"
run_ok "${TEST_NAME}" \
    cylc register --run-dir="${ALT_RUN_DIR}" "${RND_SUITE_NAME}" "${RND_SUITE_SOURCE}"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
REGISTERED ${RND_SUITE_NAME} -> ${RND_SUITE_SOURCE}
__OUT__
run_ok "${TEST_NAME}-check-link" test -L "${RND_SUITE_RUNDIR}"
run_ok "${TEST_NAME}-rm-link" rm "${RND_SUITE_RUNDIR}"
run_ok "${TEST_NAME}-rm-alt-run-dir" rm -r "${ALT_RUN_DIR}"
purge_rnd_suite

# 2. If reg already exists (as a directory).
TEST_NAME="${TEST_NAME_BASE}-alt-exists1"
make_rnd_suite
ALT_RUN_DIR="${PWD}/alt"
mkdir -p "${RND_SUITE_RUNDIR}"
run_fail "${TEST_NAME}" \
   cylc register --run-dir="${ALT_RUN_DIR}" "${RND_SUITE_NAME}" "${RND_SUITE_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__OUT__
SuiteServiceFileError: Run directory '${RND_SUITE_RUNDIR}' already exists.
__OUT__
purge_rnd_suite

# 3. If reg already exists (as a valid symlink).
TEST_NAME="${TEST_NAME_BASE}-alt-exists2"
make_rnd_suite
ALT_RUN_DIR="${PWD}/alt"
TDIR=$(mktemp -d)
mkdir -p "$(dirname "${RND_SUITE_RUNDIR}")"
ln -s "${TDIR}" "${RND_SUITE_RUNDIR}"
run_fail "${TEST_NAME}" \
    cylc register --run-dir="${ALT_RUN_DIR}" "${RND_SUITE_NAME}" "${RND_SUITE_SOURCE}"
contains_ok "${TEST_NAME}.stderr" <<__OUT__
SuiteServiceFileError: Symlink '${RND_SUITE_RUNDIR}' already points to ${TDIR}.
__OUT__
purge_rnd_suite
rm -rf "${TDIR}"

#-----------------------------------------------------------------------------
# Now use a real suite

init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
[meta]
    title = the quick brown fox
[scheduling]
    [[graph]]
        R1 = a => b => c
[runtime]
    [[a,b,c]]
        script = true
__SUITE_RC__

run_ok "${TEST_NAME_BASE}-val" cylc validate "${SUITE_NAME}"

run_ok "${TEST_NAME_BASE}-print" cylc print
contains_ok "${TEST_NAME_BASE}-print.stdout" <<__OUT__
${SUITE_NAME} | the quick brown fox | ${TEST_DIR}/${SUITE_NAME}
__OUT__

# Filter out errors from 'bad' suites in the 'cylc-run' directory
NONSPECIFIC_ERR2='\[Errno 2\] No such file or directory:'
SPECIFIC_ERR2="$NONSPECIFIC_ERR2 '$HOME/cylc-run/${SUITE_NAME}/suite.rc'"
ERR2_COUNT="$(grep -c "$SPECIFIC_ERR2" "${TEST_NAME_BASE}-print.stderr")"
if ((ERR2_COUNT == 0)); then
    grep -v -s "$NONSPECIFIC_ERR2" "${TEST_NAME_BASE}-print.stderr" > "${TEST_NAME_BASE}-print-filtered.stderr"
    cmp_ok "${TEST_NAME_BASE}-print-filtered.stderr" <'/dev/null'
else
    fail "${TEST_NAME_BASE}-print.stderr"
fi

purge_suite "${SUITE_NAME}"
exit
