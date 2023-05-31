# Python 2/3 compatibility.
from __future__ import print_function
import sys
import os
sys.path.append('../')
sys.path.append('../../')
import pprint
import time

from Xlib import X, display, Xutil
from Xlib.ext import randr, xinerama

class Illumination(object):
    def __init__(self, display, screen_id, fg_color=0xff0000, lwd=100, lht=200):
        self.d = display
        self.screen_id = screen_id
        self.fg_color = fg_color 
        
        #Grab projector screen information
        self.sc_X = self.d.xinerama_query_screens()._data['screens'][0]['x']
        self.sc_Y = self.d.xinerama_query_screens()._data['screens'][0]['y']
        self.sc_W = self.d.xinerama_query_screens()._data['screens'][0]['width'] 
        self.sc_H = self.d.xinerama_query_screens()._data['screens'][0]['height'] 
        self.sc_offset = self.d.xinerama_query_screens()._data['screens'][self.screen_id]['x']
        
        self.lwd = lwd
        self.lht = lht
        self.redraw_sw = False
        self.lcent = 0
        self.loffset = 0
        self.top_left_X = round(self.sc_W/2) - round(self.lwd/2) + self.loffset + self.sc_X 
        self.top_left_Y = round(self.sc_H/2) - round(self.lht/2) + self.lcent + self.sc_Y
        self.d90 = False
        self.stopFlag = False
        self.enable = False
        # Grab the current screen and set window
        
#         self.screen = self.d.screen()
        
#         self.window = self.screen.root.create_window(
#             self.sc_X, self.sc_Y, self.sc_W, self.sc_H, 0,
#             self.screen.root_depth,
#             X.InputOutput,
#             X.CopyFromParent,
#             background_pixel = 0x33000, #self.screen.black_pixel,
#             event_mask = (X.ExposureMask |
#                           X.StructureNotifyMask),
#             colormap = X.CopyFromParent,
#             )
#         self.gc = self.window.create_gc(
#             foreground = self.fg_color,
#             background = 0x33000, #self.screen.black_pixel,
#             )
#         #self.window.fill_rectangle(self.gc, self.top_left_X, self.top_left_Y, self.lwd, self.lht)
        
#         self.print_local_vars()
#         # Map the window, making it visible
#         self.window.map()
        
#         # Set some WM info
#         # We might not need all these (Maybe?)
#         self.WM_DELETE_WINDOW = self.d.intern_atom('WM_DELETE_WINDOW')
#         self.WM_PROTOCOLS = self.d.intern_atom('WM_PROTOCOLS')
#         self.window.set_wm_name('')
#         self.window.set_wm_icon_name('')
#         self.window.set_wm_class('xrandr', 'XlibExample')
# #         self.window.set_wm_class('xinerama', 'XlibExample')
#         self.window.set_wm_protocols([self.WM_DELETE_WINDOW])
#         self.window.set_wm_hints(flags = Xutil.StateHint,
#                                  initial_state = Xutil.NormalState)
#         self.window.set_wm_normal_hints(flags = (Xutil.PPosition | Xutil.PSize
#                                                  | Xutil.PMinSize),
#                                         min_width = 20,
#                                         min_height = 0,max_height = 0)
        self.screen = self.d.screen()

        self.window = self.screen.root.create_window(
            self.sc_X + self.sc_offset, self.sc_Y, self.sc_W, self.sc_H, 2,
            self.screen.root_depth,
            X.InputOutput,
            X.CopyFromParent,

            # special attribute values
            background_pixel = self.screen.black_pixel,
            event_mask = (X.ExposureMask |
                          X.StructureNotifyMask |
                          X.ButtonPressMask |
                          X.ButtonReleaseMask |
                          X.Button1MotionMask),
            colormap = X.CopyFromParent,
            )

        self.gc = self.window.create_gc(
            foreground = self.screen.white_pixel,
            background = self.screen.black_pixel,
            )

        # Set some WM info

        self.WM_DELETE_WINDOW = self.d.intern_atom('WM_DELETE_WINDOW')
        self.WM_PROTOCOLS = self.d.intern_atom('WM_PROTOCOLS')

        self.window.set_wm_name('Xlib example: xinerama.py')
        self.window.set_wm_icon_name('xinerama.py')
        self.window.set_wm_class('xinerama', 'XlibExample')

        self.window.set_wm_protocols([self.WM_DELETE_WINDOW])
        self.window.set_wm_hints(flags = Xutil.StateHint,
                                 initial_state = Xutil.NormalState)

        self.window.set_wm_normal_hints(flags = (Xutil.PPosition | Xutil.PSize
                                                 | Xutil.PMinSize),
                                        min_width = 20,
                                        min_height = 20)

        # Map the window, making it visible
        self.window.map()
        self.d.flush()
        
    def print_local_vars(self):
        print('sc_X: ', self.sc_X)
        print('sc_Y: ', self.sc_Y)
        print('sc_W: ', self.sc_W)
        print('sc_H: ', self.sc_H)
        print('top_left_X: ', self.top_left_X) 
        print('top_left_Y: ', self.top_left_Y)
        print('lwd: ', self.lwd)
        print('lht: ', self.lht)
        print('redraw_sw: ', self.redraw_sw)
        print('fg_color: ', self.fg_color)
        print('lcent: ', self.lcent)
        print('loffset: ', self.loffset)
        return
                

    # Main loop, handling events
    def update(self):
        self.redraw_sw = True
        
        if self.enable == True:
            self.gc.change(foreground = 0x00000)
            self.window.fill_rectangle(self.gc, self.sc_X, self.sc_Y, self.sc_W, self.sc_H)

            self.gc.change(foreground = self.fg_color)
            if (self.d90):
                self.top_left_X = round(self.sc_W/2) - round(self.lht/2) + self.lcent + self.sc_Y
                self.top_left_Y = round(self.sc_H/2) - round(self.lwd/2) + self.loffset + self.sc_X
                self.window.fill_rectangle(self.gc, self.top_left_X, self.top_left_Y, self.lht, self.lwd)

            else:
                self.top_left_X = round(self.sc_W/2) - round(self.lwd/2) + self.loffset + self.sc_X
                self.top_left_Y = round(self.sc_H/2) - round(self.lht/2) + self.lcent + self.sc_Y
                self.window.fill_rectangle(self.gc, self.top_left_X, self.top_left_Y, self.lwd, self.lht)

            self.d.flush()
        
        self.redraw_sw = False
        return
        
    def dark(self):
        self.redraw_sw = True
        
        self.gc.change(foreground = 0x00000)
        self.window.fill_rectangle(self.gc, self.sc_X, self.sc_Y, self.sc_W, self.sc_H)
        self.d.flush()
        
        self.redraw_sw = False
        return
        
    def set_illumination_offset(self, offset):
        if self.enable == True:
            self.loffset = offset
            self.update() 
        return

