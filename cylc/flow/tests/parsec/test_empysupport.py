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

"""
EmPy is an optional dependency, so tests need to check if that is installed!
"""

import sys
import tempfile
import unittest

from cylc.flow.parsec.exceptions import EmPyError
from cylc.flow.parsec.fileparse import read_and_proc

IS_EMPY_INSTALLED = True

try:
    from cylc.flow.parsec import empysupport
except ImportError:
    IS_EMPY_INSTALLED = False


@unittest.skipUnless(IS_EMPY_INSTALLED, "EmPy not installed")
class TestEmpysupport1(unittest.TestCase):

    def test_empysupport_empyprocess(self):
        lines = ["My name is @name", ""]
        variables = {'name': 'Cylc'}
        template_dir = tempfile.gettempdir()

        r = empysupport.empyprocess(lines, template_dir, variables)
        # after this, we would normally have an error in unittest as follows:
        # AttributeError: ProxyFile instance has no attribute 'getvalue'
        # That's due to a Proxy installed by EmPy to replace sys.stdout.
        # We restore the sys.stdout in the end of the tests
        # TODO: is it OK? Does everything else works OK in Jinja after this?
        # Note: writing multiple methods will result in an error too

        self.assertEqual(1, len(r))
        self.assertEqual('My name is Cylc', r[0])
        sys.stdout.getvalue = lambda: ''

        lines = []
        template_dir = tempfile.gettempdir()

        r = empysupport.empyprocess(lines, template_dir)

        self.assertEqual(0, len(r))

        # --- testing fileparse (here due to stdout issue)

        with tempfile.NamedTemporaryFile() as tf:
            fpath = tf.name
            template_vars = {
                'name': 'Cylc'
            }
            viewcfg = {
                'empy': True, 'jinja2': False,
                'contin': False, 'inline': False
            }
            asedit = None
            tf.write("#!empy\na=@name\n".encode())
            tf.flush()
            r = read_and_proc(fpath=fpath, template_vars=template_vars,
                              viewcfg=viewcfg, asedit=asedit)
            self.assertEqual(['a=Cylc'], r)

            del template_vars['name']

            with self.assertRaises(EmPyError):
                read_and_proc(fpath=fpath, template_vars=template_vars,
                              viewcfg=viewcfg, asedit=asedit)
            sys.stdout.getvalue = lambda: ''

        sys.stdout.getvalue = lambda: ''


if __name__ == '__main__':
    unittest.main()
