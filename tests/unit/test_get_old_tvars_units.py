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


from cylc.flow.templatevars import OldTemplateVars
import sqlite3
import pytest


@pytest.fixture(scope='module')
def _setup_db(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp('test_get_old_tvars')
    logfolder = tmp_path / "log/"
    logfolder.mkdir()
    db_path = logfolder / 'db'
    conn = sqlite3.connect(db_path)
    conn.execute(
        r'''
            CREATE TABLE workflow_template_vars (
                key,
                value
            )
        '''
    )
    conn.execute(
        r'''
            INSERT INTO workflow_template_vars
            VALUES
                ("FOO", "42"),
                ("BAR", "'hello world'"),
                ("BAZ", "'foo', 'bar', 48"),
                ("QUX", "['foo', 'bar', 21]")
        '''
    )
    conn.commit()
    conn.close()
    yield OldTemplateVars(tmp_path)


@pytest.mark.parametrize(
    'key, expect',
    (
        ('FOO', 42),
        ('BAR', 'hello world'),
        ('BAZ', ('foo', 'bar', 48)),
        ('QUX', ['foo', 'bar', 21])
    )
)
def test_OldTemplateVars(key, expect, _setup_db):
    """It can extract a variety of items from a workflow database.
    """
    assert _setup_db.template_vars[key] == expect
