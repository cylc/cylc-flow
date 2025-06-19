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

"""Functionality for streaming Cylc logs over network interfaces."""

from logging import Handler, NOTSET, LogRecord
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from cylc.flow.scheduler import Scheduler


class ProtobufStreamHandler(Handler):
    """Log handler for routing log messages via Protobuf."""

    def __init__(self, schd: 'Scheduler', level: int = NOTSET):
        Handler.__init__(self, level=level)
        self.schd = schd

    def emit(self, record: LogRecord):
        self.schd.data_store_mgr.delta_log_record(record)
