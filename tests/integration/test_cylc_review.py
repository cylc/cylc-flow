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

from contextlib import suppress
import json
import pytest
import socket
import subprocess
import requests
from time import sleep

from cylc.flow import __version__ as CYLC_VERSION


@pytest.fixture(scope='module')
def run_cylc_review(request):
    port, timeout, service_root = request.param
    """Start a Cylc Review server.

    (Clean it up after too)

    Yields:
        Server process, request to home page as json
    """

    proc = subprocess.Popen(
        [
            'cylc',
            'review',
            'start',
            '--port', port,
            f'--service-root={service_root}',
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )

    # Ensure that home-page is accessible:
    timeout_counter = 0
    req = None
    sleep(1)
    while (
        getattr(req, 'status_code', 1) != 200
        and timeout_counter < timeout
    ):
        sleep(1)
        with suppress(Exception):
            req = requests.get(
                f'http://localhost:{port}/{service_root}-review?form=json'
            )
        timeout_counter += 1

    yield proc, req
    proc.terminate()


@pytest.mark.parametrize(
    'run_cylc_review',
    [["8666", 10, 'foo/cylc']],
    indirect=['run_cylc_review']
)
def test_basic_path(run_cylc_review):  
    """The CLI --service-root option changes the path to Cylc Review."""
    expect = {
        'logo': 'cylc-logo.png',
        'title': 'Cylc Review',
        'host': socket.gethostname(),
        'cylc_version': CYLC_VERSION,
        'script': '/foo/cylc-review',
    }
    data = json.loads(run_cylc_review[1].text)
    assert data == expect
