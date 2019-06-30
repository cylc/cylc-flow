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
#------------------------------------------------------------------------------
# Test suite registration

. "$(dirname "$0")/test_header"
set_test_number 34

init_suite "${TEST_NAME_BASE}" <<'__SUITE_RC__'
[meta]
    title = the quick brown fox
[scheduling]
    [[dependencies]]
        graph = a => b => c
[runtime]
    [[a,b,c]]
        script = true
__SUITE_RC__

# Unique suite run-dir prefix to avoid messing with real suites.
PRE=cylctb-${CYLC_TEST_TIME_INIT}

# Test fail no suite.rc file.
CYLC_RUN_DIR=$(cylc get-global --print-run-dir)
TEST_NAME="${TEST_NAME_BASE}-noreg"
run_fail "${TEST_NAME}" cylc register "${SUITE_NAME}" "${PWD}/zilch"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
ERROR: no suite.rc in ${PWD}/zilch
__ERR__

CHEESE=${PRE}-cheese
# Test default name: "cylc reg" (suite in $PWD, no args)
TEST_NAME="${TEST_NAME_BASE}-cheese"
mkdir $CHEESE
cd $CHEESE
touch suite.rc
run_ok "${TEST_NAME}" cylc register
contains_ok "${TEST_NAME}.stdout" <<__OUT__
REGISTERED $CHEESE -> ${PWD}
__OUT__
cd ..
rm -rf "${CYLC_RUN_DIR}/$CHEESE"

# Test default name: "cylc reg REG" (suite in $PWD)
TEST_NAME="${TEST_NAME_BASE}-toast"
cd $CHEESE
TOAST=${PRE}-toast
run_ok "${TEST_NAME}" cylc register $TOAST
contains_ok "${TEST_NAME}.stdout" <<__OUT__
REGISTERED $TOAST -> ${PWD}
__OUT__
cd ..
rm -rf "${CYLC_RUN_DIR}/$TOAST"

# Test "cylc reg REG PATH"
TEST_NAME="${TEST_NAME_BASE}-bagels"
BAGELS=${PRE}-bagels
run_ok "${TEST_NAME}" cylc register $BAGELS $CHEESE
contains_ok "${TEST_NAME}.stdout" <<__OUT__
REGISTERED $BAGELS -> ${PWD}/$CHEESE
__OUT__
rm -rf "${CYLC_RUN_DIR}/$BAGELS"

# Test "cylc reg REG ~/cylc-run/REG"
TEST_NAME="${TEST_NAME_BASE}-onion"
ONION="${PRE}-onion"
mkdir -p "${CYLC_RUN_DIR}/${ONION}"
cp -p "${PWD}/suite.rc" "${CYLC_RUN_DIR}/${ONION}/"
run_ok "${TEST_NAME}" cylc register "${ONION}" "${CYLC_RUN_DIR}/${ONION}"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
REGISTERED ${ONION} -> ${CYLC_RUN_DIR}/${ONION}
__OUT__
SOURCE="$(readlink "${CYLC_RUN_DIR}/${ONION}/.service/source")"
run_ok "${TEST_NAME}-source" test '..' = "${SOURCE}"
# Run it twice
run_ok "${TEST_NAME}-2" cylc register "${ONION}" "${CYLC_RUN_DIR}/${ONION}"
contains_ok "${TEST_NAME}-2.stdout" <<__OUT__
REGISTERED ${ONION} -> ${CYLC_RUN_DIR}/${ONION}
__OUT__
SOURCE="$(readlink "${CYLC_RUN_DIR}/${ONION}/.service/source")"
run_ok "${TEST_NAME}-2-source" test '..' = "${SOURCE}"
rm -rf "${CYLC_RUN_DIR}/${ONION}"

# Test fail "cylc reg REG PATH" where REG already points to PATH2
YOGHURT=${PRE}-YOGHURT
cp -r $CHEESE $YOGHURT
TEST_NAME="${TEST_NAME_BASE}-cheese"
run_ok "${TEST_NAME}" cylc register $CHEESE $CHEESE
TEST_NAME="${TEST_NAME_BASE}-repurpose1"
run_fail "${TEST_NAME}" cylc register $CHEESE $YOGHURT
contains_ok "${TEST_NAME}.stderr" <<__ERR__
ERROR: the name '$CHEESE' already points to ${PWD}/$CHEESE.
Use --redirect to re-use an existing name and run directory.
__ERR__

