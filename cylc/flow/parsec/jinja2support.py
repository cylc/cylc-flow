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
"""cylc support for the Jinja2 template processor

Importing code should catch ImportError in case Jinja2 is not installed.
"""

from contextlib import suppress
from glob import glob
import importlib
import os
import pkgutil
import re
import sys
import traceback
import typing as t

from jinja2 import (
    BaseLoader,
    ChoiceLoader,
    Environment,
    FileSystemLoader,
    StrictUndefined,
    TemplateNotFound,
    TemplateSyntaxError)

from cylc.flow import LOG
from cylc.flow.parsec.exceptions import Jinja2Error
from cylc.flow.parsec.fileparse import get_cylc_env_vars

TRACEBACK_LINENO = re.compile(
    r'\s+?File "(?P<file>.*)", line (?P<line>\d+), in .*template'
)
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

    def load(
        self,
        environment,
        name,
        globals=None  # noqa: A002 (required to match underlying interface?)
    ):
        """Imports Python module and returns it as Jinja2 template."""
        if name.startswith(self._python_namespace_prefix):
            name = name[len(self._python_namespace_prefix):]
        with suppress(KeyError):
            return self._templates[name]
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
        raise_helper(message, 'Assertion Error')
    return ''  # Prevent None return value polluting output.


def _load_jinja2_extensions():
    """
    Load modules under the cylc.jinja package namespace.

    Filters provided by third-party packages (i.e. user created packages) will
    also be included if correctly put in the cylc.jinja.filters namespace.

    Global variables are expected to be found in cylc.jinja.globals,
    and jinja tests in cylc.jinja.tests.

    The dictionary returned contains the full module name (e.g.
    cylc.jinja.filters.pad), and the second value is the module
    object (same object as in __import__("module_name")__).

    :return: jinja2 filter modules
    :rtype: dict[string, object]
    """
    jinja2_extensions = {}
    for module_name in [
        "cylc.flow.jinja.filters",
        "cylc.flow.jinja.globals",
        "cylc.flow.jinja.tests"
    ]:
        try:
            module = importlib.import_module(module_name)
            jinja2_filters_modules = pkgutil.iter_modules(
                module.__path__, f"{module.__name__}.")
            if jinja2_filters_modules:
                namespace = module_name.split(".")[-1]
                jinja2_extensions[namespace] = {
                    name.split(".")[-1]: importlib.import_module(name)
                    for finder, name, ispkg in jinja2_filters_modules
                }
        except ModuleNotFoundError:
            # Nothing to do, we may start without any filters/globals/tests
            pass

    return jinja2_extensions


def jinja2environment(dir_=None):
    """Set up and return Jinja2 environment."""
    if dir_ is None:
        dir_ = os.getcwd()

    # Ignore bandit false positive: B701:jinja2_autoescape_false
    # This env is not used to render content that is vulnerable to XSS.
    env = Environment(  # nosec
        loader=ChoiceLoader([FileSystemLoader(dir_), PyModuleLoader()]),
        undefined=StrictUndefined,
        extensions=['jinja2.ext.do'])

    # Load Jinja2 filters using setuptools
    for scope, extensions in _load_jinja2_extensions().items():
        for fname, module in extensions.items():
            getattr(env, scope)[fname] = getattr(module, fname)

    # Load any custom Jinja2 filters, tests or globals in the workflow
    # definition directory
    # Example: a filter to pad integer values some fill character:
    # |(file WORKFLOW_DEFINITION_DIRECTORY/Jinja2/foo.py)
    # |  #!/usr/bin/env python3
    # |  def foo( value, length, fillchar ):
    # |     return str(value).rjust( int(length), str(fillchar) )
    for namespace in ['filters', 'tests', 'globals']:
        nspdir = 'Jinja2' + namespace.capitalize()
        fdirs = [os.path.join(dir_, nspdir)]
        try:
            fdirs.append(os.path.join(os.environ['HOME'], '.cylc', nspdir))
        except KeyError:
            # (Needed for tests/f/cylc-get-site-config/04-homeless.t!)
            LOG.warning(f"$HOME undefined: can't load ~/.cylc/{nspdir}")
        for fdir in fdirs:
            if os.path.isdir(fdir):
                sys.path.insert(1, os.path.abspath(fdir))
                for name in glob(os.path.join(fdir, '*.py')):
                    fname = os.path.splitext(os.path.basename(name))[0]
                    # TODO - EXCEPTION HANDLING FOR LOADING CUSTOM FILTERS
                    module = __import__(fname)
                    envnsp = getattr(env, namespace)
                    envnsp[fname] = getattr(module, fname)

    # Import WORKFLOW HOST USER ENVIRONMENT into template:
    # (Usage e.g.: {{environ['HOME']}}).
    env.globals['environ'] = os.environ
    env.globals['raise'] = raise_helper
    env.globals['assert'] = assert_helper

    # Add `CYLC_` environment variables to the global namespace.
    env.globals.update(
        get_cylc_env_vars()
    )
    return env


def get_error_lines(
    base_template_file: str,
    template_lines: t.List[str],
) -> t.Dict[str, t.List[str]]:
    """Extract exception lines from Jinja2 tracebacks.

    Returns:
        {filename: [exception_line, ...]}

        There may be multiple entries due to {% include %} statements.

    """
    ret = {}
    for line in reversed(traceback.format_exc().splitlines()):
        match = TRACEBACK_LINENO.match(line)
        lines: t.List[str] = []
        if match:
            filename = match.groupdict()['file']
            lineno = int(match.groupdict()['line'])
            start_line = max(lineno - CONTEXT_LINES, 0)
            if filename in {'<template>', '<unknown>'}:
                filename = base_template_file
                lineno += 1  # shebang line ignored by jinja2
                lines = template_lines[start_line:lineno]
            elif os.path.isfile(filename):
                with open(filename, 'r') as jinja2_file:
                    for i, fline in enumerate(jinja2_file, start=1):
                        if i < start_line:
                            continue
                        if i > lineno:
                            break
                        # use splitlines to remove the newline char at the
                        # end of the line
                        lines.append(fline.splitlines()[0])
            if lines:
                ret[filename] = lines

    return ret


def jinja2process(
    fpath: str,
    flines: t.List[str],
    dir_: str,
    template_vars: t.Optional[t.Dict[str, t.Any]] = None,
) -> t.List[str]:
    """Pass configure file through Jinja2 processor.

    Args:
        fpath:
            The path to the root template file (i.e. the flow.cylc file)
        flines:
            List of template lines to process.
        dir_:
            The path to the configuration directory.
        template_vars:
            Dictionary of template variables.

    """
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
            # error in flow.cylc or cylc include file
            lines = exc.source.splitlines()
        elif exc.lineno and exc.filename:
            # error in jinja2 include file
            filename = os.path.relpath(exc.filename, dir_)
            with open(exc.filename, 'r') as include_file:
                include_file.seek(max(exc.lineno - CONTEXT_LINES, 0), 0)
                lines = []
                for _ in range(CONTEXT_LINES):
                    lines.append(include_file.readline().splitlines()[0])

        raise Jinja2Error(
            exc,
            lines=get_error_lines(fpath, flines),
            filename=filename
        )
    except Exception as exc:
        raise Jinja2Error(
            exc,
            lines=get_error_lines(fpath, flines),
        )

    # Ignore blank lines (lone Jinja2 statements leave blank lines behind)
    return [line for line in lines if line.strip()]
