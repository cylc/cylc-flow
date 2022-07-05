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
"""
parsec config file parsing:

 1) inline include-files
 2) process with Jinja2
 3) join continuation lines
 4) parse items into a nested ordered dict
    * line-comments and blank lines are skipped
    * trailing comments are stripped from section headings
    * item value processing:
      - original quoting is retained
      - trailing comments are retained
      (distinguishing between strings and string lists, with all quoting
      and commenting options, is easier during validation when the item
      value type is known).
"""

import os
from pathlib import Path
import re
import sys
import typing as t

from cylc.flow import __version__, iter_entry_points
from cylc.flow import LOG
from cylc.flow.exceptions import PluginError
from cylc.flow.parsec.exceptions import (
    FileParseError, ParsecError, TemplateVarLanguageClash
)
from cylc.flow.parsec.OrderedDict import OrderedDictWithDefaults
from cylc.flow.parsec.include import inline
from cylc.flow.parsec.util import itemstr


# heading/sections can contain commas (namespace name lists) and any
# regex pattern characters (this was for pre cylc-6 satellite tasks).
# Proper task names are checked later in config.py.
_HEADING = re.compile(
    r'''^
    (\s*)                     # 1: indentation
    ((?:\[)+)                 # 2: section marker open
    \s*
    (.+?)                     # 3: section name
    \s*
    ((?:\])+)                 # 4: section marker close
    \s*(\#.*)?                # 5: optional trailing comment
    $''',
    re.VERBOSE)

_KEY_VALUE = re.compile(
    r'''^
    (\s*)                   # indentation
    ([\w+\-:.,!/()^$ ]+?(\s*<.*?>)?)
                            # key (and parameters, e.g. foo<m,n>)
    \s*=\s*                 # =
    (.*)                    # value (quoted any style + comment)
    $   # line end
    ''',
    re.VERBOSE)

# Designed to match lines ending '\ ' without matching '\   comment'
_BAD_CONTINUATION_TRAILING_WHITESPACE = re.compile(
    r'^([^#\n]+)?\\\s+$', re.VERBOSE)

# quoted value regex reference:
#   http://stackoverflow.com/questions/5452655/
#       python-regex-to-match-text-in-single-quotes-
#           ignoring-escaped-quotes-and-tabs-n

_LINECOMMENT = re.compile(r'^\s*#')
_BLANKLINE = re.compile(r'^\s*$')

# triple quoted values on one line
_SINGLE_LINE_SINGLE = re.compile(r"^'''(.*?)'''\s*(#.*)?$")
_SINGLE_LINE_DOUBLE = re.compile(r'^"""(.*?)"""\s*(#.*)?$')
_MULTI_LINE_SINGLE = re.compile(r"^(.*?)'''\s*(#.*)?$")
_MULTI_LINE_DOUBLE = re.compile(r'^(.*?)"""\s*(#.*)?$')

_TRIPLE_QUOTE = {
    "'''": (_SINGLE_LINE_SINGLE, _MULTI_LINE_SINGLE),
    '"""': (_SINGLE_LINE_DOUBLE, _MULTI_LINE_DOUBLE),
}

_UNCLOSED_MULTILINE = re.compile(
    r'(?<![\w>])\[.*\]'
)


def _concatenate(lines):
    """concatenate continuation lines"""
    index = 0
    clines = []
    maxline = len(lines)
    while index < maxline:
        line = lines[index]
        # Raise an error if line has a whitespace after the line break
        if re.match(_BAD_CONTINUATION_TRAILING_WHITESPACE, line):
            msg = ("Syntax error line {0}: Whitespace after the line "
                   "continuation character (\\).")
            raise FileParseError(msg.format(index + 1))
        while line.endswith('\\'):
            if index == maxline - 1:
                # continuation char on the last line
                # must be an error - safe to strip it
                line = line[:-1]
            else:
                index += 1
                line = line[:-1] + lines[index]
        clines.append(line)
        index += 1
    return clines


def addsect(cfig, sname, parents):
    """Add a new section to a nested dict."""
    for p in parents:
        # drop down the parent list
        cfig = cfig[p]
    if sname in cfig:
        # this doesn't warrant a warning unless contained items are repeated
        LOG.debug(
            'Section already encountered: %s', itemstr(parents + [sname]))
    else:
        cfig[sname] = OrderedDictWithDefaults()


