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

import tempfile
import unittest

import jinja2

from cylc.flow.parsec.jinja2support import *


class TestJinja2support(unittest.TestCase):

    def test_raise_helper(self):
        message = 'Ops'
        error_type = 'CRITICAL'
        with self.assertRaises(Exception) as cm:
            raise_helper(message=message)

        ex = cm.exception
        self.assertEqual("Jinja2 Error: Ops", str(ex))

        with self.assertRaises(Exception) as cm:
            raise_helper(message=message, error_type=error_type)

        ex = cm.exception
        self.assertEqual("Jinja2 CRITICAL: Ops", str(ex))

    def test_assert_helper(self):
        assert_helper(logical=True, message="Doesn't matter")  # harmless

        with self.assertRaises(Exception):
            assert_helper(logical=False, message="Doesn't matter")

    def test_jinja2environment(self):
        # create a temp directory, in the temp directory, to prevent
        # issues running multiple test suites in parallel
        temp_directory = tempfile.mkdtemp(prefix='cylc', suffix='test_jinja2')
        filters_dir = os.path.join(temp_directory, 'Jinja2Filters')
        os.mkdir(filters_dir)
        with open(os.path.join(filters_dir, "min.py"), "w") as tf:
            tf.write("def min():\n    raise ArithmeticError('UP!')")
            tf.seek(0)
            dir_ = temp_directory
            env = jinja2environment(dir_)
            # our jinja env contains the following keys in the global namespace
            self.assertTrue('environ' in env.globals)
            self.assertTrue('raise' in env.globals)
            self.assertTrue('assert' in env.globals)

            with self.assertRaises(ArithmeticError) as cm:
                # jinja2environment must have loaded the function from the .py
                env.filters['min']()
            self.assertEqual('UP!', str(cm.exception))

    def test_jinja2process(self):
        lines = ["skipped", "My name is {{ name }}", ""]
        variables = {'name': 'Cylc'}
        template_dir = tempfile.gettempdir()

        r = jinja2process(lines, template_dir, variables)

        self.assertEqual(['My name is Cylc'], r)

    def test_jinja2process_missing_variables(self):
        lines = ["skipped", "My name is {{ name }}", ""]
        template_dir = tempfile.gettempdir()

        with self.assertRaises(Jinja2Error) as exc:
            jinja2process(lines, template_dir, template_vars=None)
            self.assertIn('jinja2.UndefinedError', str(exc))

    def test_pymoduleloader(self):
        temp_directory = tempfile.mkdtemp(prefix='cylc', suffix='test_jinja2')
        filters_dir = os.path.join(temp_directory, 'Jinja2filters')
        os.mkdir(filters_dir)
        with tempfile.NamedTemporaryFile(dir=filters_dir, suffix=".py") as tf:
            tf.write(
                "def jinja2jinja()\n    raise Exception('It works!')".encode())
            tf.seek(0)
            dir_ = temp_directory
            env = jinja2environment(dir_)

            module_loader = PyModuleLoader()
            template = module_loader.load(environment=env, name='sys')
            self.assertEqual(sys.path, template.module.path)

            template2 = module_loader.load(
                environment=env, name='__python__.sys')

            self.assertEqual(template.module.path, template2.module.path)

    def test_pymoduleloader_invalid_module(self):
        temp_directory = tempfile.mkdtemp(prefix='cylc', suffix='test_jinja2')
        filters_dir = os.path.join(temp_directory, 'Jinja2filters')
        os.mkdir(filters_dir)
        with tempfile.NamedTemporaryFile(dir=filters_dir, suffix=".py") as tf:
            tf.write(
                "def jinja2jinja()\n    raise Exception('It works!')".encode())
            tf.seek(0)
            dir_ = temp_directory
            env = jinja2environment(dir_)

            module_loader = PyModuleLoader()
            with self.assertRaises(jinja2.TemplateNotFound):
                module_loader.load(environment=env, name='no way jose')


if __name__ == '__main__':
    unittest.main()
