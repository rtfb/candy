#!/usr/bin/env python
#
#   Copyright (C) 2008 Vytautas Saltenis.
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

# If text interface will ever be needed, this one might be handy:
# http://freshmeat.net/projects/python-urwid/

import wx
import wx.stc as stc
import os
import time
import sys
import pdb
import math
import platform
import keyboard
import wx.lib.pubsub as pubsub

if platform.system () == 'Windows':
    try:
        import win32api
    except ImportError:
        print 'You seem to be running Windows and don\'t have win32api.'
        print 'Tisk tisk tisk...'

STYLE_FOLDER = 1
STYLE_INC_SEARCH = 2

ID_SPLITTER = 100
ID_STATUS_LINE = 101

def resolveColorNameOrReturn (name):
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

    if name in dict.keys ():
        return dict[name]

    return name

def readConfig (fileName):
    lines = open (fileName).readlines ()
    dict = {}

    for l in lines:
        if l.strip () == '':
            continue

        name, value = l.split (':')
        val = resolveColorNameOrReturn (value.strip ())
        dict.setdefault (name.strip (), val)

    return dict

projectDir = os.path.dirname (__file__)
generalConfPath = os.path.join (projectDir, 'general.conf')
generalConfig = readConfig (generalConfPath)
colorConf = os.path.join (projectDir, 'colorscheme-default.conf')
colorScheme = readConfig (colorConf)

class DirectoryViewFilter (object):
    def __init__ (self, searchStr):
        self.searchStr = searchStr.lower ()

    def __call__ (self, item):
        return self.searchStr in item.fileName.lower ()

class VisualItem (object):
    """
    An item to hold visual representation. E.g. if the external item is a
    filename, this one will hold things like justified name, startChar in
    the ViewWindow coords and the like. Number of these objects is the number
    RawItems that actually fit on screen (at least partially).
    """
    def __init__ (self):
        # Character on the row-representing string, which is the str[0]-th
        # char of this item's visual representation. Will not be negative,
        # since objects of this class represent only visible things, even
        # if only a part of the thing is visible
        self.startCharOnLine = 0

        # Length of the visible item in characters. Will be as much characters
        # as actually visible
        self.visLenInChars = 0

        # The first byte in the string, representing the line that contains
        # this item. This is needed because of silly implementation detail
        # of STC: it needs to start (and apply) styling according to bytes,
        # not the characters. So for Unicode strings, I have to keep track
        # of bytes, not only characters.
        self.startByteOnLine = 0

        # Length of the item's visual repr, expressed in bytes (same reasons
        # as with startByteOnLine).
        self.visLenInBytes = 0

        # Since objects of this class only represent things that are
        # on-screen, there's no need for special check. We only need to
        # record whether the whole item was fit to screen
        self.fullyInView = False

    def setStartByte (self, visibleTextLine):
        charsBeforeThisItem = visibleTextLine[:self.startCharOnLine]
        self.startByteOnLine = len (charsBeforeThisItem.encode ('utf-8'))

class RawItem (object):
    """
    An item to hold the representation close to the one outside of the program.
    E.g. if the external item is a filename, this one will hold things like
    filename, path, attributes, etc. Number of these objects is the number of
    the real objects external to our app, e.g. len (os.listdir ()).
    """
    def __init__ (self, fileName):
        self.fileName = fileName
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

    def __eq__ (self, fileName):
        return self.fileName == fileName

    def __lt__ (self, other):
        return self.fileName < other.fileName

    def __str__ (self):
        return self.fileName

def resolveCommandByFileExt (ext):
    extDict = {
        'wmv':  'mplayer %s',
        'mpeg': 'mplayer %s',
        'mpg':  'mplayer %s',
        'avi':  'mplayer %s',
        'asf':  'mplayer %s',
        'pdf':  'evince %s',
        'ps':   'evince %s',
        'jpg':  'gqview %s',
        'jpeg': 'gqview %s',
        'png':  'gqview %s',
        'bmp':  'gqview %s',
        'xpm':  'gqview %s',
        'gif':  'gqview %s',
        # TODO: handle archives as folders
        'rar':  'file-roller %s',
        'zip':  'file-roller %s',
        'gz':   'file-roller %s',
        'tar':  'file-roller %s',
        'txt':  'gvim %s'}

    cmd = None

    try:
        cmd = extDict[ext]
    except KeyError:
        pass

    return cmd

# Obviously excludes subdirectories
def recursiveListDir (cwd):
    allFiles = []

    for root, dirs, files in os.walk (cwd):
        allFiles.extend (files)

    return allFiles

