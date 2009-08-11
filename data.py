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

import os
import platform

import wx.stc as stc    # TODO: this module should not include it!
import wx.lib.pubsub as pubsub

import util
from constants import *


# Obviously excludes subdirectories
def recursive_list_dir(cwd):
    all_files = []

    for root, dirs, files in os.walk(cwd):
        all_files.extend(util.list_of_tuples(files, root))

    return all_files


def list_files(is_flat_directory_view, cwd):
    files = []

    if is_flat_directory_view:
        files = recursive_list_dir(cwd)
    else:
        files = util.list_of_tuples(os.listdir(cwd), cwd)

    return files


def collect_list_info(is_flat_directory_view, cwd):
    items = []
    files = list_files(is_flat_directory_view, cwd)

    for file_name, path in files:
        item = RawItem(file_name, path)

        if os.path.isdir(item.file_name):
            item.style = STYLE_FOLDER
            item.is_dir = True

        if item.file_name.startswith(u'.'):
            item.is_hidden = True

        items.append(item)

    return items


def collect_drive_letters():
    items = []
    drive_letters = win32api.GetLogicalDriveStrings().split('\x00')[:-1]

    if not drive_letters:
        drive_letters = ['c:\\', 'd:\\']

    for drive in drive_letters:
        item = RawItem(drive, u'/')
        item.style = STYLE_FOLDER
        item.is_dir = True

        items.append(item)

    return items


def construct_list_for_filling(full_list, special_filter):
    dir_list = filter(lambda(f): f.is_dir, full_list)
    dir_list.sort()

    file_list = filter(lambda(f): not f.is_dir, full_list)
    file_list.sort()

    not_hidden = filter(lambda(f): not f.is_hidden, dir_list + file_list)

    dot_dot = RawItem(u'..', u'.')
    dot_dot.style = STYLE_FOLDER
    dot_dot.is_dir = True
    dot_dot.is_hidden = False
    dot_dot.visiblePartLength = len(dot_dot.file_name)
    not_hidden.insert(0, dot_dot)

    if special_filter is not None:
        return filter(special_filter, not_hidden)
    else:
        return not_hidden


class DirectoryViewFilter(object):
    def __init__(self, search_str):
        self.search_str = search_str.lower()

    def __call__(self, item):
        return self.search_str in item.file_name.lower()


class RawItem(object):
    """
    An item to hold the representation close to the one outside of the program.
    E.g. if the external item is a file_name, this one will hold things like
    file_name, path, attributes, etc. Number of these objects is the number of
    the real objects external to our app, e.g. len (os.listdir ()).
    """
    def __init__(self, file_name, path):
        self.file_name = file_name
        self.path = path
        self.style = stc.STC_STYLE_DEFAULT
        self.is_dir = False
        self.is_hidden = False
        self.visual_item = None
        self.visible_part = ''

        # All of the below are relative to fullTextLines (i.e. are absolute
        # coords/counts)
        self.coords = (0, 0)
        self.start_char_on_line = 0
        self.start_byte_on_line = 0

    def __eq__(self, file_name):
        return self.file_name == file_name

    def __lt__(self, other):
        return self.file_name < other.file_name

    def __str__(self):
        return self.file_name


class PanelModel(object):
    def __init__(self, msgSign):
        # Working directory of the pane
        self.working_dir = os.path.expanduser(u'~')

        # Signifies flattened directory view
        self.flat_directory_view = False

        # Function Object that gets called to filter out directory view.
        # Main use (for now) is for filtering out the contents by search
        # matches.
        self.directory_view_filter = None

        # List of filesystem items to be displayed. Only contains those that
        # are to be actually displayed. E.g. no dot-files when hidden files
        # are not displayed
        self.items = []

        # Signature that is added to the message, to identify the model that
        # has sent it
        self.message_signature = msgSign

    def _change_working_dir(self, newWorkingDir):
        self.working_dir = newWorkingDir
        message = self.message_signature + 'WORKDIR CHANGED'
        pubsub.Publisher().sendMessage(message, self.working_dir)

    def flatten_directory(self):
        self.flat_directory_view = True

    def _unflatten_directory(self):
        self.flat_directory_view = False

    def set_dir_filter(self, search_str):
        if search_str != u'':
            self.directory_view_filter = DirectoryViewFilter(search_str)
        else:
            self.directory_view_filter = None

    def set_items(self, items):
        self.items = items
        message = self.message_signature + 'NEW ITEMS'
        pubsub.Publisher().sendMessage(message, self.items)

    def _get_index_by_item(self, item):
        try:
            return self.items.index(item)
        except ValueError:
            return 0

    def fill_list_by_working_dir(self, cwd):
        allItems = collect_list_info(self.flat_directory_view, cwd)
        self._change_working_dir(cwd)
        list = construct_list_for_filling(allItems, self.directory_view_filter)
        self.set_items(list)

    def updir(self):
        if platform.system() == 'Windows':
            if util.is_root_of_drive(self.working_dir):
                self.set_items(collect_drive_letters())
                return 0

        self.set_dir_filter(u'')
        # if we're in self.flat_directory_view, all we want is to refresh
        # the view of self.working_dir without flattening
        if self.flat_directory_view:
            self._unflatten_directory()
            self.fill_list_by_working_dir(os.getcwdu())
            return 0

        old_dir = os.path.split(os.getcwdu())[1]
        os.chdir(u'..')
        self.fill_list_by_working_dir(os.getcwdu())
        return self._get_index_by_item(old_dir)

    def next_search_match(self, search_str, init_pos):
        if init_pos >= len(self.items):
            init_pos = 0

        search_range = util.wrapped_range(init_pos, len(self.items))
        search_str_lower = search_str.lower()

        for i in search_range:
            if search_str_lower in self.items[i].file_name.lower():
                return i

        return init_pos

