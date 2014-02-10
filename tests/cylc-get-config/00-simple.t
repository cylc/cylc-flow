#!/bin/bash
#C: THIS FILE IS PART OF THE CYLC SUITE ENGINE.
#C: Copyright (C) 2008-2014 Hilary Oliver, NIWA
#C: 
#C: This program is free software: you can redistribute it and/or modify
#C: it under the terms of the GNU General Public License as published by
#C: the Free Software Foundation, either version 3 of the License, or
#C: (at your option) any later version.
#C:
#C: This program is distributed in the hope that it will be useful,
#C: but WITHOUT ANY WARRANTY; without even the implied warranty of
#C: MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#C: GNU General Public License for more details.
#C:
#C: You should have received a copy of the GNU General Public License
#C: along with this program.  If not, see <http://www.gnu.org/licenses/>.
#-------------------------------------------------------------------------------
#C: Test cylc get-config
. $(dirname $0)/test_header
#-------------------------------------------------------------------------------
set_test_number 14
#-------------------------------------------------------------------------------
init_suite $TEST_NAME_BASE <<'__SUITERC__'

title = "multiple inheritance example"

description = """To see how multiple inheritance works:

 % cylc list -tb[m] SUITE # list namespaces
 % cylc graph -n SUITE # graph namespaces
 % cylc graph SUITE # dependencies, collapse on first-parent namespaces

  % cylc get-config --sparse --item [runtime]ops_s1 SUITE
  % cylc get-config --sparse --item [runtime]var_p2 foo"""

[scheduling]
    [[dependencies]]
        graph = "OPS:finish-all => VAR"

[runtime]
    [[root]]
    [[OPS]]
        command scripting = echo "RUN: run-ops.sh"
    [[VAR]]
        command scripting = echo "RUN: run-var.sh"
    [[SERIAL]]
        [[[directives]]]
            job_type = serial
    [[PARALLEL]]
        [[[directives]]]
            job_type = parallel
    [[ops_s1, ops_s2]]
        inherit = OPS, SERIAL

    [[ops_p1, ops_p2]]
        inherit = OPS, PARALLEL
        
    [[var_s1, var_s2]]
        inherit = VAR, SERIAL

    [[var_p1, var_p2]]
        inherit = VAR, PARALLEL

[visualization]
    # NOTE ON VISUALIZATION AND MULTIPLE INHERITANCE: overlapping
    # family groups can have overlapping attributes, so long as 
    # non-conflictling attributes are used to style each group. Below,
    # for example, OPS tasks are filled green and SERIAL tasks are
    # outlined blue, so that ops_s1 and ops_s2 are green with a blue
    # outline. But if the SERIAL tasks are explicitly styled as "not
    # filled" (by setting "style=") this will override the fill setting
    # in the (previously defined and therefore lower precedence) OPS
    # group, making ops_s1 and ops_s2 unfilled with a blue outline.
    # Alternatively you can just create a manual node group for ops_s1
    # and ops_s2 and style them separately.
    [[node groups]]
        #(see comment above:)
        #serial_ops = ops_s1, ops_s2
    [[node attributes]]
        OPS = "style=filled", "fillcolor=green"
        SERIAL = "color=blue" #(see comment above:), "style="
        #(see comment above:)
        #serial_ops = "color=blue", "style=filled", "fillcolor=green"
__SUITERC__
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-all
run_ok $TEST_NAME cylc get-config $SUITE_NAME
cmp_ok $TEST_NAME.stderr - </dev/null
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-section1
run_ok $TEST_NAME cylc get-config --item=[scheduling] $SUITE_NAME
cmp_ok $TEST_NAME.stdout - <<__OUT__
cycling = HoursOfTheDay
initial cycle time = 
runahead limit = 
final cycle time = 
[[queues]]
   [[[default]]]
      limit = 0
      members = ops_s1, ops_s2, ops_p1, ops_p2, var_p1, var_p2, var_s1, var_s2
[[special tasks]]
   include at start-up = 
   start-up = 
   one-off = 
   sequential = 
   cold-start = 
   clock-triggered = 
   exclude at start-up = 
[[dependencies]]
   graph = OPS:finish-all => VAR
