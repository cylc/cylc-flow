#!/usr/bin/env bash
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
#-------------------------------------------------------------------------------
# Test cylc show multiple tasks
. "$(dirname "$0")/test_header"

set_test_number 4

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate  "${SUITE_NAME}"
suite_run_ok "${TEST_NAME_BASE}-run" \
    cylc run --reference-test --debug --no-detach "${SUITE_NAME}"

RUND="${RUN_DIR}/${SUITE_NAME}"
for FILE in "${RUND}/show1.txt" "${RUND}/show2.txt"; do
    contains_ok "${FILE}" <<'__TXT__'
----
TASK ID: t1.2016
title: (not given)
description: (not given)

prerequisites (- => not satisfied):
  (None)

outputs (- => not completed):
  - t1.2016 expired
  + t1.2016 submitted
  - t1.2016 submit-failed
  + t1.2016 started
  - t1.2016 succeeded
  - t1.2016 failed
----
TASK ID: t1.2017
title: (not given)
description: (not given)

prerequisites (- => not satisfied):
  + t1.2016 started

outputs (- => not completed):
  - t1.2017 expired
  + t1.2017 submitted
  - t1.2017 submit-failed
  + t1.2017 started
  - t1.2017 succeeded
  - t1.2017 failed
----
TASK ID: t1.2018
title: (not given)
description: (not given)

prerequisites (- => not satisfied):
  + t1.2017 started

outputs (- => not completed):
  - t1.2018 expired
  + t1.2018 submitted
  - t1.2018 submit-failed
  + t1.2018 started
  - t1.2018 succeeded
  - t1.2018 failed
__TXT__
done

purge_suite "${SUITE_NAME}"
exit
