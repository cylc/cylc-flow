# -*- coding: utf-8 -*-
#-----------------------------------------------------------------------------
# (C) British Crown Copyright 2013-2014 Met Office.
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
#-----------------------------------------------------------------------------

"""Provide an optimisation decorator and other utilities."""


MAX_CACHE_SIZE = 100000


def cache_results(func):
    """Decorator to store results for given inputs.

    func is the decorated function.

    A maximum of MAX_CACHE_SIZE arg-value pairs are stored.

    """
    cache = {}

    def wrap_func(*args, **kwargs):
        key = (str(args), str(kwargs))
        if key in cache:
            return cache[key]
        else:
            results = func(*args, **kwargs)
            if len(cache) > MAX_CACHE_SIZE:
                cache.popitem()
            cache[key] = results
            return results
    return wrap_func
