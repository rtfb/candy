#!/usr/bin/python

import wx
import wx.stc as stc
import os
import time
import sys

numTotalColumns = 5

STYLE_FOLDER = 1
STYLE_INC_SEARCH = 2

class IncSearchDirtyInfo:
    def __init__ (self):
        self.dirtyAreaBegin = 0
        self.dirtyAreaEnd = 0
        self.dirtyItemOriginalStyle = -1

class MySTC (stc.StyledTextCtrl):
    def __init__ (self, parent, ID):
        stc.StyledTextCtrl.__init__ (self, parent, ID)

        self.Bind (wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.Bind (wx.EVT_WINDOW_DESTROY, self.OnDestroy)

        self.linesPerCol = 0
        self.charsPerCol = 0
        self.charsPerWidth = 0
        self.numFullColumns = 0
        self.items = []
        self.selectedItem = 0
        self.searchMode = False
        self.searchStr = ''
        self.incSearchDirtyInfo = IncSearchDirtyInfo ()
        self.searchMatchIndex = -1
        self.columnWidth = 0

    def setColumnWidth (self, width):
        self.columnWidth = width

    def setDefaultSelection (self):
        self.SetSelection (0, self.charsPerCol)

    def setCharsPerCol (self, chars):
        self.charsPerCol = chars

    def setCharsPerWidth (self, width):
        self.charsPerWidth = width

    def setLinesPerCol (self, lines):
        self.linesPerCol = lines

    def setItemList (self, list):
        self.items = list
        self.numFullColumns = len (self.items) / self.linesPerCol

    def fillList (self, cwd):
        self.SetReadOnly (False)
        files = os.listdir (cwd)
        files.insert (0, '..')
        linesToAdd = ['' for i in range (self.linesPerCol)]

        currLine = 0
        for file in files:
            linesToAdd[currLine] += lJustAndCut (file, self.charsPerCol)
            currLine += 1

            if currLine > self.linesPerCol - 1:
                currLine = 0

        self.SetText ('\n'.join (linesToAdd))
        self.EmptyUndoBuffer ()
        self.SetReadOnly (True)
        self.SetFocus ()
        self.SetViewWhiteSpace (stc.STC_WS_VISIBLEALWAYS)
        self.SetViewEOL (True)
        self.SetSelBackground (1, "yellow")
        self.setDefaultSelection ()
        self.setItemList (files)
        self.runStyling ()

    def afterDirChange (self):
        self.setSelectionOnCurrItem ()
        #self.GetParent ().GetParent ().sb.SetStatusText (os.getcwd ())

    def updir (self):
        oldDir = os.path.split (os.getcwd ())[1]
        os.chdir ('..')
        self.clearScreen ()
        self.fillList (os.getcwd ())
        self.selectedItem = self.items.index (oldDir)
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

    def OnKeyDown (self, evt):
        keyCode = evt.GetKeyCode ()
        key = ''

        if keyCode < 256:
            key = chr (keyCode)

        if not self.searchMode:
            # Navigation mode:
            if key == 'J':
                self.moveSelectionDown ()
            elif key == 'K':
                self.moveSelectionUp ()
            elif key == 'H':
                self.moveSelectionLeft ()
            elif key == 'L':
                self.moveSelectionRight ()
            elif key == 'Q':
                sys.exit (0)
            elif key == 'U':
                self.updir ()
            elif keyCode == wx.WXK_RETURN:
                self.downdir (self.items[self.selectedItem])
            elif key == 'C':
                self.clearScreen ()
            elif key == '/':
                self.searchMode = True
                self.searchStr = ''

            self.setSelectionOnCurrItem ()
        else:
            # Search mode:
            if keyCode == wx.WXK_RETURN:
                self.searchMode = False
                self.selectedItem = self.searchMatchIndex
                self.setSelectionOnCurrItem ()
            elif keyCode == wx.WXK_ESCAPE:
                self.searchMode = False
                self.clearIncSearchDirtyArea ()
            else:
                self.searchStr += key
                self.incrementalSearch ()

    def clearIncSearchDirtyArea (self):
        self.StartStyling (self.incSearchDirtyInfo.dirtyAreaBegin, 0xff)
        self.SetStyling (self.incSearchDirtyInfo.dirtyAreaEnd, self.incSearchDirtyInfo.dirtyItemOriginalStyle)

    def isPositionVisible (self, pos):
        if pos / self.linesPerCol > self.linesPerCol or pos / self.charsPerWidth > self.charsPerWidth:
           return False

        return True

    # TODO: wrap search
    def incrementalSearch (self):
        index = self.selectedItem       # start searching from curr selection

        for i in range (index, len (self.items)):
            match = self.items[i].lower ().find (self.searchStr.lower ())

            if match == -1:
                continue

            self.searchMatchIndex = i
            selection = self.getItemStartChar (i)
            selectionStart = selection + match

            # This is my lame approach to move search match into view
            if not self.isPositionVisible (selectionStart):
                self.GotoPos (selectionStart + self.charsPerCol)
                self.MoveCaretInsideView ()

            # First of all, clean previous match:
            self.clearIncSearchDirtyArea ()

            # Now, set the style for the new match:
            self.incSearchDirtyInfo.dirtyItemOriginalStyle = self.GetStyleAt (selectionStart)   # remember original style
            self.StartStyling (selectionStart, 0xff)
            stylingRegion = len (self.searchStr)
            self.incSearchDirtyInfo.dirtyAreaBegin = selectionStart
            self.incSearchDirtyInfo.dirtyAreaEnd = stylingRegion
            self.SetStyling (stylingRegion, STYLE_INC_SEARCH)
            break

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

    def runStyling (self):
        # Now set some text to those styles...  Normally this would be
        # done in an event handler that happens when text needs displayed.
        for i in range (len (self.items)):
            fileName = self.items[i]

            if os.path.isdir (fileName):
                selStart = self.getItemStartChar (i)
                self.StartStyling (selStart, 0xff)
                self.SetStyling (len (fileName), STYLE_FOLDER)

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

        self.p1 = MySTC (self, -1)

        # make some styles
        self.p1.StyleSetSpec (stc.STC_STYLE_DEFAULT, "size:%d,face:%s" % (pb, faceCourier))
        self.p1.StyleClearAll ()
        self.p1.StyleSetSpec (STYLE_FOLDER, "size:%d,bold,face:%s,fore:#0000FF" % (pb, faceCourier))
        self.p1.StyleSetSpec (STYLE_INC_SEARCH, "size:%d,bold,face:%s,fore:#000000,back:#00ffff" % (pb, faceCourier))
        """
        self.p1.StyleSetSpec (2, "face:%s,italic,fore:#FF0000,size:%d" % (face3, pb))
        self.p1.StyleSetSpec (3, "face:%s,bold,size:%d" % (face3, pb + 2))
        self.p1.StyleSetSpec (4, "face:%s,size:%d" % (face3, pb - 1))
        """

        self.Bind (wx.EVT_SIZE, self.OnSize)
        #self.Bind (wx.EVT_SPLITTER_DCLICK, self.OnDoubleClick, id = ID_SPLITTER)
        self.Bind (wx.EVT_KEY_DOWN, self.OnKeyDown)

        size = wx.DisplaySize ()
        self.SetSize (size)

        self.sb = self.CreateStatusBar ()
        self.sb.SetStatusText (os.getcwd ())
        self.Center ()
        self.Show (True)

        width, height = self.p1.GetClientSizeTuple ()
        colWidth = width / numTotalColumns
        lineHeight = self.p1.TextHeight (0)
        linesPerCol = height / lineHeight
        charWidth = self.p1.TextWidth (stc.STC_STYLE_DEFAULT, 'a')
        charsPerCol = width / charWidth / numTotalColumns

        self.p1.setCharsPerWidth (width / charWidth)
        self.p1.setCharsPerCol (charsPerCol)
        self.p1.setLinesPerCol (linesPerCol)
        self.p1.setColumnWidth (colWidth)

        dir = '/home/rtfb'
        os.chdir (dir)
        self.p1.fillList (dir)

    def OnExit (self, e):
        self.Close (True)

    def OnSize (self, event):
        size = self.GetSize ()
        event.Skip ()

    def OnDoubleClick (self, event):
        size =  self.GetSize ()

    def OnKeyDown (self, event):
        print "OKD in Candy"
        keycode = event.GetKeyCode ()
        self.sb.SetStatusText (str (keycode))
        if keycode == wx.WXK_ESCAPE:
            ret  = wx.MessageBox ('Are you sure to quit?',
                                  'Question',
                                  wx.YES_NO | wx.CENTRE | wx.NO_DEFAULT,
                                  self)
            if ret == wx.YES:
                self.Close ()
        event.Skip ()

def main ():
    app = wx.App (0)
    candy = Candy (None, -1, 'Candy')
    app.MainLoop ()

if __name__ == '__main__':
    main ()

