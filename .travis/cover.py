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

import os
from subprocess import call
import sys


def main():
    """Run tests with virtual frame buffer for X support."""
    command = [
        'xvfb-run',
        '-a',
        os.path.join(
            os.path.dirname(__file__),
            '..',
            'etc',
            'bin',
            'run-functional-tests.sh',
        ),
    ]
    flakytests = os.getenv('FLAKYTESTS')
    if flakytests:
        command.append(flakytests)
        command.append('--jobs=1')
    else:
        command.append('--jobs=5')
    # Safe here - only used in Travis CI for tests with predefined environment
    sys.exit(call(command, stdin=open(os.devnull)))  # nosec


if __name__ == '__main__':
    main()
