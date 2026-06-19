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
"""Test set for the filter_keys function.

Tests a series of different keys to evaluate whether they get the correct
possible output.
"""

import pytest

from cylc.flow.parsec.util import filter_keys


# A real example of a list of 40 possible keys
REAL_TEST_DATA: list[str] = ['completion', 'platform', 'inherit', 'script',
                             'init-script', 'env-script', 'err-script',
                             'exit-script', 'pre-script', 'post-script',
                             'work sub-directory',
                             'execution polling intervals',
                             'execution retry delays', 'execution time limit',
                             'submission polling intervals',
                             'submission retry delays', 'run mode', 'meta',
                             'skip', 'simulation', 'environment filter', 'job',
                             'remote', 'events', 'mail',
                             'workflow state polling', 'environment',
                             'directives', 'outputs',
                             'parameter environment templates']


# The list of different key inputs and expected outputs for that key.
@pytest.mark.parametrize(
    'key, expected',
    [("execution retry delays", ['execution retry delays']),
     ("retry delays", ['execution retry delays', 'submission retry delays',
                       'parameter environment templates']),
     ("execution retry SHED delays", ['execution retry delays']),
     ("execution retry delays SHED", ['execution retry delays']),
     ("execution delays retry", ['execution retry delays']),
     ("execution retrydelays", ['execution retry delays']),
     ("", []),
     ("execution    retry delays", ['execution retry delays']),
     ("execuion retry delays", ['execution retry delays']),
     ("executionee retry edelays", ['execution retry delays']),
     ("execution", ['execution polling intervals',
                    'execution retry delays',
                    'execution time limit']),
     ("j", ['job']),
     ("retr delays", ['execution retry delays',
                      'submission retry delays',
                      'parameter environment templates']),
     ]
)
def test_filter_key(key, expected):
    filtered_keys = filter_keys(REAL_TEST_DATA, key)
    assert filtered_keys == expected
