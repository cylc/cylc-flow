# -*- coding: utf-8 -*-
# -----------------------------------------------------------------------------
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
# -----------------------------------------------------------------------------
# This is illustrative code developed for tutorial purposes, it is not
# intended for scientific use and is not guarantied to be accurate or correct.
from copy import copy
from contextlib import suppress
import math
import os
import sys
import time

import jinja2

R_0 = 6371.  # Radius of the Earth (km).


def frange(start, stop, step):
    """Implementation of python's xrange which works with floats."""
    while start < stop:
        yield start
        start += step


def read_csv(filename, cast=float):
    """Reads in data from a 2D csv file.

    Args:
        filename (str): The path to the file to read.
        cast (function): A function to call on each value to convert the data
            into the desired format.

    """
    data = []
    with open(filename, 'r') as datafile:
        line = datafile.readline()
        while line:
            data.append(list(map(cast, line.split(','))))
            line = datafile.readline()
    return data


def write_csv(filename, matrix, fmt='%.2f'):
    """Write data from a 2D array to a csv format file."""
    with open(filename, 'w+') as datafile:
        for row in matrix:
            datafile.write(', '.join(fmt % x for x in row) + '\n')


def field_to_csv(field, x_range, y_range, filename):
    """Extrapolate values from the field and write them to a csv file.

    Args:
        filename (str): The path of the csv file to write to.
        field (function): A function of the form f(x, y) -> z.
        x_range (list): List of the x coordinates of the extrapolated grid.
            These are the extrapolation coordinates, the length of this list
            defines the size of the grid.
        y_range (list): List of the y coordinates of the extrapolated grid.
            These are the extrapolation coordinates, the length of this list
            defines the size of the grid.

    """
    with open(filename, 'w+') as csv_file:
        for itt_y in y_range:
            csv_file.write(', '.join('%.2f' % field(x, itt_y) for
                                     x in x_range) + '\n')


def generate_matrix(dim_x, dim_y, value=0.):
    """Generates a 2D list with the desired dimensions.

    Args:
        dim_x (int): The x-dimension of the matrix.
        dim_y (int): The y-dimension of the matrix.
        value: The default value for each cell of the matrix.

    """
    matrix = []
    for _ in range(dim_y):
        matrix.append([copy(value)] * dim_x)
    return matrix


def permutations(collection_1, collection_2):
    """Yield all permutations of two collections."""
    for val_1 in collection_1:
        for val_2 in collection_2:
            yield val_1, val_2


def great_arc_distance(coordinate_1, coordinate_2):
    """Compute the distance between two (lng, lat) coordinates in km.

    Uses the Haversine formula.

    Args:
        coordinate_1 (tuple): A 2-tuple (lng, lat) of the first coordinate.
        coordinate_2 (tuple): A 2-tuple (lng, lat) of the second coordinate.

    """
    (lng_1, lat_1) = coordinate_1
    (lng_2, lat_2) = coordinate_2
    lng_1 = math.radians(lng_1)
    lat_1 = math.radians(lat_1)
    lng_2 = math.radians(lng_2)
    lat_2 = math.radians(lat_2)
    return (
        2 * R_0 * math.asin(
            math.sqrt(
                (math.sin((lat_2 - lat_1) / 2.) ** 2) + (
                    math.cos(lat_1) *
                    math.cos(lat_2) *
                    (math.sin((lng_2 - lng_1) / 2.) ** 2)
                )
            )
        )
    )


def interpolate_grid(points, dim_x, dim_y, d_x, d_y, spline_order=0):
    """Interpolate 2D data onto a grid.

    Args:
        points (list): The points to interpolate as a list of 3-tuples
            (x, y, z).
        dim_x (int): The size of the grid in the x-dimension.
        dim_y (int): The size of the grid in the y-dimension.
        d_x (float): The grid spacing in the x-dimension.
        d_y (float): The grid spacing in the y-dimension.
        spline_order (int): The order of the beta-spline to use for
            interpolation (0 = nearset).

    Return:
        list - 2D matrix of dimensions dim_x, dim_y containing the interpolated
        data.

    """
    def spline_0(pos_x, pos_y, z_val):
        """Zeroth order beta spline (i.e. nearest point)."""
        return [(int(round(pos_x)), int(round(pos_y)), z_val)]  # [(x, y, z)]

    def spline_1(pos_x, pos_y, z_val):
        """First order beta spline (weight spread about four nearest
        points)."""
        x_0 = int(math.floor(pos_x))
        y_0 = int(math.floor(pos_y))
        x_1 = x_0 + 1
        y_1 = y_0 + 1
        return [
            # (x, y, z), ...
            (x_0, y_0, (x_0 + d_x - pos_x) * (y_0 + d_y - pos_y) * z_val),
            (x_1, y_0, (pos_x - x_0) * (y_0 + d_y - pos_y) * z_val),
            (x_0, y_1, (x_0 + d_x - pos_x) * (pos_y - y_0) * z_val),
            (x_1, y_1, (pos_x - x_0) * (pos_y - y_0) * z_val)
        ]

    if spline_order == 0:
        spline = spline_0
    elif spline_order == 1:  # noqa: SIM106 (case type matching)
        spline = spline_1
    else:
        raise ValueError('Invalid spline order "%d" must be in (0, 1).' %
                         spline_order)

    grid = generate_matrix(dim_x, dim_y, 0.)

    for x_val, y_val, z_val in points:
        x_coord = x_val / d_x
        y_coord = y_val / d_y
        for grid_x, grid_y, grid_z in spline(x_coord, y_coord, z_val):
            with suppress(IndexError):
                grid[grid_y][grid_x] += grid_z
                # skip grid point out of bounds

    return grid


