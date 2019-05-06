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

# When we run cylc commands, there are processes being forked, that get a
# new working directory. As .coveragerc contains relatives paths, it fails
# to produce the correct coverage, unless we use absolute paths. The `sed`
# call below tries to define the data_file, and sources locations for Travis.
sed -e "s|data_file=.coverage|data_file=${TRAVIS_BUILD_DIR}/.coverage|g; s|./bin|${TRAVIS_BUILD_DIR}/bin|g; s|\./cylc|${TRAVIS_BUILD_DIR}/cylc|g" .coveragerc > /tmp/.coveragerc
# And some tests fail if we touch files in the git working directory, due
# to Cylc's version appearing with the "dirty" suffix. To avoid this, we
# are using a new coveragerc created under the temporary directory.
