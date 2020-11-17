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
# Test jinja2 from rose-suite.conf file is processed into a suite.
. "$(dirname "$0")/test_header"
#-------------------------------------------------------------------------------
python -c "import cylc.rose" > /dev/null 2>&1 ||
  skip_all "cylc.rose not installed in environment."

set_test_number 3
install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

sed -i "s@REPLACE_THIS@${CYLC_REPO_DIR}/tests/functional/rose-conf/fileinstall_data@g" rose-suite.conf


run_ok "${TEST_NAME_BASE}-validate" cylc install "${SUITE_NAME}"

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