__OUT__
cmp_ok $TEST_NAME.stderr - </dev/null
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-section1-section
run_ok $TEST_NAME cylc get-config --item=[scheduling][dependencies] $SUITE_NAME
cmp_ok $TEST_NAME.stdout - <<__OUT__
graph = OPS:finish-all => VAR
__OUT__
cmp_ok $TEST_NAME.stderr - </dev/null
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-section1-section-option
run_ok $TEST_NAME cylc get-config --item=[scheduling][dependencies][graph] $SUITE_NAME
cmp_ok $TEST_NAME.stdout - <<__OUT__
OPS:finish-all => VAR
__OUT__
cmp_ok $TEST_NAME.stderr - </dev/null
#-------------------------------------------------------------------------------
TEST_NAME=$TEST_NAME_BASE-section2
run_ok $TEST_NAME cylc get-config --item=[runtime] $SUITE_NAME
cmp_ok $TEST_NAME.stdout - <<'__OUT__'
[[var_p2]]
   command scripting = echo "RUN: run-var.sh"
   enable resurrection = False
   manual completion = False
   retry delays = 
   environment scripting = 
   execution polling intervals = 
   title = 
   extra log files = 
   work sub-directory = $CYLC_TASK_ID
   submission polling intervals = 
   description = 
   initial scripting = 
   pre-command scripting = 
   post-command scripting = 
   inherit = VAR, PARALLEL
   [[[event hooks]]]
      submission timeout handler = 
      submitted handler = 
      started handler = 
      execution timeout handler = 
      submission failed handler = 
      submission retry handler = 
      warning handler = 
      succeeded handler = 
      retry handler = 
      reset timer = False
      execution timeout = 
      failed handler = 
      submission timeout = 
   [[[environment]]]
   [[[directives]]]
      job_type = parallel
   [[[environment filter]]]
      exclude = 
      include = 
   [[[dummy mode]]]
      disable pre-command scripting = True
      disable post-command scripting = True
      disable retries = True
      command scripting = echo Dummy command scripting; sleep $(cylc rnd 1 16)
      disable task event hooks = True
   [[[outputs]]]
   [[[simulation mode]]]
      run time range = 1, 16
      simulate failure = False
      disable retries = True
      disable task event hooks = True
   [[[suite state polling]]]
      interval = 
      host = 
      max-polls = 
      run-dir = 
      user = 
      verbose mode = 
   [[[remote]]]
      owner = 
      suite definition directory = 
      host = 
   [[[job submission]]]
      shell = /bin/bash
      command template = 
      method = background
      retry delays = 
[[OPS]]
   command scripting = echo "RUN: run-ops.sh"
   enable resurrection = False
   manual completion = False
   retry delays = 
   environment scripting = 
   execution polling intervals = 
   title = 
   extra log files = 
   work sub-directory = $CYLC_TASK_ID
   submission polling intervals = 
   description = 
   initial scripting = 
   pre-command scripting = 
   post-command scripting = 
   inherit = 
   [[[event hooks]]]
      submission timeout handler = 
      submitted handler = 
      started handler = 
      execution timeout handler = 
      submission failed handler = 
      submission retry handler = 
      warning handler = 
      succeeded handler = 
      retry handler = 
      reset timer = False
      execution timeout = 
      failed handler = 
      submission timeout = 
   [[[environment]]]
   [[[directives]]]
   [[[environment filter]]]
      exclude = 
      include = 
   [[[dummy mode]]]
      disable pre-command scripting = True
      disable post-command scripting = True
      disable retries = True
      command scripting = echo Dummy command scripting; sleep $(cylc rnd 1 16)
      disable task event hooks = True
   [[[outputs]]]
   [[[simulation mode]]]
      run time range = 1, 16
      simulate failure = False
      disable retries = True
      disable task event hooks = True
   [[[suite state polling]]]
      interval = 
      host = 
      max-polls = 
      run-dir = 
      user = 
      verbose mode = 
   [[[remote]]]
      owner = 
      suite definition directory = 
      host = 
   [[[job submission]]]
      shell = /bin/bash
      command template = 
      method = background
      retry delays = 
