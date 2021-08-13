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
import tempfile
import unittest

from types import SimpleNamespace

from cylc.flow.exceptions import PluginError
from cylc.flow.templatevars import get_template_vars, load_template_vars

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


if __name__ == '__main__':
    unittest.main()


def test_get_template_vars_installed_flow(monkeypatch):
    """It works on an installed flow.

    n.b. Does not attempt to test ``load_template_vars``
    """
    monkeypatch.setattr(
        'cylc.flow.templatevars.load_template_vars',
        lambda templatevars, templatevars_file: {'foo': 'bar'}
    )
    opts = SimpleNamespace(templatevars='', templatevars_file='')
    result = get_template_vars(opts, '', names=('eg/runN', 'eg/runN'))
    assert result == {'foo': 'bar'}


@pytest.fixture(scope='module')
def provide_opts():
    """Provide a fake opts"""
    return SimpleNamespace(
        templatevars='', templatevars_file=''
    )


@pytest.fixture
def monkeypatch_load_template_vars(monkeypatch):
    monkeypatch.setattr(
        'cylc.flow.templatevars.load_template_vars',
        lambda templatevars, templatevars_file: {}
    )


def test_get_template_vars_src_flow(
    monkeypatch, provide_opts, monkeypatch_load_template_vars):
    """It works on a flow which hasn't been installed.
    """
    def fake_iter_entry_points(_):
        class fake_ep:
            name = 'Zaphod'
            def resolve():
                def _inner(srcdir, opts):
                    return {
                        'template_variables': {'MYVAR': 'foo'},
                        'templating_detected': 'lazyman'
                    }
                return _inner
        return [fake_ep]

    monkeypatch.setattr(
        'cylc.flow.templatevars.iter_entry_points',
        fake_iter_entry_points
    )
    assert get_template_vars(provide_opts, '') == {'MYVAR': 'foo'}


def test_get_template_vars_src_flow_fails(
    monkeypatch, provide_opts, monkeypatch_load_template_vars):
    """It fails if there is a plugin error.
    """
    def fake_iter_entry_points(_):
        class fake_ep:
            name = 'Zaphod'
            def resolve():
                def _inner(srcdir, opts):
                    raise TypeError('Utter Drivel.')
                return _inner
        return [fake_ep]

    monkeypatch.setattr(
        'cylc.flow.templatevars.iter_entry_points',
        fake_iter_entry_points
    )

    with pytest.raises(PluginError) as exc:
        get_template_vars(provide_opts, '')
    assert exc.match(
        'Error in plugin cylc.pre_configure.Zaphod\nUtter Drivel.')
