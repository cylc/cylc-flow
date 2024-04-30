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

from copy import copy
import os
import textwrap
import typing as t

from cylc.flow.parsec.util import itemstr


TRACEBACK_WRAPPER = textwrap.TextWrapper()


class ParsecError(Exception):
    """Generic exception for Parsec errors."""

    schd_expected: bool = False
    """Set this flag to True on the exception if it is anticipated during
    Cylc Scheduler run (apart from loading of config we do not expect
    ParsecErrors during runtime)."""


class ItemNotFoundError(ParsecError, KeyError):
    """Error raised for missing configuration items."""

    def __init__(self, item):
        self.item = item

    def __str__(self):
        return f'You have not set \"{self.item}\" in this config.'


class InvalidConfigError(ParsecError, KeyError):
    """Error raised for missing configuration items."""

    def __init__(self, item, specname):
        self.item = item
        self.specname = specname

    def __str__(self):
        return (
            f'"{self.item}" is not a valid '
            f'configuration for {self.specname}.'
        )


class NotSingleItemError(ParsecError, TypeError):
    """Error raised if an iterable is given where an item is expected."""

    def __init__(self, item):
        self.item = item

    def __str__(self):
        return f'not a singular item: {self.item}'


class FileParseError(ParsecError):
    """Error raised when attempting to read in the config file(s).

    Args:
        reason:
            Description of error.
        err_type:
            Classification of error (e.g. Jinja2Error).
        help_lines:
            Additional info to include in the exception.
        lines:
            (preferred) Dictionary in the format
            {filename: [context_line, ..., error_line]}
        index:
            The line number of the error in the config (counting from the
            shebang line *not* the first line).
        line:
            The line of the error in the config.
        fpath:
            The path to the file containing the error.

    """

    def __init__(
        self,
        reason: str,
        index: t.Optional[int] = None,
        line: t.Optional[str] = None,
        lines: t.Optional[t.Dict[str, t.List[str]]] = None,
        err_type: t.Optional[str] = None,
        fpath: t.Optional[str] = None,
        help_lines: t.Optional[t.Iterable[str]] = None,
    ):
        self.reason = reason
        self.line_num = index + 1 if index is not None else None
        self.line = line
        self.lines = lines
        self.err_type = err_type
        self.fpath = fpath
        self.help_lines = help_lines or []

    def __str__(self) -> str:
        msg = ''
        msg += self.reason

        if self.line_num is not None or self.fpath:
            temp = []
            if self.fpath:
                temp.append(f'in {self.fpath}')
            if self.line_num is not None:
                temp.append(f'line {self.line_num}')
            msg += f' ({" ".join(temp)})'
        if self.line:
            msg += ":\n   " + self.line.strip()
        if self.lines:
            for filename, lines in self.lines.items():
                msg += f'\nFile {filename}\n  ' + '\n  '.join(lines)
                msg += "\t<--"
                if self.err_type:
                    msg += ' %s' % self.err_type
        help_lines = list(self.help_lines)
        if self.line_num:
            # TODO - make 'view' function independent of cylc:
            help_lines.append("line numbers match 'cylc view -p'")
        for help_line in help_lines:
            msg += f'\n({help_line})'
        return msg


class TemplateVarLanguageClash(FileParseError):
    """Multiple workflow configuration templating engines configured."""


class EmPyError(FileParseError):
    """Wrapper class for EmPy exceptions."""


class Jinja2Error(FileParseError):
    """Wrapper class for Jinja2 exceptions.

    Args:
        exception:
            The exception being re-raised
        lines:
            Dictionary in the format
            {filename: [context_line, ..., error_line]}
        filename:
            Alternative to "lines" where less detail is available.

    """

    def __init__(
        self,
        exception: Exception,
        lines: t.Optional[t.Dict[str, t.List[str]]] = None,
        filename: t.Optional[str] = None,
    ):
        # extract the first sentence of exception
        msg: str = str(exception)
        try:
            msg, tail = msg.split('. ', 1)
        except ValueError:
            tail = ''
        else:
            msg += '.'
            tail = tail.strip()

        # append the filename e.g. for a Jinja2 template
        if filename:
            msg += f'\nError in file "{filename}"'

        # append the rest of the exception
        if tail:
            msg += '\n' + '\n'.join(TRACEBACK_WRAPPER.wrap(tail))

        FileParseError.__init__(
            self,
            msg,
            lines=lines,
            err_type=exception.__class__.__name__
        )


class IncludeFileNotFoundError(ParsecError):
    """Error raised for missing include files."""

    def __init__(self, flist):
        """Missing include file error.

        E.g. for [DIR/top.cylc, DIR/inc/sub.cylc, DIR/inc/gone.cylc]
        "Include-file not found: inc/gone.cylc via inc/sub.cylc from
        DIR/top.cylc"
        """
        rflist = copy(flist)
        top_file = rflist[0]
        top_dir = os.path.dirname(top_file) + '/'
        rflist.reverse()
        msg = rflist[0].replace(top_dir, '')
        for f in rflist[1:-1]:
            msg += ' via %s' % f.replace(top_dir, '')
        msg += ' from %s' % top_file
        ParsecError.__init__(self, msg)


class UpgradeError(ParsecError):
    """Error raised upon fault in an upgrade operation."""


class ValidationError(ParsecError):
    """Generic exception for invalid configurations."""

    def __init__(self, keys, value=None, msg=None, exc=None, vtype=None,
                 key=None):
        self.keys = keys
        self.value = value
        self.msg = msg
        self.exc = exc
        self.vtype = vtype
        self.key = key

    def __str__(self):
        msg = ''
        if self.vtype:
            msg += f'(type={self.vtype}) '
        if self.key:
            msg += itemstr(self.keys, self.key)
        elif self.value:
            msg += itemstr(self.keys[:-1], self.keys[-1], value=self.value)
        if self.msg or self.exc:
            msg += (
                f' - ({self.exc or ""}'
                f'{": " if (self.exc and self.msg) else ""}'
                f'{self.msg or ""})'
            )
        return msg


class IllegalValueError(ValidationError):
    """Bad setting value."""

    def __init__(self, vtype, keys, value, exc=None, msg=None):
        ValidationError.__init__(
            self, keys, vtype=vtype, value=value, exc=exc, msg=msg)


class ListValueError(IllegalValueError):
    """Bad setting value, for a comma separated list."""

    def __init__(self, keys, value, msg=None, exc=None):
        IllegalValueError.__init__(
            self, 'list', keys, value, exc=exc, msg=msg)


class IllegalItemError(ValidationError):
    """Bad setting section or option name."""

    def __init__(self, keys, key, msg=None, exc=None):
        ValidationError.__init__(self, keys, key=key, exc=exc, msg=msg)
