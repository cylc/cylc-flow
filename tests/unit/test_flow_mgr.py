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


@pytest.fixture
def patch_datetime_now(monkeypatch):

    class mydatetime:
        @classmethod
        def now(cls):
            return FAKE_NOW

    monkeypatch.setattr(datetime, 'datetime', mydatetime)


def test_all(
    patch_datetime_now,
    caplog: pytest.LogCaptureFixture,
):
    db_mgr = WorkflowDatabaseManager()
    flow_mgr = FlowMgr(db_mgr)
    caplog.set_level(logging.INFO, CYLC_LOG)

    count = 1
    meta = "the quick brown fox"
    msg1 = f"flow: {count} ({meta}) {FAKE_NOW}"
    assert flow_mgr.get_new_flow(meta) == count
    assert f"New {msg1}" in caplog.messages

    count = 2
    meta = "jumped over the lazy"
    msg2 = f"flow: {count} ({meta}) {FAKE_NOW}"
    assert flow_mgr.get_new_flow(meta) == count
    assert f"New {msg2}" in caplog.messages

    flow_mgr._log()
    assert (
        "Flows:\n"
        f"{msg1}\n"
        f"{msg2}"
    ) in caplog.messages
