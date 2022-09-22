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

# Check undefined $HOME does not break:
# a) use of $HOME in global config (GitHub #2895)
# b) global config Jinja2 support (GitHub #5155)

. "$(dirname "$0")/test_header"
set_test_number 5

# shellcheck disable=SC2016
create_test_global_config '' '
[install]
    [[symlink dirs]]
        [[[localhost]]]
            run = $HOME/dr-malcolm
'
run_ok "${TEST_NAME_BASE}" \
    env -u HOME \
    cylc config --item='[install][symlink dirs][localhost]run'

cmp_ok "${TEST_NAME_BASE}.stdout" <<<"\$HOME/dr-malcolm"

# The test global config is created with #!Jinja2 at the top, in case of any
# Jinja2 code in global-tests.cylc. Parsec Jinja2 support uses $HOME to find
# custom filters etc. GitHub #5155.
for DIR in Filters Tests Globals; do
    grep_ok "\$HOME undefined: can't load ~/.cylc/Jinja2$DIR" "${TEST_NAME_BASE}.stderr"
done
