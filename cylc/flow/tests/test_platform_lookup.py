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
#
# Tests for the platform lookup.

from cylc.flow.platform_lookup import forward_lookup, reverse_lookup

# The platforms list for testing is set as a constant
# [platforms]
#     [[desktop\d\d|laptop\d\d]]
#         # hosts = platform name (default)
#         # Note: "desktop01" and "desktop02" are both valid and distinct platforms
#     [[sugar]]
#         hosts = localhost
#         batch system = slurm
#     [[hpc]]
#         hosts = hpcl1, hpcl2
#         retrieve job logs = True
#         batch system = pbs
#     [[hpcl1-bg]]
#         hosts = hpcl1
#         retrieve job logs = True
#         batch system = background
#     [[hpcl2-bg]]
#         hosts = hpcl2
#         retrieve job logs = True
#         batch system = background
PLATFORMS = {
    'desktop\d\d|laptop\d\d': None,
    'sugar': {
        'hosts': 'localhost',
        'batch system': 'slurm',
    },
    'hpc': {
        'hosts': ['hpc1', 'hpc2'],
        'batch system': 'pbs',
    },
    'hpc1-bg': {
        'hosts': 'hpc1',
        'batch system': 'background',
    },
    'hpc2-bg': {
        'hosts': 'hpc2',
        'batch system': 'background'
    }
}


PLATFORMS_NO_UNIQUE = {
    'sugar': {
        'login hosts': 'localhost',
        'batch system': 'slurm',
    },
    'pepper': {
        'login hosts': ['hpc1', 'hpc2'],
        'batch system': 'slurm',
    },

}


class TestForwardLookup():
    """
    Tests to ensure that the job platform forward lookup works as intended.
    """
    def test_basic(self):
        assert 1 == 1


class TestReverseLookup():
    """
    Tests to ensure that job platform reverse lookup works as intended.
    """

    def test_reverse_lookup(self):
        assert 'Hello' == 'Hello'

    CASES = [
        # Settings left blank - should select suite host
        (
            {'batch system': None},
            {'host': None},
            'suite host',
            'ok'
        ),
        # # Host set, batch system unset - desktop machines, hpc background
        # (
        #     {'batch system': None},
        #     {'host': 'laptop42'},
        #     'laptop42',
        #     'ok'
        # ),
        # (
        #     {'batch system': None},
        #     {'host': 'hpc1'},
        #     'hpc1-bg',
        #     'ok'
        # ),
        # # Host unset, batch system set
        # # Should infer a host from the batch system, but only if the batch
        # # system is unique to one platform
        # # TODO write a test with an alternative platfroms set to show the
        # # failure case where multiple systems have the same batch system
        # (
        #     {'batch system': 'slurm'},
        #     {'host': None},
        #     'sugar',
        #     'ok'
        # ),
        # (
        #     {'batch system': 'pbs'},
        #     {'host': None},
        #     'hpc',
        #     'ok'
        # ),
        # # Host Set, Batch system set
        # # Batch system should match platfrom __and__ host should be in the
        # # list of login hosts for the platform
        # (
        #     {'batch system': 'pbs'},
        #     {'host': 'hpc'},
        #     'desktop42',
        #     'ok'
        # ),
        # (
        #     {'batch system': 'pbs'},
        #     {'host': 'hpc1'},
        #     'desktop42',
        #     'ok'
        # ),
    ]
    @pytest.mark.parametrize('task_job, task_remote, selected_platform, result',
                             CASES)
    def test_ok(self, task_job, task_remote, selected_platform, result):
        if result == 'ok':
            assert reverse_lookup(task_job, task_remote, PLATFORMS) == selected_platform
        elif result == 'error':
            with pytest.raises(PlatformLookupError):
                reverse_lookup(task_job, task_remote, PLATFORMS)
        elif result == 'not ok':
            assert reverse_lookup(task_job, task_remote, PLATFORMS) != selected_platform

