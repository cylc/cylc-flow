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
# ----------------------------------------------------------------------------
# Tests for methods in file cylc/flow/cfgspec/suite.py

import pytest
import re

from cylc.flow.cfgspec.suite import host_to_platform_warner
from cylc.flow.parsec.exceptions import UpgradeError


@pytest.mark.parametrize(
    'task_confs, expected',
    [
        (
            # Check that the limit counter works and only the
            # first 5 warnings are shown.
            {
                'TASK1': {
                    'remote': {
                        'host': 'alpha007'
                    }
                },
                'TASK2': {
                    'job': {
                        'batch system': 'barm'
                    }
                },
                'TASK3': {
                    'job': {
                        'batch submit command template': 'ham filling'
                    }
                },
                'TASK4': {
                    'job': {
                        'batch system': 'barm'
                    }
                },
                'TASK5': {
                    'job': {
                        'batch system': 'barm'
                    }
                },
                'TASK6': {
                    'job': {
                        'batch system': 'barm'
                    }
                }
            },
            r'WARNING.*\[TASK5\]\[job\]batch system = barm\nCylc'
        )
    ]
)
def test_host_to_platform_warner(caplog, task_confs, expected):
    conf = {
        'runtime': {}
    }
    conf['runtime'].update(task_confs)
    host_to_platform_warner(conf)
    assert re.match(expected, caplog.text, re.DOTALL)


def test_host_to_platform_failer(caplog):
    conf = {
        'runtime': {
            'TASK1': {
                'platform': 'shoes',
                'remote': {
                    'host': 'alpha007'
                }
            },
        },
    }

    with pytest.raises(UpgradeError):
        host_to_platform_warner(conf)

    errmsg = r'ERROR.*A mixture of Cylc 7.*alpha007.*shoes'
    assert re.match(errmsg, caplog.text, re.DOTALL)
