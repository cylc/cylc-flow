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
"""Set up the cylc environment."""

import logging
import os

CYLC_LOG = 'cylc'

LOG = logging.getLogger(CYLC_LOG)
# Start with a null handler
LOG.addHandler(logging.NullHandler())

LOG_LEVELS = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "NORMAL": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


class LoggerAdaptor(logging.LoggerAdapter):
    """Adds a prefix to log messages."""
    def process(self, msg, kwargs):
        ret = f"[{self.extra['prefix']}] {msg}" if self.extra else msg
        return ret, kwargs


def environ_init():
    """Initialise cylc environment."""
    # Python output buffering delays appearance of stdout and stderr
    # when output is not directed to a terminal (this occurred when
    # running pre-5.0 cylc via the posix nohup command; is it still the
    # case in post-5.0 daemon-mode cylc?)
    os.environ['PYTHONUNBUFFERED'] = 'true'


environ_init()

__version__ = '8.4.0.dev755'


def iter_entry_points(entry_point_name):
    """Iterate over Cylc entry points."""
    import sys
    if sys.version_info[:2] > (3, 11):
        from importlib.metadata import entry_points
    else:
        # BACK COMPAT: importlib_metadata
        #   importlib.metadata was added in Python 3.8. The required interfaces
        #   were completed by 3.12. For lower versions we must use the
        #   importlib_metadata backport.
        # FROM: Python 3.7
        # TO: Python: 3.12
        from importlib_metadata import entry_points
    yield from (
        entry_point
        # for entry_point in entry_points()[entry_point_name]
        for entry_point in entry_points().select(group=entry_point_name)
    )
