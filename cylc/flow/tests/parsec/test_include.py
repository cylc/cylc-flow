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

"""Basic tests for the include module and its functions. Some functions
rely on file system operations, and are probably better tested by functional
tests. So this suite of unit tests should not cover all the module features.
"""

import tempfile
import unittest

from cylc.flow.parsec.exceptions import ParsecError
from cylc.flow.parsec.include import *


class TestInclude(unittest.TestCase):

    def test_include_file_not_found_error(self):
        dir_temp = tempfile.mkdtemp()
        with tempfile.NamedTemporaryFile(dir=dir_temp) as tf:
            file_list = [tf.name, tf.name, tf.name]
            error = IncludeFileNotFoundError(file_list)
            self.assertTrue(" via " in str(error))

    def test_inline_error_empty_lines_1(self):
        """The inline function throws an error when you have the following
        combination:

        - lines is an empty list
        - for_edit is True
        - level is None
        """
        with self.assertRaises(IndexError):
            inline(
                lines=[],
                dir_=None,
                filename=None,
                for_edit=True,
                level=None)

    def test_inline_error_mismatched_quotes(self):
        """The inline function throws an error when you have the
        %include statement with a value without the correct balance
        for quotes, e.g. %include "abc.txt
        """
        with self.assertRaises(ParsecError):
            inline(
                lines=["%include 'abc.txt"],
                dir_=None,
                filename=None,
                for_edit=True,
                level=None)

    def test_inline(self):
        with tempfile.NamedTemporaryFile() as tf:
            filename = tf.name
            file_lines = [
                "#!jinja2",
                "[section]",
                "value 1"
            ]
            file_lines_with_include = file_lines + [
                "%include '{0}'".format(filename)
            ]

            # same as before as there was no include lines
            r = inline(lines=file_lines,
                       dir_=os.path.dirname(tf.name),
                       filename=filename)
            self.assertEqual(file_lines, r)

            # here the include line is removed, so the value returned
            # is still file_lines, not file_lines_with_include
            r = inline(lines=file_lines_with_include,
                       dir_=os.path.dirname(tf.name),
                       filename=filename)
            self.assertEqual(file_lines, r)

            # the for_grep adds some marks helpful for when grep'ing the file
            r = inline(lines=file_lines_with_include,
                       dir_=os.path.dirname(tf.name),
                       filename=filename, for_grep=True)
            expected = file_lines + [
                "#++++ START INLINED INCLUDE FILE {0}".format(filename),
                "#++++ END INLINED INCLUDE FILE {0}".format(filename)
            ]
            self.assertEqual(expected, r)

            # for_edit would call the backup function, which triggers file
            # system operations. So we avoid testing that option here.

            # test that whatever is in the included file appears in the output
            tf.write("[section2]".encode())
            tf.flush()
            r = inline(lines=file_lines_with_include,
                       dir_=os.path.dirname(tf.name),
                       filename=filename)
            expected = file_lines + [
                "[section2]"
            ]
            self.assertEqual(expected, r)


if __name__ == '__main__':
    unittest.main()
