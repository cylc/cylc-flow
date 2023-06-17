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

import pytest
from pathlib import Path

from cylc.flow.scripts.scan import (
    ScanOptions,
    get_pipe,
    _format_plain,
    _construct_tree,
    FLOW_STATES,
    BAD_CONTACT_FILE_MSG
)


def test_no_connection():
    """Ensure scan uses the filesystem where possible."""
    pipe = get_pipe(ScanOptions(states=FLOW_STATES), _format_plain)
    assert 'graphql_query' not in repr(pipe)


def test_ping_connection():
    """Ensure scan always connects to the flow when requested via --ping."""
    pipe = get_pipe(ScanOptions(states=FLOW_STATES, ping=True), _format_plain)
    assert 'graphql_query' in repr(pipe)


def test_good_contact_info() -> None:
    """Check correct reporting of workflow contact information."""
    port = 8888
    host = "wizard"
    name = "blargh/run1"
    pid = 12345
    res = _format_plain(
        {
            "name": name,
            "contact": Path(f"/path/to/{name}"),
            "CYLC_WORKFLOW_HOST": host,
            "CYLC_WORKFLOW_PORT": port,
            "CYLC_WORKFLOW_PID": pid,
        },
        None
    )
    assert name in res
    assert f"{host}:{port} {pid}" in res


def test_bad_contact_info(caplog: pytest.LogCaptureFixture) -> None:
    """Check correct reporting of bad workflow contact information.

    Missing contact keys should result in a warning.
    """
    name = "blargh/run1"
    _format_plain(
        {
            "name": name,
            "contact": Path(f"/path/to/{name}"),
        },
        None
    )
    assert BAD_CONTACT_FILE_MSG.format(flow_name=name) in caplog.text


def test_bad_contact_info_tree(caplog: pytest.LogCaptureFixture) -> None:
    """Check correct reporting of bad workflow contact information.

    Missing contact keys should result in a warning.
    """
    name = "blargh/run1"
    flows = [{
        "name": name,
        "contact": Path(f"/path/to/{name}"),
    }]
    tree = {}
    _construct_tree(flows, tree, _format_plain, None, None)

    # Error during tree formatting: reports only the last name component.
    assert (
        BAD_CONTACT_FILE_MSG.format(flow_name=f"{Path(name).name}")
        in caplog.text
    )