def listFiles (isFlatDirectoryView, cwd):
    files = []

    if isFlatDirectoryView:
        files = recursiveListDir (cwd)
    else:
        files = os.listdir (cwd)

    return files

def collectListInfo (isFlatDirectoryView, cwd):
    items = []

    files = listFiles (isFlatDirectoryView, cwd)

    for f in files:
        item = RawItem (f)

        if os.path.isdir (f):
            item.style = STYLE_FOLDER
            item.isDir = True

        if f.startswith (u'.'):
            item.isHidden = True

        items.append (item)

    return items

def collectDriveLetters ():
    items = []
    driveLetters = win32api.GetLogicalDriveStrings ().split ('\x00')[:-1]

    for d in driveLetters:
        item = RawItem (d)
        item.style = STYLE_FOLDER
        item.isDir = True

        items.append (item)

    return items

def isRootOfDrive (path):
    letters = [chr (n) for n in range (ord (u'a'), ord (u'z') + 1)]
    return len (path) == 3 \
           and path.lower ()[0] in letters \
           and path[1:] == u':\\'

def constructListForFilling (fullList, specialFilter):
    dirList = filter (lambda (f): f.isDir, fullList)
    dirList.sort ()

    fileList = filter (lambda (f): not f.isDir, fullList)
    fileList.sort ()

    notHidden = filter (lambda (f): not f.isHidden, dirList + fileList)

    dotDot = RawItem (u'..')
    dotDot.style = STYLE_FOLDER
    dotDot.isDir = True
    dotDot.isHidden = False
    dotDot.visiblePartLength = len (dotDot.fileName)
    notHidden.insert (0, dotDot)

    if specialFilter:
        return filter (specialFilter, notHidden)
    else:
        return notHidden

def intDivCeil (a, b):
    return int (math.ceil (float (a) / b))

def intDivFloor (a, b):
    return int (math.floor (float (a) / b))

class SmartJustifier (object):
    def __init__ (self, width):
        self.width = width
        self.numDots = 3

    def justify (self, text):
        if len (text) <= self.width:
            return text.ljust (self.width)

        root, ext = os.path.splitext (text)
        newWidth = self.width - self.numDots

        if ext != u'':
            newWidth -= len (ext)

        if newWidth <= 5:       # 5 = len ('a...b')
            halfWidthCeil = 1
            halfWidthFloor = 1
            extTop = self.width - halfWidthCeil - halfWidthFloor - self.numDots
        else:
            halfWidthCeil = intDivCeil (newWidth, 2)
            halfWidthFloor = intDivFloor (newWidth, 2)
            extTop = len (ext)

        if extTop > len (ext):
            halfWidthCeil += extTop - len (ext)

        dots = u'.' * self.numDots
        leftPart = root[:halfWidthCeil]
        rightPart = root[-halfWidthFloor:]
        newText = leftPart + dots + rightPart + ext[:extTop]

        return newText

# The width/height/left/right are in characters
class ViewWindow (object):
    def __init__ (self, width, height):
        # Number of characters that can fit in whole width of the pane
        self.width = width

        # Number of lines per single column
        self.height = height

        # How much characters to the right is the view window
        self.left = 0

        # Number of columns of items across all the width of the pane
        self.numColumns = 0

    def right (self):
        return self.left + self.width

    # only handles horizontal dimension
    def charInView (self, charPos):
        return charPos >= self.left and charPos < self.right ()

