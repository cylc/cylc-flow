#!/usr/bin/env bash
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
#-------------------------------------------------------------------------------
# Test cylc show multiple tasks
. "$(dirname "$0")/test_header"

set_test_number 4

install_workflow "${TEST_NAME_BASE}" "${TEST_NAME_BASE}"

run_ok "${TEST_NAME_BASE}-validate" cylc validate  "${WORKFLOW_NAME}"
workflow_run_ok "${TEST_NAME_BASE}-run" \
    cylc play --reference-test --debug --no-detach "${WORKFLOW_NAME}"

RUND="${RUN_DIR}/${WORKFLOW_NAME}"
contains_ok "${RUND}/show.txt" <<'__TXT__'

Task ID: 2016/t1
title: (not given)
description: (not given)
URL: (not given)
state: running
prerequisites: ('⨯': not satisfied)
  ✓ 2015/t1 started
outputs: ('⨯': not completed)
  ⨯ 2016/t1 expired
  ✓ 2016/t1 submitted
  ⨯ 2016/t1 submit-failed
  ✓ 2016/t1 started
  ⨯ 2016/t1 succeeded
  ⨯ 2016/t1 failed
output completion: incomplete
  ⨯ ⦙  succeeded

Task ID: 2017/t1
title: (not given)
description: (not given)
URL: (not given)
state: running
prerequisites: ('⨯': not satisfied)
  ✓ 2016/t1 started
outputs: ('⨯': not completed)
  ⨯ 2017/t1 expired
  ✓ 2017/t1 submitted
  ⨯ 2017/t1 submit-failed
  ✓ 2017/t1 started
  ⨯ 2017/t1 succeeded
  ⨯ 2017/t1 failed
output completion: incomplete
  ⨯ ⦙  succeeded

Task ID: 2018/t1
title: (not given)
description: (not given)
URL: (not given)
state: running
prerequisites: ('⨯': not satisfied)
  ✓ 2017/t1 started
outputs: ('⨯': not completed)
  ⨯ 2018/t1 expired
  ✓ 2018/t1 submitted
  ⨯ 2018/t1 submit-failed
  ✓ 2018/t1 started
  ⨯ 2018/t1 succeeded
  ⨯ 2018/t1 failed
output completion: incomplete
  ⨯ ⦙  succeeded
__TXT__

contains_ok "${RUND}/show2.txt" <<'__TXT__'

TASK NAME: t1
title: (not given)
description: (not given)
URL: (not given)

TASK NAME: t2
title: beer
description: better than water
abv: 12%
URL: beer.com
__TXT__


purge
exit