[[ops_s1]]
   command scripting = echo "RUN: run-ops.sh"
   enable resurrection = False
   manual completion = False
   retry delays = 
   environment scripting = 
   execution polling intervals = 
   title = 
   extra log files = 
   work sub-directory = $CYLC_TASK_ID
   submission polling intervals = 
   description = 
   initial scripting = 
   pre-command scripting = 
   post-command scripting = 
   inherit = OPS, SERIAL
   [[[event hooks]]]
      submission timeout handler = 
      submitted handler = 
      started handler = 
      execution timeout handler = 
      submission failed handler = 
      submission retry handler = 
      warning handler = 
      succeeded handler = 
      retry handler = 
      reset timer = False
      execution timeout = 
      failed handler = 
      submission timeout = 
   [[[environment]]]
   [[[directives]]]
      job_type = serial
   [[[environment filter]]]
      exclude = 
      include = 
   [[[dummy mode]]]
      disable pre-command scripting = True
      disable post-command scripting = True
      disable retries = True
      command scripting = echo Dummy command scripting; sleep $(cylc rnd 1 16)
      disable task event hooks = True
   [[[outputs]]]
   [[[simulation mode]]]
      run time range = 1, 16
      simulate failure = False
      disable retries = True
      disable task event hooks = True
   [[[suite state polling]]]
      interval = 
      host = 
      max-polls = 
      run-dir = 
      user = 
      verbose mode = 
   [[[remote]]]
      owner = 
      suite definition directory = 
      host = 
   [[[job submission]]]
      shell = /bin/bash
      command template = 
      method = background
      retry delays = 
[[ops_s2]]
   command scripting = echo "RUN: run-ops.sh"
   enable resurrection = False
   manual completion = False
   retry delays = 
   environment scripting = 
   execution polling intervals = 
   title = 
   extra log files = 
   work sub-directory = $CYLC_TASK_ID
   submission polling intervals = 
   description = 
   initial scripting = 
   pre-command scripting = 
   post-command scripting = 
   inherit = OPS, SERIAL
   [[[event hooks]]]
      submission timeout handler = 
      submitted handler = 
      started handler = 
      execution timeout handler = 
      submission failed handler = 
      submission retry handler = 
      warning handler = 
      succeeded handler = 
      retry handler = 
      reset timer = False
      execution timeout = 
      failed handler = 
      submission timeout = 
   [[[environment]]]
   [[[directives]]]
      job_type = serial
   [[[environment filter]]]
      exclude = 
      include = 
   [[[dummy mode]]]
      disable pre-command scripting = True
      disable post-command scripting = True
      disable retries = True
      command scripting = echo Dummy command scripting; sleep $(cylc rnd 1 16)
      disable task event hooks = True
   [[[outputs]]]
   [[[simulation mode]]]
      run time range = 1, 16
      simulate failure = False
      disable retries = True
      disable task event hooks = True
   [[[suite state polling]]]
      interval = 
      host = 
      max-polls = 
      run-dir = 
      user = 
      verbose mode = 
   [[[remote]]]
      owner = 
      suite definition directory = 
      host = 
   [[[job submission]]]
      shell = /bin/bash
      command template = 
      method = background
      retry delays = 
[[ops_p1]]
   command scripting = echo "RUN: run-ops.sh"
   enable resurrection = False
   manual completion = False
   retry delays = 
   environment scripting = 
   execution polling intervals = 
   title = 
   extra log files = 
   work sub-directory = $CYLC_TASK_ID
   submission polling intervals = 
   description = 
   initial scripting = 
   pre-command scripting = 
   post-command scripting = 
   inherit = OPS, PARALLEL
   [[[event hooks]]]
      submission timeout handler = 
      submitted handler = 
      started handler = 
      execution timeout handler = 
      submission failed handler = 
      submission retry handler = 
      warning handler = 
      succeeded handler = 
      retry handler = 
      reset timer = False
      execution timeout = 
      failed handler = 
      submission timeout = 
   [[[environment]]]
   [[[directives]]]
      job_type = parallel
   [[[environment filter]]]
      exclude = 
      include = 
   [[[dummy mode]]]
      disable pre-command scripting = True
      disable post-command scripting = True
      disable retries = True
      command scripting = echo Dummy command scripting; sleep $(cylc rnd 1 16)
      disable task event hooks = True
   [[[outputs]]]
   [[[simulation mode]]]
      run time range = 1, 16
      simulate failure = False
      disable retries = True
      disable task event hooks = True
   [[[suite state polling]]]
      interval = 
      host = 
      max-polls = 
      run-dir = 
      user = 
      verbose mode = 
   [[[remote]]]
      owner = 
      suite definition directory = 
      host = 
   [[[job submission]]]
      shell = /bin/bash
      command template = 
      method = background
      retry delays = 
