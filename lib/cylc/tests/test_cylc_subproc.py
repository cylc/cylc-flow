#!/usr/bin/env python3

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

from cylc.cylc_subproc import procopen
from unittest.mock import call
from testfixtures import compare
from testfixtures.popen import PIPE, MockPopen

# Method could be a function
# pylint: disable=no-self-use


class TestSubprocessSafe(unittest.TestCase):
    """Unit tests for the parameter procopen utility function"""

    def setUp(self):
        self.Popen = MockPopen()

    def test_sprocess_communicate_with_process(self):
        foo = ' foo'
        bar = ' bar'
        cmd = ["echo", "this is a command" + foo + bar]
        p = procopen(cmd, stdoutpipe=True)
        stdout, _ = p.communicate()
        compare(stdout, b"this is a command foo bar\n")

    def test_sprocess_communicate_with_input(self):
        command = "a command"
        Popen = MockPopen()
        Popen.set_command(command)
        #  only static input used with simulated mockpopen
        # codacy mistakenly sees this as a call to popen
        process = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)  # nosec
        err, out = process.communicate('foo')
        compare([
                #  only static input used with simulated mockpopen
                # codacy mistakenly sees this as a call to popen
                call.Popen(command, shell=True, stderr=-1, stdout=-1),  # nosec
                call.Popen_instance.communicate('foo'),
                ], Popen.mock.method_calls)
        return err, out

    def test_sprocess_safe_read_from_stdout_and_stderr(self):
        command = "a command"
        Popen = MockPopen()
        #  only static input used with simulated mockpopen
        # codacy mistakenly sees this as a call to popen
        Popen.set_command(command, stdout=b'foo', stderr=b'bar')
        process = Popen(command, stdout=PIPE, stderr=PIPE, shell=True)  # nosec
        compare(process.stdout.read(), b'foo')
        compare(process.stderr.read(), b'bar')
        compare([
                call.Popen(command, shell=True, stderr=PIPE,  # nosec
                           stdout=PIPE),
                ], Popen.mock.method_calls)

    def test_sprocess_safe_write_to_stdin(self):
        command = "a command"
        Popen = MockPopen()
        Popen.set_command(command)
        #  only static input used with simulated mockpopen
        # codacy mistakenly sees this as a call to popen
        process = Popen(command, stdin=PIPE, shell=True)  # nosec
        process.stdin.write(command)
        process.stdin.close()
        compare([
                # static input used with simulated mockpopen
                # codacy mistakenly sees this as a call to popen
                call.Popen(command, shell=True, stdin=PIPE),  # nosec
                call.Popen_instance.stdin.write(command),
                call.Popen_instance.stdin.close(),
                ], Popen.mock.method_calls)

    def test_sprocess_safe_wait_and_return_code(self):
        command = "a command"
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
