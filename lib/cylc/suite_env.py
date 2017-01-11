#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
"""Dump and load "cylc-suite-env" file."""

import os


class CylcSuiteEnvLoadError(Exception):
    """Error on loading cylc-suite-env file."""
    BASE_NAME = "cylc-suite-env"
    MISSING_KEY = (BASE_NAME + ": missing %(attr_key)s")
    UNEXPECTED_SUITE_NAME = (
        BASE_NAME + ": suite name expected [%(expected)s], got [%(actual)s]")


class CylcSuiteEnv(object):
    """Data structure, dumper and loader for suite contact file.

    An instance of this class has the following attributes:

    suite_name: the name of the suite
    suite_host: the name of the host on which the suite is running
    suite_port: the port number on host for connecting to the running suite
    suite_owner: the owner user ID of the suite
    suite_cylc_version: version of cylc for running the suite

    Constants:

    BASE_NAME: the default base name of the suite contact file
    ATTRS: map instance attributes to text keys in the suite contact file

    """

    BASE_NAME = CylcSuiteEnvLoadError.BASE_NAME
    ATTRS = {
        "CYLC_SUITE_NAME": "suite_name",
        "CYLC_SUITE_HOST": "suite_host",
        "CYLC_SUITE_PORT": "suite_port",
        "CYLC_SUITE_OWNER": "suite_owner",
        "CYLC_VERSION": "suite_cylc_version",
    }

    @classmethod
    def load(cls, suite_name, suite_run_dir):
        """Load suite contact file for suite_name from suite_run_dir.

        Return an instance of CylcSuiteEnv.
        Raise CylcSuiteEnvLoadError on failure.

        """
        ret = cls()
        try:
            for line in open(os.path.join(suite_run_dir, cls.BASE_NAME)):
                key, value = line.strip().split('=', 1)
                setattr(ret, cls.ATTRS[key], value)
        except (IOError, KeyError, ValueError):
            pass
        # Check that all expected attributes are defined
        for attr_key, attr in cls.ATTRS.items():
            if getattr(ret, attr) is None:
                raise CylcSuiteEnvLoadError(
                    CylcSuiteEnvLoadError.MISSING_KEY % {"attr_key": attr_key})
        # Check that we have loaded a file with the expected suite name
        if suite_name != ret.suite_name:
            raise CylcSuiteEnvLoadError(
                CylcSuiteEnvLoadError.UNEXPECTED_SUITE_NAME % {
                    "expected": suite_name, "actual": ret.suite_name})
        return ret

    def __init__(self, data=None):
        self.suite_name = None
        self.suite_host = None
        self.suite_port = None
        self.suite_owner = None
        self.suite_cylc_version = None
        if data:
            for attr_key, attr in self.ATTRS.items():
                setattr(self, attr, data.get(attr_key))

    def __str__(self):
        ret = ""
        for attr_key, attr in sorted(self.ATTRS.items()):
            ret += "%s=%s\n" % (attr_key, getattr(self, attr))
        return ret

    def dump(self, suite_run_dir):
        """Dump suite contact file under suite_run_dir.

        Don't bother staying alive on failure. Something must be very wrong.

        """
        with open(os.path.join(suite_run_dir, self.BASE_NAME), 'wb') as handle:
            handle.write(str(self))
