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
import sqlite3
import tempfile
import unittest

from types import SimpleNamespace


from cylc.flow.exceptions import PluginError
from cylc.flow.templatevars import (
    get_template_vars_from_db,
    get_template_vars,
    load_template_vars
)


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
