#!/usr/bin/env python

# http://freshmeat.net/projects/python-urwid/

import wx
import wx.stc as stc
import os
import time
import sys
import pdb

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

def colorNameToHtmlValue (name):
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

    return dict[name]

def readColorScheme (fileName):
    lines = open (fileName).readlines ()
    dict = {}

    for l in lines:
        if l.strip () == '':
            continue

        name, value = l.split (':')
        dict.setdefault (name.strip (), colorNameToHtmlValue (value.strip ()))

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

    if cwd != '/':
        files.insert (0, '..')

    return files

def collectListInfo (isFlatDirectoryView, cwd):
    items = []

    files = listFiles (isFlatDirectoryView, cwd)

    for f in files:
        item = ListItem (f)

        if os.path.isdir (f):
            item.style = STYLE_FOLDER
            item.isDir = True

        if f.startswith ('.') and f != '..':
            item.isHidden = True

        items.append (item)

    return items

def constructListForFilling (fullList, specialFilter):
    dirList = filter (lambda (f): f.isDir, fullList)
    dirList.sort ()

    fileList = filter (lambda (f): not f.isDir, fullList)
    fileList.sort ()

    notHidden = filter (lambda (f): not f.isHidden, dirList + fileList)

    if specialFilter:
        return filter (specialFilter, notHidden)
    else:
        return notHidden

def lJustAndCut (text, width):
    newText = text.ljust (width)

    if len (newText) > width:
        newText = newText [:width]

    return newText

