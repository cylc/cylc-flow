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
import math


R_0 = 6356752.3


def get_offset(bbox, scale=(1., 1.)):
    """Define an offset from the origin using the provided bbox.

    Args:
        bbox: The coordinates of the domain as a dictionary {'lat1', 'lng1',
            'lat2', 'lng2'}
        scale: The x, y scale factor as returned by get_scale().

    """
    return coord_to_pos(bbox['lng1'], bbox['lat1'], scale=scale)


def get_scale(bbox, width):
    """Define the scale of the transformation.

    Args:
        bbox: The coordinates of the domain as a dictionary {'lat1', 'lng1',
            'lat2', 'lng2'}
        width: The width of the projection.

    """
    scale = width * (180. / abs(bbox['lng2'] - bbox['lng1']))
    return (
        (math.pi * R_0) / scale,
        (math.pi * R_0 * 2.) / scale)


def coord_to_pos(lng, lat, offset=(0., 0.), scale=(1., 1.)):
    """Convert a lng, lat coord to an x, y position in a mercator projection.

    proj equivalent:
        $ echo <lng> <lat> | proj +proj=merc
        # Divide by scale.
        # Subtract offset.

    """
    lng = math.radians(lng)
    lat = math.radians(lat)
    pos_x = R_0 * lng
    pos_y = R_0 * math.log(math.tan((math.pi / 4.) + (lat / 2.)))
    pos_x /= scale[0]
    pos_y /= scale[1]
    pos_x -= offset[0]
    pos_y -= offset[1]
    return pos_x, pos_y


def pos_to_coord(pos_x, pos_y, offset=(0., 0.), scale=(1., 1.)):
    """Convert an x, y coordinate in a mercator projection to a lng, lat coord.

    proj equivalent:
        # Add offset
        # Multiply by scale.
        $ echo <pos_x> <pos_y> | proj -I +proj=merc

    """
    pos_x += offset[0]
    pos_y += offset[1]
    pos_x *= scale[0]
    pos_y *= scale[1]
    lng = pos_x / R_0
    lat = 2 * math.atan(math.exp(pos_y / R_0)) - (math.pi / 2.)
    return math.degrees(lng), math.degrees(lat)
