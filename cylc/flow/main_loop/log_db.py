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
"""Log all database transactions.

.. note::

   This plugin is for Cylc developers debugging database issues.

Writes an SQL file into the workflow run directory on shutown.

"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

import sqlparse

from cylc.flow import CYLC_LOG
from cylc.flow.main_loop import (startup, shutdown)


DB_LOG = logging.getLogger(f'{CYLC_LOG}-db')


def _format(sql_string):
    """Pretty print an SQL statement."""
    return '\n'.join(
        sqlparse.format(
            statement,
            reindent_aligned=True,
            use_space_around_operators=True,
            strip_comments=True,
            keyword_case='upper',
            identifier_case='lower',
        )
        for statement in sqlparse.split(sql_string)
    ) + '\n'


def _log(sql_string):
    """Log a SQL string."""
    DB_LOG.info(_format(sql_string))


def _patch_db_connect(db_connect_method):
    """Patch the workflow DAO to configure logging.

    We patch the connect method so that any subsequent re-connections
    are also patched.
    """
    def _inner(*args, **kwargs):
        conn = db_connect_method(*args, **kwargs)
        conn.set_trace_callback(_log)
        return conn
    return _inner


@startup
async def init(scheduler, state):
    # configure log handler
    DB_LOG.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        str(Path(scheduler.workflow_run_dir, f'{__name__}.sql')),
        maxBytes=1000000,
    )
    state['log_handler'] = handler
    DB_LOG.addHandler(handler)

    # configure the DB manager to log all DB operations
    scheduler.workflow_db_mgr.pri_dao.connect = _patch_db_connect(
        scheduler.workflow_db_mgr.pri_dao.connect
    )


@shutdown
async def stop(scheduler, state):
    handler = state.get('log_handler')
    if handler:
        handler.close()
