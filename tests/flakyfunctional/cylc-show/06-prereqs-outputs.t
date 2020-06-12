#!/bin/bash
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
# Use "cylc show" to confirm that the prerequisites and outputs of a task (with
# conditional triggers) are as expected after various internal and forced state
# changes. See GitHub #2599, #2600, #2329.

. "$(dirname "$0")/test_header"

set_test_number 9

install_suite "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"
SHARE="$(cylc get-site-config --print-run-dir)/${SUITE_NAME}/share"

#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-validate"
run_ok "${TEST_NAME}" cylc validate "${SUITE_NAME}"

#-------------------------------------------------------------------------------
TEST_NAME="${TEST_NAME_BASE}-run"
suite_run_ok "${TEST_NAME}" cylc run --debug --no-detach "${SUITE_NAME}"

#-------------------------------------------------------------------------------
# While bar_4 runs, before baz.1 runs.
cmp_ok "${SHARE}/bar_x4.out" <<'__SHOW_OUTPUT__'
title: (not given)
description: (not given)
URL: (not given)

prerequisites (- => not satisfied):
  - (0 | 1 | 2 | 3)
  - 	0 = foo_x1.1 succeeded
  - 	1 = foo_x2.1 succeeded
  - 	2 = foo_x3.1 succeeded
  - 	3 = foo_x4.1 succeeded
  - ((1 | 0) & (3 | 2) & (5 | 4) & (7 | 6))
  + 	0 = bar_x1.1 failed
  - 	1 = bar_x1.1 succeeded
  + 	2 = bar_x2.1 failed
  - 	3 = bar_x2.1 succeeded
  + 	4 = bar_x3.1 failed
  - 	5 = bar_x3.1 succeeded
  - 	6 = bar_x4.1 failed
  - 	7 = bar_x4.1 succeeded

outputs (- => not completed):
  - baz.1 expired
  - baz.1 submitted
  - baz.1 submit-failed
  - baz.1 started
  - baz.1 succeeded
  - baz.1 failed
__SHOW_OUTPUT__

#-------------------------------------------------------------------------------
# While baz.1 runs
cmp_ok "${SHARE}/baz2.out" <<'__SHOW_OUTPUT__'
title: (not given)
description: (not given)
URL: (not given)

prerequisites (- => not satisfied):
  + (0 | 1 | 2 | 3)
  - 	0 = foo_x1.1 succeeded
  - 	1 = foo_x2.1 succeeded
  - 	2 = foo_x3.1 succeeded
  + 	3 = foo_x4.1 succeeded
  + ((1 | 0) & (3 | 2) & (5 | 4) & (7 | 6))
  + 	0 = bar_x1.1 failed
  - 	1 = bar_x1.1 succeeded
  + 	2 = bar_x2.1 failed
  - 	3 = bar_x2.1 succeeded
  + 	4 = bar_x3.1 failed
  - 	5 = bar_x3.1 succeeded
  - 	6 = bar_x4.1 failed
  + 	7 = bar_x4.1 succeeded

outputs (- => not completed):
  - baz.1 expired
  + baz.1 submitted
  - baz.1 submit-failed
  + baz.1 started
  - baz.1 succeeded
  - baz.1 failed
__SHOW_OUTPUT__

#-------------------------------------------------------------------------------
# After baz.1 succeeded.
cmp_ok "${SHARE}/succeeded.out" <<'__SHOW_OUTPUT__'
title: (not given)
description: (not given)
URL: (not given)

prerequisites (- => not satisfied):
  + (0 | 1 | 2 | 3)
  - 	0 = foo_x1.1 succeeded
  - 	1 = foo_x2.1 succeeded
  - 	2 = foo_x3.1 succeeded
  + 	3 = foo_x4.1 succeeded
  + ((1 | 0) & (3 | 2) & (5 | 4) & (7 | 6))
  + 	0 = bar_x1.1 failed
  - 	1 = bar_x1.1 succeeded
  + 	2 = bar_x2.1 failed
  - 	3 = bar_x2.1 succeeded
  + 	4 = bar_x3.1 failed
  - 	5 = bar_x3.1 succeeded
  - 	6 = bar_x4.1 failed
  + 	7 = bar_x4.1 succeeded

outputs (- => not completed):
  - baz.1 expired
  + baz.1 submitted
  - baz.1 submit-failed
  + baz.1 started
  + baz.1 succeeded
  - baz.1 failed
__SHOW_OUTPUT__

#-------------------------------------------------------------------------------
# After baz.1 reset to expired.
cmp_ok "${SHARE}/expired.out" <<'__SHOW_OUTPUT__'
title: (not given)
description: (not given)
URL: (not given)

