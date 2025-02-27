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

"""Unit tests for FlowManager."""

import pytest
import datetime
import logging

from cylc.flow.flow_mgr import FlowMgr
from cylc.flow.workflow_db_mgr import WorkflowDatabaseManager
from cylc.flow import CYLC_LOG


FAKE_NOW = datetime.datetime(2020, 12, 25, 17, 5, 55)
FAKE_NOW_ISO = FAKE_NOW.isoformat()


@pytest.fixture
def patch_datetime_now(monkeypatch):

    class mydatetime:
        @classmethod
        def now(cls, tz=None):
            return FAKE_NOW

    monkeypatch.setattr(datetime, 'datetime', mydatetime)


def test_all(
    patch_datetime_now,
    caplog: pytest.LogCaptureFixture,
):
    """Test flow number management."""

    db_mgr = WorkflowDatabaseManager()
    flow_mgr = FlowMgr(db_mgr)
    caplog.set_level(logging.DEBUG, CYLC_LOG)

    meta = "the quick brown fox"
    assert flow_mgr.get_flow_num(None, meta) == 1
    msg1 = f"flow: 1 ({meta}) {FAKE_NOW_ISO}"
    assert f"New {msg1}" in caplog.messages

    # automatic: expect 2
    meta = "jumped over the lazy dog"
    assert flow_mgr.get_flow_num(None, meta) == 2
    msg2 = f"flow: 2 ({meta}) {FAKE_NOW_ISO}"
    assert f"New {msg2}" in caplog.messages

    # give flow 2: not a new flow
    meta = "jumped over the moon"
    assert flow_mgr.get_flow_num(2, meta) == 2
    msg3 = f"flow: 2 ({meta}) {FAKE_NOW_ISO}"
    assert f"New {msg3}" not in caplog.messages
    assert (
        f"Ignoring flow metadata \"{meta}\": 2 is not a new flow"
        in caplog.messages
    )

    # give flow 4: new flow
    meta = "jumped over the cheese"
    assert flow_mgr.get_flow_num(4, meta) == 4
    msg4 = f"flow: 4 ({meta}) {FAKE_NOW_ISO}"
    assert f"New {msg4}" in caplog.messages

    # automatic: expect 3
    meta = "jumped over the log"
    assert flow_mgr.get_flow_num(None, meta) == 3
    msg5 = f"flow: 3 ({meta}) {FAKE_NOW_ISO}"
    assert f"New {msg5}" in caplog.messages

    # automatic: expect 5 (skip over 4)
    meta = "crawled under the log"
    assert flow_mgr.get_flow_num(None, meta) == 5
    msg6 = f"flow: 5 ({meta}) {FAKE_NOW_ISO}"
    assert f"New {msg6}" in caplog.messages
    flow_mgr._log()
    assert (
        "Flows:\n"
        f"{msg1}\n"
        f"{msg2}\n"
        f"{msg4}\n"
        f"{msg5}\n"
        f"{msg6}"
    ) in caplog.messages
