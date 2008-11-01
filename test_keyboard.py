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

import unittest
import wx
import keyboard
import pdb

class TestKeyboardEventHandler (unittest.TestCase):
    def setUp (self):
        pass

    def tearDown (self):
        pass

    def testNewKeyboardEventIsEmpty (self):
        ke = keyboard.KeyboardEvent ()
        self.assertEquals (ke.char, '')
        self.assertEquals (ke.keyCode, 0)
        self.assertEquals (ke.modCtrl, False)
        self.assertEquals (ke.modAlt, False)
        self.assertEquals (ke.modShift, False)

    def testOneLetterLowercase (self):
        ke = keyboard.KeyboardEvent ()
        # ke.char is simply the letter, ke.keyCode is the uppercased letter
        for char in range (ord ('a'), ord ('z')):
            ke.parse (chr (char))
            self.assertEquals (ke.char, chr (char))
            self.assertEquals (ke.keyCode, ord (chr (char).upper ()))
            self.assertFalse (ke.modShift)

    def testOneLetterUppercase (self):
        ke = keyboard.KeyboardEvent ()
        for char in range (ord ('A'), ord ('Z')):
            ke.parse (chr (char))
            self.assertEquals (ke.char, chr (char))
            self.assertEquals (ke.keyCode, char)
            self.assertTrue (ke.modShift)

    def testDigits (self):
        ke = keyboard.KeyboardEvent ()
        # ke.char is simply the digit, ke.keyCode is the ascii number for that digit
        for char in range (ord ('0'), ord ('9')):
            ke.parse (chr (char))
            self.assertEquals (ke.char, chr (char))
            self.assertEquals (ke.keyCode, char)
            self.assertFalse (ke.modShift)

    def testShiftDigits (self):
        ke = keyboard.KeyboardEvent ()
        # ke.char is the '!@#', etc., ke.keyCode is the ascii number for that symbol
        for char in '!@#$%^&*()':
            ke.parse (char)
            self.assertEquals (ke.char, char)
            self.assertEquals (ke.keyCode, ord (char))
            self.assertTrue (ke.modShift)

    def testOtherUnshifted (self):
        ke = keyboard.KeyboardEvent ()
        # ke.char is the '`-=', etc., ke.keyCode is the ascii number for that symbol
        for char in '`-=[];\',./\\':
            ke.parse (char)
            self.assertEquals (ke.char, char)
            self.assertEquals (ke.keyCode, ord (char))
            self.assertFalse (ke.modShift)

    def testOtherShifted (self):
        ke = keyboard.KeyboardEvent ()
        # ke.char is the '~_+', etc., ke.keyCode is the ascii number for that symbol
        for char in '~_+{}|:"<>?':
            ke.parse (char)
            self.assertEquals (ke.char, char)
            self.assertEquals (ke.keyCode, ord (char))
            self.assertTrue (ke.modShift)

    def testSomeSpecials (self):
        ke = keyboard.KeyboardEvent ()

        for key, code in [('Esc', wx.WXK_ESCAPE), ('esc', wx.WXK_ESCAPE),
                          ('Space', wx.WXK_SPACE), ('space', wx.WXK_SPACE),
                          ('Enter', wx.WXK_RETURN), ('enter', wx.WXK_RETURN),
                          ('Tab', wx.WXK_TAB), ('TAB', wx.WXK_TAB), ('tab', wx.WXK_TAB),
                          ('Return', wx.WXK_RETURN), ('return', wx.WXK_RETURN)]:
            ke.parse (key)
            self.assertEquals (ke.char, '')
            self.assertEquals (ke.keyCode, code)

    def testEmpty (self):
        ke = keyboard.KeyboardEvent ()

        try:
            ke.parse ('')
            self.fail ()
        except keyboard.EventParseError:
            pass

    def testControlA (self):
        ke = keyboard.KeyboardEvent ()
        ke.parse ('C-a')
        self.assertEquals (ke.char, 'a')
        self.assertEquals (ke.keyCode, ord ('A'))
        self.assertTrue (ke.modCtrl)
        self.assertFalse (ke.modShift)
        self.assertFalse (ke.modAlt)

    def testShiftB (self):
        ke = keyboard.KeyboardEvent ()
        ke.parse ('S-b')
        self.assertEquals (ke.char, 'b')
        self.assertEquals (ke.keyCode, ord ('B'))
        self.assertTrue (ke.modShift)
        self.assertFalse (ke.modAlt)
        self.assertFalse (ke.modCtrl)

    def testAltZ (self):
        def check (ke):
            self.assertEquals (ke.char, 'z')
            self.assertEquals (ke.keyCode, ord ('Z'))
            self.assertTrue (ke.modAlt)
            self.assertFalse (ke.modShift)
            self.assertFalse (ke.modCtrl)

        ke = keyboard.KeyboardEvent ()
        ke.parse ('A-z')
        check (ke)
        ke.reset ()
        ke.parse ('M-z')
        check (ke)

    def testFunctionKeys (self):
        funcs = [wx.WXK_F1, wx.WXK_F2, wx.WXK_F3, wx.WXK_F4, wx.WXK_F5,
                 wx.WXK_F6, wx.WXK_F7, wx.WXK_F8, wx.WXK_F9, wx.WXK_F10,
                 wx.WXK_F11, wx.WXK_F12, wx.WXK_F13, wx.WXK_F14, wx.WXK_F15,
                 wx.WXK_F16, wx.WXK_F17, wx.WXK_F18, wx.WXK_F19, wx.WXK_F20,
                 wx.WXK_F21, wx.WXK_F22, wx.WXK_F23, wx.WXK_F24]

        for i in range (1, 25):
            ke = keyboard.KeyboardEvent ()
            ke.parse ('f%d' % (i))
            self.assertEquals (ke.keyCode, funcs[i - 1])

    def testControlAltM (self):
        ke = keyboard.KeyboardEvent ()
        ke.parse ('C-A-m')
        self.assertEquals (ke.char, 'm')
        self.assertEquals (ke.keyCode, ord ('M'))
        self.assertFalse (ke.modShift)
        self.assertTrue (ke.modAlt)
        self.assertTrue (ke.modCtrl)

def suite ():
    keyboardEventHandlerSuite = unittest.makeSuite (TestKeyboardEventHandler, 'test')
    return unittest.TestSuite ([keyboardEventHandlerSuite])

if __name__ == '__main__':
    unittest.main (defaultTest = 'suite')

