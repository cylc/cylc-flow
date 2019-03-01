# -*- coding: utf-8 -*-
# ----------------------------------------------------------------------------
# Copyright (C) 2013-2019 British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# ----------------------------------------------------------------------------

"""This tests the ISO 8601 parsing and data model functionality."""

import datetime
import pytest
import random
import unittest
import concurrent.futures

from isodatetime.data import TimePoint, Duration, get_days_since_1_ad


def daterange(start_date, end_date):
    """https://stackoverflow.com/a/1060330"""
    for n in range(1 + int((end_date - start_date).days)):
        yield start_date + datetime.timedelta(n)


test_duration_attributes = [
    ("weeks", 110),
    ("days", 770),
    ("hours", 770 * 24),
    ("minutes", 770 * 24 * 60),
    ("seconds", 770 * 24 * 60 * 60)
]


@pytest.mark.slow
class TestTimePointCompat(unittest.TestCase):
    """Test time point compatibility with "datetime"."""

    def test_timepoint(self):
        """Test the time point data model (takes a while).

        For a range of years (e.g. 1801 to 2403) it iterates through each
        year, then creates another range with the days in this year. Finally
        performs a series of tests, failing if any operation results in
        an error."""

        for test_year in range(1801, 2403):
            my_date = datetime.datetime(test_year, 1, 1)
            stop_date = datetime.datetime(test_year + 1, 1, 1)

            # test each day in the year concurrently
            # using the number of cores in a travis ci server for max_workers
            with concurrent.futures.ThreadPoolExecutor(max_workers=2)\
                    as executor:
                futures = {executor.submit(self._do_test_dates, d):
                           d for d in daterange(my_date, stop_date)}
                concurrent.futures.wait(futures)

                # Each day takes approx 0.5s to compute, so let's give
                # it four times the normal as buffer
                for _, future in enumerate(
                        concurrent.futures.as_completed(futures, timeout=2.0)):
                    future.result()  # This will also raise any exceptions

    def _do_test_dates(self, my_date):
        """Performs a series of tests against a given date.

        This method does some time consuming operations, which are not IO
        bound, so this method is a good candidate to be run concurrently.

        :param my_date: a date to be tested
        :type my_date: datetime.datetime
        """
        ctrl_data = my_date.isocalendar()
        test_date = TimePoint(
            year=my_date.year,
            month_of_year=my_date.month,
            day_of_month=my_date.day
        )
        test_week_date = test_date.to_week_date()
        test_data = test_week_date.get_week_date()
        self.assertEqual(test_data, ctrl_data)
        ctrl_data = (my_date.year, my_date.month, my_date.day)
        test_data = test_week_date.get_calendar_date()
        self.assertEqual(test_data, ctrl_data)
        ctrl_data = my_date.toordinal()
        year, day_of_year = test_date.get_ordinal_date()
        test_data = day_of_year
        test_data += get_days_since_1_ad(year - 1)
        self.assertEqual(test_data, ctrl_data)
        for attribute, attr_max in test_duration_attributes:
            kwargs = {attribute: random.randrange(0, attr_max)}
            ctrl_data = my_date + datetime.timedelta(**kwargs)
            ctrl_data = ctrl_data.year, ctrl_data.month, ctrl_data.day
            test_data = (
                (test_date + Duration(**kwargs)).get_calendar_date())
            self.assertEqual(test_data, ctrl_data)
            ctrl_data = my_date - datetime.timedelta(**kwargs)
            ctrl_data = ctrl_data.year, ctrl_data.month, ctrl_data.day
            # TBD: the subtraction is quite slow. Much slower than other
            # operations. Could be related to the fact it converts the value
            # in kwargs to negative multiplying by -1 (i.e. from __sub__ to
            # __mul__), and also adds it to the date (i.e. __add__).
            # Profiling the tests, the __sub__ operation used in the next
            # line will appear amongst the top of time consuming operations.
            test_data = (
                (test_date - Duration(**kwargs)).get_calendar_date())
            self.assertEqual(test_data, ctrl_data)
        kwargs = {}
        for attribute, attr_max in test_duration_attributes:
            kwargs[attribute] = random.randrange(0, attr_max)
        test_date_minus = test_date - Duration(**kwargs)
        test_data = test_date - test_date_minus
        ctrl_data = Duration(**kwargs)
        self.assertEqual(test_data, ctrl_data)
        test_data = test_date_minus + (test_date - test_date_minus)
        ctrl_data = test_date
        self.assertEqual(test_data, ctrl_data)
        test_data = (test_date_minus + Duration(**kwargs))
        ctrl_data = test_date
        self.assertEqual(test_data, ctrl_data)
        ctrl_data = (
            my_date +
            datetime.timedelta(minutes=450) +
            datetime.timedelta(hours=5) -
            datetime.timedelta(seconds=500, weeks=5))
        ctrl_data = [
            (ctrl_data.year, ctrl_data.month, ctrl_data.day),
            (ctrl_data.hour, ctrl_data.minute, ctrl_data.second)]
        test_data = (
            test_date + Duration(minutes=450) +
            Duration(hours=5) -
            Duration(weeks=5, seconds=500)
        )
        test_data = [
            test_data.get_calendar_date(),
            test_data.get_hour_minute_second()]
        self.assertEqual(test_data, ctrl_data)


if __name__ == '__main__':
    unittest.main()
