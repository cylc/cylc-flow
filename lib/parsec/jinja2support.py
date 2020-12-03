#!/usr/bin/env python2

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
"""cylc support for the Jinja2 template processor

Importing code should catch ImportError in case Jinja2 is not installed.
"""

from glob import glob
import os
import sys
from jinja2 import (
    select_autoescape,
    BaseLoader,
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    StrictUndefined,
    TemplateNotFound)
from parsec import LOG


def listrange(*args):
    """Return a range as a list.

    Python equivalent to the Jinja2:
        range() | list

        >>> listrange(5)
        [0, 1, 2, 3, 4]
        >>> listrange(0, 5, 2)
        [0, 2, 4]

    """
    return list(range(*args))


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
        autoescape=select_autoescape(
            enabled_extensions=(),
            default_for_string=False,
            default=False),
        loader=ChoiceLoader([FileSystemLoader(dir_), PyModuleLoader()]),
        undefined=StrictUndefined,
        extensions=['jinja2.ext.do']
    )

    # Load any custom Jinja2 filters, tests or globals in the suite
    # definition directory
    # Example: a filter to pad integer values some fill character:
    # |(file SUITE_DEFINITION_DIRECTORY/Jinja2/foo.py)
    # |  #!/usr/bin/env python2
    # |  def foo( value, length, fillchar ):
    # |     return str(value).rjust( int(length), str(fillchar) )
    for namespace in ['filters', 'tests', 'globals']:
        nspdir = 'Jinja2' + namespace.capitalize()
        for fdir in [
                os.path.join(os.environ['CYLC_DIR'], 'lib', nspdir),
                os.path.join(dir_, nspdir),
                os.path.join(os.environ['HOME'], '.cylc', nspdir)]:
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
    env.globals['listrange'] = listrange
    return env


def jinja2process(flines, dir_, template_vars=None):
    """Pass configure file through Jinja2 processor."""
    # Set up Jinja2 environment.
    env = jinja2environment(dir_)

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
