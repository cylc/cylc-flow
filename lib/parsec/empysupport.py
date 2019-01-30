#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
"""cylc support for the EmPy template processor

Importing code should catch ImportError in case EmPy is not installed.
"""

from StringIO import StringIO
import em
import os
import sys


class EmPyError(Exception):
    """Wrapper class for EmPy exceptions."""

    def __init__(self, exc, lineno):
        Exception.__init__(self, exc)
        self.lineno = lineno


def empyprocess(flines, dir_, template_vars=None):
    """Pass configure file through EmPy processor."""

    cwd = os.getcwd()

    os.chdir(dir_)
    ftempl = StringIO('\n'.join(flines))
    xtempl = StringIO()
    interpreter = em.Interpreter(output=em.UncloseableFile(xtempl))
    try:
        interpreter.file(ftempl, '<template>', template_vars)
    except Exception as exc:
        lineno = interpreter.contexts[-1].identify()[1]
        raise EmPyError(interpreter.meta(exc), lineno), None, sys.exc_info()[2]
    finally:
        interpreter.shutdown()
        xsuite = xtempl.getvalue()
        os.chdir(cwd)
        ftempl.close()
        xtempl.close()

    suiterc = []
    for line in xsuite.splitlines():
        # EmPy leaves blank lines where source lines contain
        # only EmPy code; this matters if line continuation
        # markers are involved, so we remove blank lines here.
        if not line.strip():
            continue
            # restoring newlines here is only necessary for display by
        # the cylc view command:
        # ##suiterc.append(line + '\n')
        suiterc.append(line)

    return suiterc