[[ops_p2]]
   command scripting = echo "RUN: run-ops.sh"
   enable resurrection = False
   manual completion = False
   retry delays = 
   environment scripting = 
   execution polling intervals = 
   title = 
   extra log files = 
   work sub-directory = $CYLC_TASK_ID
   submission polling intervals = 
   description = 
   initial scripting = 
   pre-command scripting = 
   post-command scripting = 
   inherit = OPS, PARALLEL
   [[[event hooks]]]
      submission timeout handler = 
      submitted handler = 
      started handler = 
      execution timeout handler = 
      submission failed handler = 
      submission retry handler = 
      warning handler = 
      succeeded handler = 
      retry handler = 
      reset timer = False
      execution timeout = 
      failed handler = 
      submission timeout = 
   [[[environment]]]
   [[[directives]]]
      job_type = parallel
   [[[environment filter]]]
      exclude = 
      include = 
   [[[dummy mode]]]
      disable pre-command scripting = True
      disable post-command scripting = True
      disable retries = True
      command scripting = echo Dummy command scripting; sleep $(cylc rnd 1 16)
      disable task event hooks = True
   [[[outputs]]]
   [[[simulation mode]]]
      run time range = 1, 16
      simulate failure = False
      disable retries = True
      disable task event hooks = True
   [[[suite state polling]]]
      interval = 
      host = 
      max-polls = 
      run-dir = 
      user = 
      verbose mode = 
   [[[remote]]]
      owner = 
      suite definition directory = 
      host = 
   [[[job submission]]]
      shell = /bin/bash
      command template = 
      method = background
      retry delays = 
[[var_p1]]
   command scripting = echo "RUN: run-var.sh"
   enable resurrection = False
   manual completion = False
   retry delays = 
   environment scripting = 
   execution polling intervals = 
   title = 
   extra log files = 
   work sub-directory = $CYLC_TASK_ID
   submission polling intervals = 
   description = 
   initial scripting = 
   pre-command scripting = 
   post-command scripting = 
   inherit = VAR, PARALLEL
   [[[event hooks]]]
      submission timeout handler = 
      submitted handler = 
      started handler = 
      execution timeout handler = 
      submission failed handler = 
      submission retry handler = 
      warning handler = 
      succeeded handler = 
      retry handler = 
      reset timer = False
      execution timeout = 
      failed handler = 
      submission timeout = 
   [[[environment]]]
   [[[directives]]]
      job_type = parallel
   [[[environment filter]]]
      exclude = 
      include = 
   [[[dummy mode]]]
      disable pre-command scripting = True
      disable post-command scripting = True
      disable retries = True
      command scripting = echo Dummy command scripting; sleep $(cylc rnd 1 16)
      disable task event hooks = True
   [[[outputs]]]
   [[[simulation mode]]]
      run time range = 1, 16
      simulate failure = False
      disable retries = True
      disable task event hooks = True
   [[[suite state polling]]]
      interval = 
      host = 
      max-polls = 
      run-dir = 
      user = 
      verbose mode = 
   [[[remote]]]
      owner = 
      suite definition directory = 
      host = 
   [[[job submission]]]
      shell = /bin/bash
      command template = 
      method = background
      retry delays = 
[[VAR]]
   command scripting = echo "RUN: run-var.sh"
   enable resurrection = False
   manual completion = False
   retry delays = 
   environment scripting = 
   execution polling intervals = 
   title = 
   extra log files = 
   work sub-directory = $CYLC_TASK_ID
   submission polling intervals = 
   description = 
   initial scripting = 
   pre-command scripting = 
   post-command scripting = 
   inherit = 
   [[[event hooks]]]
      submission timeout handler = 
      submitted handler = 
      started handler = 
      execution timeout handler = 
      submission failed handler = 
      submission retry handler = 
      warning handler = 
      succeeded handler = 
      retry handler = 
      reset timer = False
      execution timeout = 
      failed handler = 
      submission timeout = 
   [[[environment]]]
   [[[directives]]]
   [[[environment filter]]]
      exclude = 
      include = 
   [[[dummy mode]]]
      disable pre-command scripting = True
      disable post-command scripting = True
      disable retries = True
      command scripting = echo Dummy command scripting; sleep $(cylc rnd 1 16)
      disable task event hooks = True
   [[[outputs]]]
   [[[simulation mode]]]
      run time range = 1, 16
      simulate failure = False
      disable retries = True
      disable task event hooks = True
   [[[suite state polling]]]
      interval = 
      host = 
      max-polls = 
      run-dir = 
      user = 
      verbose mode = 
   [[[remote]]]
      owner = 
      suite definition directory = 
      host = 
   [[[job submission]]]
      shell = /bin/bash
      command template = 
      method = background
      retry delays = 
