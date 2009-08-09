#!/usr/bin/env python
#
#   Copyright (C) 2009 Vytautas Saltenis.
#
# This file is part of Candy.
#
# Candy is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# Candy is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Candy. If not, see <http://www.gnu.org/licenses/>.
#

import math

def resolve_color_name_or_return(name):
    # http://html-color-codes.com/
    dict = {
        'black':  '#000000',
        'white':  '#ffffff',
        'yellow': '#ffff00',
        'blue':   '#0000ff',
        'red':    '#ff0000',
        'lgrey':  '#cccccc',
        'grey':   '#999999',
        }

    if name in dict.keys():
        return dict[name]

    return name


def read_config(fileName):
    lines = open(fileName).readlines()
    dict = {}

    for l in lines:
        if l.strip() == '':
            continue

        name, value = l.split(':')
        val = resolve_color_name_or_return(value.strip())
        dict.setdefault(name.strip(), val)

    return dict


def resolve_command_by_file_ext(ext):
    extDict = {
        'wmv':  'mplayer',
        'mpeg': 'mplayer',
        'mpg':  'mplayer',
        'avi':  'mplayer',
        'asf':  'mplayer',
        'pdf':  'evince',
        'ps':   'evince',
        'jpg':  'gqview',
        'jpeg': 'gqview',
        'png':  'gqview',
        'bmp':  'gqview',
        'xpm':  'gqview',
        'gif':  'gqview',
        # TODO: handle archives as folders
        'rar':  'file-roller',
        'zip':  'file-roller',
        'gz':   'file-roller',
        'tar':  'file-roller',
        'txt':  'gvim'}

    try:
        return extDict[ext]
    except KeyError:
        return None


def list_of_tuples(list, secondItem):
    tuples = []

    for i in list:
        tuples.append((i, secondItem))

    return tuples


def is_root_of_drive(path):
    letters = [chr(n) for n in range(ord(u'a'), ord(u'z') + 1)]
    return len(path) == 3 \
           and path.lower()[0] in letters \
           and path[1:] == u':\\'


def int_div_ceil(a, b):
    return int(math.ceil(float(a) / b))


def int_div_floor(a, b):
    return int(math.floor(float(a) / b))


def wrapped_range(start, length):
    # Construct a range of indices to produce wrapped search from
    # given position
    return range(start, length) + range(start)