class StatusLine (stc.StyledTextCtrl):
    def __init__ (self, parent, id, width):
        stc.StyledTextCtrl.__init__ (self, parent, id, size = (width, 20))
        self.messagePrefix = ''
        self.SetMarginWidth (1, 0)
        self.SetUseHorizontalScrollBar (0)

        faceCourier = generalConfig['font-face'] # 'Courier'
        pb = int (generalConfig['font-size']) # 12

        # Set the styles according to color scheme
        styleSpec = 'size:%d,face:%s,back:%s,fore:%s' \
                    % (pb, faceCourier, colorScheme['background'],
                       colorScheme['default-text'])
        self.StyleSetSpec (stc.STC_STYLE_DEFAULT, styleSpec)
        self.StyleClearAll ()

        self.Bind (stc.EVT_STC_MODIFIED, self.onStatusLineChange)
        self.Bind (wx.EVT_KEY_DOWN, self.OnKeyDown)

    def OnKeyDown (self, evt):
        keyCode = evt.GetKeyCode ()
        keyMod = evt.GetModifiers ()

        if not self.processKeyEvent (keyCode, keyMod):
            evt.Skip ()

    def processKeyEvent (self, keyCode, keyMod):
        message = self.messagePrefix

        if keyCode == wx.WXK_RETURN:
            if keyMod == wx.MOD_CONTROL:
                message += 'CONTROL '
            message += 'ENTER'
        elif keyCode == wx.WXK_ESCAPE:
            message += 'ESCAPE'

        if message != self.messagePrefix:
            text = self.GetText ()
            self.ClearAll ()
            pubsub.Publisher ().sendMessage (message, text[1:])
            return True

        return False

    def onStatusLineChange (self, evt):
        type = evt.GetModificationType ()

        if stc.STC_MOD_BEFOREINSERT & type != 0 \
           or stc.STC_MOD_BEFOREDELETE & type != 0:
            return

        message = self.messagePrefix + 'NEW STATUS LINE TEXT'
        text = self.GetText ()

        if text != '':
            pubsub.Publisher ().sendMessage (message, text[1:])

class PanelModel (object):
    def __init__ (self, msgSign):
        # Working directory of the pane
        self.workingDir = os.path.expanduser (u'~')

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

    def changeWorkingDir (self, newWorkingDir):
        self.workingDir = newWorkingDir
        message = self.messageSignature + 'WORKDIR CHANGED'
        pubsub.Publisher ().sendMessage (message, self.workingDir)

    def flattenDirectory (self):
        self.flatDirectoryView = True

    def unflattenDirectory (self):
        self.flatDirectoryView = False

    def setDirFilter (self, searchStr):
        if searchStr != u'':
            self.directoryViewFilter = DirectoryViewFilter (searchStr)
        else:
            self.directoryViewFilter = None

    def setItems (self, items):
        self.items = items
        message = self.messageSignature + 'NEW ITEMS'
        pubsub.Publisher ().sendMessage (message, self.items)

    def getIndexByItem (self, item):
        try:
            return self.items.index (item)
        except ValueError:
            return 0

    def fillListByWorkingDir (self, cwd):
        allItems = collectListInfo (self.flatDirectoryView, cwd)
        self.changeWorkingDir (cwd)
        list = constructListForFilling (allItems, self.directoryViewFilter)
        self.setItems (list)

    def updir (self):
        if platform.system () == 'Windows':
            if isRootOfDrive (self.workingDir):
                self.setItems (collectDriveLetters ())
                return 0

        self.setDirFilter (u'')
        # if we're in self.flatDirectoryView, all we want is to refresh
        # the view of self.workingDir without flattening
        if self.flatDirectoryView:
            self.unflattenDirectory ()
            self.fillListByWorkingDir (os.getcwdu ())
            return 0

        oldDir = os.path.split (os.getcwdu ())[1]
        os.chdir (u'..')
        self.fillListByWorkingDir (os.getcwdu ())
        return self.getIndexByItem (oldDir)