[[var_s1]]
   command scripting = echo "RUN: run-var.sh"
   enable resurrection = False
   manual completion = False
   retry delays = 
   environment scripting = 
   execution polling intervals = 
   title = 
   extra log files = 
   work sub-directory = $CYLC_TASK_ID
   submission polling intervals = 
   description = 
   initial scripting = 
   pre-command scripting = 
   post-command scripting = 
   inherit = VAR, SERIAL
   [[[event hooks]]]
      submission timeout handler = 
      submitted handler = 
      started handler = 
      execution timeout handler = 
      submission failed handler = 
      submission retry handler = 
      warning handler = 
      succeeded handler = 
      retry handler = 
      reset timer = False
      execution timeout = 
      failed handler = 
      submission timeout = 
   [[[environment]]]
   [[[directives]]]
      job_type = serial
   [[[environment filter]]]
      exclude = 
      include = 
   [[[dummy mode]]]
      disable pre-command scripting = True
      disable post-command scripting = True
      disable retries = True
      command scripting = echo Dummy command scripting; sleep $(cylc rnd 1 16)
      disable task event hooks = True
   [[[outputs]]]
   [[[simulation mode]]]
      run time range = 1, 16
      simulate failure = False
      disable retries = True
      disable task event hooks = True
   [[[suite state polling]]]
      interval = 
      host = 
      max-polls = 
      run-dir = 
      user = 
      verbose mode = 
   [[[remote]]]
      owner = 
      suite definition directory = 
      host = 
   [[[job submission]]]
      shell = /bin/bash
      command template = 
      method = background
      retry delays = 
[[SERIAL]]
   command scripting = echo Default command scripting; sleep $(cylc rnd 1 16)
   enable resurrection = False
   manual completion = False
   retry delays = 
   environment scripting = 
   execution polling intervals = 
   title = 
   extra log files = 
   work sub-directory = $CYLC_TASK_ID
   submission polling intervals = 
   description = 
   initial scripting = 
   pre-command scripting = 
   post-command scripting = 
   inherit = 
   [[[event hooks]]]
      submission timeout handler = 
      submitted handler = 
      started handler = 
      execution timeout handler = 
      submission failed handler = 
      submission retry handler = 
      warning handler = 
      succeeded handler = 
      retry handler = 
      reset timer = False
      execution timeout = 
      failed handler = 
      submission timeout = 
   [[[environment]]]
   [[[directives]]]
      job_type = serial
   [[[environment filter]]]
      exclude = 
      include = 
   [[[dummy mode]]]
      disable pre-command scripting = True
      disable post-command scripting = True
      disable retries = True
      command scripting = echo Dummy command scripting; sleep $(cylc rnd 1 16)
      disable task event hooks = True
   [[[outputs]]]
   [[[simulation mode]]]
      run time range = 1, 16
      simulate failure = False
      disable retries = True
      disable task event hooks = True
   [[[suite state polling]]]
      interval = 
      host = 
      max-polls = 
      run-dir = 
      user = 
      verbose mode = 
   [[[remote]]]
      owner = 
      suite definition directory = 
      host = 
   [[[job submission]]]
      shell = /bin/bash
      command template = 
      method = background
      retry delays = 
