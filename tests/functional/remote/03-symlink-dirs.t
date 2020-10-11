# #!/usr/bin/env bash
# # THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# # Copyright (C) NIWA & British Crown (Met Office) & Contributors.
# #
# # This program is free software: you can redistribute it and/or modify
# # it under the terms of the GNU General Public License as published by
# # the Free Software Foundation, either version 3 of the License, or
# # (at your option) any later version.
# #
# # This program is distributed in the hope that it will be useful,
# # but WITHOUT ANY WARRANTY; without even the implied warranty of
# # MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# # GNU General Public License for more details.
# #
# # You should have received a copy of the GNU General Public License
# # along with this program.  If not, see <http://www.gnu.org/licenses/>.
# #-------------------------------------------------------------------------------
# # Checks configured symlinks are created for run, work, share, share/cycle, log 
# # directories on the remote platform.
# . "$(dirname "$0")/test_header"
# require_remote_platform
# set_test_number 1

# CONFIG="[symlink dirs][${CYLC_TEST_PLATFORM}]"
# SYMLINK_DIRS=$(cylc get-global-config -i ${CONFIG} >&2)
# if [[ -z "${SYMLINK_DIRS}" ]]; then
# skip_all "\"[symlink dirs][${CYLC_TEST_PLATFORM}]\": not defined"
# fi 
# create_test_global_config "" "
#     [platforms]
#         [[${CYLC_TEST_PLATFORM}]]
#             retrieve job logs = True
#             retrieve job logs retry delays = PT5S
#             install target = ${CYLC_TEST_HOST}
#      [symlink dirs]
#          [[${CYLC_TEST_HOST}]]
#             echo ${SYMLINK_DIRS}
# "
# install_suite "${TEST_NAME_BASE}"

# run_ok "${TEST_NAME_BASE}-validate" cylc validate "${SUITE_NAME}" \
#      -s "CYLC_TEST_PLATFORM=${CYLC_TEST_PLATFORM}"
