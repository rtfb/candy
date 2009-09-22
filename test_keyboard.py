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
import pdb

import wx

import keyboard


class TestKeyboardEventHandler(unittest.TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def testNewKeyboardEventIsEmpty(self):
        ke = keyboard.KeyboardEvent()
        self.assertEquals(ke.char, '')
        self.assertEquals(ke.key_code, 0)
        self.assertEquals(ke.mod_ctrl, False)
        self.assertEquals(ke.mod_alt, False)
        self.assertEquals(ke.mod_shift, False)

    def testOneLetterLowercase(self):
        ke = keyboard.KeyboardEvent()
        # ke.char is simply the letter, ke.key_code is the uppercased letter
        for char in range(ord('a'), ord('z')):
            ke.parse(chr(char))
            self.assertEquals(ke.char, chr(char))
            self.assertEquals(ke.key_code, ord(chr(char).upper()))
            self.assertFalse(ke.mod_shift)

    def testOneLetterUppercase(self):
        ke = keyboard.KeyboardEvent()
        for char in range(ord('A'), ord('Z')):
            ke.parse(chr(char))
            self.assertEquals(ke.char, chr(char))
            self.assertEquals(ke.key_code, char)
            self.assertTrue(ke.mod_shift)

    def testDigits(self):
        ke = keyboard.KeyboardEvent()
        # ke.char is simply the digit, ke.key_code is the ascii number for that
        # digit
        for char in range(ord('0'), ord('9')):
            ke.parse(chr(char))
            self.assertEquals(ke.char, chr(char))
            self.assertEquals(ke.key_code, char)
            self.assertFalse(ke.mod_shift)

    def testShiftDigits(self):
        ke = keyboard.KeyboardEvent()
        # ke.char is the '!@#', etc., ke.key_code is the ascii number for that
        # symbol
        for char in '!@#$%^&*()':
            ke.parse(char)
            self.assertEquals(ke.char, char)
            self.assertEquals(ke.key_code, ord(char))
            self.assertTrue(ke.mod_shift)

    def testOtherUnshifted(self):
        ke = keyboard.KeyboardEvent()
        # ke.char is the '`-=', etc., ke.key_code is the ascii number for that
        # symbol
        for char in '`-=[];\',./\\':
            ke.parse(char)
            self.assertEquals(ke.char, char)
            self.assertEquals(ke.key_code, ord(char))
            self.assertFalse(ke.mod_shift)

    def testOtherShifted(self):
        ke = keyboard.KeyboardEvent()
        # ke.char is the '~_+', etc., ke.key_code is the ascii number for that
        # symbol
        for char in '~_+{}|:"<>?':
            ke.parse(char)
            self.assertEquals(ke.char, char)
            self.assertEquals(ke.key_code, ord(char))
            self.assertTrue(ke.mod_shift)

    def testSomeSpecials(self):
        ke = keyboard.KeyboardEvent()

        for key, code in [('Esc', wx.WXK_ESCAPE), ('esc', wx.WXK_ESCAPE),
                          ('Space', wx.WXK_SPACE), ('space', wx.WXK_SPACE),
                          ('Enter', wx.WXK_RETURN), ('enter', wx.WXK_RETURN),
                          ('Tab', wx.WXK_TAB), ('TAB', wx.WXK_TAB),
                          ('tab', wx.WXK_TAB),
                          ('Return', wx.WXK_RETURN), ('return', wx.WXK_RETURN)]:
            ke.parse(key)
            self.assertEquals(ke.char, '')
            self.assertEquals(ke.key_code, code)

    def testEmpty(self):
        ke = keyboard.KeyboardEvent()

        try:
            ke.parse('')
            self.fail()
        except keyboard.EventParseError:
            pass

    def testControlA(self):
        ke = keyboard.KeyboardEvent()
        ke.parse('C-a')
        self.assertEquals(ke.char, 'a')
        self.assertEquals(ke.key_code, ord('A'))
        self.assertTrue(ke.mod_ctrl)
        self.assertFalse(ke.mod_shift)
        self.assertFalse(ke.mod_alt)

    def testShiftB(self):
        ke = keyboard.KeyboardEvent()
        ke.parse('S-b')
        self.assertEquals(ke.char, 'b')
        self.assertEquals(ke.key_code, ord('B'))
        self.assertTrue(ke.mod_shift)
        self.assertFalse(ke.mod_alt)
        self.assertFalse(ke.mod_ctrl)

    def testAltZ(self):
        def check(ke):
            self.assertEquals(ke.char, 'z')
            self.assertEquals(ke.key_code, ord('Z'))
            self.assertTrue(ke.mod_alt)
            self.assertFalse(ke.mod_shift)
            self.assertFalse(ke.mod_ctrl)

        ke = keyboard.KeyboardEvent()
        ke.parse('A-z')
        check(ke)
        ke.reset()
        ke.parse('M-z')
        check(ke)

    def testFunctionKeys(self):
        funcs = [wx.WXK_F1, wx.WXK_F2, wx.WXK_F3, wx.WXK_F4, wx.WXK_F5,
                 wx.WXK_F6, wx.WXK_F7, wx.WXK_F8, wx.WXK_F9, wx.WXK_F10,
                 wx.WXK_F11, wx.WXK_F12, wx.WXK_F13, wx.WXK_F14, wx.WXK_F15,
                 wx.WXK_F16, wx.WXK_F17, wx.WXK_F18, wx.WXK_F19, wx.WXK_F20,
                 wx.WXK_F21, wx.WXK_F22, wx.WXK_F23, wx.WXK_F24]

        for i in range(1, 25):
            ke = keyboard.KeyboardEvent()
            ke.parse('f%d' % (i))
            self.assertEquals(ke.key_code, funcs[i - 1])

    def testControlAltM(self):
        ke = keyboard.KeyboardEvent()
        ke.parse('C-A-m')
        self.assertEquals(ke.char, 'm')
        self.assertEquals(ke.key_code, ord('M'))
        self.assertFalse(ke.mod_shift)
        self.assertTrue(ke.mod_alt)
        self.assertTrue(ke.mod_ctrl)

    def testGetFuncReturnsNone(self):
        kc = keyboard.KeyboardConfig()
        # XXX: there should not be such a code and mod combo:
        f = kc.get_func(0, 0)
        self.assertEquals(f, None)


class TestKeyValueSplit(unittest.TestCase):
    def test_simple_cplit(self):
        test_val = 'on_next_match: n'
        k, v = keyboard.split_left_colon(test_val)
        k2, v2 = test_val.strip().split(':')
        self.assertEquals(k, k2)
        self.assertEquals(v, v2)

    def test_split_with_extra_spaces(self):
        test_val = '  on_next_match: n  '
        k, v = keyboard.split_left_colon(test_val)
        k2, v2 = test_val.strip().split(':')
        self.assertEquals(k, k2)
        self.assertEquals(v, v2)

    def test_split_preserves_commas(self):
        test_val = 'on_next_match: n, m, l'
        k, v = keyboard.split_left_colon(test_val)
        self.assertEquals(2, test_val.count(','))

    def test_colon_binding(self):
        test_val = 'on_next_match: :'
        k, v = keyboard.split_left_colon(test_val)
        self.assertEquals(' :', v)


def suite():
    kbd_handler_suite = unittest.makeSuite(TestKeyboardEventHandler, 'test')
    split_suite = unittest.makeSuite(TestKeyValueSplit)
    return unittest.TestSuite([kbd_handler_suite, split_suite])


if __name__ == '__main__':
    unittest.main(defaultTest='suite')

