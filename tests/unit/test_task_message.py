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

from socket import gaierror

import pytest

from cylc.flow.task_message import send_messages


def test_send_messages_err(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
):
    """If an error occurs while initializing the client, it should be printed.
    """
    exc_msg = 'Relic malfunction detected'

    def mock_get_client(*a, **k):
        raise gaierror(-2, exc_msg)

    monkeypatch.setattr('cylc.flow.task_message.get_client', mock_get_client)
    send_messages(
        'arasaka', '1/v/01', [['INFO', 'silverhand']], '2077-01-01T00:00:00Z'
    )
    assert f"gaierror: [Errno -2] {exc_msg}" in capsys.readouterr().err