class PanelController (object):
    def __init__ (self, parent, modelSignature, controllerSignature):
        self.model = PanelModel (modelSignature)
        self.controllerSignature = controllerSignature
        self.view = Panel (parent)
        self.bindEvents ()
        signature = modelSignature + 'NEW ITEMS'
        pubsub.Publisher ().subscribe (self.afterDirChange, signature)

        self.subscribe (self.searchCtrlEnter, 'CONTROL ENTER')
        self.subscribe (self.searchEnter, 'ENTER')
        self.subscribe (self.searchEscape, 'ESCAPE')
        self.subscribe (self.searchNewStatusLineText, 'NEW STATUS LINE TEXT')

        # String being searched incrementally
        self.searchStr = ''

        # Index of an item that is an accepted search match. Needed to know
        # which next match should be focused upon go-to-next-match
        self.searchMatchIndex = -1

        # Index of an item that is currently selected
        self.selectedItem = 0

        self.keys = keyboard.KeyboardConfig ()
        self.keys.load ('keys.conf', self)

    def subscribe (self, func, signature):
        msg = self.controllerSignature + signature
        pubsub.Publisher ().subscribe (func, msg)

    # Used in tests
    def clearList (self):
        self.model.setItems ([])
        self.selectedItem = 0
        self.view.numFullColumns = 0

    def initializeViewSettings (self, numColumns = 3):
        self.view.initializeViewSettings (self.model.items, numColumns)

    def initializeAndShowInitialView (self):
        self.initializeViewSettings ()
        self.goHome ()

        # This one is needed here to get the initial focus:
        self.view.SetFocus ()

    def bindEvents (self):
        self.view.Bind (wx.EVT_CHAR, self.OnChar)
        self.view.Bind (wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.view.Bind (wx.EVT_SET_FOCUS, self.OnSetFocus)

    def handleKeyEvent (self, evt, keyCode, keyMod):
        skipper = lambda *a, **k: evt.Skip ()
        func = self.keys.getFunc (skipper, keyCode, keyMod)
        func ()
        self.setSelectionOnCurrItem ()

    def OnKeyDown (self, evt):
        keyCode = evt.GetKeyCode ()
        keyMod = evt.GetModifiers ()
        self.handleKeyEvent (evt, keyCode, keyMod)

    def OnChar (self, evt):
        keyCode = evt.GetKeyCode ()
        self.handleKeyEvent (evt, keyCode, None)

    def OnSetFocus (self, evt):
        self.view.onSetFocus ()
        os.chdir (self.model.workingDir)

    def quiter (self):
        sys.exit (0)

    def updateView (self):
        self.view.updateDisplayByItems (self.model.items)

    def updir (self):
        self.selectedItem = 0
        self.view.clearScreen ()
        self.selectedItem = self.model.updir ()

    def listDriveLetters (self):
        if platform.system () != 'Windows':
            return

        self.selectedItem = 0
        self.model.setItems (collectDriveLetters ())

    def flattenDirectory (self):
        self.model.flattenDirectory ()
        self.model.fillListByWorkingDir (self.model.workingDir)

    def changeDir (self, fullPath, searchStr = u''):
        self.model.setDirFilter (searchStr)
        os.chdir (fullPath)
        self.view.clearScreen ()
        self.selectedItem = 0
        self.model.fillListByWorkingDir (fullPath)

    def listSearchMatches (self, searchStr):
        self.changeDir (self.model.workingDir, searchStr)

    def downdir (self, dirName):
        self.changeDir (os.path.join (self.model.workingDir, dirName))

    def goHome (self):
        self.changeDir (os.path.expanduser (u'~'))

    def afterDirChange (self, message):
        self.updateView ()
        self.setSelectionOnCurrItem ()
        # in the line below, I'm subtracting 1 from number of items because
        # of '..' pseudoitem
        statusText = u'[Folder view]: %s\t%d item(s)' \
                     % (os.getcwdu (), len (self.model.items) - 1)
        self.view.getFrame ().statusBar.SetStatusText (statusText)

    def searchCtrlEnter (self, msg):
        self.view.SetFocus ()
        self.listSearchMatches (self.searchStr)

    def searchEnter (self, msg):
        self.view.SetFocus ()
        # Here we want to stop searching and set focus on first search match.
        # But if there was no match, we want to behave more like when we cancel
        # search. Except we've no matches to clear, since no match means
        # nothing was highlighted
        if self.searchMatchIndex != -1:
            self.selectedItem = self.searchMatchIndex
            self.setSelectionOnCurrItem ()

    def searchEscape (self, msg):
        self.view.SetFocus ()
        self.view.applyDefaultStyles (self.model.items)  # clean matches

    def searchNewStatusLineText (self, msg):
        self.searchStr = msg.data
        self.searchMatchIndex = self.incrementalSearch (self.searchStr)

    def onEnter (self):
        selection = self.model.items[self.selectedItem]

        if selection.isDir:
            if selection.fileName == u'..':
                self.updir ()
            else:
                self.downdir (selection.fileName)
        else:
            base, ext = os.path.splitext (selection.fileName)
            commandLine = resolveCommandByFileExt (ext[1:].lower ())

            if commandLine:
                os.system (commandLine % (selection.fileName))

    def clearScreen (self):
        self.view.clearScreen ()

    def onNextMatch (self):
        item = self.selectedItem + 1
        self.searchMatchIndex = self.nextSearchMatch (self.searchStr, item)
        self.selectedItem = self.searchMatchIndex

    def wrappedRange (self, start, length):
        # Construct a range of indices to produce wrapped search from
        # given position
        return range (start, length) + range (start)

    def nextSearchMatch (self, searchStr, initPos):
        searchRange = self.wrappedRange (initPos, len (self.model.items))
        searchStrLower = searchStr.lower ()

        for i in searchRange:
            if searchStrLower in self.model.items[i].fileName.lower ():
                return i

        return initPos

    def incrementalSearch (self, searchStr):
        matchIndex = self.nextSearchMatch (searchStr, self.selectedItem)
        self.view.moveItemIntoView (self.model.items, matchIndex)
        self.view.highlightSearchMatches (self.model.items, searchStr)
        return matchIndex

    def onStartIncSearch (self):
        self.searchStr = ''
        self.view.getFrame ().statusLine.SetText (u'/')
        self.view.getFrame ().statusLine.GotoPos (1)
        self.view.getFrame ().statusLine.SetFocus ()

    def setSelectionOnCurrItem (self):
        if len (self.model.items) <= 0:
            return

        item = self.model.items[self.selectedItem]
        if not item.visualItem or not item.visualItem.fullyInView:
            self.view.moveItemIntoView (self.model.items, self.selectedItem)

        self.view.setSelectionOnItem (item)

    def moveSelectionDown (self):
        self.selectedItem += 1

        if self.selectedItem >= len (self.model.items):
            self.selectedItem = 0

    def moveSelectionUp (self):
        self.selectedItem -= 1

        if self.selectedItem < 0:
            self.selectedItem = len (self.model.items) - 1

        # This can happen if self.model.items is empty
        if self.selectedItem < 0:
            self.selectedItem = 0

    def moveSelectionLeft (self):
        self.selectedItem -= self.view.viewWindow.height

        if len (self.model.items) == 0:
            self.selectedItem = 0
            return

        if self.selectedItem < 0:
            # undo the decrement and start calculating from scratch:
            self.selectedItem += self.view.viewWindow.height

            # Avoiding too long line here... but...
            # TODO: figure out how to deal with that long line without
            # splitting. It suggests some nasty coupling.
            selItem = self.selectedItem
            numItems = len (self.model.items)
            selItem = self.view.updateSelectedItemLeft (selItem, numItems)
            self.selectedItem = selItem

    def moveSelectionRight (self):
        self.selectedItem += self.view.viewWindow.height

        if len (self.model.items) == 0:
            self.selectedItem = 0
            return

        if self.selectedItem > len (self.model.items):
            self.selectedItem -= self.view.viewWindow.height
            self.selectedItem %= self.view.viewWindow.height
            self.selectedItem += 1

    def moveSelectionZero (self):
        self.selectedItem = 0

    def moveSelectionLast (self):
        self.selectedItem = len (self.model.items) - 1

        if self.selectedItem < 0:
            self.selectedItem = 0

    def startEditor (self):
        os.system ('gvim ' + self.model.items[self.selectedItem].fileName)

    def startViewer (self):
        import viewr
        file = self.model.items[self.selectedItem].fileName
        wnd = viewr.BuiltinViewerFrame (self.view, -1, file, file)
        wnd.Show (True)

    def switchPane (self):
        self.view.getFrame ().switchPane ()
        self.afterDirChange (None)

    def switchSplittingMode (self):
        self.view.switchSplittingMode ()

class Panel (stc.StyledTextCtrl):
    def __init__ (self, parent):
        stc.StyledTextCtrl.__init__ (self, parent)

        # No margins and scroll bars over here!
        self.SetMarginWidth (1, 0)
        self.SetUseHorizontalScrollBar (0)

        self.bindEvents ()
        self.setStyles ()

        self.viewWindow = None

        # Number of characters per column width
        self.charsPerCol = 0

        # Number of columns in the whole-wide view, that are filled from top
        # to bottom
        self.numFullColumns = 0

        # A set of VisualItems that are referenced from subset of
        # controller.items and represent visible parts of them on screen.
        self.visualItems = []

        # List of full-width lines, containing the text of the items.
        # Only sublines of these lines are displayed both for performance
        # reasons and to bypass a bug in STC, failing to display extremely
        # long lines correctly.
        self.fullTextLines = []

    def bindEvents (self):
        self.Bind (wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.Bind (wx.EVT_KILL_FOCUS, self.OnLoseFocus)

    def setStyles (self):
        # This repeats the default: the five bits are for styling, the rest
        # three are for indicators (like green squiggle line). I'm setting it
        # explicitly to have a reference to the starting point in the code if I
        # ever need some messing around with indicators.
        self.SetStyleBits (5)

        faceCourier = generalConfig['font-face'] # 'Courier'
        pb = int (generalConfig['font-size']) # 12
        sizeAndFace = 'size:%d,face:%s' % (pb, faceCourier)

        # Set the styles according to color scheme
        styleSpec = sizeAndFace + ',back:%s,fore:%s' \
                    % (colorScheme['background'], colorScheme['default-text'])
        self.StyleSetSpec (stc.STC_STYLE_DEFAULT, styleSpec)
        self.StyleClearAll ()
        styleSpec = sizeAndFace + ',bold,fore:%s' % (colorScheme['folder'])
        self.StyleSetSpec (STYLE_FOLDER, styleSpec)
        styleSpec = sizeAndFace + ',bold,fore:%s,back:%s' \
                    % (colorScheme['search-highlight-fore'],
                       colorScheme['search-highlight-back'])
        self.StyleSetSpec (STYLE_INC_SEARCH, styleSpec)
        self.SetSelBackground (1, colorScheme['selection-inactive'])
        self.SetSelForeground (1, colorScheme['selection-fore'])

    def initializeViewSettings (self, items, numColumns):
        width, height = self.GetClientSizeTuple ()
        lineHeight = self.TextHeight (0)
        charWidth = self.TextWidth (stc.STC_STYLE_DEFAULT, 'a')

        # Here viewWindow.left will be set to 0. Even if it's not,
        # it will be brought back to life when doing moveItemIntoView:
        self.viewWindow = ViewWindow (width / charWidth,
                                      height / lineHeight)
        self.viewWindow.numColumns = numColumns
        self.charsPerCol = width / charWidth / self.viewWindow.numColumns
        self.clearScreen ()
        self.updateDisplayByItems (items)

    def setDebugWhitespace (self):
        if generalConfig['debug-whitespace'].lower () == 'true':
            self.SetViewWhiteSpace (stc.STC_WS_VISIBLEALWAYS)
            self.SetViewEOL (True)
        else:
            self.SetViewWhiteSpace (stc.STC_WS_INVISIBLE)
            self.SetViewEOL (False)

    def createVisualItem (self, rawItem):
        row = rawItem.coords[1]
        vi = VisualItem ()
        startCharOnLine = rawItem.startCharOnLine - self.viewWindow.left
        endCharOnLine = startCharOnLine + len (rawItem.visiblePart)
        visibleLine = self.GetLine (row)

        # Partially, to the left of ViewWindow:
        if startCharOnLine < 0 and endCharOnLine >= 0:
            vi.visLenInChars = startCharOnLine + len (rawItem.visiblePart)
            vi.startCharOnLine = 0
            vi.setStartByte (visibleLine)
            tail = rawItem.visiblePart[-vi.visLenInChars:]
            vi.visLenInBytes = len (tail.encode ('utf-8'))
            vi.fullyInView = False
            return vi

        # Partially, to the right of ViewWindow:
        if endCharOnLine >= self.viewWindow.width \
           and startCharOnLine < self.viewWindow.width:
            vi.startCharOnLine = startCharOnLine
            vi.visLenInChars = self.viewWindow.width - vi.startCharOnLine
            vi.setStartByte (visibleLine)
            head = rawItem.visiblePart[:vi.visLenInChars]
            vi.visLenInBytes = len (head.encode ('utf-8'))
            vi.fullyInView = False
            return vi

        # Fully in view:
        vi.startCharOnLine = startCharOnLine
        vi.visLenInChars = len (rawItem.visiblePart)
        vi.setStartByte (visibleLine)
        vi.visLenInBytes = len (rawItem.visiblePart.encode ('utf-8'))
        vi.fullyInView = True
        return vi

    def extractVisualItems (self, items):
        self.visualItems = []

        for i in items:
            i.visualItem = None
            startCharInView = self.viewWindow.charInView (i.startCharOnLine)
            endCharPos = i.startCharOnLine + len (i.visiblePart)
            endCharInView = self.viewWindow.charInView (endCharPos)

            if startCharInView or endCharInView:
                i.visualItem = self.createVisualItem (i)
                self.visualItems.append (i.visualItem)

    def extractVisibleSubLines (self):
        visibleSublines = []

        for line in self.fullTextLines:
            rawSubLine = line[self.viewWindow.left : self.viewWindow.right ()]
            subLine = rawSubLine.ljust (self.viewWindow.width)
            visibleSublines.append (subLine)

        return u'\n'.join (visibleSublines).encode ('utf-8')

    def constructFullTextLines (self, items):
        if self.viewWindow.height == 0:
            # Avoid division by zero
            self.viewWindow.height = 1

        self.numFullColumns = len (items) / self.viewWindow.height
        self.fullTextLines = ['' for i in range (self.viewWindow.height)]

        row = 0
        column = 0
        sj = SmartJustifier (self.charsPerCol - 1)

        for item in items:
            visiblePart = sj.justify (item.fileName) + u' '
            item.coords = (column, row)
            item.startCharOnLine = len (self.fullTextLines[row])
            utf8Line = self.fullTextLines[row].encode ('utf-8')
            item.startByteOnLine = len (utf8Line)
            item.visiblePart = visiblePart
            self.fullTextLines[row] += visiblePart
            row += 1

            if row > self.viewWindow.height - 1:
                row = 0
                column += 1

    def updateDisplayByItems (self, rawItems, constructFullLines = True):
        self.clearScreen ()
        self.SetReadOnly (False)

        if constructFullLines:
            self.constructFullTextLines (rawItems)

        self.SetTextUTF8 (self.extractVisibleSubLines ())
        self.extractVisualItems (rawItems)
        self.EmptyUndoBuffer ()
        self.SetReadOnly (True)
        self.setDebugWhitespace ()
        self.applyDefaultStyles (rawItems)

    def getFrame (self):
        return self.GetParent ().GetParent ()

    def OnDestroy (self, evt):
        # This is how the clipboard contents can be preserved after
        # the app has exited.
        wx.TheClipboard.Flush ()
        evt.Skip ()

    def clearScreen (self):
        self.SetReadOnly (False)
        self.ClearAll ()
        self.SetReadOnly (True)

    def switchSplittingMode (self):
        self.getFrame ().switchSplittingMode ()

    def onSetFocus (self):
        self.SetSelBackground (1, colorScheme['selection-back'])
        self.SetSelForeground (1, colorScheme['selection-fore'])

    def OnLoseFocus (self, evt):
        self.SetSelBackground (1, colorScheme['selection-inactive'])
        self.SetSelForeground (1, colorScheme['selection-fore'])

    def highlightSearchMatches (self, items, searchStr):
        self.applyDefaultStyles (items)
        searchStrLower = searchStr.lower ()

        for i in items:
            if i.visualItem:
                matchOffset = i.fileName.lower ().find (searchStrLower)

                if matchOffset != -1:
                    endOfHighlight = i.visualItem.visLenInChars
                    if matchOffset + len (searchStr) > endOfHighlight:
                        # TODO: this is a temporary hack to make the highlight
                        # always fit the visible part of an item. As we must
                        # run the search through the actual filename by
                        # definition, this match offset can be way off the
                        # visible part of an item. This issue of highlighting a
                        # search match inside the invisible part of a file name
                        # needs to be addressed separately, but for now it will
                        # suffice to make it less visually disturbing.
                        matchOffset = 0

                    selectionStart = self.getItemStartByte (i) + matchOffset

                    # Set the style for the new match:
                    self.StartStyling (selectionStart, 0xff)
                    stylingRegion = len (searchStr.encode ('utf-8'))
                    self.SetStyling (stylingRegion, STYLE_INC_SEARCH)

    def moveItemIntoView (self, items, index):
        item = items[index]
        startCharOnLine = item.startCharOnLine
        endCharOnLine = startCharOnLine + len (item.visiblePart)

        if startCharOnLine < self.viewWindow.left:
            # move view window left
            self.viewWindow.left = startCharOnLine
        elif endCharOnLine > self.viewWindow.right ():
            # move view window right
            self.viewWindow.left = endCharOnLine - self.viewWindow.width
        else:
            return      # The item is already in view

        self.updateDisplayByItems (items, False)

    def setSelectionOnItem (self, item):
        selectionStart = self.getItemStartByte (item)
        self.SetCurrentPos (selectionStart)
        self.EnsureCaretVisible ()

        if item:
            numCharsToSelect = item.visualItem.visLenInBytes
        else:
            numCharsToSelect = self.charsPerCol

        self.SetSelection (selectionStart, selectionStart + numCharsToSelect)

    def updateSelectedItemLeft (self, selectedItem, numItems):
        numFullLines = numItems % self.viewWindow.height
        bottomRightIndex = self.viewWindow.height * (self.numFullColumns + 1)
        bottomRightIndex -= 1

        if selectedItem % self.viewWindow.height > numFullLines:
            bottomRightIndex = self.viewWindow.height * self.numFullColumns - 1

        return selectedItem - self.viewWindow.height + bottomRightIndex

    def getItemStartByte (self, item):
        # -1 below because I want to get byte count for the lines [0..currLine)
        row = item.coords[1] - 1
        sumBytes = 0

        if row >= 0:
            # +1 below because GetLineEndPosition doesn't account for newlines
            # TODO: why not +row? If it skips newlines, it should have
            # skipped N (=row) of them
            sumBytes = self.GetLineEndPosition (row) + 1

        return sumBytes + item.visualItem.startByteOnLine

    def applyDefaultStyles (self, rawItems):
        for index, item in enumerate (rawItems):
            if item.visualItem:
                selStart = self.getItemStartByte (item)

                # Note the 0x1f. It means I'm only affecting the style
                # bits, leaving the indicators alone. This avoids having
                # the nasty green squiggle underline.
                self.StartStyling (selStart, 0x1f)

                itemNameLen = item.visualItem.visLenInBytes
                self.SetStyling (itemNameLen, item.style)

class Candy (wx.Frame):
    def __init__ (self, parent, id, title):
        wx.Frame.__init__ (self, parent, -1, title)

        self.splitter = wx.SplitterWindow (self, ID_SPLITTER,
                                           style = wx.SP_BORDER)
        self.splitter.SetMinimumPaneSize (50)

        displaySize = wx.DisplaySize ()
        appSize = (displaySize[0] / 2, displaySize[1] / 2)
        self.SetSize (appSize)

        self.sizer = wx.BoxSizer (wx.VERTICAL)
        self.sizer.Add (self.splitter, 1, wx.EXPAND)
        self.statusLine = StatusLine (self, ID_STATUS_LINE, appSize[0])
        self.sizer.AddSpacer (2)
        sizerFlags = wx.BOTTOM | wx.ALIGN_BOTTOM | wx.EXPAND
        self.sizer.Add (self.statusLine, 0, sizerFlags)
        self.SetSizer (self.sizer)

        self.p1 = PanelController (self.splitter, 'm1.', 'c1.')
        self.p2 = PanelController (self.splitter, 'm2.', 'c2.')
        self.splitter.SplitVertically (self.p1.view, self.p2.view)

        self.Bind (wx.EVT_SIZE, self.OnSize)
        self.Bind (wx.EVT_SPLITTER_DCLICK, self.OnDoubleClick, id = ID_SPLITTER)
        self.Bind (wx.EVT_SPLITTER_SASH_POS_CHANGED, self.OnSashPosChanged,
                   id = ID_SPLITTER)

        self.statusBar = self.CreateStatusBar ()
        self.statusBar.SetStatusText (os.getcwdu ())
        self.Center ()
        self.setActivePane (self.p1)

    def setActivePane (self, pane):
        self.activePane = pane
        pane.view.SetFocus ()
        self.statusLine.messagePrefix = pane.controllerSignature

    def setUpAndShow (self):
        self.p2.initializeAndShowInitialView ()
        self.p1.initializeAndShowInitialView ()
        self.setActivePane (self.p1)

    def OnExit (self, e):
        self.Close (True)

    def updatePanesOnSize (self):
        numColumns = 3

        if self.splitter.GetSplitMode () == wx.SPLIT_HORIZONTAL:
            numColumns = 5

        self.p1.initializeViewSettings (numColumns)
        self.p2.initializeViewSettings (numColumns)

    def splitEqual (self):
        size = self.GetSize ()

        splitMode = self.splitter.GetSplitMode ()
        sashDimension = size.x

        if splitMode == wx.SPLIT_HORIZONTAL:
            sashDimension = size.y

        # compensate for the five pixels of sash itself (dammit!)
        sashDimension -= 5
        self.splitter.SetSashPosition (sashDimension / 2)
        self.updatePanesOnSize ()

    def OnSize (self, event):
        self.splitEqual ()
        event.Skip ()

    def OnDoubleClick (self, event):
        self.splitEqual ()

    def OnSashPosChanged (self, event):
        self.splitter.UpdateSize ()
        self.updatePanesOnSize ()
        event.Skip ()

    def switchPane (self):
        if self.activePane == self.p1:
            self.setActivePane (self.p2)
        else:
            self.setActivePane (self.p1)

    def switchSplittingMode (self):
        currSplitMode = self.splitter.GetSplitMode ()
        newSplitMode = wx.SPLIT_VERTICAL
        numColumns = 3

        if currSplitMode == wx.SPLIT_VERTICAL:
            newSplitMode = wx.SPLIT_HORIZONTAL
            numColumns = 5

        self.splitter.SetSplitMode (newSplitMode)
        self.splitEqual ()
        self.p1.initializeViewSettings (numColumns)
        self.p2.initializeViewSettings (numColumns)

def main ():
    app = wx.App (0)
    candy = Candy (None, -1, 'Candy')
    candy.Show ()
    candy.setUpAndShow ()
    app.MainLoop ()

if __name__ == '__main__':
    main ()

