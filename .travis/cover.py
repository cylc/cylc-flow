#!/usr/bin/env python2

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

import sys

from subprocess import call


def main():
    # Run tests with virtual frame buffer for X support.
    if call('xvfb-run -a cylc test-battery --chunk $CHUNK --state=save -j 5',
            shell=True) != 0:
        # Non-zero return code
        sys.stderr.write('\n\nRerunning Failed Tests...\n\n')
        # Exit with final return code
        sys.exit(call('cylc test-battery --state=failed -j 5', shell=True))


if __name__ == '__main__':
    main()
