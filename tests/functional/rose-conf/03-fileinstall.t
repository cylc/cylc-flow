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
#-------------------------------------------------------------------------------
# Test that fileinstall section of rose-suite.conf causes files to be
# installed.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
python -c "import cylc.rose" > /dev/null 2>&1 ||
  skip_all "cylc.rose not installed in environment."

set_test_number 3

# make new source dir 
SOURCE_DIR="${PWD}/cylc-source-dir"
mkdir "${SOURCE_DIR}"
cp -r "${TEST_SOURCE_DIR}/${TEST_NAME_BASE}" "${SOURCE_DIR}/03-fileinstall"
sed -i "s@REPLACE_THIS@${CYLC_REPO_DIR}/tests/functional/rose-conf/fileinstall_data@g" "${SOURCE_DIR}/03-fileinstall/rose-suite.conf"
SUITE_NAME="cylctb-${CYLC_TEST_TIME_INIT}/${TEST_SOURCE_DIR_BASE}"
SUITE_RUN_DIR="${RUN_DIR}/${SUITE_NAME}/03-fileinstall"
run_ok "{TEST_NAME_BASE}-install" cylc install --no-run-name --flow-name="${SUITE_NAME}/03-fileinstall" --directory="${SOURCE_DIR}/03-fileinstall"

# Test that data files have been concatenated.
DATA_INSTALLED_PATH="${SUITE_RUN_DIR}/data"
DATA_ORIGIN_PATH="${CYLC_REPO_DIR}/tests/functional/rose-conf/fileinstall_data/"
if [[ $(cat "${DATA_ORIGIN_PATH}randoms1.data"; cat "${DATA_ORIGIN_PATH}randoms3.data") == $(cat "${DATA_INSTALLED_PATH}") ]]; then
  ok "${TEST_NAME_BASE}.File installed from wildcards name."
else
  fail "${TEST_NAME_BASE}.File not installed from wildcards name."
fi

# Test that lion.py has been installed in a sub directory.
LION_INSTALLED_PATH="${SUITE_RUN_DIR}/lib/python/lion.py"
LION_ORIGIN_PATH="${CYLC_REPO_DIR}/tests/functional/rose-conf/fileinstall_data/lion.py"
if [[ $(cat "${LION_INSTALLED_PATH}") == $(cat "${LION_ORIGIN_PATH}") ]]; then
  ok "${TEST_NAME_BASE}.File installed to subfolder"
else
  fail "${TEST_NAME_BASE}.File not installed to subfolder"
fi

purge
exit
