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

"""Built-in Cylc task qualifiers.

Qualifier, i.e. the bit after a colon in a graph string: <task>:<qualifer>
"""

from cylc.flow.task_outputs import (
    TASK_OUTPUTS,
    TASK_OUTPUT_EXPIRED,
    TASK_OUTPUT_SUBMITTED,
    TASK_OUTPUT_SUBMIT_FAILED,
    TASK_OUTPUT_STARTED,
    TASK_OUTPUT_SUCCEEDED,
    TASK_OUTPUT_FAILED,
    TASK_OUTPUT_FINISHED,
)


# family qualifiers
QUAL_FAM_SUCCEED_ALL = "succeed-all"
QUAL_FAM_SUCCEED_ANY = "succeed-any"
QUAL_FAM_FAIL_ALL = "fail-all"
QUAL_FAM_FAIL_ANY = "fail-any"
QUAL_FAM_FINISH_ALL = "finish-all"
QUAL_FAM_FINISH_ANY = "finish-any"
QUAL_FAM_START_ALL = "start-all"
QUAL_FAM_START_ANY = "start-any"
QUAL_FAM_SUBMIT_ALL = "submit-all"
QUAL_FAM_SUBMIT_ANY = "submit-any"
QUAL_FAM_SUBMIT_FAIL_ALL = "submit-fail-all"
QUAL_FAM_SUBMIT_FAIL_ANY = "submit-fail-any"

# alternative (shorthand) qualifiers
ALT_QUALIFIERS = {
    "expire": TASK_OUTPUT_EXPIRED,
    "submit": TASK_OUTPUT_SUBMITTED,
    "submit-fail": TASK_OUTPUT_SUBMIT_FAILED,
    "start": TASK_OUTPUT_STARTED,
    "succeed": TASK_OUTPUT_SUCCEEDED,
    "fail": TASK_OUTPUT_FAILED,
    "finish": TASK_OUTPUT_FINISHED,
}

# all built-in qualifiers
TASK_QUALIFIERS = (
    *TASK_OUTPUTS,
    *ALT_QUALIFIERS,
    QUAL_FAM_SUCCEED_ALL,
    QUAL_FAM_SUCCEED_ANY,
    QUAL_FAM_FAIL_ALL,
    QUAL_FAM_FAIL_ANY,
    QUAL_FAM_FINISH_ALL,
    QUAL_FAM_FINISH_ANY,
    QUAL_FAM_START_ALL,
    QUAL_FAM_START_ANY,
    QUAL_FAM_SUBMIT_ALL,
    QUAL_FAM_SUBMIT_ANY,
    QUAL_FAM_SUBMIT_FAIL_ALL,
    QUAL_FAM_SUBMIT_FAIL_ANY,
)
