#!/usr/bin/env python

import unittest
import candy
import wx
import os

def fakeFileLister (isFlatDirectoryView, cwd):
    dirs = []
    files = []
    hidden = []

    for i in range (10):
        dirs.append ('dir' + str (i))

    dirs.insert (0, '..')

    for i in range (20):
        files.append ('file' + str (i))

    for i in range (5):
        hidden.append ('.hid' + str (i))

    return dirs + files + hidden

candy.listFiles = fakeFileLister

class TestCandy (unittest.TestCase):
    def setUp (self):
        self.app = wx.PySimpleApp ()
        self.frame = candy.Candy (None, -1, 'foo')
        self.frame.setUpAndShow ()

    def tearDown (self):
        self.frame.Destroy ()

    # only passes if frame is shown... :-/
    #def testSplitEqual (self):
        #size = self.frame.GetSize ()
        #self.assertEqual (size.x / 2, self.frame.splitter.GetSashPosition ())

    def testInitialDirectoryOnActivePane (self):
        self.assertEqual (self.frame.activePane.workingDir, os.path.expanduser ('~'))

    def testInitialSelection (self):
        self.assertEqual (self.frame.activePane.selectedItem, 0)

    def testItemListIsEmpty (self):
        self.frame.p1.clearList ()
        self.frame.p2.clearList ()
        self.assertEquals (len (self.frame.p1.items), 0)
        self.assertEquals (len (self.frame.p2.items), 0)

    def testSelectionDoesntGetAnywhereOnEmptyList (self):
        self.frame.p1.clearList ()
        self.frame.p2.clearList ()
        self.frame.p1.moveSelectionUp ()
        self.assertEquals (self.frame.p1.selectedItem, 0)
        self.frame.p1.moveSelectionDown ()
        self.assertEquals (self.frame.p1.selectedItem, 0)
        self.frame.p1.moveSelectionLeft ()
        self.assertEquals (self.frame.p1.selectedItem, 0)
        self.frame.p1.moveSelectionRight ()
        self.assertEquals (self.frame.p1.selectedItem, 0)

    def testItemStartCharIsZeroOnEmptyList (self):
        self.assertEquals (self.frame.p1.getItemStartChar (0), 0)

    def testItemsListIsNotEmpty (self):
        self.assertTrue (len (self.frame.p1.items) > 0)

    def testSimpleIncSearch (self):
        self.frame.p1.incrementalSearch ('dir')
        self.assertEquals (self.frame.p1.searchMatchIndex, 1)

    def testNextSearchMatch (self):
        searchStr = 'file'
        self.frame.p1.incrementalSearch (searchStr)
        currPos = self.frame.p1.searchMatchIndex
        match = self.frame.p1.nextSearchMatch (searchStr, self.frame.p1.searchMatchIndex + 1)
        self.assertEquals (match, currPos + 1)

def suite ():
    suite = unittest.makeSuite (TestCandy, 'test')
    return suite

if __name__ == '__main__':
    unittest.main (defaultTest = 'suite')