def addict(cfig, key, val, parents, index):
    """Add a new [parents...]key=value pair to a nested dict."""
    for p in parents:
        # drop down the parent list
        cfig = cfig[p]

    if not isinstance(cfig, dict):
        # an item of this name has already been encountered at this level
        raise FileParseError(
            'line %d: already encountered %s',
            index, itemstr(parents, key, val))

    if key in cfig:
        oldval = cfig[key]
        # this item already exists
        if (
            parents[0:2] == ['scheduling', 'graph'] or
            # BACK COMPAT: [scheduling][dependencies]
            # url:
            #     https://github.com/cylc/cylc-flow/pull/3191
            # from:
            #     Cylc<=7
            # to:
            #     Cylc8
            # remove at:
            #     Cylc8.x
            parents[0:2] == ['scheduling', 'dependencies']
        ):
            # append the new graph string to the existing one
            if not isinstance(cfig, list):
                cfig[key] = [cfig[key]]
            cfig[key].append(val)
        else:
            cfig[key] = val
        LOG.debug(
            '%s: already exists in configuration:\nold: %s\nnew: %s',
            key, repr(oldval), repr(cfig[key]))  # repr preserves \n
    else:
        cfig[key] = val


def multiline(flines, value, index, maxline):
    """Consume lines for multiline strings."""
    o_index = index
    quot = value[:3]
    newvalue = value[3:]

    # could be a triple-quoted single line:
    single_line = _TRIPLE_QUOTE[quot][0]
    multi_line = _TRIPLE_QUOTE[quot][1]
    mat = single_line.match(value)
    if mat:
        return value, index
    elif newvalue.find(quot) != -1:
        # TODO - this should be handled by validation?:
        # e.g. non-comment follows single-line triple-quoted string
        raise FileParseError('Invalid line', o_index, flines[index])

    while index < maxline:
        index += 1
        newvalue += '\n'
        line = flines[index]
        if line.find(quot) == -1:
            newvalue += line
        else:
            # end of multiline, process it
            break
    else:
        raise FileParseError(
            'Multiline string not closed', o_index, flines[o_index])

    mat = multi_line.match(line)
    if not mat:
        # e.g. end multi-line string followed by a non-comment
        raise FileParseError('Invalid line', o_index, line)

    # value, comment = mat.groups()
    return quot + newvalue + line, index


def process_plugins(fpath, opts):
    """Run a Cylc pre-configuration plugin.

    Plugins should return a dictionary containing:
        'env': A dictionary of environment variables.
        'template_variables': A dictionary of template variables.
        'templating_detected': Where the plugin identifies a templating
            language this is specified here. Expected values are ``jinja2``
            or ``empy``.

    args:
        fpath: Directory where the plugin will look for a config.
        opts: Command line options to be passed to the plugin.

    Returns: Dictionary in the form:
        extra_vars = {
            'env': {},
            'template_variables': {},
            'templating_detected': None
        }
    """
    # Set out blank dictionary for return:
    extra_vars = {
        'env': {},
        'template_variables': {},
        'templating_detected': None
    }

    # Run entry point pre_configure items, trying to merge values with each.:
    for entry_point in iter_entry_points(
        'cylc.pre_configure'
    ):
        try:
            # If you want it to work on sourcedirs you need to get the options
            # to here.
            plugin_result = entry_point.resolve()(
                srcdir=fpath, opts=opts
            )
        except Exception as exc:
            # NOTE: except Exception (purposefully vague)
            # this is to separate plugin from core Cylc errors
            raise PluginError(
                'cylc.pre_configure',
                entry_point.name,
                exc
            ) from None
        for section in ['env', 'template_variables']:
            if section in plugin_result and plugin_result[section] is not None:
                # Raise error if multiple plugins try to update the same keys.
                section_update = plugin_result.get(section, {})
                keys_collision = (
                    extra_vars[section].keys() & section_update.keys()
                )
                if keys_collision:
                    raise ParsecError(
                        f"{entry_point.name} is trying to alter "
                        f"[{section}]{', '.join(sorted(keys_collision))}."
                    )
                extra_vars[section].update(section_update)

        if (
            'templating_detected' in plugin_result and
            plugin_result['templating_detected'] is not None and
            extra_vars['templating_detected'] is not None and
            extra_vars['templating_detected'] !=
                plugin_result['templating_detected']
        ):
            # Don't allow subsequent plugins with different templating_detected
            raise ParsecError(
                "Can't merge templating languages "
                f"{extra_vars['templating_detected']} and "
                f"{plugin_result['templating_detected']}"
            )
        elif(
            'templating_detected' in plugin_result and
            plugin_result['templating_detected'] is not None
        ):
            extra_vars['templating_detected'] = plugin_result[
                'templating_detected'
            ]

    return extra_vars


