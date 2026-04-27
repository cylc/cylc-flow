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
"""
    Test set for the filter_keys function, tests a series of different
    keys to evaluate whether they get the correct possible output.

    real_test_data : List[String]
        A real examples of a list of 40 possible keys

    parametrize: test cases
        The list of different key inputs and expected outputs for that key.

"""
from cylc.flow.parsec.util import filter_keys
import pytest
real_test_data = ['completion', 'platform', 'inherit', 'script',
                  'init-script', 'env-script', 'err-script',
                  'exit-script', 'pre-script', 'post-script',
                  'work sub-directory', 'execution polling intervals',
                  'execution retry delays', 'execution time limit',
                  'submission polling intervals', 'submission retry delays',
                  'run mode', 'meta', 'skip', 'simulation',
                  'environment filter', 'job', 'remote', 'events', 'mail',
                  'workflow state polling', 'environment', 'directives',
                  'outputs', 'parameter environment templates']


@pytest.mark.parametrize(
    'key, expected',
    [("execution retry delays", ['execution retry delays']),
     ("retry delays", ['execution retry delays', 'submission retry delays']),
     ("execution retry SHED delays", ['execution retry delays']),
     ("execution retry delays SHED", ['execution retry delays']),
     ("execution delays retry", ['execution retry delays']),
     ("execution retrydelays", ['execution retry delays']),
     ("", []),
     ("execution    retry delays", ['execution retry delays']),
     ("execuion retry delays", ['execution retry delays']),
     ("executionee retry edelays", ['execution retry delays']),
     ("execution", ['execution polling intervals',
                    'execution retry delays']),
     ("delays retry", ['execution retry delays',
                       'submission retry delays']),
     ("j", ['job']),
     ("retr delays", ['execution retry delays',
                      'submission retry delays']),
     ]
)
def test_filter_key(key, expected):
    filtered_keys = filter_keys(real_test_data, key)
    assert filtered_keys == expected
