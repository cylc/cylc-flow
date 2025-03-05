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

from pathlib import Path
import pytest
from pytest import param
import tempfile
import unittest

from cylc.flow import __version__ as cylc_version
from cylc.flow.exceptions import ServiceFileError, InputError
from cylc.flow.rundb import CylcWorkflowDAO
from cylc.flow.templatevars import (
    get_template_vars_from_db,
    load_template_vars
)
from cylc.flow.workflow_files import WorkflowFiles


class TestTemplatevars(unittest.TestCase):

    def test_load_template_vars_no_params(self):
        self.assertFalse(load_template_vars())

    def test_load_template_vars_from_string(self):
        pairs = [
            "name='John'",
            "type='Human'",
            "age='12'"
        ]
        expected = {
            "name": "John",
            "type": "Human",
            "age": "12"
        }
        self.assertEqual(expected, load_template_vars(template_vars=pairs))

    def test_load_template_vars_from_file(self):
        with tempfile.NamedTemporaryFile() as tf:
            tf.write("""
            name='John'
            type='Human'
            # a comment
            # type=Test
            age='12'
            """.encode())
            tf.flush()
            expected = {
                "name": "John",
                "type": "Human",
                "age": "12"
            }
            self.assertEqual(
                expected, load_template_vars(template_vars=None,
                                             template_vars_file=tf.name))

    def test_load_template_vars_from_string_and_file_1(self):
        """Text pair variables take precedence over file."""
        pairs = [
            "name='John'",
            "age='12'"
        ]
        with tempfile.NamedTemporaryFile() as tf:
            tf.write("""
            name='Mariah'
            type='Human'
            # a comment
            # type=Test
            age='70'
            """.encode())
            tf.flush()
            expected = {
                "name": "John",
                "type": "Human",
                "age": "12"
            }
            self.assertEqual(
                expected, load_template_vars(template_vars=pairs,
                                             template_vars_file=tf.name))

    def test_load_template_vars_from_string_and_file_2(self):
        """Text pair variables take precedence over file."""
        pairs = [
            "str='str'",
            "int=12",
            "float=12.3",
            "bool=True",
            "none=None"
        ]
        expected = {
            'str': 'str',
            'int': 12,
            'float': 12.3,
            'bool': True,
            'none': None
        }
        self.assertEqual(expected, load_template_vars(template_vars=pairs))


@pytest.fixture(scope='module')
def _setup_db(tmp_path_factory):
    tmp_path: Path = tmp_path_factory.mktemp('test_get_old_tvars')
    logfolder = tmp_path / WorkflowFiles.LogDir.DIRNAME
    logfolder.mkdir()
    db_path = logfolder / WorkflowFiles.LogDir.DB
    with CylcWorkflowDAO(db_path, create_tables=True) as dao:
        dao.connect().execute(
            r'''
                INSERT INTO workflow_params
                VALUES
                    (?, ?)
            ''',
            ("cylc_version", cylc_version),
        )
        dao.connect().executemany(
            r'''
                INSERT INTO workflow_template_vars
                VALUES
                    (?, ?)
            ''',
            [
                ("FOO", "42"),
                ("BAR", "'hello world'"),
                ("BAZ", "'foo', 'bar', 48"),
                ("QUX", "['foo', 'bar', 21]"),
            ],
        )
        dao.connect().commit()
    yield get_template_vars_from_db(tmp_path)


@pytest.mark.parametrize(
    'key, expect',
    (
        ('FOO', 42),
        ('BAR', 'hello world'),
        ('BAZ', ('foo', 'bar', 48)),
        ('QUX', ['foo', 'bar', 21])
    )
)
def test_get_old_tvars(key, expect, _setup_db):
    """It can extract a variety of items from a workflow database.
    """
    assert _setup_db[key] == expect


def test_get_old_tvars_fails_if_cylc_7_db(tmp_path):
    """get_template_vars_from_db fails with error if db file is not a valid
    Cylc 8 DB.
    """
    dbfile = tmp_path / WorkflowFiles.LogDir.DIRNAME / WorkflowFiles.LogDir.DB
    dbfile.parent.mkdir()
    dbfile.touch()
    with pytest.raises(ServiceFileError, match='database is incompatible'):
        get_template_vars_from_db(tmp_path)


@pytest.mark.parametrize(
    'tvars_lists, expect',
    (
        param(
            ['FOO=a,b,c'], {'FOO': ['a', 'b', 'c']},
            id='basic'
        ),
        param(
            ['FOO=a,"b,b",c'], {'FOO': ['a', 'b,b', 'c']},
            id='contains-quotes'
        ),
    )
)
def test_load_var_lists(tvars_lists, expect):
    """
    load_template_vars should parse template vars lists and dump these
    into template vars.
    """
    result = load_template_vars(templatevars_lists=tvars_lists)
    assert result == expect


def test_load_var_lists_warns_overwriting(caplog):
    """It wars user if same tvar name used twice."""
    load_template_vars(template_vars=["BAZ='HEY'", "BAZ='THERE'"])
    assert 'BAZ' in caplog.records[-1].message
    load_template_vars(templatevars_lists=['FOO=a,b', 'FOO=b,c'])
    assert 'FOO' in caplog.records[-1].message


def test_load_var_lists_fails():
    """
    load_template_vars should fail if the same var is set using -s and -z
    """
    errmsg = r"FOO=a and FOO=\['a', 'b'\]"
    with pytest.raises(InputError, match=errmsg):
        load_template_vars(
            template_vars=['FOO="a"'],
            templatevars_lists=['FOO=a,b']
        )


def test_load_vars_invalid_value_pairs():
    with pytest.raises(InputError, match="FOO\n.*qux\n.*BAZ\n.*QUX"):
        load_template_vars(
            template_vars=['FOO', 'qux'],
            templatevars_lists=['BAZ', 'QUX']
        )


def test_load_template_vars_ValueError_fm_file(monkeypatch):
    from io import StringIO
    handle = StringIO('Hello')
    monkeypatch.setattr('builtins.open', lambda *_: handle)
    with pytest.raises(InputError, match='Hello'):
        load_template_vars(template_vars_file='foo')