def plot_vector_grid(filename, x_grid, y_grid):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
    except ImportError:
        print('Plotting disabled', file=sys.stderr)
        return

    fig = plt.figure()
    x_coords = []
    y_coords = []
    z_coords = []
    for itt_x in range(len(x_grid[0])):
        for itt_y in range(len(x_grid)):
            x_coords.append(itt_x)
            y_coords.append(itt_y)
            z_coords.append((
                x_grid[itt_y][itt_x],
                y_grid[itt_y][itt_x]
            ))

    plt.quiver(x_coords,
               y_coords,
               [x[0] for x in z_coords],
               [y[1] for y in z_coords])
    fig.savefig(filename)


def get_grid_coordinates(lng, lat, domain, resolution):
    """Return the grid coordinates for a lat, long coordinate pair."""
    # NOTE: Grid coordinates run from *top* left to bottom right.
    length_y = int(abs(domain['lat2'] - domain['lat1']) // resolution)
    return (
        int((abs(lng - domain['lng1'])) // resolution),
        length_y - int((abs(lat - domain['lat1'])) // resolution))


class SurfaceFitter:
    """A 2D interpolation for random points.

    A standin for scipy.interpolate.interp2d

    Args:
        x_points (list): A list of the x coordinates of the points to
            interpolate.
        y_points (list): A list of the y coordinates of the points.
        z_points (list): A list of the z coordinates of the points.
        kind (str): String representing the order of the interpolation to
            perform (either linear, quadratic or cubic).

    Returns:
        function: fcn(x, y) -> z

    """

    def __init__(self, x_points, y_points, z_points, kind='linear'):
        self.points = list(zip(x_points, y_points, z_points))

        if kind == 'linear':
            self.power = 1.
        elif kind == 'quadratic':
            self.power = 2.
        elif kind == 'cubic':  # noqa: SIM106 (case type matching)
            self.power = 3.
        else:
            raise ValueError('"%s" is not a valid interpolation method' % kind)

    def __call__(self, grid_x, grid_y):
        sum_value = 0.0
        sum_weight = 0.0
        z_val = None
        for x_point, y_point, z_point in self.points:
            d_x = grid_x - x_point
            d_y = grid_y - y_point
            if d_x == 0 and d_y == 0:
                # This point is exactly at the grid location we are
                # interpolating for, return this value.
                z_val = z_point
                break
            else:
                weight = 1. / ((math.sqrt(d_x ** 2 + d_y ** 2)) ** self.power)
                sum_weight += weight
                sum_value += weight * z_point

        if z_val is None:
            z_val = sum_value / sum_weight

        return z_val


def parse_domain(domain: str):
    lng1, lat1, lng2, lat2 = list(map(float, domain.split(',')))
    msg = "Invalid domain '{}' ({} {} >= {})"
    if lng1 >= lng2:
        raise ValueError(msg.format(domain, 'longitude', lng1, lng2))
    if lat1 >= lat2:
        raise ValueError(msg.format(domain, 'latitude', lat1, lat2))
    return {
        'lng1': lng1,
        'lat1': lat1,
        'lng2': lng2,
        'lat2': lat2,
    }


def generate_html_map(filename, template_file, data, domain, resolution):
    with open(template_file, 'r') as template:  # noqa: SIM117
        with open(filename, 'w+') as html_file:
            html_file.write(jinja2.Template(template.read()).render(
                resolution=resolution,
                lng1=domain['lng1'],
                lng2=domain['lng2'],
                lat1=domain['lat1'],
                lat2=domain['lat2'],
                data=data
            ))


def sleep(secs=4):
    """Make the tutorials run a little slower so users can follow along.

    (Only if not running in CI).
    """
    if 'CI' not in os.environ:
        time.sleep(secs)
