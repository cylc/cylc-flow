#!/usr/bin/env python3

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
"""cylc support for the Jinja2 template processor

Importing code should catch ImportError in case Jinja2 is not installed.
"""

from glob import glob
import os
import re
import sys
import traceback

from jinja2 import (
    BaseLoader,
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    StrictUndefined,
    TemplateNotFound,
    TemplateSyntaxError)

from parsec import LOG
from parsec.exceptions import Jinja2Error


TRACEBACK_LINENO = re.compile(r'(\s+)?File "<template>", line (\d+)')
CONTEXT_LINES = 3


class PyModuleLoader(BaseLoader):
    """Load python module as Jinja2 template.

    This loader piggybacks on the jinja import mechanism and
    returns an empty template that exports module's namespace."""

    # no source access for this loader
    has_source_access = False

    def __init__(self, prefix='__python__'):
        self._templates = {}
        # prefix that can be used to avoid name collisions with template files
        self._python_namespace_prefix = prefix + '.'

    # pylint: disable-msg=redefined-builtin
    def load(self, environment, name, globals=None):
        """Imports Python module and returns it as Jinja2 template."""
        if name.startswith(self._python_namespace_prefix):
            name = name[len(self._python_namespace_prefix):]
        try:
            return self._templates[name]
        except KeyError:
            pass
        try:
            mdict = __import__(name, fromlist=['*']).__dict__
        except ImportError:
            raise TemplateNotFound(name)

        # inject module dict into the context of an empty template
        def root_render_func(context, *args, **kwargs):
            """Template render function."""
            if False:
                yield None  # to make it a generator
            context.vars.update(mdict)
            context.exported_vars.update(mdict)

        templ = environment.from_string('')
        templ.root_render_func = root_render_func
        self._templates[name] = templ
        return templ


def raise_helper(message, error_type='Error'):
    """Provides a Jinja2 function for raising exceptions."""
    # TODO - this more nicely
    raise Exception('Jinja2 %s: %s' % (error_type, message))


def assert_helper(logical, message):
    """Provides a Jinja2 function for asserting logical expressions."""
    if not logical:
        raise_helper(message, 'Assertation Error')
    return ''  # Prevent None return value polluting output.


def jinja2environment(dir_=None):
    """Set up and return Jinja2 environment."""
    if dir_ is None:
        dir_ = os.getcwd()

    env = Environment(
        loader=ChoiceLoader([FileSystemLoader(dir_), PyModuleLoader()]),
        undefined=StrictUndefined,
        extensions=['jinja2.ext.do'])

    # Load any custom Jinja2 filters, tests or globals in the suite
    # definition directory
    # Example: a filter to pad integer values some fill character:
    # |(file SUITE_DEFINITION_DIRECTORY/Jinja2/foo.py)
    # |  #!/usr/bin/env python3
    # |  def foo( value, length, fillchar ):
    # |     return str(value).rjust( int(length), str(fillchar) )
    for namespace in ['filters', 'tests', 'globals']:
        nspdir = 'Jinja2' + namespace.capitalize()
        fdirs = [
            os.path.join(dir_, nspdir),
            os.path.join(os.environ['HOME'], '.cylc', nspdir)
        ]
        if 'CYLC_DIR' in os.environ:
            fdirs.append(os.path.join(os.environ['CYLC_DIR'], 'lib', nspdir))
        for fdir in fdirs:
            if os.path.isdir(fdir):
                sys.path.insert(1, os.path.abspath(fdir))
                for name in glob(os.path.join(fdir, '*.py')):
                    fname = os.path.splitext(os.path.basename(name))[0]
                    # TODO - EXCEPTION HANDLING FOR LOADING CUSTOM FILTERS
                    module = __import__(fname)
                    envnsp = getattr(env, namespace)
                    envnsp[fname] = getattr(module, fname)

    # Import SUITE HOST USER ENVIRONMENT into template:
    # (usage e.g.: {{environ['HOME']}}).
    env.globals['environ'] = os.environ
    env.globals['raise'] = raise_helper
    env.globals['assert'] = assert_helper
    return env


def get_error_location():
    """Extract template line number from end of traceback.

    Returns:
        int: The line number or None if not found.

    """
    for line in reversed(traceback.format_exc().splitlines()):
        match = TRACEBACK_LINENO.match(line)
        if match:
            return int(match.groups()[1])
    return None


def jinja2process(flines, dir_, template_vars=None):
    """Pass configure file through Jinja2 processor."""
    # Load file lines into a template, excluding '#!jinja2' so that
    # '#!cylc-x.y.z' rises to the top. Callers should handle jinja2
    # TemplateSyntaxerror and TemplateError.
    if template_vars:
        LOG.debug(
            'Setting Jinja2 template variables:\n%s',
            '\n'.join(
                ['+ %s=%s' % item for item in sorted(template_vars.items())]))

    # Jinja2 render method requires a dictionary as argument (not None):
    if not template_vars:
        template_vars = {}

    # CALLERS SHOULD HANDLE JINJA2 TEMPLATESYNTAXERROR AND TEMPLATEERROR
    # AND TYPEERROR (e.g. for not using "|int" filter on number inputs.
    # Convert unicode to plain str, ToDo - still needed for parsec?)

    try:
        env = jinja2environment(dir_)
        template = env.from_string('\n'.join(flines[1:]))
        lines = str(template.render(template_vars)).splitlines()
    except TemplateSyntaxError as exc:
        filename = None
        # extract source lines
        if exc.lineno and exc.source and not exc.filename:
            # error in suite.rc or cylc include file
            lines = exc.source.splitlines()
        elif exc.lineno and exc.filename:
            # error in jinja2 include file
            filename = os.path.relpath(exc.filename, dir_)
            with open(exc.filename, 'r') as include_file:
                include_file.seek(max(exc.lineno - CONTEXT_LINES, 0), 0)
                lines = []
                for _ in range(CONTEXT_LINES):
                    lines.append(include_file.readline().splitlines()[0])
        if lines:
            # extract context lines from source lines
            lines = lines[max(exc.lineno - CONTEXT_LINES, 0):exc.lineno]

        raise Jinja2Error(exc, lines=lines, filename=filename)
    except Exception as exc:
        lineno = get_error_location()
        lines = None
        if lineno:
            lineno += 1  # shebang line ignored by jinja2
            lines = flines[max(lineno - CONTEXT_LINES, 0):lineno]
        raise Jinja2Error(exc, lines=lines)

    suiterc = []
    for line in lines:
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
