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
"""cylc support for the EmPy template processor

Importing code should catch ImportError in case EmPy is not installed.
"""

from io import StringIO
import em
import os
import typing as t

from cylc.flow.parsec.exceptions import EmPyError


def empyprocess(
    _fpath: str,
    flines: t.List[str],
    dir_: str,
    template_vars: t.Optional[t.Dict[str, t.Any]] = None,
) -> t.List[str]:
    """Pass configure file through EmPy processor.

    Args:
        _fpath:
            The path to the root template file (i.e. the flow.cylc file)
        flines:
            List of template lines to process.
        dir_:
            The path to the configuration directory.
        template_vars:
            Dictionary of template variables.

    """

    cwd = os.getcwd()

    os.chdir(dir_)
    ftempl = StringIO('\n'.join(flines))
    xtempl = StringIO()
    interpreter = em.Interpreter(output=em.UncloseableFile(xtempl))
    try:
        interpreter.file(ftempl, '<template>', template_vars)
    except Exception as exc:
        lineno = interpreter.contexts[-1].identify()[1]
        raise EmPyError(
            str(exc),
            lines={'<template>': flines[max(lineno - 4, 0): lineno]},
        )
    finally:
        interpreter.shutdown()
        xworkflow = xtempl.getvalue()
        os.chdir(cwd)
        ftempl.close()
        xtempl.close()

    flow_config = []
    for line in xworkflow.splitlines():
        # EmPy leaves blank lines where source lines contain
        # only EmPy code; this matters if line continuation
        # markers are involved, so we remove blank lines here.
        if not line.strip():
            continue
            # restoring newlines here is only necessary for display by
        # the cylc view command:
        # ##flow_config.append(line + '\n')
        flow_config.append(line)

    return flow_config
