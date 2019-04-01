# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
import random
import unittest

from cylc.task_outputs import TaskOutputs


class TestMessageSorting(unittest.TestCase):

    TEST_MESSAGES = [
        ['expired', 'expired', False],
        ['submitted', 'submitted', False],
        ['submit-failed', 'submit-failed', False],
        ['started', 'started', False],
        ['succeeded', 'succeeded', False],
        ['failed', 'failed', False],
        [None, None, False],
        ['foo', 'bar', False],
        ['foot', 'bart', False],
        # NOTE: [None, 'bar', False] is unstable under Python2
    ]

    def test_sorting(self):
        messages = list(self.TEST_MESSAGES)
        for _ in range(5):
            random.shuffle(messages)
            output = sorted(messages, key=TaskOutputs.msg_sort_key)
            self.assertEqual(output, self.TEST_MESSAGES, output)


if __name__ == '__main__':
    unittest.main()