class MySTC (stc.StyledTextCtrl):
    def __init__ (self, parent, ID):
        stc.StyledTextCtrl.__init__ (self, parent, ID)

        self.bindEvents ()

        projectDir = os.path.dirname (__file__)
        self.colorScheme = readColorScheme (os.path.join (projectDir, 'colorscheme-default.conf'))
        self.setStyles ()

        # Number of lines per single column
        self.linesPerCol = 0

        # Number of characters per column width
        self.charsPerCol = 0

        # Number of characters that can fit in whole width of the pane
        self.charsPerWidth = 0

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

        # Width of the column in pixels
        self.columnWidth = 0

        # Working directory of the pane
        self.workingDir = os.path.expanduser ('~')

        # Number of columns of items across all the width of the pane
        self.numberOfColumns = 3

        # Signifies flattened directory view
        self.flatDirectoryView = False

        # Function Object that gets called to filter out directory view.
        # Main use is for filtering out the contents by search matches.
        self.directoryViewFilter = None

        self.navigationModeMap = {
            ord ('J'): self.moveSelectionDown,
            ord ('K'): self.moveSelectionUp,
            ord ('H'): self.moveSelectionLeft,
            ord ('L'): self.moveSelectionRight,
            ord ('Q'): self.quiter,
            ord ('F'): self.flattenDirectory,
            ord ('U'): self.updir,
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

    def clearList (self):
        self.items = []
        self.selectedItem = 0
        self.numFullColumns = 0

    def initializeViewSettings (self, numColumns = 3):
        self.numberOfColumns = numColumns
        width, height = self.GetClientSizeTuple ()
        self.columnWidth = width / self.numberOfColumns
        lineHeight = self.TextHeight (0)
        self.linesPerCol = height / lineHeight - 5
        charWidth = self.TextWidth (stc.STC_STYLE_DEFAULT, 'a')
        self.charsPerCol = width / charWidth / self.numberOfColumns
        #print height, lineHeight, self.linesPerCol

        self.charsPerWidth = width / charWidth
        self.clearScreen ()
        self.updateDisplayByItems ()

    def initializeAndShowInitialView (self):
        self.initializeViewSettings ()

        dir = os.path.expanduser ('~')
        #dir = '/usr/lib'
        os.chdir (dir)
        self.fillList (dir)
        self.SetFocus ()
        self.afterDirChange ()

    def updateDisplayByItems (self):
        self.SetReadOnly (False)
        self.numFullColumns = len (self.items) / self.linesPerCol

        linesToAdd = ['' for i in range (self.linesPerCol)]

        currLine = 0
        for item in self.items:
            visiblePart = lJustAndCut (item.fileName, self.charsPerCol)
            linesToAdd[currLine] += visiblePart
            item.visiblePartLength = len (visiblePart)
            currLine += 1

            if currLine > self.linesPerCol - 1:
                currLine = 0

        self.SetText ('\n'.join (linesToAdd))
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
                self.searchMode = False
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
        # Navigation mode:
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

    def getLeftmostColumn (self):
        point = wx.Point ()
        point.x = self.GetXOffset ()
        point.y = 0
        return self.GetColumn (self.PositionFromPoint (point))

    def highlightSearchMatch (self, itemIndex, matchOffset):
        selectionStart = self.getItemStartChar (itemIndex) + matchOffset

        # Set the style for the new match:
        self.StartStyling (selectionStart, 0xff)
        stylingRegion = len (self.searchStr)
        self.SetStyling (stylingRegion, STYLE_INC_SEARCH)

    def moveItemIntoView (self, itemIndex):
        selectionStart = self.getItemStartChar (itemIndex)
        leftmostColumn = self.getLeftmostColumn ()
        rightmostColumn = leftmostColumn + self.charsPerWidth
        columnOfTheMatch = self.GetColumn (selectionStart)

        # This is my lame approach to move search match into view
        if columnOfTheMatch + len (self.searchStr) > rightmostColumn:
            # we're to the right of the view:
            self.GotoPos (selectionStart + self.charsPerCol)
        elif columnOfTheMatch < leftmostColumn:
            # we're to the left:
            self.GotoPos (selectionStart)

        self.MoveCaretInsideView ()

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

                self.highlightSearchMatch (i, match)

        self.searchMatchIndex = firstMatch

    def setSelectionOnCurrItem (self):
        selectionStart = self.getItemStartChar (self.selectedItem)
        self.SetCurrentPos (selectionStart)
        self.EnsureCaretVisible ()
        self.SetSelection (selectionStart , selectionStart + self.charsPerCol)

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
        self.selectedItem -= self.linesPerCol

        if len (self.items) == 0:
            self.selectedItem = 0
            return

        if self.selectedItem < 0:
            self.selectedItem += self.linesPerCol   # undo the decrement and start calculating from scratch
            numFullLines = len (self.items) % self.linesPerCol
            bottomRightIndex = self.linesPerCol * (self.numFullColumns + 1) - 1

            if self.selectedItem % self.linesPerCol > numFullLines:
                bottomRightIndex = self.linesPerCol * self.numFullColumns - 1

            self.selectedItem = self.selectedItem - self.linesPerCol + bottomRightIndex

    def moveSelectionRight (self):
        self.selectedItem += self.linesPerCol

        if len (self.items) == 0:
            self.selectedItem = 0
            return

        if self.selectedItem > len (self.items):
            self.selectedItem -= self.linesPerCol
            self.selectedItem = self.selectedItem % self.linesPerCol + 1

    def getItemStartChar (self, itemNo):
        itemX = 0
        itemY = 0
        numFullLines = 0

        # Avoid div0
        if self.linesPerCol != 0:
            itemX = itemNo / self.linesPerCol
            itemY = itemNo % self.linesPerCol
            numFullLines = len (self.items) % self.linesPerCol

        numNonEmptyColumns = self.numFullColumns + 1

        if itemY > numFullLines:
            selStart = numFullLines * numNonEmptyColumns * self.charsPerCol \
                       + (itemY - numFullLines) * self.numFullColumns * self.charsPerCol \
                       + (itemX * self.charsPerCol) + itemY
        else:
            selStart = itemY * numNonEmptyColumns * self.charsPerCol + (itemX * self.charsPerCol) + itemY

        return selStart

    def applyDefaultStyles (self):
        # Now set some text to those styles...  Normally this would be
        # done in an event handler that happens when text needs displayed.
        for index, item in enumerate (self.items):
            selStart = self.getItemStartChar (index)
            self.StartStyling (selStart, 0xff)
            self.SetStyling (min (len (item.fileName), item.visiblePartLength), item.style)

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

