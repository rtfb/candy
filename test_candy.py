#!/usr/bin/env python

import unittest
import candy
import wx
import os

class TestCandy (unittest.TestCase):
    def setUp (self):
        self.app = wx.PySimpleApp ()
        self.frame = candy.Candy (None, -1, 'foo')

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

    # This one fails as of yet. Should make it pass to get rid of automatic listdir
    def testItemListIsEmpty (self):
        self.assertEquals (len (self.frame.p1.items), 0)
        self.assertEquals (len (self.frame.p2.items), 0)

def suite ():
    suite = unittest.makeSuite (TestCandy, 'test')
    return suite

if __name__ == '__main__':
    unittest.main (defaultTest = 'suite')