def merge_template_vars(
    native_tvars: t.Dict[str, t.Any],
    plugin_result: t.Dict[str, t.Any]
) -> t.Dict[str, t.Any]:
    """Manage the merger of Cylc Native and Plugin template variables.

    Args:
        native_tvars: Template variables set on the Cylc command line
            using ``-s`` or a template variable file.
        plugin_result: Plugin result which should contain _at least_
            "templating_detected" and "template_variable" keys.

    Returns:
        template_variables.

    Strategy:
        template variables set in a Cylc Native way should override
        the results of plugins.

    Examples:
        >>> a = {'FOO': 42, 'BAR': 'Hello World'}
        >>> tvars = {'FOO': 24, 'BAZ': 3.14159}
        >>> b = {'templating_detected': 'any', 'template_variables': tvars}
        >>> merge_template_vars(a, b)
        {'FOO': 42, 'BAZ': 3.14159, 'BAR': 'Hello World'}
    """
    if plugin_result['templating_detected'] is not None:
        plugin_tvars = plugin_result['template_variables']
        will_be_overwritten = (
            native_tvars.keys() &
            plugin_tvars.keys()
        )
        for key in will_be_overwritten:
            if plugin_tvars[key] != native_tvars[key]:
                LOG.warning(
                    f'Overriding {key}: {plugin_tvars[key]} ->'
                    f' {native_tvars[key]}'
                )
        plugin_tvars.update(native_tvars)
        return plugin_tvars
    else:
        return native_tvars


def read_and_proc(
    fpath: str,
    template_vars: t.Optional[t.Dict[str, t.Any]] = None,
    viewcfg: t.Any = None,
    opts: t.Any = None,
) -> t.List[str]:
    """
    Read a cylc parsec config file (at fpath), inline any include files,
    process with Jinja2, and concatenate continuation lines.
    Jinja2 processing must be done before concatenation - it could be
    used to generate continuation lines.
    """

    fdir = os.path.dirname(fpath)

    # Allow Python modules in lib/python/ (e.g. for use by Jinja2 filters).
    workflow_lib_python = os.path.join(fdir, "lib", "python")
    if (
        os.path.isdir(workflow_lib_python)
        and workflow_lib_python not in sys.path
    ):
        sys.path.append(workflow_lib_python)

    LOG.debug('Reading file %s', fpath)

    # read the file into a list, stripping newlines
    with open(fpath) as f:
        flines = [line.rstrip('\n') for line in f]

    do_inline = True
    do_empy = True
    do_jinja2 = True
    do_contin = True

    extra_vars = process_plugins(Path(fpath).parent, opts)

    if not template_vars:
        template_vars = {}

    if viewcfg:
        if not viewcfg['empy']:
            do_empy = False
        if not viewcfg['jinja2']:
            do_jinja2 = False
        if not viewcfg['contin']:
            do_contin = False
        if not viewcfg['inline']:
            do_inline = False

    # inline any cylc include-files
    if do_inline:
        flines = inline(
            flines, fdir, fpath, viewcfg=viewcfg)

    template_vars['CYLC_VERSION'] = __version__

    template_vars = merge_template_vars(template_vars, extra_vars)

    template_vars['CYLC_TEMPLATE_VARS'] = template_vars

    # Fail if templating_detected ≠ hashbang
    process_with = hashbang_and_plugin_templating_clash(
        extra_vars['templating_detected'], flines
    )
    # process with EmPy
    if do_empy:
        if (
            extra_vars['templating_detected'] == 'empy' and
            not process_with and
            process_with != 'empy'
        ):
            flines.insert(0, '#!empy')

        if flines and re.match(r'^#![Ee]m[Pp]y\s*', flines[0]):
            LOG.debug('Processing with EmPy')
            try:
                from cylc.flow.parsec.empysupport import empyprocess
            except ImportError:
                raise ParsecError('EmPy Python package must be installed '
                                  'to process file: ' + fpath)
            flines = empyprocess(
                fpath, flines, fdir, template_vars
            )

    # process with Jinja2
    if do_jinja2:
        if (
            extra_vars['templating_detected'] == 'jinja2' and
            not process_with and
            process_with != 'jinja2'
        ):
            flines.insert(0, '#!jinja2')

        if flines and re.match(r'^#![jJ]inja2\s*', flines[0]):
            LOG.debug('Processing with Jinja2')
            try:
                from cylc.flow.parsec.jinja2support import jinja2process
            except ImportError:
                raise ParsecError('Jinja2 Python package must be installed '
                                  'to process file: ' + fpath)
            flines = jinja2process(
                fpath, flines, fdir, template_vars
            )

    # concatenate continuation lines
    if do_contin:
        flines = _concatenate(flines)

    # return rstripped lines
    return [fl.rstrip() for fl in flines]


