#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
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

import unittest
from pipes import quote
from subprocess import PIPE

from mock import call
from testfixtures import compare
from testfixtures.popen import MockPopen


class TestSubprocessSafe(unittest.TestCase):
    """Unit tests for the parameter subprocess_safe utility function"""

    def setUp(self):
        self.Popen = MockPopen()

    def test_subprocess_safe_quote(self):
        cmd = "$!#&'()|<>`\ ; "
        command = quote(cmd)
        self.assertEqual(command, '\'$!#&\'"\'"\'()|<>`\\ ; \'')
        self.assertEqual(command, quote("$!#&'()|<>`\\ ; "))

    def test_subprocess_safe_communicate_with_input(self):
        cmd = "a command"
        command = quote(cmd)
        Popen = MockPopen()
        Popen.set_command(command)
        process = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
        err, out = process.communicate('foo')
        compare([
                call.Popen(command, shell=True, stderr=-1, stdout=-1),
                call.Popen_instance.communicate('foo'),
                ], Popen.mock.method_calls)
        return err, out

    def test_subprocess_safe_read_from_stdout_and_stderr(self):
        cmd = "a command"
        command = quote(cmd)
        Popen = MockPopen()
        Popen.set_command(command, stdout=b'foo', stderr=b'bar')
        process = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)
        compare(process.stdout.read(), b'foo')
        compare(process.stderr.read(), b'bar')
        compare([
                call.Popen(command, shell=True, stderr=PIPE, stdout=PIPE),
                ], Popen.mock.method_calls)

    def test_subprocess_safe_write_to_stdin(self):
        cmd = "a command"
        command = quote(cmd)
        Popen = MockPopen()
        Popen.set_command(command)
        process = Popen(command, stdin=PIPE, shell=True)
        process.stdin.write(command)
        process.stdin.close()
        compare([
                call.Popen(command, shell=True, stdin=PIPE),
                call.Popen_instance.stdin.write(command),
                call.Popen_instance.stdin.close(),
                ], Popen.mock.method_calls)

    def test_subprocess_safe_wait_and_return_code(self):
        cmd = "a command"
        command = quote(cmd)
        Popen = MockPopen()
        Popen.set_command(command, returncode=3)
        process = Popen(command)
        compare(process.returncode, None)
        compare(process.wait(), 3)
        compare(process.returncode, 3)
        compare([
                call.Popen(command),
                call.Popen_instance.wait(),
                ], Popen.mock.method_calls)


if __name__ == "__main__":
    unittest.main()
