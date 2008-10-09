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

STYLE_FOLDER = 1
STYLE_INC_SEARCH = 2

ID_SPLITTER = 100

class DirectoryViewFilter:
    def __init__ (self, searchStr):
        self.searchStr = searchStr.lower ()

    def __call__ (self, item):
        return self.searchStr in item.fileName.lower ()

class ListItem:
    """An item to be stored in the list: basically, a filename with additional info
    """
    def __init__ (self, fileName):
        self.fileName = fileName
        self.style = stc.STC_STYLE_DEFAULT
        self.isDir = False
        self.isHidden = False
        self.visiblePartLength = 0

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
        dict.setdefault (name.strip (), resolveColorNameOrReturn (value.strip ()))

    return dict

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
        item = ListItem (f)

        if os.path.isdir (f):
            item.style = STYLE_FOLDER
            item.isDir = True

        if f.startswith ('.'):
            item.isHidden = True

        items.append (item)

    return items

def constructListForFilling (fullList, specialFilter):
    dirList = filter (lambda (f): f.isDir, fullList)
    dirList.sort ()

    fileList = filter (lambda (f): not f.isDir, fullList)
    fileList.sort ()

    notHidden = filter (lambda (f): not f.isHidden, dirList + fileList)

    dotDot = ListItem ('..')
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

class SmartJustifier:
    def __init__ (self, width):
        self.width = width

    def justify (self, text):
        if len (text) <= self.width:
            return text.ljust (self.width)

        root, ext = os.path.splitext (text)
        newWidth = self.width - 3       # The 3 positions are for dots

        if ext != '':
            newWidth -= len (ext)

        halfWidthCeil = intDivCeil (newWidth, 2)
        halfWidthFloor = intDivFloor (newWidth, 2)
        newText = root[:halfWidthCeil] + '...' + root[-halfWidthFloor:] + ext

        return newText

# The width/height/left/right are in characters
class ViewWindow:
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