# Test succeed "cylc reg REG PATH" where REG already points to PATH2
TEST_NAME="${TEST_NAME_BASE}-repurpose2"
cp -r $CHEESE $YOGHURT
run_ok "${TEST_NAME}" cylc register --redirect $CHEESE $YOGHURT
sed -i 's/^\t//; s/^.* WARNING - /WARNING - /' "${TEST_NAME}.stderr"
contains_ok "${TEST_NAME}.stderr" <<__ERR__
WARNING - the name '$CHEESE' points to ${PWD}/$CHEESE.
It will now be redirected to ${PWD}/$YOGHURT.
Files in the existing $CHEESE run directory will be overwritten.
__ERR__
contains_ok "${TEST_NAME}.stdout" <<__OUT__
REGISTERED $CHEESE -> ${PWD}/$YOGHURT
__OUT__
rm -rf "${CYLC_RUN_DIR}/$CHEESE"

run_ok "${TEST_NAME_BASE}-get-dir" cylc get-directory "${SUITE_NAME}"

cd .. # necessary so the suite is being validated via the database not filepath
run_ok "${TEST_NAME_BASE}-val" cylc validate "${SUITE_NAME}"
cd "${OLDPWD}"

run_ok "${TEST_NAME_BASE}-print" cylc print
contains_ok "${TEST_NAME_BASE}-print.stdout" <<__OUT__
${SUITE_NAME} | the quick brown fox | ${TEST_DIR}/${SUITE_NAME}
__OUT__

# Filter out errors from 'bad' suites in the 'cylc-run' directory
NONSPECIFIC_ERR2='\[Errno 2\] No such file or directory:'
SPECIFIC_ERR2="$NONSPECIFIC_ERR2 '$HOME/cylc-run/$SUITE_NAME/suite.rc'"
ERR2_COUNT=$(grep -c "$SPECIFIC_ERR2" "${TEST_NAME_BASE}-print.stderr")
if [ "$ERR2_COUNT" -eq "0" ]; then
    grep -v -s "$NONSPECIFIC_ERR2" "${TEST_NAME_BASE}-print.stderr" > "${TEST_NAME_BASE}-print-filtered.stderr"
    cmp_ok "${TEST_NAME_BASE}-print-filtered.stderr" <'/dev/null'
else
    fail "${TEST_NAME_BASE}-print.stderr"
fi

# Test alternate run dir.
# 1. Normal case.
TEST_NAME="${TEST_NAME_BASE}-alt-run-dir"
SRC_DIR="${PWD}/foo"
REG="${PRE}/foo"
RUN_DIR="${CYLC_RUN_DIR}/${REG}"
ALT_RUN_DIR="${PWD}/alt"
mkdir "${SRC_DIR}"; touch "${SRC_DIR}/suite.rc"
run_ok "${TEST_NAME}" cylc register --run-dir="${ALT_RUN_DIR}" "${REG}" "${SRC_DIR}"
contains_ok "${TEST_NAME}.stdout" <<__OUT__
REGISTERED ${REG} -> ${SRC_DIR}
__OUT__
run_ok "${TEST_NAME}-check-link" test -L "${RUN_DIR}"
run_ok "${TEST_NAME}-rm-link" rm "${RUN_DIR}"
run_ok "${TEST_NAME}-rm-alt-run-dir" rm -r "${ALT_RUN_DIR}"
rm -r "${SRC_DIR}"

# Test alternate run dir.
# 2. If reg already exists (as a directory).
TEST_NAME="${TEST_NAME_BASE}-alt-exists1"
mkdir "${RUN_DIR}"
mkdir "${SRC_DIR}"; touch "${SRC_DIR}/suite.rc"
run_fail "${TEST_NAME}" cylc register --run-dir="${ALT_RUN_DIR}" "${REG}" "${SRC_DIR}"
contains_ok "${TEST_NAME}.stderr" <<__OUT__
Run directory '${RUN_DIR}' already exists.
__OUT__
rm -r $SRC_DIR ${RUN_DIR}

# Test alternate run dir.
# 3. If reg already exists (as a valid symlink).
TEST_NAME="${TEST_NAME_BASE}-alt-exists2"
mkdir "${SRC_DIR}"; touch "${SRC_DIR}/suite.rc"
mkdir "${PWD}/target"
ln -s "${PWD}/target" "${RUN_DIR}"
run_fail "${TEST_NAME}" cylc register --run-dir="${ALT_RUN_DIR}" "${REG}" "${SRC_DIR}"
contains_ok "${TEST_NAME}.stderr" <<__OUT__
Symlink '${RUN_DIR}' already points to ${PWD}/target.
__OUT__
rm -r "${SRC_DIR}" "${PWD}/target" "${CYLC_RUN_DIR}/${PRE}"

purge_suite "${SUITE_NAME}"
exit
