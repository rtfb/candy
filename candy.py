#!/usr/bin/env python

# http://freshmeat.net/projects/python-urwid/

import wx
import wx.stc as stc
import os
import time
import sys
import pdb

numTotalColumns = 3

STYLE_FOLDER = 1
STYLE_INC_SEARCH = 2

ID_SPLITTER = 100

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
    extDict = { \
        'wmv':  'mplayer %s', \
        'mpeg': 'mplayer %s', \
        'mpg':  'mplayer %s', \
        'avi':  'mplayer %s', \
        'asf':  'mplayer %s', \
        'pdf':  'evince %s', \
        'jpg':  'gqview %s', \
        'jpeg': 'gqview %s', \
        'png':  'gqview %s', \
        'bmp':  'gqview %s', \
        'xpm':  'gqview %s', \
        'gif':  'gqview %s', \
        # TODO: handle archives as folders
        'rar':  'file-roller %s', \
        'zip':  'file-roller %s', \
        'gz':   'file-roller %s', \
        'tar':  'file-roller %s', \
        'txt':  'gvim %s'}

    cmd = None

    try:
        cmd = extDict[ext]
    except KeyError:
        pass

    return cmd

def colorNameToHtmlValue (name):
    # http://html-color-codes.com/
    dict = { \
        'black':  '#000000', \
        'white':  '#ffffff', \
        'yellow': '#ffff00', \
        'blue':   '#0000ff', \
        'red':    '#ff0000', \
        'lgrey':  '#cccccc', \
        'grey':   '#999999', \
        }

    return dict[name]

def readColorScheme (fileName):
    lines = open (fileName).readlines ()
    dict = {}

    for l in lines:
        if l.strip () == '':
            continue

        configPair = l.split (':')
        dict.setdefault (configPair[0].strip (), colorNameToHtmlValue (configPair[1].strip ()))

    return dict

