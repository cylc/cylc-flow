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

import sys
from time import sleep
from cylc.network import COMMS_EXT_TRIG_OBJ_NAME
from cylc.network.https.base_client import BaseCommsClient
from cylc.suite_logging import OUT, ERR


class ExtTriggerClient(BaseCommsClient):
    """Client-side external trigger interface."""

    MAX_N_TRIES = 5
    RETRY_INTVL_SECS = 10.0

    MSG_SEND_FAILED = "Send message: try %s of %s failed"
    MSG_SEND_RETRY = "Retrying in %s seconds, timeout is %s"
    MSG_SEND_SUCCEED = "Send message: try %s of %s succeeded"

    def put(self, event_message, event_id):
        return self.call_server_func(COMMS_EXT_TRIG_OBJ_NAME, "put",
                                     event_message=event_message,
                                     event_id=event_id)

    def send_retry(self, event_message, event_id,
                   max_n_tries, retry_intvl_secs):
        """CLI external trigger interface."""

        max_n_tries = int(max_n_tries or self.__class__.MAX_N_TRIES)
        retry_intvl_secs = float(
            retry_intvl_secs or self.__class__.RETRY_INTVL_SECS)

        sent = False
        i_try = 0
        while not sent and i_try < max_n_tries:
            i_try += 1
            try:
                self.put(event_message, event_id)
            except Exception as exc:
                ERR.error(exc)
                OUT.info(self.__class__.MSG_SEND_FAILED % (
                    i_try,
                    max_n_tries,
                ))
                if i_try >= max_n_tries:
                    break
                OUT.info(self.__class__.MSG_SEND_RETRY % (
                    retry_intvl_secs,
                    self.timeout
                ))
                sleep(retry_intvl_secs)
            else:
                if i_try > 1:
                    OUT.info(self.__class__.MSG_SEND_SUCCEEDED % (
                        i_try,
                        max_n_tries
                    ))
                sent = True
                break
        if not sent:
            sys.exit('ERROR: send failed')
        return sent