prerequisites (- => not satisfied):
  + (0 | 1 | 2 | 3)
  - 	0 = foo_x1.1 succeeded
  - 	1 = foo_x2.1 succeeded
  - 	2 = foo_x3.1 succeeded
  + 	3 = foo_x4.1 succeeded
  + ((1 | 0) & (3 | 2) & (5 | 4) & (7 | 6))
  + 	0 = bar_x1.1 failed
  - 	1 = bar_x1.1 succeeded
  + 	2 = bar_x2.1 failed
  - 	3 = bar_x2.1 succeeded
  + 	4 = bar_x3.1 failed
  - 	5 = bar_x3.1 succeeded
  - 	6 = bar_x4.1 failed
  + 	7 = bar_x4.1 succeeded

outputs (- => not completed):
  + baz.1 expired
  - baz.1 submitted
  - baz.1 submit-failed
  - baz.1 started
  - baz.1 succeeded
  - baz.1 failed
__SHOW_OUTPUT__

#-------------------------------------------------------------------------------
# After baz.1 reset to failed.
cmp_ok "${SHARE}/failed.out" <<'__SHOW_OUTPUT__'
title: (not given)
description: (not given)
URL: (not given)

prerequisites (- => not satisfied):
  + (0 | 1 | 2 | 3)
  - 	0 = foo_x1.1 succeeded
  - 	1 = foo_x2.1 succeeded
  - 	2 = foo_x3.1 succeeded
  + 	3 = foo_x4.1 succeeded
  + ((1 | 0) & (3 | 2) & (5 | 4) & (7 | 6))
  + 	0 = bar_x1.1 failed
  - 	1 = bar_x1.1 succeeded
  + 	2 = bar_x2.1 failed
  - 	3 = bar_x2.1 succeeded
  + 	4 = bar_x3.1 failed
  - 	5 = bar_x3.1 succeeded
  - 	6 = bar_x4.1 failed
  + 	7 = bar_x4.1 succeeded

outputs (- => not completed):
  - baz.1 expired
  + baz.1 submitted
  - baz.1 submit-failed
  + baz.1 started
  - baz.1 succeeded
  + baz.1 failed
__SHOW_OUTPUT__

#-------------------------------------------------------------------------------
# After baz.1 reset to submit-failed
cmp_ok "${SHARE}/submit-failed.out" <<'__SHOW_OUTPUT__'
title: (not given)
description: (not given)
URL: (not given)

prerequisites (- => not satisfied):
  + (0 | 1 | 2 | 3)
  - 	0 = foo_x1.1 succeeded
  - 	1 = foo_x2.1 succeeded
  - 	2 = foo_x3.1 succeeded
  + 	3 = foo_x4.1 succeeded
  + ((1 | 0) & (3 | 2) & (5 | 4) & (7 | 6))
  + 	0 = bar_x1.1 failed
  - 	1 = bar_x1.1 succeeded
  + 	2 = bar_x2.1 failed
  - 	3 = bar_x2.1 succeeded
  + 	4 = bar_x3.1 failed
  - 	5 = bar_x3.1 succeeded
  - 	6 = bar_x4.1 failed
  + 	7 = bar_x4.1 succeeded

outputs (- => not completed):
  - baz.1 expired
  - baz.1 submitted
  + baz.1 submit-failed
  - baz.1 started
  - baz.1 succeeded
  - baz.1 failed
__SHOW_OUTPUT__

#-------------------------------------------------------------------------------
# After baz.1 manually triggered (prereqs should remain unset).
cmp_ok "${SHARE}/trigger.out" <<'__SHOW_OUTPUT__'
title: (not given)
description: (not given)
URL: (not given)

prerequisites (- => not satisfied):
  - (0 | 1 | 2 | 3)
  - 	0 = foo_x1.1 succeeded
  - 	1 = foo_x2.1 succeeded
  - 	2 = foo_x3.1 succeeded
  - 	3 = foo_x4.1 succeeded
  - ((1 | 0) & (3 | 2) & (5 | 4) & (7 | 6))
  - 	0 = bar_x1.1 failed
  - 	1 = bar_x1.1 succeeded
  - 	2 = bar_x2.1 failed
  - 	3 = bar_x2.1 succeeded
  - 	4 = bar_x3.1 failed
  - 	5 = bar_x3.1 succeeded
  - 	6 = bar_x4.1 failed
  - 	7 = bar_x4.1 succeeded

outputs (- => not completed):
  - baz.1 expired
  + baz.1 submitted
  - baz.1 submit-failed
  + baz.1 started
  - baz.1 succeeded
  - baz.1 failed
__SHOW_OUTPUT__

purge_suite "${SUITE_NAME}"
