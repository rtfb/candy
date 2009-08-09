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
    allFiles = []

    for root, dirs, files in os.walk(cwd):
        allFiles.extend(util.list_of_tuples(files, root))

    return allFiles


def list_files(isFlatDirectoryView, cwd):
    files = []

    if isFlatDirectoryView:
        files = recursive_list_dir(cwd)
    else:
        files = util.list_of_tuples(os.listdir(cwd), cwd)

    return files


def collect_list_info(isFlatDirectoryView, cwd):
    items = []
    files = list_files(isFlatDirectoryView, cwd)

    for fileName, path in files:
        item = RawItem(fileName, path)

        if os.path.isdir(item.fileName):
            item.style = STYLE_FOLDER
            item.isDir = True

        if item.fileName.startswith(u'.'):
            item.isHidden = True

        items.append(item)

    return items


def collect_drive_letters():
    items = []
    driveLetters = win32api.GetLogicalDriveStrings().split('\x00')[:-1]

    for d in driveLetters:
        item = RawItem(d, u'/')
        item.style = STYLE_FOLDER
        item.isDir = True

        items.append(item)

    return items


def construct_list_for_filling(fullList, specialFilter):
    dirList = filter(lambda(f): f.isDir, fullList)
    dirList.sort()

    fileList = filter(lambda(f): not f.isDir, fullList)
    fileList.sort()

    notHidden = filter(lambda(f): not f.isHidden, dirList + fileList)

    dotDot = RawItem(u'..', u'.')
    dotDot.style = STYLE_FOLDER
    dotDot.isDir = True
    dotDot.isHidden = False
    dotDot.visiblePartLength = len(dotDot.fileName)
    notHidden.insert(0, dotDot)

    if specialFilter is not None:
        return filter(specialFilter, notHidden)
    else:
        return notHidden


class DirectoryViewFilter(object):
    def __init__(self, searchStr):
        self.searchStr = searchStr.lower()

    def __call__(self, item):
        return self.searchStr in item.fileName.lower()


class RawItem(object):
    """
    An item to hold the representation close to the one outside of the program.
    E.g. if the external item is a filename, this one will hold things like
    filename, path, attributes, etc. Number of these objects is the number of
    the real objects external to our app, e.g. len (os.listdir ()).
    """
    def __init__(self, fileName, path):
        self.fileName = fileName
        self.path = path
        self.style = stc.STC_STYLE_DEFAULT
        self.isDir = False
        self.isHidden = False
        self.visualItem = None
        self.visiblePart = ''

        # All of the below are relative to fullTextLines (i.e. are absolute
        # coords/counts)
        self.coords = (0, 0)
        self.startCharOnLine = 0
        self.startByteOnLine = 0

    def __eq__(self, fileName):
        return self.fileName == fileName

    def __lt__(self, other):
        return self.fileName < other.fileName

    def __str__(self):
        return self.fileName


class PanelModel(object):
    def __init__(self, msgSign):
        # Working directory of the pane
        self.workingDir = os.path.expanduser(u'~')

        # Signifies flattened directory view
        self.flatDirectoryView = False

        # Function Object that gets called to filter out directory view.
        # Main use (for now) is for filtering out the contents by search
        # matches.
        self.directoryViewFilter = None

        # List of filesystem items to be displayed. Only contains those that
        # are to be actually displayed. E.g. no dot-files when hidden files
        # are not displayed
        self.items = []

        # Signature that is added to the message, to identify the model that
        # has sent it
        self.messageSignature = msgSign

    def changeWorkingDir(self, newWorkingDir):
        self.workingDir = newWorkingDir
        message = self.messageSignature + 'WORKDIR CHANGED'
        pubsub.Publisher().sendMessage(message, self.workingDir)

    def flattenDirectory(self):
        self.flatDirectoryView = True

    def unflattenDirectory(self):
        self.flatDirectoryView = False

    def setDirFilter(self, searchStr):
        if searchStr != u'':
            self.directoryViewFilter = DirectoryViewFilter(searchStr)
        else:
            self.directoryViewFilter = None

    def setItems(self, items):
        self.items = items
        message = self.messageSignature + 'NEW ITEMS'
        pubsub.Publisher().sendMessage(message, self.items)

    def getIndexByItem(self, item):
        try:
            return self.items.index(item)
        except ValueError:
            return 0

    def fillListByWorkingDir(self, cwd):
        allItems = collect_list_info(self.flatDirectoryView, cwd)
        self.changeWorkingDir(cwd)
        list = construct_list_for_filling(allItems, self.directoryViewFilter)
        self.setItems(list)

    def updir(self):
        if platform.system() == 'Windows':
            if util.is_root_of_drive(self.workingDir):
                self.setItems(collect_drive_letters())
                return 0

        self.setDirFilter(u'')
        # if we're in self.flatDirectoryView, all we want is to refresh
        # the view of self.workingDir without flattening
        if self.flatDirectoryView:
            self.unflattenDirectory()
            self.fillListByWorkingDir(os.getcwdu())
            return 0

        oldDir = os.path.split(os.getcwdu())[1]
        os.chdir(u'..')
        self.fillListByWorkingDir(os.getcwdu())
        return self.getIndexByItem(oldDir)

    def nextSearchMatch(self, searchStr, initPos):
        if initPos >= len(self.items):
            initPos = 0

        searchRange = util.wrapped_range(initPos, len(self.items))
        searchStrLower = searchStr.lower()

        for i in searchRange:
            if searchStrLower in self.items[i].fileName.lower():
                return i

        return initPos