class MySTC (stc.StyledTextCtrl):
    def __init__ (self, parent, ID):
        stc.StyledTextCtrl.__init__ (self, parent, ID)

        self.bindEvents ()

        projectDir = os.path.dirname (__file__)
        colorConf = os.path.join (projectDir, 'colorscheme-default.conf')
        self.colorScheme = readConfig (colorConf)
        self.setStyles ()

        self.viewWindow = None

        # Number of characters per column width
        self.charsPerCol = 0

        # Number of columns in the whole-wide view, that are filled from top to bottom
        self.numFullColumns = 0

        # List of filesystem items to be displayed. Only contains those that are to be
        # actually displayed. E.g. no dot-files when hidden files are not displayed
        self.items = []

        # Index of an item that is currently selected
        self.selectedItem = 0

        # Signifies incremental search mode
        self.searchMode = False

        # String being searched incrementally
        self.searchStr = ''

        # Index of an item that is an accepted search match. Needed to know which
        # next match should be focused upon go-to-next-match
        self.searchMatchIndex = -1

        # Working directory of the pane
        self.workingDir = os.path.expanduser ('~')

        # Signifies flattened directory view
        self.flatDirectoryView = False

        # Function Object that gets called to filter out directory view.
        # Main use is for filtering out the contents by search matches.
        self.directoryViewFilter = None

        # List of full-width lines, containing the text of the items.
        # Only sublines of these lines are displayed both for performance
        # reasons and to bypass a bug in STC, failing to display extremely
        # long lines correctly.
        self.fullTextLines = []

        self.navigationModeMap = {
            ord ('J'): self.moveSelectionDown,
            ord ('K'): self.moveSelectionUp,
            ord ('H'): self.moveSelectionLeft,
            ord ('L'): self.moveSelectionRight,
            ord ('Q'): self.quiter,
            ord ('F'): self.flattenDirectory,
            ord ('U'): self.updir,
            ord ('`'): self.goHome,
            wx.WXK_RETURN: self.onEnter,
            wx.WXK_SPACE: self.onEnter,
            ord ('C'): self.clearScreen,
            ord ('N'): self.onNextMatch,
            ord ('/'): self.onStartIncSearch,
            wx.WXK_F4: self.startEditor,
            ord ('E'): self.startEditor,
            wx.WXK_TAB: self.switchPane,
            ord ('X'): self.switchSplittingMode,
            ord ('Y'): self.switchSplittingMode,
            wx.WXK_F3: self.startViewer,
            ord ('V'): self.startViewer}

    def bindEvents (self):
        self.Bind (wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind (wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.Bind (wx.EVT_SET_FOCUS, self.OnSetFocus)
        self.Bind (wx.EVT_KILL_FOCUS, self.OnLoseFocus)

    def setStyles (self):
        # Set the styles according to color scheme
        self.StyleSetSpec (stc.STC_STYLE_DEFAULT, "size:%d,face:%s,back:%s,fore:%s"
                                                  % (pb, faceCourier,
                                                     self.colorScheme['background'],
                                                     self.colorScheme['default-text']))
        self.StyleClearAll ()
        self.StyleSetSpec (STYLE_FOLDER, "size:%d,bold,face:%s,fore:%s"
                                         % (pb, faceCourier,
                                            self.colorScheme['folder']))
        self.StyleSetSpec (STYLE_INC_SEARCH, "size:%d,bold,face:%s,fore:%s,back:%s"
                                             % (pb, faceCourier,
                                                self.colorScheme['search-highlight-fore'],
                                                self.colorScheme['search-highlight-back']))
        self.SetSelBackground (1, self.colorScheme['selection-inactive'])
        self.SetSelForeground (1, self.colorScheme['selection-fore'])

    # Used in tests
    def clearList (self):
        self.items = []
        self.selectedItem = 0
        self.numFullColumns = 0

    def initializeViewSettings (self, numColumns = 3):
        width, height = self.GetClientSizeTuple ()
        lineHeight = self.TextHeight (0)
        charWidth = self.TextWidth (stc.STC_STYLE_DEFAULT, 'a')

        # Here viewWindow.left will be set to 0. Even if it's not,
        # it will be brought back to life when doing moveItemIntoView:
        self.viewWindow = ViewWindow (width / charWidth,
                                      height / lineHeight - 5)
        self.viewWindow.numColumns = numColumns
        self.charsPerCol = width / charWidth / self.viewWindow.numColumns
        self.clearScreen ()
        self.updateDisplayByItems ()

    def initializeAndShowInitialView (self):
        self.initializeViewSettings ()

        dir = os.path.expanduser ('~')
        #dir = '/usr/share'
        os.chdir (dir)
        self.fillList (dir)
        self.SetFocus ()
        self.afterDirChange ()

    def updateDisplayByItems (self):
        self.SetReadOnly (False)
        self.numFullColumns = len (self.items) / self.viewWindow.height

        self.fullTextLines = ['' for i in range (self.viewWindow.height)]

        currLine = 0
        sj = SmartJustifier (self.charsPerCol - 1)

        for item in self.items:
            visiblePart = sj.justify (item.fileName) + ' '
            self.fullTextLines[currLine] += visiblePart
            item.visiblePartLength = len (visiblePart)
            currLine += 1

            if currLine > self.viewWindow.height - 1:
                currLine = 0

        visibleSublines = []

        for line in self.fullTextLines:
            subLine = line[:self.viewWindow.width].ljust (self.viewWindow.width, ' ')
            visibleSublines.append (subLine)

        self.SetText ('\n'.join (visibleSublines))
        self.EmptyUndoBuffer ()
        self.SetReadOnly (True)
        self.SetViewWhiteSpace (stc.STC_WS_VISIBLEALWAYS)
        self.SetViewEOL (True)
        self.setSelectionOnCurrItem ()
        self.applyDefaultStyles ()

    def fillList (self, cwd):
        allItems = collectListInfo (self.flatDirectoryView, cwd)
        self.workingDir = cwd
        self.items = constructListForFilling (allItems, self.directoryViewFilter)
        self.updateDisplayByItems ()

    def flattenDirectory (self):
        self.flatDirectoryView = True
        self.fillList (self.workingDir)
        self.afterDirChange ()

    def getFrame (self):
        return self.GetParent ().GetParent ()

    def afterDirChange (self):
        self.setSelectionOnCurrItem ()
        # in the line below, I'm subtracting 1 from number of items because of '..' pseudoitem
        statusText = '[Folder view]: %s\t%d item(s)' % (os.getcwd (), len (self.items) - 1)
        self.getFrame ().statusBar.SetStatusText (statusText)

    def updir (self):
        self.directoryViewFilter = None
        # if we're in self.flatDirectoryView, all we want is to refresh the view of
        # self.workingDir without flattening
        if self.flatDirectoryView:
            self.flatDirectoryView = False
            self.clearScreen ()
            self.fillList (os.getcwd ())

            # forget the selection of the flattened view
            self.selectedItem = 0
            self.afterDirChange ()
            return

        oldDir = os.path.split (os.getcwd ())[1]
        os.chdir ('..')
        self.clearScreen ()
        self.fillList (os.getcwd ())

        try:
            self.selectedItem = self.items.index (oldDir)
        except ValueError:
            pass

        self.afterDirChange ()

    def downdir (self, dirName):
        self.directoryViewFilter = None
        os.chdir (dirName)
        self.clearScreen ()
        self.selectedItem = 0
        self.fillList (os.getcwd ())
        self.afterDirChange ()

    def goHome (self):
        self.directoryViewFilter = None
        os.chdir (os.path.expanduser ('~'))
        self.clearScreen ()
        self.fillList (os.getcwd ())
        self.selectedItem = 0
        self.afterDirChange ()

    def OnDestroy (self, evt):
        # This is how the clipboard contents can be preserved after
        # the app has exited.
        wx.TheClipboard.Flush ()
        evt.Skip ()

    def clearScreen (self):
        self.SetReadOnly (False)
        self.ClearAll ()
        self.SetReadOnly (True)

    def quiter (self):
        sys.exit (0)

    def onEnter (self):
        selection = self.items[self.selectedItem]

        if selection.isDir:
            if selection.fileName == '..':
                self.updir ()
            else:
                self.downdir (selection.fileName)
        else:
            base, ext = os.path.splitext (selection.fileName)
            commandLine = resolveCommandByFileExt (ext[1:])

            if commandLine:
                os.system (commandLine % (selection.fileName))

    def onNextMatch (self):
        self.searchMatchIndex = self.nextSearchMatch (self.searchStr, self.selectedItem + 1)
        self.selectedItem = self.searchMatchIndex

    def onStartIncSearch (self):
        self.searchMode = True
        self.searchStr = ''

    def startEditor (self):
        os.system ('gvim ' + self.items[self.selectedItem].fileName)

    def startViewer (self):
        import viewr
        file = self.items[self.selectedItem].fileName
        wnd = viewr.BuiltinViewerFrame (self, -1, file, file)
        wnd.Show (True)

    def switchPane (self):
        self.getFrame ().switchPane ()
        self.afterDirChange ()

    def switchSplittingMode (self):
        self.getFrame ().switchSplittingMode ()

    def OnKeyDown (self, evt):
        keyCode = evt.GetKeyCode ()
        keyMod = evt.GetModifiers ()

        if self.searchMode:
            self.searchModeKeyDown (keyCode, keyMod)
        else:
            self.navigationModeKeyDown (keyCode, keyMod)

    def searchModeKeyDown (self, keyCode, keyMod):
        if keyCode == wx.WXK_RETURN:
            if keyMod == wx.MOD_CONTROL:
                self.directoryViewFilter = DirectoryViewFilter (self.searchStr)
                self.searchMode = False
                self.clearScreen ()
                self.fillList (self.workingDir)
                self.selectedItem = 0
                self.afterDirChange ()
            else:
                # Here we want to stop searching and set focus on first search match.
                # But if there was no match, we want to behave more like when we
                # click Escape. Except we've no matches to clear, since no match means
                # nothing was highlighted
                self.searchMode = False

                if self.searchMatchIndex != -1:
                    self.selectedItem = self.searchMatchIndex
                    self.setSelectionOnCurrItem ()
        elif keyCode == wx.WXK_ESCAPE:
            self.searchMode = False
            self.applyDefaultStyles ()  # Stop searching; clean matches
        else:
            if keyCode < 256:
                self.searchStr += chr (keyCode)
                self.incrementalSearch (self.searchStr)

    def navigationModeKeyDown (self, keyCode, keyMod):
        func = None

        try:
            func = self.navigationModeMap[keyCode]
        except KeyError:
            pass

        if func:
            func ()
            self.setSelectionOnCurrItem ()

    def OnSetFocus (self, evt):
        self.SetSelBackground (1, self.colorScheme['selection-back'])
        self.SetSelForeground (1, self.colorScheme['selection-fore'])
        os.chdir (self.workingDir)

    def OnLoseFocus (self, evt):
        self.SetSelBackground (1, self.colorScheme['selection-inactive'])
        self.SetSelForeground (1, self.colorScheme['selection-fore'])

    def nextSearchMatch (self, searchStr, initPos):
        # Construct a range of indices to produce wrapped search from current pos
        searchRange = range (initPos, len (self.items)) + range (initPos)
        searchStrLower = searchStr.lower ()

        for i in searchRange:
            if searchStrLower in self.items[i].fileName.lower ():
                return i

    def highlightSearchMatch (self, itemIndex, matchOffset):
        selectionStart = self.getItemStartChar (itemIndex) + matchOffset

        # Set the style for the new match:
        self.StartStyling (selectionStart, 0xff)
        stylingRegion = len (self.searchStr)
        self.SetStyling (stylingRegion, STYLE_INC_SEARCH)

    def moveItemIntoView (self, itemNo):
        if len (self.items) <= 0:
            return

        itemX, itemY = self.getItemCoordsByIndex (itemNo)
        startCharOnLine = itemX * self.charsPerCol
        endCharOnLine = startCharOnLine + self.charsPerCol

        if startCharOnLine < self.viewWindow.left:
            # move view window left
            self.viewWindow.left = startCharOnLine
        elif endCharOnLine > self.viewWindow.right ():
            # move view window right
            self.viewWindow.left = endCharOnLine - self.viewWindow.width
        else:
            return      # The item is already in view

        self.updateDisplay ()

    def updateDisplay (self):
        self.clearScreen ()
        self.SetReadOnly (False)
        visibleSublines = []

        for line in self.fullTextLines:
            rawSubLine = line[self.viewWindow.left : self.viewWindow.right ()]
            subLine = rawSubLine.ljust (self.viewWindow.width, ' ')
            visibleSublines.append (subLine)

        self.SetText ('\n'.join (visibleSublines))
        self.EmptyUndoBuffer ()
        self.SetReadOnly (True)
        self.SetViewWhiteSpace (stc.STC_WS_VISIBLEALWAYS)
        self.SetViewEOL (True)
        self.applyDefaultStyles ()

    def setSelectionOnCurrItem (self):
        if not self.isItemInView (self.selectedItem, fully = True):
            self.moveItemIntoView (self.selectedItem)

        selectionStart = self.getItemStartChar (self.selectedItem)
        self.SetCurrentPos (selectionStart)
        self.EnsureCaretVisible ()
        self.SetSelection (selectionStart , selectionStart + self.charsPerCol)

    def incrementalSearch (self, searchStr):
        index = self.selectedItem       # start searching from curr selection

        # Construct a range of indices to produce wrapped search from current pos
        searchRange = range (index, len (self.items)) + range (index)

        # First of all, clean previous matches
        self.applyDefaultStyles ()

        # We only want to remember first match
        firstMatch = -1

        for i in searchRange:
            match = self.items[i].fileName.lower ().find (searchStr.lower ())

            if match != -1:
                if firstMatch == -1:
                    firstMatch = i
                    self.moveItemIntoView (i)

                if self.isItemInView (i):
                    self.highlightSearchMatch (i, match)

        self.searchMatchIndex = firstMatch

    def moveSelectionDown (self):
        self.selectedItem += 1

        if self.selectedItem >= len (self.items):
            self.selectedItem = 0

    def moveSelectionUp (self):
        self.selectedItem -= 1

        if self.selectedItem < 0:
            self.selectedItem = len (self.items) - 1

        # This can happen if self.items is empty
        if self.selectedItem < 0:
            self.selectedItem = 0

    def moveSelectionLeft (self):
        self.selectedItem -= self.viewWindow.height

        if len (self.items) == 0:
            self.selectedItem = 0
            return

        if self.selectedItem < 0:
            self.selectedItem += self.viewWindow.height   # undo the decrement and start calculating from scratch
            numFullLines = len (self.items) % self.viewWindow.height
            bottomRightIndex = self.viewWindow.height * (self.numFullColumns + 1) - 1

            if self.selectedItem % self.viewWindow.height > numFullLines:
                bottomRightIndex = self.viewWindow.height * self.numFullColumns - 1

            self.selectedItem = self.selectedItem - self.viewWindow.height + bottomRightIndex

    def moveSelectionRight (self):
        self.selectedItem += self.viewWindow.height

        if len (self.items) == 0:
            self.selectedItem = 0
            return

        if self.selectedItem > len (self.items):
            self.selectedItem -= self.viewWindow.height
            self.selectedItem = self.selectedItem % self.viewWindow.height + 1

    def isItemInView (self, itemNo, **kwd):
        if len (self.items) <= 0:
            return False

        itemX, itemY = self.getItemCoordsByIndex (itemNo)
        startCharOnLine = itemX * self.charsPerCol
        endCharOnLine = startCharOnLine + self.charsPerCol

        secondCriterion = startCharOnLine

        try:
            fullyInView = kwd['fully']
            if fullyInView:
                secondCriterion = endCharOnLine
        except:
            pass

        if startCharOnLine >= self.viewWindow.left \
           and secondCriterion <= self.viewWindow.right ():
            return True

        return False

    def getItemCoordsByIndex (self, itemNo):
        itemX = 0
        itemY = 0

        # Avoid div0
        if self.viewWindow.height != 0:
            itemX, itemY = divmod (itemNo, self.viewWindow.height)

        return itemX, itemY

    def itemIndexToViewWindowCoords (self, itemNo):
        itemX, itemY = self.getItemCoordsByIndex (itemNo)
        itemViewX = itemX - intDivCeil (self.viewWindow.left, self.charsPerCol)
        itemViewY = itemY
        return itemViewX, itemViewY

    # self.viewWindow.left does not necessarily match corresponding item's
    # fileName[0]-th char. So when calculating getItemStartChar, we need to
    # compensate by the amount of mismatch. Think about this situation:
    #
    # 01234567890123456789
    # item0  |  item1
    #
    # self.charsPerCol is 10 in this diagram. The '|' denotes self.viewWindow.left.
    # So this function would return 3 in this case.
    def compensateViewWindowLeftChar (self):
        leftPos = self.viewWindow.left % self.charsPerCol

        if leftPos != 0:
            return self.charsPerCol - leftPos

        return leftPos

    def getItemStartChar (self, itemNo):
        itemViewX, itemViewY = self.itemIndexToViewWindowCoords (itemNo)
        return itemViewY * self.viewWindow.width + itemViewX * self.charsPerCol \
               + itemViewY + self.compensateViewWindowLeftChar ()

    def applyDefaultStyles (self):
        for index, item in enumerate (self.items):
            if self.isItemInView (index):
                selStart = self.getItemStartChar (index)
                self.StartStyling (selStart, 0xff)

                # By default, style whole item name:
                itemNameLen = len (item.fileName)

                # ...unless the whole name is wider than column:
                visiblePartLen = item.visiblePartLength

                # AND unless we're dealing with an item with only
                # few first characters visible on the right of the
                # view window:
                itemX, itemY = self.getItemCoordsByIndex (index)
                startCharOnLine = itemX * self.charsPerCol
                firstFewChars = self.viewWindow.width - (startCharOnLine - self.viewWindow.left)

                # Now choose the smallest from the above:
                stylingRange = min (itemNameLen, item.visiblePartLength, firstFewChars)
                self.SetStyling (stylingRange, item.style)

# TODO: read these from general.conf
faceCourier = 'Courier'
pb = 12

class Candy (wx.Frame):
    def __init__ (self, parent, id, title):
        wx.Frame.__init__ (self, parent, -1, title)

        self.splitter = wx.SplitterWindow (self, ID_SPLITTER, style = wx.SP_BORDER)
        self.splitter.SetMinimumPaneSize (50)

        self.p1 = MySTC (self.splitter, -1)
        self.p2 = MySTC (self.splitter, -1)
        self.splitter.SplitVertically (self.p1, self.p2)

        self.Bind (wx.EVT_SIZE, self.OnSize)
        self.Bind (wx.EVT_SPLITTER_DCLICK, self.OnDoubleClick, id = ID_SPLITTER)

        self.sizer = wx.BoxSizer (wx.VERTICAL)
        self.sizer.Add (self.splitter, 1, wx.EXPAND)
        self.SetSizer (self.sizer)

        size = wx.DisplaySize ()
        self.SetSize (size)

        self.statusBar = self.CreateStatusBar ()
        self.statusBar.SetStatusText (os.getcwd ())
        self.Center ()
        self.activePane = self.p1

    def setUpAndShow (self):
        self.p2.initializeAndShowInitialView ()
        self.p1.initializeAndShowInitialView ()
        self.activePane = self.p1

    def OnExit (self, e):
        self.Close (True)

    def splitEqual (self):
        size = self.GetSize ()

        splitMode = self.splitter.GetSplitMode ()
        sashDimension = size.x

        if splitMode == wx.SPLIT_HORIZONTAL:
            sashDimension = size.y

        self.splitter.SetSashPosition (sashDimension / 2)

    def OnSize (self, event):
        self.splitEqual ()
        event.Skip ()

    def OnDoubleClick (self, event):
        self.splitEqual ()

    def switchPane (self):
        if self.activePane == self.p1:
            self.activePane = self.p2
        else:
            self.activePane = self.p1

        self.activePane.SetFocus ()

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