class MySTC (stc.StyledTextCtrl):
    def __init__ (self, parent, ID):
        stc.StyledTextCtrl.__init__ (self, parent, ID)

        self.Bind (wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind (wx.EVT_WINDOW_DESTROY, self.OnDestroy)
        self.Bind (wx.EVT_SET_FOCUS, self.OnSetFocus)
        self.Bind (wx.EVT_KILL_FOCUS, self.OnLoseFocus)

        self.colorScheme = readColorScheme ('/home/rtfb/projects/candy/colorscheme-default.conf')

        # Set the styles according to color scheme
        self.StyleSetSpec (stc.STC_STYLE_DEFAULT, "size:%d,face:%s,back:%s,fore:%s"
                                                  % (pb, faceCourier, \
                                                     self.colorScheme['background'], \
                                                     self.colorScheme['default-text']))
        self.StyleClearAll ()
        self.StyleSetSpec (STYLE_FOLDER, "size:%d,bold,face:%s,fore:%s"
                                         % (pb, faceCourier, \
                                            self.colorScheme['folder']))
        self.StyleSetSpec (STYLE_INC_SEARCH, "size:%d,bold,face:%s,fore:%s,back:%s" \
                                             % (pb, faceCourier, \
                                                self.colorScheme['search-highlight-fore'], \
                                                self.colorScheme['search-highlight-back']))
        self.SetSelBackground (1, self.colorScheme['selection-inactive'])
        self.SetSelForeground (1, self.colorScheme['selection-fore'])

        self.linesPerCol = 0
        self.charsPerCol = 0
        self.charsPerWidth = 0
        self.numFullColumns = 0
        self.items = []
        self.selectedItem = 0
        self.searchMode = False
        self.searchStr = ''
        self.searchMatchIndex = -1
        self.columnWidth = 0

        self.navigationModeMap = { \
            ord ('J'): self.moveSelectionDown, \
            ord ('K'): self.moveSelectionUp, \
            ord ('H'): self.moveSelectionLeft, \
            ord ('L'): self.moveSelectionRight, \
            ord ('Q'): self.quiter, \
            ord ('U'): self.updir, \
            wx.WXK_RETURN: self.onEnter, \
            wx.WXK_SPACE: self.onEnter, \
            ord ('C'): self.clearScreen, \
            ord ('N'): self.onNextMatch, \
            ord ('/'): self.onStartIncSearch, \
            wx.WXK_F4: self.startEditor, \
            ord ('E'): self.startEditor, \
            wx.WXK_TAB: self.switchPane, \
            wx.WXK_F3: self.startViewer, \
            ord ('V'): self.startViewer}

    def initializeAndShowInitialView (self):
        width, height = self.GetClientSizeTuple ()
        self.columnWidth = width / numTotalColumns
        lineHeight = self.TextHeight (0)
        self.linesPerCol = height / lineHeight - 5
        charWidth = self.TextWidth (stc.STC_STYLE_DEFAULT, 'a')
        self.charsPerCol = width / charWidth / numTotalColumns
        print height, lineHeight, self.linesPerCol

        self.charsPerWidth = width / charWidth

        dir = '/home/rtfb'
        #dir = '/usr/lib'
        os.chdir (dir)
        self.fillList (dir)
        self.SetFocus ()
        self.afterDirChange ()

    def setDefaultSelection (self):
        self.SetSelection (0, self.charsPerCol)

    def collectListInfo (self, cwd):
        items = []
        files = os.listdir (cwd)

        if cwd != '/':
            files.insert (0, '..')

        for f in files:
            item = ListItem (f)

            if os.path.isdir (f):
                item.style = STYLE_FOLDER
                item.isDir = True

            if f.startswith ('.') and f != '..':
                item.isHidden = True

            items.append (item)

        return items

    def constructListForFilling (self, fullList):
        dirList = filter (lambda (f): f.isDir, fullList)
        dirList.sort ()

        fileList = filter (lambda (f): not f.isDir, fullList)
        fileList.sort ()

        return filter (lambda (f): not f.isHidden, dirList + fileList)

    def fillList (self, cwd):
        self.SetReadOnly (False)
        allItems = self.collectListInfo (cwd)
        self.items = self.constructListForFilling (allItems)
        self.numFullColumns = len (self.items) / self.linesPerCol
        print 'Number of files in the list:', len (self.items)

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
        self.setDefaultSelection ()
        self.applyDefaultStyles ()

    def afterDirChange (self):
        self.setSelectionOnCurrItem ()
        self.GetParent ().GetParent ().statusBar.SetStatusText (os.getcwd ())

    def updir (self):
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
        self.searchMatchIndex = self.nextSearchMatch (self.selectedItem + 1)
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
        self.GetParent ().GetParent ().switchPane ()

    def OnKeyDown (self, evt):
        keyCode = evt.GetKeyCode ()

        if not self.searchMode:
            # Navigation mode:
            func = None

            try:
                func = self.navigationModeMap[keyCode]
            except KeyError:
                pass

            if func:
                func ()
                self.setSelectionOnCurrItem ()
        else:
            # Search mode:
            if keyCode == wx.WXK_RETURN:
                self.searchMode = False
                self.selectedItem = self.searchMatchIndex
                self.setSelectionOnCurrItem ()
            elif keyCode == wx.WXK_ESCAPE:
                self.searchMode = False
                self.applyDefaultStyles ()  # Stop searching; clean matches
            else:
                self.searchStr += chr (keyCode)
                self.incrementalSearch ()

    def OnSetFocus (self, evt):
        self.SetSelBackground (1, self.colorScheme['selection-back'])
        self.SetSelForeground (1, self.colorScheme['selection-fore'])

    def OnLoseFocus (self, evt):
        self.SetSelBackground (1, self.colorScheme['selection-inactive'])
        self.SetSelForeground (1, self.colorScheme['selection-fore'])

    def posToColumn (self, pos):
        return pos % self.GetLineEndPosition (0) - pos / self.GetLineEndPosition (0)

    def nextSearchMatch (self, initPos):
        # Construct a range of indices to produce wrapped search from current pos
        searchRange = range (initPos, len (self.items)) + range (initPos)

        for i in searchRange:
            match = self.items[i].fileName.lower ().find (self.searchStr.lower ())

            if match != -1:
                return i

    def getLeftmostColumn (self):
        point = wx.Point ()
        point.x = self.GetXOffset ()
        point.y = 0
        return self.posToColumn (self.PositionFromPoint (point))

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
        columnOfTheMatch = self.posToColumn (selectionStart)

        # This is my lame approach to move search match into view
        if columnOfTheMatch + len (self.searchStr) > rightmostColumn:
            # we're to the right of the view:
            self.GotoPos (selectionStart + self.charsPerCol)
        elif columnOfTheMatch < leftmostColumn:
            # we're to the left:
            self.GotoPos (selectionStart)

        self.MoveCaretInsideView ()

    def incrementalSearch (self):
        index = self.selectedItem       # start searching from curr selection

        # Construct a range of indices to produce wrapped search from current pos
        searchRange = range (index, len (self.items)) + range (index)

        # First of all, clean previous matches
        self.applyDefaultStyles ()

        # We only want to remember first match
        firstMatch = -1

        for i in searchRange:
            match = self.items[i].fileName.lower ().find (self.searchStr.lower ())

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

    def moveSelectionLeft (self):
        self.selectedItem -= self.linesPerCol

        if self.selectedItem < 0:
            self.selectedItem += self.linesPerCol   # undo the decrement and start calculating from scratch
            numFullLines = len (self.items) % self.linesPerCol
            bottomRightIndex = self.linesPerCol * (self.numFullColumns + 1) - 1

            if self.selectedItem % self.linesPerCol > numFullLines:
                bottomRightIndex = self.linesPerCol * self.numFullColumns - 1

            self.selectedItem = self.selectedItem - self.linesPerCol + bottomRightIndex

    def moveSelectionRight (self):
        self.selectedItem += self.linesPerCol

        if self.selectedItem > len (self.items):
            self.selectedItem -= self.linesPerCol
            self.selectedItem = self.selectedItem % self.linesPerCol + 1

    def getItemStartChar (self, itemNo):
        itemX = itemNo / self.linesPerCol
        itemY = itemNo % self.linesPerCol
        numNonEmptyColumns = self.numFullColumns + 1
        numFullLines = len (self.items) % self.linesPerCol

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
        for i in self.items:
            selStart = self.getItemStartChar (self.items.index (i))
            self.StartStyling (selStart, 0xff)
            self.SetStyling (min (len (i.fileName), i.visiblePartLength), i.style)

faceCourier = 'Courier'
pb = 12

def lJustAndCut (text, width):
    newText = text.ljust (width)

    if len (newText) > width:
        newText = newText [:width]

    return newText

class Candy (wx.Frame):
    def __init__ (self, parent, id, title):
        wx.Frame.__init__ (self, parent, -1, title)

        self.splitter = wx.SplitterWindow (self, ID_SPLITTER, style = wx.SP_BORDER)
        self.splitter.SetMinimumPaneSize (50)

        self.p1 = MySTC (self.splitter, -1)
        self.p2 = MySTC (self.splitter, -1)
        self.splitter.SplitVertically (self.p1, self.p2)

        self.Bind (wx.EVT_SIZE, self.OnSize)
        self.Bind (wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind (wx.EVT_SPLITTER_DCLICK, self.OnDoubleClick, id = ID_SPLITTER)

        self.sizer = wx.BoxSizer (wx.VERTICAL)
        self.sizer.Add (self.splitter, 1, wx.EXPAND)
        self.SetSizer (self.sizer)

        size = wx.DisplaySize ()
        self.SetSize (size)

        self.statusBar = self.CreateStatusBar ()
        self.statusBar.SetStatusText (os.getcwd ())
        self.Center ()
        self.Show (True)

        self.p2.initializeAndShowInitialView ()
        self.p1.initializeAndShowInitialView ()
        self.activePane = self.p1

    def OnExit (self, e):
        self.Close (True)

    def OnSize (self, event):
        size = self.GetSize ()
        self.splitter.SetSashPosition (size.x / 2)
        event.Skip ()

    def OnDoubleClick (self, event):
        size = self.GetSize ()
        self.splitter.SetSashPosition (size.x / 2)

    def OnKeyDown (self, event):
        keycode = event.GetKeyCode ()
        self.statusBar.SetStatusText (str (keycode))
        if keycode == wx.WXK_ESCAPE:
            ret  = wx.MessageBox ('Are you sure to quit?',
                                  'Question',
                                  wx.YES_NO | wx.CENTRE | wx.NO_DEFAULT,
                                  self)
            if ret == wx.YES:
                self.Close ()
        event.Skip ()

    def switchPane (self):
        if self.activePane == self.p1:
            self.activePane = self.p2
        else:
            self.activePane = self.p1

        self.activePane.SetFocus ()

def main ():
    app = wx.App (0)
    candy = Candy (None, -1, 'Candy')
    app.MainLoop ()

if __name__ == '__main__':
    main ()

