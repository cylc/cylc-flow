#!/usr/bin/env python2

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

import pytest
import sqlite3
from mock import Mock

from cylc.suite_db_mgr import SuiteDatabaseManager
from cylc.suite_srv_files_mgr import SuiteCylcVersionError

db_params_dump = """
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE {table}(key TEXT, value TEXT, PRIMARY KEY(key));
INSERT INTO "{table}" VALUES('uuid_str','60271845-6e61-4208-83fd-0cc705a01903');
INSERT INTO "{table}" VALUES('cylc_version','{version}');
INSERT INTO "{table}" VALUES('UTC_mode','0');
INSERT INTO "{table}" VALUES('cycle_point_tz','+0100');
COMMIT;
"""


@pytest.fixture
def tmp_dao():
    """Provides an sqlite3 connection and a mock CylcSuiteDAO."""
    conn = sqlite3.connect(':memory:')
    mock_dao = Mock(connect=lambda: conn)
    yield (conn, mock_dao)
    conn.close()


def test_check_forward_compatibility__cylc_7_ok(tmp_dao):
    """SuiteDatabaseManager.check_forward_compatibility() should not raise for
    a Cylc version < 7.7.0 suite database."""
    conn, mock_dao = tmp_dao
    conn.executescript(
        """
        PRAGMA foreign_keys=OFF;
        BEGIN TRANSACTION;
        CREATE TABLE suite_params(key TEXT, value TEXT, PRIMARY KEY(key));
        INSERT INTO "suite_params" VALUES('UTC_mode','0');
        COMMIT;
        """
    )
    SuiteDatabaseManager.check_forward_compatibility(mock_dao)
    mock_dao.close.assert_not_called()

def test_check_forward_compatibility__cylc_7_7_0_ok(tmp_dao):
    """SuiteDatabaseManager.check_forward_compatibility() should not raise for
    a Cylc 7.7.0+ database."""
    conn, mock_dao = tmp_dao
    conn.executescript(db_params_dump.format(
        table='suite_params', version='7.7.0'
    ))
    SuiteDatabaseManager.check_forward_compatibility(mock_dao)
    mock_dao.close.assert_not_called()


def test_check_forward_compatibility__cylc_8_fail(tmp_dao):
    """SuiteDatabaseManager.check_forward_compatibility() should raise for
    a Cylc 8 database."""
    conn, mock_dao = tmp_dao
    conn.executescript(db_params_dump.format(
        table='workflow_params', version='8.0b2.dev'
    ))
    with pytest.raises(SuiteCylcVersionError):
        SuiteDatabaseManager.check_forward_compatibility(mock_dao)
    mock_dao.close.assert_called()
