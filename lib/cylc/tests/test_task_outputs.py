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
            self.assertEquals(output, self.TEST_MESSAGES, output)


if __name__ == '__main__':
    unittest.main()
