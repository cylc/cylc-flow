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

import sys
from pathlib import Path

from cylc.flow.scripts.scan import (
    ScanOptions,
    get_pipe,
    _format_plain,
    FLOW_STATES,
    format_and_write,
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


def test_good_contact_info(capsys, monkeypatch):
    """Check correct printing of workflow contact information."""
    port = 8888
    host = "wizard"
    name = "blargh/run1"
    format_and_write(
        sys.stdout.write,
        _format_plain,
        {
            "name": name,
            "contact": Path("/path/to/blargh/run1"),
            "CYLC_WORKFLOW_HOST": host,
            "CYLC_WORKFLOW_PORT": port,
        },
        None
    )
    outerr = capsys.readouterr()
    assert name in outerr.out
    assert f"{host}:{port}" in outerr.out


def test_bad_contact_info(capsys, monkeypatch):
    """Check correct printing of bad contact info.

    Missing contact keys should result in a warning, not crash scan.
    """
    name = "blargh/run1"
    format_and_write(
        sys.stdout.write,
        _format_plain,
        {
            "name": name,
            "contact": Path("/path/to/blargh/run1"),
        },
        None
    )
    outerr = capsys.readouterr()
    assert BAD_CONTACT_FILE_MSG.format(workflow_name=name) in outerr.err