def hashbang_and_plugin_templating_clash(
    templating: str, flines: t.List[str]
) -> t.Optional[str]:
    """Return file's hashbang/shebang, but raise TemplateVarLanguageClash
    if plugin-set template engine and hashbang do not match.

    Args:
        templating: Template engine set by a plugin.
        flines: The lines of text from file.

    Returns:
        The hashbang, in lower case, to allow for users using any of
        ['empy', 'EmPy', 'EMPY'], or similar in other templating languages.

    Examples:
        - Hashbang and templating_detected match:
            >>> thisfunc = hashbang_and_plugin_templating_clash
            >>> thisfunc('jinja2', ['#!Jinja2', 'stuff'])
            'jinja2'

        - Function returns nothing:
            >>> thisfunc('', [''])

        - Function raises if templating engines clash:
            >>> thisfunc('empy', ['#!jinja2'])
            Traceback (most recent call last):
                ...
            cylc.flow.parsec.exceptions.TemplateVarLanguageClash: ...
    """
    hashbang: t.Optional[str] = None
    # Get hashbang if possible:
    if flines:
        match = re.match(r'^#!(\S+)', flines[0])
        if match:
            hashbang = match[1].lower()
    if (
        hashbang and templating
        and templating != 'template variables'
        and hashbang != templating
    ):
        raise TemplateVarLanguageClash(
            f"A plugin set the templating engine to {templating}"
            f" which does not match {flines[0]} set in flow.cylc."
        )
    return hashbang


def parse(
    fpath: str,
    output_fname: t.Optional[str] = None,
    template_vars: t.Optional[t.Dict[str, t.Any]] = None,
    opts: t.Any = None,
) -> OrderedDictWithDefaults:
    """Parse file items line-by-line into a corresponding nested dict."""

    # read and process the file (jinja2, include-files, line continuation)
    flines = read_and_proc(fpath, template_vars, opts=opts)
    if output_fname:
        with open(output_fname, 'w') as handle:
            handle.write('\n'.join(flines) + '\n')
        LOG.debug('Processed configuration dumped: %s', output_fname)

    nesting_level = 0
    config = OrderedDictWithDefaults()
    parents: t.List[str] = []

    maxline = len(flines) - 1
    index = -1

    while index < maxline:
        index += 1
        line = flines[index]

        if re.match(_LINECOMMENT, line):
            # skip full-line comments
            continue

        if re.match(_BLANKLINE, line):
            # skip blank lines
            continue

        m = re.match(_HEADING, line)
        if m:
            # matched a section heading
            s_open, sect_name, s_close = m.groups()[1:-1]
            nb = len(s_open)

            if nb != len(s_close):
                raise FileParseError('bracket mismatch', index, line)
            elif nb == nesting_level:
                # sibling section
                parents = parents[:-1] + [sect_name]
            elif nb == nesting_level + 1:
                # child section
                parents = parents + [sect_name]
            elif nb < nesting_level:  # noqa: SIM106
                # back up one or more levels
                ndif = nesting_level - nb
                parents = parents[:-ndif - 1] + [sect_name]
            else:
                raise FileParseError('Error line', index=index, line=line)
            nesting_level = nb
            addsect(config, sect_name, parents[:-1])

        else:
            m = re.match(_KEY_VALUE, line)
            if m:
                # matched a key=value item
                key, _, val = m.groups()[1:]
                if val.startswith('"""') or val.startswith("'''"):
                    # triple quoted - may be a multiline value
                    val, index = multiline(flines, val, index, maxline)
                addict(config, key, val, parents, index)
            else:
                # no match
                help_lines = None
                if 'val' in locals() and _UNCLOSED_MULTILINE.search(val):
                    # this might be an unclosed multiline string
                    # provide a helpful error message
                    key_name = ''.join(
                        [f'[{parent}]' for parent in parents]
                    ) + key
                    help_lines = [f'Did you forget to close {key_name}?']
                raise FileParseError(
                    'Invalid line',
                    index=index,
                    line=line,
                    help_lines=help_lines
                )

    return config
