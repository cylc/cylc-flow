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
"""cylc support for the Jinja2 template processor

Importing code should catch ImportError in case Jinja2 is not installed.
"""

from glob import glob
import os
import sys
from jinja2 import (
    Environment,
    FileSystemLoader,
    TemplateError,
    UndefinedError,
    StrictUndefined)
import cylc.flags


def jinja2process(flines, dir_, template_vars=None):
    """Pass configure file through Jinja2 processor."""
    env = Environment(
        loader=FileSystemLoader(dir_),
        undefined=StrictUndefined,
        extensions=['jinja2.ext.do'])

    # Load any custom Jinja2 filters in the suite definition directory
    # Example: a filter to pad integer values some fill character:
    # |(file SUITE_DEFINIION_DIRECTORY/Jinja2/foo.py)
    # |  #!/usr/bin/env python
    # |  def foo( value, length, fillchar ):
    # |     return str(value).rjust( int(length), str(fillchar) )
    for fdir in [
            os.path.join(os.environ['CYLC_DIR'], 'lib', 'Jinja2Filters'),
            os.path.join(dir_, 'Jinja2Filters'),
            os.path.join(os.environ['HOME'], '.cylc', 'Jinja2Filters')]:
        if os.path.isdir(fdir):
            sys.path.append(os.path.abspath(fdir))
            for name in glob(os.path.join(fdir, '*.py')):
                fname = os.path.splitext(os.path.basename(name))[0]
                # TODO - EXCEPTION HANDLING FOR LOADING CUSTOM FILTERS
                module = __import__(fname)
                env.filters[fname] = getattr(module, fname)

    # Import SUITE HOST USER ENVIRONMENT into template:
    # (usage e.g.: {{environ['HOME']}}).
    env.globals['environ'] = os.environ

    # load file lines into a template, excluding '#!jinja2' so
    # that '#!cylc-x.y.z' rises to the top.
    # CALLERS SHOULD HANDLE JINJA2 TEMPLATESYNTAXERROR AND TEMPLATEERROR
    # try:
    # except Exception as exc:
    #     # This happens if we use an unknown Jinja2 filter, for example.
    #     # TODO - THIS IS CAUGHT BY VALIDATE BUT NOT BY VIEW COMMAND...
    #     raise TemplateError(exc)
    if cylc.flags.verbose and template_vars:
        print 'Setting Jinja2 template variables:'
        for item in sorted(template_vars.items()):
            print '    + %s=%s' % item

    # CALLERS SHOULD HANDLE JINJA2 TEMPLATESYNTAXERROR AND TEMPLATEERROR
    # AND TYPEERROR (e.g. for not using "|int" filter on number inputs.
    # Convert unicode to plain str, ToDo - still needed for parsec?)

    suiterc = []
    template = env.from_string('\n'.join(flines[1:]))
    for line in str(template.render(template_vars)).splitlines():
        # Jinja2 leaves blank lines where source lines contain
        # only Jinja2 code; this matters if line continuation
        # markers are involved, so we remove blank lines here.
        if not line.strip():
            continue
            # restoring newlines here is only necessary for display by
        # the cylc view command:
        # ##suiterc.append(line + '\n')
        suiterc.append(line)

    return suiterc
