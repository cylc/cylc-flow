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

import doctest
import os
import pkgutil
import sys
import unittest


def iter_package(name, path):
    """Yield modules contained within the provided package."""
    stack = [(name, path)]
    while stack:
        namespace, path = stack.pop()
        for _, name, is_package in pkgutil.walk_packages([path]):
            modname = '%s.%s' % (namespace, name)
            modpath = os.path.join(path, name)
            yield modname, modpath
            if is_package:
                stack.append((modname, modpath))


def load_tests(loader, tests, _):
    """Called by unittest to determine which tests to run.

    See: https://docs.python.org/3/library/unittest.html#load-tests-protocol
    """
    import importlib

    cylc_package_path = os.path.split(os.path.split(__file__)[0])[0]
    for module_name, _ in iter_package('cylc',  cylc_package_path):
        # ensure the module is importable
        try:
            importlib.import_module(module_name)
        except ImportError as exc:
            print 'doctest: skipping "%s" - %s' % (module_name, exc)
            continue

        try:
            doctests = doctest.DocTestSuite(module_name)
        except ValueError:
            # Python 3.4-, DocTestSuite raises ValueError if no doctests are
            # present.
            print 'doctest: skipping "%s" - no tests' % module_name
            continue
        else:
            # Python 3.5+, DocTestSuite returns an empty suite if no
            # doctests are present.
            if doctests.countTestCases() > 0:
                tests.addTests(doctests)

    return tests


if __name__ == '__main__':
    if sys.version_info < (2, 7):
        # Python 2.6 or less, unittes load_tests protocol not yet implemented
        print 'doctest: skipping all doctests (requires Python 2.7+)'
    else:
        unittest.main()
