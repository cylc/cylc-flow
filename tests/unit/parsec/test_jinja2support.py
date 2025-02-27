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

import jinja2
import pytest
import sys

from cylc.flow.parsec.jinja2support import (
    Jinja2AssertionError,
    Jinja2Error,
    PyModuleLoader,
    jinja2environment,
    jinja2process,
    assert_helper,
    raise_helper,
)


def test_raise_helper():
    message = 'Ops'
    with pytest.raises(Jinja2AssertionError) as cm:
        raise_helper(message=message)

    assert str(cm.value) == "Ops"


def test_assert_helper():
    assert_helper(logical=True, message="Doesn't matter")  # harmless

    with pytest.raises(Exception):
        assert_helper(logical=False, message="Doesn't matter")


def test_jinja2environment(tmp_path):
    # create a temp directory, in the temp directory, to prevent
    # issues running multiple test workflows in parallel
    filters_dir = tmp_path / 'Jinja2Filters'
    filters_dir.mkdir()
    with open(filters_dir / "min.py", "w") as tf:
        tf.write("def min():\n    raise ArithmeticError('UP!')")
        tf.seek(0)
        env = jinja2environment(tmp_path)
        # our jinja env contains the following keys in the global namespace
        assert 'environ' in env.globals
        assert 'raise' in env.globals
        assert 'assert' in env.globals

        with pytest.raises(ArithmeticError) as cm:
            # jinja2environment must have loaded the function from the .py
            env.filters['min']()
        assert str(cm.value) == 'UP!'


def test_jinja2process(tmp_path):
    lines = ["skipped", "My name is {{ name }}", ""]
    variables = {'name': 'Cylc'}
    r = jinja2process(None, lines, tmp_path, variables)
    assert ['My name is Cylc'] == r


def test_jinja2process_missing_variables(tmp_path):
    lines = ["skipped", "My name is {{ name }}", ""]
    with pytest.raises(Jinja2Error) as exc:
        jinja2process(None, lines, tmp_path, template_vars=None)
        assert 'jinja2.UndefinedError' in str(exc)


def test_pymoduleloader(tmp_path):
    filters_dir = tmp_path / 'Jinja2filters'
    filters_dir.mkdir()
    with open(filters_dir / 'jinja2jinja.py', 'bw+') as tf:
        tf.write(
            "def jinja2jinja():\n    raise Exception('It works!')".encode())
        tf.seek(0)
        env = jinja2environment(tmp_path)

        module_loader = PyModuleLoader()
        template = module_loader.load(environment=env, name='sys')
        assert sys.path == template.module.path

        template2 = module_loader.load(
            environment=env, name='__python__.sys')

        assert template.module.path == template2.module.path


def test_pymoduleloader_invalid_module(tmp_path):
    filters_dir = tmp_path / 'Jinja2filters'
    filters_dir.mkdir()
    with open(filters_dir / 'jinja2jinja.py', 'bw+') as tf:
        tf.write(
            "def jinja2jinja():\n    raise Exception('It works!')".encode())
        tf.seek(0)
        env = jinja2environment(tmp_path)

        module_loader = PyModuleLoader()
        with pytest.raises(jinja2.TemplateNotFound):
            module_loader.load(environment=env, name='no way jose')