[[root]]
   command scripting = echo Default command scripting; sleep $(cylc rnd 1 16)
   enable resurrection = False
   manual completion = False
   retry delays = 
   environment scripting = 
   execution polling intervals = 
   title = 
   extra log files = 
   work sub-directory = $CYLC_TASK_ID
   submission polling intervals = 
   description = 
   initial scripting = 
   pre-command scripting = 
   post-command scripting = 
   inherit = 
   [[[event hooks]]]
      submission timeout handler = 
      submitted handler = 
      started handler = 
      execution timeout handler = 
      submission failed handler = 
      submission retry handler = 
      warning handler = 
      succeeded handler = 
      retry handler = 
      reset timer = False
      execution timeout = 
      failed handler = 
      submission timeout = 
   [[[environment]]]
   [[[directives]]]
   [[[environment filter]]]
      exclude = 
      include = 
   [[[dummy mode]]]
      disable pre-command scripting = True
      disable post-command scripting = True
      disable retries = True
      command scripting = echo Dummy command scripting; sleep $(cylc rnd 1 16)
      disable task event hooks = True
   [[[outputs]]]
   [[[simulation mode]]]
      run time range = 1, 16
      simulate failure = False
      disable retries = True
      disable task event hooks = True
   [[[suite state polling]]]
      interval = 
      host = 
      max-polls = 
      run-dir = 
      user = 
      verbose mode = 
   [[[remote]]]
      owner = 
      suite definition directory = 
      host = 
   [[[job submission]]]
      shell = /bin/bash
      command template = 
      method = background
      retry delays = 
[[PARALLEL]]
   command scripting = echo Default command scripting; sleep $(cylc rnd 1 16)
   enable resurrection = False
   manual completion = False
   retry delays = 
   environment scripting = 
   execution polling intervals = 
   title = 
   extra log files = 
   work sub-directory = $CYLC_TASK_ID
   submission polling intervals = 
   description = 
   initial scripting = 
   pre-command scripting = 
   post-command scripting = 
   inherit = 
   [[[event hooks]]]
      submission timeout handler = 
      submitted handler = 
      started handler = 
      execution timeout handler = 
      submission failed handler = 
      submission retry handler = 
      warning handler = 
      succeeded handler = 
      retry handler = 
      reset timer = False
      execution timeout = 
      failed handler = 
      submission timeout = 
   [[[environment]]]
   [[[directives]]]
      job_type = parallel
   [[[environment filter]]]
      exclude = 
      include = 
   [[[dummy mode]]]
      disable pre-command scripting = True
      disable post-command scripting = True
      disable retries = True
      command scripting = echo Dummy command scripting; sleep $(cylc rnd 1 16)
      disable task event hooks = True
   [[[outputs]]]
   [[[simulation mode]]]
      run time range = 1, 16
      simulate failure = False
      disable retries = True
      disable task event hooks = True
   [[[suite state polling]]]
      interval = 
      host = 
      max-polls = 
      run-dir = 
      user = 
      verbose mode = 
   [[[remote]]]
      owner = 
      suite definition directory = 
      host = 
   [[[job submission]]]
      shell = /bin/bash
      command template = 
      method = background
      retry delays = 
[[var_s2]]
   command scripting = echo "RUN: run-var.sh"
   enable resurrection = False
   manual completion = False
   retry delays = 
   environment scripting = 
   execution polling intervals = 
   title = 
   extra log files = 
   work sub-directory = $CYLC_TASK_ID
   submission polling intervals = 
   description = 
   initial scripting = 
   pre-command scripting = 
   post-command scripting = 
   inherit = VAR, SERIAL
   [[[event hooks]]]
      submission timeout handler = 
      submitted handler = 
      started handler = 
      execution timeout handler = 
      submission failed handler = 
      submission retry handler = 
      warning handler = 
      succeeded handler = 
      retry handler = 
      reset timer = False
      execution timeout = 
      failed handler = 
      submission timeout = 
   [[[environment]]]
   [[[directives]]]
      job_type = serial
   [[[environment filter]]]
      exclude = 
      include = 
   [[[dummy mode]]]
      disable pre-command scripting = True
      disable post-command scripting = True
      disable retries = True
      command scripting = echo Dummy command scripting; sleep $(cylc rnd 1 16)
      disable task event hooks = True
   [[[outputs]]]
   [[[simulation mode]]]
      run time range = 1, 16
      simulate failure = False
      disable retries = True
      disable task event hooks = True
   [[[suite state polling]]]
      interval = 
      host = 
      max-polls = 
      run-dir = 
      user = 
      verbose mode = 
   [[[remote]]]
      owner = 
      suite definition directory = 
      host = 
   [[[job submission]]]
      shell = /bin/bash
      command template = 
      method = background
      retry delays = 
__OUT__
cmp_ok $TEST_NAME.stderr - </dev/null
#-------------------------------------------------------------------------------
purge_suite $SUITE_NAME
