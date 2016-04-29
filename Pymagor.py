##  Copyright (c) 2011-, Iori Namekawa.
##  All rights reserved.
##
##  Redistribution and use in source and binary forms, with or without
##  modification, are permitted provided that the following conditions are met:
##
##      * Redistributions of source code must retain the above copyright
##        notice, this list of conditions and the following disclaimer.
##      * Redistributions in binary form must reproduce the above copyright
##        notice, this list of conditions and the following disclaimer in the
##        documentation and/or other materials provided with the distribution.
##      * Neither the name of Pymagor nor the names of its contributors may be
##        used to endorse or promote products derived from this software
##        without specific prior written permission.
##
##  THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
##  ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
##  WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
##  DISCLAIMED. IN NO EVENT SHALL PYMAGOR OR CONTRIBUTORS BE LIABLE FOR ANY
##  DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
##  (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
##  LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
##  ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
##  (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
##  SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# major changes
# major bug: within trial alignment is not reflected in dF/F trace for indivisual file
# major bug: trial alignment offset not reflected to average response
# refactor the MESS around image file loading (pack function and its many friends)
# abort btn was not working. fixed.

# minor changes
# remove dependency on win32process, yapsy will stay
# check if the platform is windows when creating avi with ffmpeg.exe.
# update avi creation code for PIL/pillow API changes
# in PDF export a new page with a large anatomy image with ROIs overlaid
# put during stim period and Fnoise into offset file.
# use ini file to store colormap in use

# TODO: MATLAB generated color tiff support is broken but maybe no one needs this. Let's drop it

# STANDARD libraries
from __future__ import with_statement, division
from pprint import pprint
import cPickle as pickle
import ConfigParser, csv, getpass, itertools, os, platform
import re, subprocess, sys, time, webbrowser
myOS = platform.system()

# 3rd party libraries
from PIL import Image # actually pillow
from PIL import ImageDraw
from PIL import TiffImagePlugin  # for py2exe

import numpy as np
import scipy

import scipy.ndimage as ndimage
import scipy.io as sio
from scipy.sparse.csgraph import _validation  ## for py2exe
if int(scipy.__version__.split('.')[1])>11:
    from scipy.spatial import ConvexHull

import matplotlib
if myOS in ('Windows', 'Linux'): # until sip can be installed on OS X Darwin.
    matplotlib.use('Qt4Agg')

import matplotlib.cm as cm
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import Polygon
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties
matplotlib.rcParams['figure.facecolor'] = 'w'
if myOS in ('Windows', 'Linux'): # until I can update matplotlib on OS X Darwin.
    matplotlib.rcParams['figure.max_open_warning'] = 200

import xlrd  # reading excel
import xlwt  # writing excel

if not hasattr(sys, 'frozen'):
    import wxversion
    wxversion.select('2.8-msw-unicode')
import wx

import wx.aui as AUI
import wx.lib.agw.floatspin as FS
import wx.lib.delayedresult as delayedresult
import wx.lib.mixins.listctrl as listmix
import wx.py

from yapsy.PluginManager import PluginManager


# Pymagor2 user libraries
import corr, ROImanager
from ROImanager import z_prefix
from ROI import ROIv3 as ROI
from opentif import opentif, get_tags
from create_pymagorsheet_v2 import create_csv

# Global variables
release_version = '2.7.3'
with open('resources/version.info', 'r') as f:
    __version__ = f.readline().splitlines()[0]

# used in windows only (taken from win32process.CREATE_NO_WINDOW)
CREATE_NO_WINDOW = 134217728 

# hardcoding the difference between xp and win7
# because wx2.8 does not support vista and above yet
# until I managed to update to wx3.0
homedir = os.path.join(os.path.expanduser('~'), 'pymagor')
if myOS == 'Windows':
    magnifier = wx.CURSOR_MAGNIFIER
    _keys = os.environ.keys()
    if 'HOMESHARE' in _keys:
        homedir = os.path.join(os.environ['HOMESHARE'], 'pymagor') # shared network drive
        # using HOMESHARE rather than USERPROFILE here, because
        # Group policy Our IT did may redirect USERPROFILE to HOMESHARE when exists
    elif 'USERPROFILE' in _keys: # XP machine legacy stuff? I dont recall...
        homedir = os.path.join(os.environ['USERPROFILE'], 'Documents\\pymagor')
    if platform.win32_ver()[0] == 'XP':  # resizable boarder is thin on XP.
        ymargin = (24, 32)
        xmargin = 12
    else:  # resizable boarder is thicker on windows 7.
        ymargin = (25, 32+8)  # 60
        xmargin = 12+8
else:
    ymargin = (24, 32)
    xmargin = 12
    magnifier = wx.CURSOR_SIZEWE

if not os.path.exists(homedir):
    os.mkdir(homedir)

MPLcache = matplotlib.get_configdir()
bindir = r'https://github.com/i-namekawa/Pymagor/releases'
documentationURL = 'https://github.com/i-namekawa/Pymagor/wiki'

## if Pymagor.ini exists, use some parameters defined there.
cfg = ConfigParser.ConfigParser()
cfg.optionxform = str
results = cfg.read(os.path.join(homedir,'Pymagor.ini'))
if results: ## if Pymagor.ini exists, use it for user params
    for section in cfg.sections():
        for key, value in cfg.items(section):
            exec key + '=' + value
    ini_log = 'Pymagor.ini file found.'
    # ini file from old ver will not have customROIcategory
    if 'customROIcategory' not in dir():
        customROIcategory = []
    if 'ColorMapName' not in dir():
        ColorMapName = 'clut2b (custom)'
else:
    ## default parameters that are normally defined in Pymagor.ini
    ini_log = 'No Pymagor.ini found.'

    durpre, durres = [0,25], [40,70]
    cmax = 70
    cmin = -cmax/4.0
    margin = 9
    SpatMed, SpatMed2, fastLoad = True, True, False
    
    ColorMapName = 'clut2b (custom)'

    min_fontsize = 7
    pickle_stacked = False
    verbose = False
    fit2Toolbar_width = True
    if myOS == 'Linux':
        lastdir = os.path.expanduser('~')
    else:
        lastdir = 'C:\\'
    npz = False
    mat_compress = True
    selectiveWeightedAvgFilter = True

    corr2use = True
    Autoalign = False
    usecsv = False

    EXPORT_group_odor = False
    EXPORT_needplotting = True
    EXPORT_eachfile = True
    EXPORT_avgtraces = True
    EXPOSE_transpose_collage = True

    customROIcategory = []

anatomy_method = False
Overlay = False
cutoff = -cmin
cutoffON = False
SDthrs = False

working_singles, need_abort_singles = False, False
working, need_abort = False, False

ch = 0           # default channel to load from tiff
ref_ch = 0       # default channel to use for alignment
csvdict = None   # Pymagor sheet
CntxPlugin = {}  # plugin objects dictionary for context menu

img_keys = ['unshifted frames', 'dFoFfil', 'F', 'dFoFavg', 'anatomy',
            'avg_F', 'avg_odormaps', 'avg projection', 'max projection']

kernel = \
   [[0.0075, 0.0211, 0.0296, 0.0211, 0.0075],
    [0.0211, 0.0588, 0.0828, 0.0588, 0.0211],
    [0.0296, 0.0828, 0.1166, 0.0828, 0.0296],
    [0.0211, 0.0588, 0.0828, 0.0588, 0.0211],
    [0.0075, 0.0211, 0.0296, 0.0211, 0.0075]]

# our custom jet like colormap "clut2b" (color look up table 2b, 8-bit) 
# inherited from "Imagor3" written by Rainer Friedrich.
# near the max value it replaces darker red in jet with brighter, whitish red.
# 
# this buffer format works only with Python2
clut2b_buffer = "\x00\x01\r\x00\x02\x14\x00\x03\x1b\x00\x03!\x00\x03'\x00\x04-\x00\x053\x00\x069\x00\t?\x00\tE\x00\nK\x00\x0cQ\x00\x0cW\x00\r]\x00\rc\x00\x0ei\x00\x0fo\x00\x0fu\x00\x12{\x00\x15\x81\x00\x18\x87\x00\x1a\x8d\x00\x1d\x93\x00 \x99\x00#\x9f\x00&\xa5\x00)\xab\x00,\xb1\x00/\xb7\x002\xbd\x005\xc2\x007\xc8\x009\xce\x00;\xd4\x00=\xda\x00?\xe0\x00@\xe5\x00A\xea\x00B\xef\x00C\xf5\x00D\xfb\x00E\xff\x00F\xff\x00G\xff\x00H\xff\x00I\xff\x00J\xff\x00K\xff\x00L\xff\x00M\xff\x00N\xff\x00O\xff\x00P\xff\x00T\xff\x00W\xff\x00[\xff\x00^\xff\x00b\xff\x00e\xff\x00i\xff\x00l\xff\x00p\xff\x00s\xff\x00w\xff\x00z\xff\x00~\xff\x00\x81\xff\x00\x85\xff\x00\x88\xff\x00\x8c\xff\x00\x8f\xff\x00\x93\xf7\x00\x96\xf0\x00\x9a\xe8\x00\x9d\xe0\x00\xa1\xd8\x00\xa4\xd1\x00\xa8\xc9\x00\xab\xc1\x00\xaf\xb9\x00\xb2\xb2\x00\xb6\xaa\x00\xb9\xa2\x00\xbd\x9b\x00\xc0\x93\x00\xc4\x8b\x00\xc7\x83\x00\xcb|\x00\xcet\x00\xd2l\x00\xd5d\x00\xd9]\x00\xdcU\x00\xe0M\x00\xe3F\x00\xe7>\x07\xea6\r\xee.\x14\xf1'\x1a\xf5\x1f!\xf8\x17'\xfc\x0f.\xff\x084\xff\x00;\xff\x00A\xff\x00H\xff\x00N\xff\x00U\xff\x00\\\xff\x00b\xff\x00i\xff\x00o\xff\x00v\xff\x00|\xff\x00\x83\xff\x00\x89\xff\x00\x90\xff\x00\x96\xff\x00\x9d\xff\x00\xa3\xff\x00\xaa\xff\x00\xb1\xff\x00\xb7\xff\x00\xbe\xff\x00\xc4\xff\x00\xcb\xff\x00\xd1\xff\x00\xd8\xff\x00\xde\xff\x00\xe5\xff\x00\xeb\xff\x00\xf2\xff\x00\xf8\xff\x00\xfe\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xfe\x00\xff\xfa\x00\xff\xf8\x00\xff\xf4\x00\xff\xf0\x00\xff\xed\x00\xff\xe9\x00\xff\xe6\x00\xff\xe2\x00\xff\xde\x00\xff\xdb\x00\xff\xd7\x00\xff\xd3\x00\xff\xd0\x00\xff\xcc\x00\xff\xc8\x00\xff\xc5\x00\xff\xc1\x00\xff\xbd\x00\xff\xba\x00\xff\xb6\x00\xff\xb2\x00\xff\xaf\x00\xff\xab\x00\xff\xa8\x00\xff\xa4\x00\xff\xa0\x00\xff\x9d\x00\xff\x99\x00\xff\x95\x00\xff\x92\x00\xff\x8e\x00\xff\x8a\x00\xff\x87\x00\xff\x83\x00\xff\x80\x00\xff|\x00\xffx\x00\xffu\x00\xffq\x00\xffm\x00\xffj\x00\xfff\x00\xffb\x00\xff_\x00\xff[\x00\xffW\x00\xffT\x00\xffP\x00\xffL\x00\xffI\x00\xffE\x00\xffB\x00\xfd>\x00\xff:\x00\xff7\x00\xff3\x00\xff/\x00\xff,\x00\xff(\x00\xff$\x00\xff!\x00\xff\x1d\x00\xff\x1a\x00\xff\x16\x00\xff\x12\x00\xff\x0f\x00\xff\x0b\x00\xff\x07\x00\xff\x04\x04\xff\x00\x07\xff\x00\x0b\xff\x00\x0f\xff\x00\x13\xff\x00\x16\xff\x00\x1a\xff\x00\x1e\xff\x00!\xff\x00%\xff\x00)\xff\x00,\xff\x000\xff\x004\xff\x008\xff\x00;\xff\x00?\xff\x00C\xff\x00F\xff\x00J\xff\x00N\xff\x00Q\xff\x00U\xff\x00Y\xff\x00]\xff\x00`\xff\x00d\xff\x00\xff\xff\xff\xff"
clut2b = np.fromstring(clut2b_buffer, dtype=np.uint8).reshape((256,3))
cmap = clut2b # default is copied to global var cmap

# parula is MATLAB's new default colormap. data converted from https://github.com/BIDS/colormap/blob/master/parula.py
parula_buffer = '5*\x865+\x8a5-\x8d5.\x9050\x9361\x9663\x9964\x9c66\x9f57\xa259\xa55;\xa95<\xac4>\xaf3?\xb22A\xb52C\xb90D\xbc/F\xbf-H\xc2+J\xc5)K\xc9&N\xcc#P\xcf R\xd2\x1cT\xd5\x18V\xd7\x14X\xda\x10[\xdc\r\\\xdd\n^\xde\x07`\xdf\x04b\xe0\x02c\xe0\x02d\xe0\x02f\xe1\x01g\xe1\x01h\xe0\x02i\xe0\x03k\xe0\x03l\xe0\x04m\xdf\x05n\xdf\x06o\xde\x07p\xde\x08q\xde\tr\xdd\x0bs\xdd\x0ct\xdc\ru\xdc\rv\xdb\x0ew\xdb\x0fx\xda\x10y\xd9\x10z\xd9\x11{\xd8\x12{\xd8\x12|\xd7\x12}\xd7\x13~\xd6\x13\x7f\xd6\x13\x80\xd5\x13\x81\xd5\x14\x82\xd4\x14\x83\xd4\x14\x84\xd3\x13\x85\xd3\x13\x87\xd3\x13\x88\xd2\x12\x89\xd2\x12\x8a\xd2\x11\x8b\xd2\x10\x8c\xd2\x10\x8e\xd2\x0f\x8f\xd2\x0e\x90\xd1\r\x92\xd1\x0c\x93\xd1\x0b\x94\xd1\n\x95\xd1\t\x96\xd1\x08\x98\xd1\x08\x99\xd0\x07\x9a\xd0\x07\x9b\xcf\x06\x9c\xcf\x06\x9d\xce\x06\x9e\xce\x06\x9f\xcd\x06\xa0\xcc\x06\xa1\xcc\x05\xa1\xcb\x05\xa2\xca\x05\xa3\xc9\x05\xa4\xc8\x05\xa5\xc8\x05\xa5\xc7\x05\xa6\xc6\x06\xa7\xc5\x06\xa7\xc4\x06\xa8\xc3\x06\xa9\xc2\x07\xa9\xc1\x08\xaa\xc0\x08\xab\xbe\t\xab\xbd\n\xac\xbc\x0c\xac\xbb\r\xad\xba\x0e\xae\xb9\x10\xae\xb8\x11\xaf\xb6\x13\xaf\xb5\x14\xb0\xb4\x16\xb1\xb3\x18\xb1\xb1\x1a\xb2\xb0\x1c\xb2\xaf\x1e\xb3\xae \xb3\xac"\xb4\xab$\xb4\xaa&\xb5\xa8(\xb5\xa7*\xb6\xa5,\xb6\xa4/\xb7\xa31\xb7\xa13\xb8\xa06\xb8\x9e8\xb9\x9d;\xb9\x9b=\xb9\x9a@\xba\x98C\xba\x97E\xbb\x95H\xbb\x94K\xbb\x92N\xbc\x91Q\xbc\x8fS\xbc\x8eV\xbd\x8cY\xbd\x8b\\\xbd\x89_\xbd\x88b\xbe\x86e\xbe\x85h\xbe\x84k\xbe\x82n\xbe\x81q\xbe\x80t\xbe~w\xbe}y\xbe||\xbf{\x7f\xbfz\x82\xbfx\x84\xbfw\x87\xbfv\x8a\xbeu\x8c\xbet\x8f\xbes\x91\xber\x94\xbeq\x96\xbep\x99\xbeo\x9b\xben\x9d\xbem\xa0\xbel\xa2\xbek\xa5\xbej\xa7\xbdi\xa9\xbdh\xab\xbdh\xae\xbdg\xb0\xbdf\xb2\xbde\xb4\xbdd\xb6\xbdc\xb9\xbcb\xbb\xbca\xbd\xbca\xbf\xbc`\xc1\xbc_\xc3\xbb^\xc5\xbb]\xc7\xbb\\\xca\xbb[\xcc\xbb[\xce\xbbZ\xd0\xbaY\xd2\xbaX\xd4\xbaW\xd6\xbaV\xd8\xbaU\xda\xbaU\xdc\xb9T\xde\xb9S\xe0\xb9R\xe2\xb9Q\xe4\xb9P\xe6\xb9O\xe8\xb9N\xea\xb9M\xec\xb9L\xee\xb9K\xf0\xb9J\xf2\xb9H\xf3\xb9G\xf5\xbaF\xf7\xbaD\xf8\xbaC\xfa\xbbA\xfb\xbc?\xfc\xbd>\xfd\xbe<\xfd\xbf;\xfe\xc19\xfe\xc28\xfe\xc36\xfe\xc55\xfe\xc64\xfd\xc72\xfd\xc81\xfd\xca0\xfc\xcb/\xfc\xcc.\xfb\xce-\xfb\xcf,\xfa\xd0+\xfa\xd1*\xf9\xd3)\xf8\xd4(\xf8\xd5\'\xf7\xd7&\xf7\xd8%\xf6\xda$\xf6\xdb#\xf5\xdc"\xf5\xde!\xf5\xdf \xf4\xe1\x1e\xf4\xe2\x1d\xf4\xe4\x1c\xf4\xe6\x1b\xf4\xe7\x1a\xf4\xe9\x19\xf4\xeb\x18\xf5\xed\x16\xf5\xee\x15\xf5\xf0\x14\xf6\xf2\x13\xf7\xf4\x11\xf7\xf6\x10\xf8\xf8\x0f\xf8\xfa\r'

if hasattr(cm, 'viridis'): # matplotlib 1.5 and above
    colormapOptions = {}
    colormapOptions['clut2b (custom)'] = clut2b
    colormapOptions['parula (MATLAB)'] = np.fromstring(parula_buffer, dtype=np.uint8).reshape((256,3))
    colormapOptions['jet (MATLAB)'] = (cm.jet(range(256))[:,:3]* 255).astype(np.uint8)
    colormapOptions['magma (matplotlib)'] = (cm.magma(range(256))[:,:3]* 255).astype(np.uint8)
    colormapOptions['inferno (matplotlib)'] = (cm.inferno(range(256))[:,:3]* 255).astype(np.uint8)
    colormapOptions['cubehelix (matplotlib)'] = (cm.cubehelix(range(256))[:,:3]* 255).astype(np.uint8)
    colormapOptions['plasma (matplotlib)'] = (cm.plasma(range(256))[:,:3]* 255).astype(np.uint8)
    colormapOptions['viridis (matplotlib)'] = (cm.viridis(range(256))[:,:3]* 255).astype(np.uint8)

# load odor and plane persistency file
PlaneList = []
ConditionList = []
try:
    with open(os.path.join(homedir,'Stim_FieldOfView_Names.csv')) as f:
        dialect = csv.Sniffer().sniff(f.read(2024))
        f.seek(0)
        csvReader = csv.reader(f, dialect=dialect)
        for plane, odor in csvReader:
            if len(plane):
                PlaneList.append(plane)
            if len(odor):
                ConditionList.append(odor)
except IOError:
    PlaneList = ['z-10','z0','z+10', 'z-stack']
    ConditionList = ['Control', 'StimulusA', 'StimulusB', 'Beads']


class FileDrop(wx.FileDropTarget):
    def __init__(self, window, open_flag, dlg):
        wx.FileDropTarget.__init__(self)
        self.parent = window
        self.open_flag = open_flag
        self.dlg = dlg

    def OnDropFiles(self, x, y, filenames):
        filenames.sort()
        for f in filenames:
            self.parent.fp = f
            # file history
            self.parent.filehistory.AddFileToHistory(f)
            self.parent.filehistory.Save(self.parent.config)
            self.parent.config.Flush()
            # open
            if len(filenames) > 1:
                opencb = False
            else:
                opencb = True
            self.parent.open_filetype(
                self.open_flag, dlg = self.dlg, opencb=opencb)


class matDrop(wx.FileDropTarget):
    def __init__(self, parent):
        wx.FileDropTarget.__init__(self)
        self.parent = parent

    def OnDropFiles(self, x, y, filenames):
        filenames.sort()
        for fp in filenames:
            self.parent.loadROI(fp)


class RedirectText(object):  # from a blog: www.blog.pythonlibrary.org
    def __init__(self, aWxTextCtrl):
        self.out=aWxTextCtrl
    def write(self,string):
        self.out.SetInsertionPointEnd()  # go to the bottom
        self.out.WriteText(string)


class BaseListCtrl(wx.ListCtrl,
                        listmix.ListCtrlAutoWidthMixin):
    def __init__(self, parent, columns, name='ListCtrl',
                style=wx.LC_EDIT_LABELS|wx.LC_REPORT):
        wx.ListCtrl.__init__(self, parent, name=name, style=style)
        listmix.ListCtrlAutoWidthMixin.__init__(self)


class canvaspanel(wx.Panel):

    def __init__(self, parent, id, size):
        style = wx.DEFAULT_FRAME_STYLE | wx.WANTS_CHARS  # catch arrow key events
        wx.Panel.__init__(self, parent, id, size=size, style=style)
        self.Bind(wx.EVT_PAINT, self.OnPaint)
        self.parent = parent
        self.SetDoubleBuffered(True)

    def OnPaint(self, event):
        parent = self.parent

        dc = wx.BufferedPaintDC(self)
        dc.Clear()
        dc.DrawBitmap(parent.bmp,0,0)  # now blit frame bmp

        def normxy2dc(x,y):
            ''' a child function to normalize
                to the zoomed area for dc canvas. '''
            fr_w, fr_h = parent.display.GetSizeTuple()
            x1, y1, x2, y2 = parent.zoomrect
            if parent.zoomingmode:  # zoomrect update not yet happend
                offsetx, offsety = parent.boarder_check()
                x = (x-x1-offsetx) / float(x2 - x1) * fr_w
                y = (y-y1-offsety) / float(y2 - y1) * fr_h
            else:
                x = (x-x1) / float(x2 - x1) * fr_w
                y = (y-y1) / float(y2 - y1) * fr_h
            return x,y

        dc.BeginDrawing()
        dc.SetBrush(wx.Brush(wx.RED, wx.TRANSPARENT))

        x1, y1, x2, y2 = parent.zoomrect
        if (x2-x1) * (y2-y1) < parent.h*parent.w/4:  # if zoomed more than 4x
            dc.SetPen(wx.Pen(wx.NamedColour('green'), 1))
            x,y = normxy2dc(parent.curx, parent.cury)
            dc.DrawPoint(x,y)

        ## zooming mode
        if (parent.zoomingmode and     # drawing the square allowed?
            parent.st_x is not None):  # started drawing but not finished?
            dc.SetPen(wx.Pen(wx.NamedColour('yellow'), 1))
            # absolute (x,y)
            x1, y1 = parent.st_x, parent.st_y
            x2, y2 = parent.assure_box(parent.curx, parent.cury)

            # normalize to the zoomed area for dc canvas
            x1, y1 = normxy2dc(x1,y1)
            x2, y2 = normxy2dc(x2,y2)
            dc.DrawRectangleRect( wx.Rect(x1,y1,x2-x1,y2-y1) )
        ## ROI drawing mode
        elif (parent.drawing and       # cursor is pencil, draw allowed
              parent.roibuf != None):  # started drawing but not finished
            dc.SetPen(wx.Pen(wx.NamedColour('cyan'), 1))
            dc.DrawLines([normxy2dc(x,y) for x,y in parent.roibuf])

        ## Lastly draw existing ROIs
        if parent.ROImode and parent.ROI.data != []:
            if parent.ROInumbers: # set font size for ROI numbers only once here
                font = parent.GetFont()
                font.SetPointSize(10)
                dc.SetFont(font)

            # NULL color will cause a gtk error on Ubuntu
            # (http://python-forum.com/pythonforum/viewtopic.php?f=4&t=6939)

            z = parent.changetitle(wantz=True)

            for n, roi in enumerate(parent.ROI.data):
                if parent.ROI.z[n] == z: # matching z-plane for this ROI?

                    data = [normxy2dc(x,y) for x,y in roi]
                    if (not parent.drawing or parent.ROIoutlines):
                        #Change this line to change the color and thickness of the ROI!!!
                        dc.SetPen(wx.Pen(wx.NamedColour('red'), 3))
                        dc.DrawPolygon(data)

                    if parent.ROInumbers:
                        x,y = np.array(data).mean(axis=0) # Top left = (0,0)
                        label = str(n+1)
                        txtwidth, txtheight = dc.GetTextExtent(label)
                        dc.SetTextForeground(wx.NamedColour('black'))
                        dc.DrawText(label, x-txtwidth/2+1, y-txtheight/2+1)
                        dc.SetTextForeground(wx.NamedColour('white'))
                        dc.DrawText(label, x-txtwidth/2, y-txtheight/2)

        dc.EndDrawing()


class trial2(wx.Frame):

    def __init__(self, parent, id, imgdict, tag, lock=False):

        wx.Frame.__init__(self, parent, id, '', style=wx.DEFAULT_FRAME_STYLE)
        self.SetIcon(fishicon)
        self.DispSize = wx.GetDisplaySize()

        self.parent = parent
        self.ch = ch
        self.ref_ch = ref_ch
        # prepare img data and buffer
        if type(imgdict) == dict:
            self.img = imgdict['unshifted frames']
            if verbose:
                print 'raw image size (MB): ', self.img.nbytes / 1024 / 1024
            self.imgdict = imgdict
        else:
            self.img = imgdict[::-1,:,:]
        self.tag = tag
        self.lock = lock

        if hasattr(parent, 'bl'):
            self.Launcher = parent.bl
        else:
            self.Launcher = None
        self.param = parent.ParamsPane
        self.TVch = 0
        self.b4play = 0
        self.durpre = durpre  # in case imgdict is numpy array (not a dict)
        self.durres = durres  # imgdict has the same info

        # shift by 1 so that 0 means no channel detected.
        self.TVch_found = [(n+1) * imgdict.has_key(key) for n,key
                         in enumerate(img_keys) ]

        self.h, self.w, self.z = self.img.shape
        self.curframe = 0
        self.ScalingFactor = 1.0
        self.zoomrect = (0, 0, self.w, self.h)
        self.b4resize = (self.w, self.h)
        self.dx, self.dy = 0, 0
        self.st_x = self.st_y = None
        self.dragging = False
        self.drawing = False
        self.flipxy = []
        self.ID_fitw = wx.NewId()      # needed for frame_resize
        self.ID_scaling1 = wx.NewId()
        self.ID_plotraw = wx.NewId()

        self.baseline = False
        self.ROI = ROI()
        self.ROImode = True
        self.ROInumbers = True
        self.ROIoutlines = True
        self.need_resize = False
        self.scaling = False
        self.zoomingmode = False
        self.panmode = False
        self.playing = False
        self.record = False
        self.moving = False
        self.trashing = False
        self.curx, self.cury = 0,0
        self.jobID = 0
        self.imgdict['hist'] = {}

        self.abortEvent = delayedresult.AbortEvent()
        self.init_workers()

        # put panels
        self.toolbar1 = wx.Panel(self, -1)
        self.toolbar2 = wx.Panel(self, -1)
        self.btnbar = wx.Panel(self, -1)
        self.display = canvaspanel(self, -1, size=(self.w, self.h))

        self.SetBackgroundColour(self.toolbar1.GetBackgroundColour())

        # ToolTip
        info = '%d file(s) opened as %s, (w,h,z)=(%d,%d,%d)' % (
                    len(tag), self.img.dtype, self.w, self.h, self.z)
        self.toolbar1.SetToolTip(wx.ToolTip(info))

        # Create widgets on Toolbar 1
        txt_z = wx.StaticText(self.toolbar1, -1, 'z:')
        self.scz = wx.SpinCtrl(self.toolbar1, -1, '0', size=(60,20))
        self.scz.SetRange(0, self.z-1)

        self.ManScaling = wx.CheckBox(self.toolbar1, -1, 'ManSc')
        self.ManScaling.SetSize( self.ManScaling.GetBestSize() )
        self.ManScaling.SetValue(True)

        txt_H = wx.StaticText(self.toolbar1, -1, ' hi:')
        self.scH = wx.SpinCtrl(self.toolbar1, -1, '', size=(60,20))

        txt_L = wx.StaticText(self.toolbar1, -1, ' lo:')
        self.scL = wx.SpinCtrl(self.toolbar1, -1, '', size=(60,20))

        if self.img.dtype == np.uint8:
            self.scH.SetRange(1, 255)
            self.scL.SetRange(0, 254)
        else:
            self.scH.SetRange(1, 256**2-1)
            self.scL.SetRange(0, 255**2-2)
        inputmax = self.img.max()
        inputmin = self.img.min()
        self.scH.SetValue(inputmax)
        self.scL.SetValue(inputmin)
        print 'Image data dimention (width, height, nframes) = (%d,%d,%d), pixel value (max,min) = (%d,%d)'\
                % (self.w, self.h, self.z, inputmax, inputmin)

        # Create widgets on Toolbar 2
        self.IDscYmax = wx.NewId()
        self.IDscYmin = wx.NewId()

        self.updateimgbtn = wx.Button(self.toolbar2, -1, 'Reload', style=wx.BU_EXACTFIT)
        self.autoY = wx.CheckBox(self.toolbar2, -1, 'autoY')
        self.autoY.SetSize( self.autoY.GetBestSize() )
        self.autoY.SetValue(True)

        txt_Ymax = wx.StaticText(self.toolbar2, -1, 'max:')
        self.scYmax = wx.SpinCtrl(self.toolbar2, self.IDscYmax, '', size=(48,20))
        self.scYmax.SetRange(-9999,9999)
        Ymax = 80
        self.scYmax.SetValue(Ymax)
        self.scYmax.Enable(False)

        txt_Ymin = wx.StaticText(self.toolbar2, -1, 'min:')
        self.scYmin = wx.SpinCtrl(self.toolbar2, self.IDscYmin, '', size=(48,20))
        self.scYmin.SetRange(-9999,9999)
        self.scYmin.SetValue(-Ymax/4)
        self.scYmin.Enable(False)

        # Create widgets on btnbar
        zoomin_bmp = wx.Bitmap(r'resources/Baumgartner/zoomin_24.ico', wx.BITMAP_TYPE_ICO)
        self.zoominbtn = wx.BitmapButton(self.btnbar, -1, zoomin_bmp, style = wx.NO_BORDER)
        zoomin_disabled_bmp = wx.Bitmap(r'resources/Baumgartner/zoomin_disabled_24.ico', wx.BITMAP_TYPE_ICO)
        self.zoominbtn.SetBitmapDisabled(zoomin_disabled_bmp)
        self.zoominbtn.SetToolTip(wx.ToolTip('Zoom mode. Shortcut key: z'))

        zoomout_bmp = wx.Bitmap(r'resources/Baumgartner/zoomout_24.ico', wx.BITMAP_TYPE_ICO)
        self.zoomoutbtn = wx.BitmapButton(self.btnbar, -1, zoomout_bmp, style = wx.NO_BORDER)
        zoomout_disabled_bmp = wx.Bitmap(r'resources/Baumgartner/zoomout_disabled_24.ico', wx.BITMAP_TYPE_ICO)
        self.zoomoutbtn.SetBitmapDisabled(zoomout_disabled_bmp)
        self.zoomoutbtn.SetToolTip(wx.ToolTip('Zoom-out to the entire view (Shortcut key: e)'))

        pan_bmp = wx.Bitmap(r'resources/gentleface.com/cursor_drag_hand_icon.ico', wx.BITMAP_TYPE_ICO)
        self.panbtn = wx.BitmapButton(self.btnbar, -1, pan_bmp, style = wx.NO_BORDER)
        self.panbtn.SetToolTip(wx.ToolTip('Pannig hand mode. Drag to move around (Shortcut key: h)'))

        self.play_bmp = wx.Bitmap(r'resources/Baumgartner/button_play_24.ico', wx.BITMAP_TYPE_ICO)
        self.stop_bmp = wx.Bitmap(r'resources/Baumgartner/button_pause_24.ico', wx.BITMAP_TYPE_ICO)
        self.rec_bmp = wx.Bitmap(r'resources/Baumgartner/Button_Record_24.ico', wx.BITMAP_TYPE_ICO)
        rewind_bmp = wx.Bitmap(r'resources/Baumgartner/button_previous_24.ico', wx.BITMAP_TYPE_ICO)
        self.playbtn = wx.BitmapButton(self.btnbar, -1, self.play_bmp, style = wx.NO_BORDER)
        self.playbtn.SetToolTip(wx.ToolTip('Play/Stop video (Shortcut key: v)'))
        self.rewindbtn = wx.BitmapButton(self.btnbar, -1, rewind_bmp, style = wx.NO_BORDER)
        self.rewindbtn.SetToolTip(wx.ToolTip('Back to the beginning (Shortcut key: b)'))

        draw_bmp = wx.Bitmap(r'resources/Baumgartner/pencil_24.ico', wx.BITMAP_TYPE_ICO)
        self.drawROIbtn = wx.BitmapButton(self.btnbar, -1, draw_bmp, style = wx.NO_BORDER)
        self.drawROIbtn.SetToolTip(wx.ToolTip('ROI drawing (Shortcut key: r)'))

        roimove_bmp = wx.Bitmap(r'resources/David_Hopkins/arrow_move_24.ico', wx.BITMAP_TYPE_ICO)
        self.moveROIbtn = wx.BitmapButton(self.btnbar, -1, roimove_bmp, style = wx.NO_BORDER)
        self.moveROIbtn.SetToolTip(wx.ToolTip('shift ROI (Shortcut key: s)'))

        eraser_bmp = wx.Bitmap(r'resources/Nayak/eraser.ico', wx.BITMAP_TYPE_ICO)
        self.trashROIbtn = wx.BitmapButton(self.btnbar, -1, eraser_bmp, style = wx.NO_BORDER)
        self.trashROIbtn.SetToolTip(wx.ToolTip('Delete ROI (Shortcut key: d)'))

        self.trash_img = wx.ImageFromBitmap(eraser_bmp)
        self.trash_img.SetOptionInt(wx.IMAGE_OPTION_CUR_HOTSPOT_X, 1)
        self.trash_img.SetOptionInt(wx.IMAGE_OPTION_CUR_HOTSPOT_Y, 1)

        plot_bmp = wx.Bitmap(r'resources/Baumgartner/chart_24.ico', wx.BITMAP_TYPE_ICO)
        self.plotbtn = wx.BitmapButton(self.btnbar, -1, plot_bmp, style = wx.NO_BORDER)
        self.plotbtn.SetBitmapSelected( wx.Bitmap(r'resources/Baumgartner/chart_24_selected.bmp') )
        self.plotbtn.SetToolTip(wx.ToolTip('Quick plot (Shortcut key: q)'))

        report_bmp = wx.Bitmap(r'resources/Tango/save.ico', wx.BITMAP_TYPE_ICO)
        saving_bmp = wx.Bitmap(r'resources/Tango/saving.ico', wx.BITMAP_TYPE_ICO)
        self.reportbtn = wx.BitmapButton(self.btnbar, -1, report_bmp, style = wx.NO_BORDER)
        self.reportbtn.SetBitmapSelected( saving_bmp )
        self.reportbtn.SetToolTip(wx.ToolTip('Make a PDF Report and export as mat/npz file'))

        self.ID_jump2anat = wx.NewId()
        self.ID_jump2avgmap = wx.NewId()
        self.ID_jump2eachmap = wx.NewId()
        self.ID_toggleROImngr = wx.NewId()
        self.ID_toggleRecalc = wx.NewId()
        self.jump2anat = wx.Button(self.btnbar, self.ID_jump2anat, 'Anatomy', style=wx.BU_EXACTFIT)
        self.jump2anat.SetMinSize(self.jump2anat.GetSize())
        self.jump2avgmap = wx.Button(self.btnbar, self.ID_jump2avgmap, 'avg_dF/F', style=wx.BU_EXACTFIT)
        self.jump2avgmap.SetMinSize(self.jump2avgmap.GetSize())
        self.ROImngr = wx.ToggleButton(self.btnbar, self.ID_toggleROImngr, 'ROItable', style=wx.BU_EXACTFIT)
        self.ROImngr.SetOwnFont(wx.Font(8, wx.DEFAULT, wx.NORMAL, wx.BOLD))
        self.ROImngr.Bind(wx.EVT_TOGGLEBUTTON, self.OnROImngr)
        self.ROImngr.SetToolTip(wx.ToolTip('Toggle show/hide the ROI table'))

        self.btns = [self.zoominbtn, self.zoomoutbtn, self.panbtn, self.playbtn,
                self.rewindbtn, self.drawROIbtn, self.moveROIbtn,
                self.trashROIbtn, self.plotbtn, self.reportbtn,
                self.jump2anat, self.jump2avgmap, self.ROImngr,
                ]

        # sizer
        hbox1 = wx.BoxSizer(wx.HORIZONTAL)
        hbox2 = wx.BoxSizer(wx.HORIZONTAL)
        tools1 = [txt_z, self.scz, self.ManScaling, txt_H, self.scH, txt_L, self.scL]
        tools2 = [self.updateimgbtn, self.autoY, txt_Ymax, self.scYmax, txt_Ymin, self.scYmin]
        for t in tools1:
            hbox1.Add(t, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 1)
        for t in tools2:
            hbox2.Add(t, 0, wx.ALIGN_CENTER_VERTICAL|wx.RIGHT, 1)
        self.toolbar1.SetSizer(hbox1)
        self.toolbar2.SetSizer(hbox2)
        self.toolbar1.Fit()
        self.toolbar2.Fit()
        # call a method to place other widgets, wich can move in resize event
        self.placing = True

        if parent.fitw.IsChecked():
            self.placepanels(None)
        else:
            self.placepanels(self.w)

        self.refresh_buf() # initialize before binding paint event

        # event bindlings
        self.Bind(wx.EVT_SIZE, self.OnResizeBorder)
        self.display.Bind(wx.EVT_CONTEXT_MENU, self.OnCtxMenu)
        self.display.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
        self.display.Bind(wx.EVT_KEY_UP, self.OnKeyUp)
        self.display.Bind(wx.EVT_MOUSE_EVENTS, self.OnMouse)
        self.Bind(wx.EVT_IDLE, self.OnCheckSize)
        self.Bind(wx.EVT_CLOSE, self.OnQuit)
        # File drop
        self.display.SetDropTarget(matDrop(self))

        # evt for bottuns
        self.scz.Bind(wx.EVT_SPINCTRL, self.OnSpin_z)
        self.ManScaling.Bind(wx.EVT_CHECKBOX, self.OnCheckBoxes)
        self.scH.Bind(wx.EVT_SPINCTRL, self.OnSpin_ManSc)
        self.scL.Bind(wx.EVT_SPINCTRL, self.OnSpin_ManSc)
        self.updateimgbtn.Bind(wx.EVT_BUTTON, self.OnReload)
        self.autoY.Bind(wx.EVT_CHECKBOX, self.OnCheckBoxes)

        self.playbtn.Bind(wx.EVT_BUTTON, self.OnPlay)
        self.rewindbtn.Bind(wx.EVT_BUTTON, self.OnRewind)
        self.panbtn.Bind(wx.EVT_BUTTON, self.OnPanMode)
        self.zoominbtn.Bind(wx.EVT_BUTTON, self.OnZoomMode)
        self.zoomoutbtn.Bind(wx.EVT_BUTTON, self.OnZoomReset)
        self.drawROIbtn.Bind(wx.EVT_BUTTON, self.OnROIDraw)
        self.moveROIbtn.Bind(wx.EVT_BUTTON, self.OnROIMove)
        self.trashROIbtn.Bind(wx.EVT_BUTTON, self.OnROITrash)
        self.plotbtn.Bind(wx.EVT_BUTTON, self.OnQuickPlot)
        self.reportbtn.Bind(wx.EVT_BUTTON, self.export)

        self.jump2anat.Bind(wx.EVT_BUTTON, self.OnJumpButtons)
        self.jump2avgmap.Bind(wx.EVT_BUTTON, self.OnJumpButtons)

        self.t0 = time.time()
        self.timer = wx.Timer(self) # Timer for video
        self.Bind(wx.EVT_TIMER, self.OnTimer, self.timer)
        self.timer.Start(1000/60.0)

        self.display.SetFocus()

        self.changetitle()
        self.Iconize(False)


    def OnRecalc(self, event):

        togglestate = self.recalc.GetValue()
        if not togglestate:
            self.ResFindframe.Destroy()
        else:
            fp, Foffset = self.changetitle(wantfp_offset=True)
            self.ResFindframe = ResFind(self)
            self.ResFindframe.Show()

            if 'dFoFfil' in self.imgdict.keys():
                print 'dFoFfil found'


    def OnROImngr(self, event):

        togglestate = self.ROImngr.GetValue()

        if self.ROI.data and togglestate:
            # disable/enable 3 ROI editing buttons
            self.drawROIbtn.Enable(False)
            self.moveROIbtn.Enable(False)
            self.trashROIbtn.Enable(False)

            x,y = self.GetPosition()
            w,h = self.GetSize()
            pos = (x+w, y)
            self.ROImngrframe = ROImanager.ROImanager(self, self.ROI, pos=pos)
            self.ROImngrframe.Show()
        elif not togglestate and hasattr(self, 'ROImngrframe'):
            if self.ROImngrframe.IsShown():
                self.drawROIbtn.Enable(True)
                self.moveROIbtn.Enable(True)
                self.trashROIbtn.Enable(True)
                self.ROImngrframe.Destroy()
                del self.ROImngrframe
        elif not self.ROI.data and togglestate:
            self.ROImngr.SetValue(False)


    def loadROI(self, fp):

        planesfound = set([tag[1] for tag in self.tag])

        if fp.endswith('mat'):

            a = sio.loadmat(fp)
            ind = [n for n, aa in enumerate(a.keys()) if aa.startswith('pymg')]

            if ind: # roi v2 or above
                sname = a.keys()[ind[0]]
                if 'ROI_planes' in a[sname].dtype.names: # pymagor2.6.* or under
                    roiz = [str(aa[0]) for aa in a[sname]['ROI_planes'][0][0][0]]
                    _ind = [n for n,aa in enumerate(roiz) if aa in planesfound]

                    if not _ind:
                        print 'Field-of-Views found in matfile:', roiz
                        print 'Current Field-of-Views opened:', planesfound
                        self.parent.showmessage('None of\n%s in the mat file were found in \n%s that are opened' % (roiz, list(planesfound)) )
                        return
                    roipoly = [zip(aa[:,0], aa[:,1]) for aa in a[sname]['ROI_polygons'][0][0][0]]
                    roipoly = [roipoly[n] for n in _ind]
                    roiz = [roiz[n] for n in _ind]

                    if 'ROI_categories' in a[sname].dtype.names:
                        roi_ctgr = [ str(aa[0]) for aa in a[sname]['ROI_categories'][0][0][0] ]
                        roi_ctgr = [roi_ctgr[n] for n in _ind]

                elif 'ROIs' in a[sname][0][0].dtype.names:  # then probably roiv3? github? this part seems brocken
                    ROIs = a[sname][0][0]['ROIs'][0]
                    roiz = [str(aa[0]) for aa in ROIs['ROI_Field_of_views'][0][0]]
                    roipoly = [zip(aa[:,0], aa[:,1]) for aa in ROIs['ROI_polygons'][0][0]]
                    _ind = [n for n,aa in enumerate(roiz) if aa in planesfound]
                    if not _ind:
                        print 'Field-of-Views found in matfile:', roiz
                        print 'Current Field-of-Views opened:', planesfound
                        self.parent.showmessage('None of\n%s in the mat file were found in \n%s that are opened' % (roiz, list(planesfound)) )
                        return
                    roipoly = [roipoly[n] for n in _ind]
                    roiz = [roiz[n] for n in _ind]
                    roi_ctgr = [ str(aa[0]) for aa in ROIs['ROI_categories'][0][0] ]
                    roi_ctgr = [roi_ctgr[n] for n in _ind]

                else: # github ver (2.7)
                    roiz = [str(aa[0]) for aa in a[sname][0][0]['ROI_Field_of_views'][0]]
                    roipoly = [zip(aa[:,0], aa[:,1]) for aa in a[sname][0][0]['ROI_polygons'][0]]
                    _ind = [n for n,aa in enumerate(roiz) if aa in planesfound]
                    if not _ind:
                        print 'Field-of-Views found in matfile:', roiz
                        print 'Current Field-of-Views opened:', planesfound
                        dlg = wx.MessageDialog(None, 'None of\n%s in the mat file were found in \n%s that are opened. Overwrite anyway?' % (roiz, list(planesfound)), style=wx.YES_NO)
                        if dlg.ShowModal() == wx.ID_NO:
                            dlg.Destroy()
                            return
                        roiz = self.changetitle(wantz=True)
                        roi_ctgr = 'Cell'
                    else:
                        roipoly = [roipoly[n] for n in _ind]
                        roiz = [roiz[n] for n in _ind]
                        roi_ctgr = [ str(aa[0]) for aa in a[sname][0][0]['ROI_categories'][0] ]
                        roi_ctgr = [roi_ctgr[n] for n in _ind]

            else: # for roi v1 file, use the current plane name
                roiz = self.changetitle(wantz=True)
                roi_ctgr = 'Cell'
                h = a['F'].shape[0]
                roipoly = [ zip(aa[:,0].astype('int'), h-aa[:,1].astype('int'))
                            for aa in a['ROIs'][0] ]

        elif fp.endswith('npz'):

            a = np.load(fp)
            if 'ROI_Field_of_views' in a.keys():  # renamed after public release at github
                roiz = a['ROI_Field_of_views'].tolist()
            else:
                roiz = a['ROI_planes'].tolist()
            _ind = [n for n,aa in enumerate(roiz) if aa in planesfound]

            roiz = [roiz[n] for n in _ind]

            roipoly = a['ROI_polygons'].tolist()
            roipoly = [roipoly[n] for n in _ind]

            roi_ctgr = [aa for aa in a['ROI_categories']]
            roi_ctgr = [roi_ctgr[n] for n in _ind]

        if self.parent.appendROI.IsChecked() and self.ROI.data:
            self.ROI.add(roipoly, z=roiz, category=roi_ctgr)
        else:
            self.ROI = ROI(roipoly, z=roiz, category=roi_ctgr)


    # GENERAL METHODS
    def assure_box(self, end_x, end_y):

        w = abs(end_x - self.st_x)
        h = abs(end_y - self.st_y)

        if self.w > self.h:
            if self.st_y+h > self.h:
                h = self.h - self.st_y
            h = w * self.h / self.w
        elif self.w < self.h:
            if self.st_x+w > self.w:
                w = self.w - self.st_x
            h = w * self.h / self.w
        else:  # if self.w == self.h:
            w = w*(w>h) + h*(h>=w)
            h = w*(w>h) + h*(h>=w)

        # outside of image? 
        ex,ey = self.st_x+w, self.st_y+h
        if ex >= self.w:
            ex = self.w
            w = self.w - self.st_x
            h = w * self.h / self.w
            ey = self.st_y+h
        if ey >= self.h:
            ey = self.h
            h = self.h - self.st_y
            w = h * self.w / self.h
            ex = self.st_x + w
        
        return ex, ey

    def init_workers(self):
        self.workers = {}
        for t in self.tag:
            fname = t[0]
            data_path = t[-1]
            fp = path2img(data_path, t)
            self.workers[fp] = False

    def boarder_check(self):
        x1, y1, x2, y2 = self.zoomrect
        # x1, y1, x2, y2 are in absolute cordinates
        # dx = -1 means zoomrect should shift by +1
        if (x1 - self.dx) < 0:
            offsetx = 0 - x1
        elif (x2 - self.dx) > self.w:
            offsetx = self.w -x2
        else:
            offsetx = -self.dx

        if (y1 - self.dy) < 0:
            offsety = 0 - y1
        elif (y2 - self.dy) > self.h:
            offsety = self.w - y2
        else:
            offsety = -self.dy

        return offsetx, offsety

    def changetitle(self, wantz=False, wantfp_offset=False):

        postfix = ''
        data_path = ''
        fname = ''

        if self.TVch in [2,3,4]: # F, each dF/F map, anatomy
            title = ' '.join([self.tag[self.curframe][ind] for ind in [1,2,3,0]])[:-4]
            data_path = self.tag[self.curframe][-1]
            fname = self.tag[self.curframe][0]
            z = self.tag[self.curframe][1]
            Foffset = self.imgdict['Foffset'][self.curframe, 0:2]
        elif self.TVch in [7,8]: # max or avg projection
            title = z = self.imgdict['uniquekey'][self.curframe]
            if wantfp_offset:
                print 'Plotting from max or avg projection is not suported'
                return None, None
        elif self.TVch in [5,6]: # avg odor maps, avg_F
            z, odorname = self.imgdict['avg_odormap odornames'][self.curframe]
            title = '%s %s' % (z, odorname)
            if wantfp_offset:
                eachplane = [ tag for tag in self.tag if z == tag[1] and tag[2] == odorname]
                offsets = [ offset for tag,offset in zip(self.tag, self.imgdict['Foffset']) if z == tag[1] and tag[2] == odorname]
                return eachplane, offsets
        else: # [0] raw or [1] dF/F filtered
            zsize = self.z / len(self.tag)
            _ind = int(self.curframe / zsize)
            _tag = self.tag[_ind]
            data_path = _tag[-1]

            z = _tag[1]
            fname = _tag[0]
            title = z + ' ' + fname
            Foffset = self.imgdict['Foffset'][_ind, 0:2]

        if wantz:
            return z

        if data_path != '' and fname != '':
            if os.path.exists(data_path):
                fp = os.path.join(data_path, fname)
            else:
                fp = path_check(os.path.join(self.imgdict['data_path'], fname), verbose)
                if verbose:
                    print data_path, 'does not exist. alternate used: ', fp
            # check if it's a Micro-Manager file
            if fname.count('_') and os.path.basename(data_path).count('_'):
                if fname.split('_')[-2] == os.path.basename(data_path).split('_')[-2]:
                    postfix = data_path.split('\\')[-1]
                    title += ' in ' + postfix
        else:
            fp = []

        if wantfp_offset:
            return fp, Foffset
        if type(fp) != list:
            self.checkhist(fp)

        img = self.img[:,:,self.curframe]
        txt = 'Min and Max pixel values in image : %d, %d' % (img.min(), img.max())
        self.ManScaling.SetToolTip( wx.ToolTip(txt) )

        title = img_keys[self.TVch]+': ' + title
        if self.lock:
            title = '*'+title
        self.SetTitle(title)
        self.Refresh()

    def placepanels(self, width_for_btns):
        '''
        manually wrapping the UI elements
        In the future, re-implement this using WrapSizer in wxPython 3.0
        http://wxpython.org/Phoenix/docs/html/WrapSizer.html
        '''

        #print 'placepanels: width_for_btns = ', width_for_btns
        self.placing = True
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add((0,1), proportion=0, flag=wx.EXPAND)

        hbox3 = wx.BoxSizer(wx.HORIZONTAL)
        hbox3.Add(self.toolbar1, proportion=0, flag=wx.EXPAND)
        hbox3.Add(self.toolbar2, proportion=0, flag=wx.EXPAND)
        w,_ = hbox3.ComputeFittingClientSize(self)
        #print 'placepanels: w', w

        if width_for_btns:
            _width_for_btns = width_for_btns
        else:
            dw, dh = self.DispSize
            if w * self.h / self.w > dh * 0.85:
                _width_for_btns = dh * 0.85 * self.w / self.h
            else:
                _width_for_btns = w

        if w <= _width_for_btns:
            sizer.Add(hbox3, proportion=0, flag=wx.EXPAND)
            max_w = _width_for_btns
        else:
            self.toolbar1.Fit()
            self.toolbar2.Fit()
            max_w = max(_width_for_btns,
                        self.toolbar1.GetSizeTuple()[0],
                        self.toolbar2.GetSizeTuple()[0])
            sizer.Add(self.toolbar1, proportion=0, flag=wx.EXPAND)
            sizer.Add(self.toolbar2, proportion=0, flag=wx.EXPAND)

        hbox4 = wx.BoxSizer(wx.HORIZONTAL)
        hbox5 = wx.BoxSizer(wx.HORIZONTAL)
        for b in self.btns:
            _w,_h = hbox4.ComputeFittingClientSize(self.btnbar)
            if (_w + b.GetSizeTuple()[0] ) < max_w:
                hbox4.Add(b,0)
            else:
                hbox5.Add(b,0)

        if hbox5.ComputeFittingClientSize(self.btnbar)[0]:
            vbox2 = wx.BoxSizer(wx.VERTICAL)
            vbox2.Add(hbox4)
            vbox2.Add(hbox5)
            self.btnbar.SetSizer(vbox2)
        else:
            self.btnbar.SetSizer(hbox4)
        self.btnbar.Fit()

        if max_w < self.btnbar.GetSizeTuple()[0]:
            max_w = self.btnbar.GetSizeTuple()[0]

        sizer.Add(self.btnbar, proportion=0, flag=wx.EXPAND)
        self.ScalingFactor = max_w / float(self.w)

        if self.ScalingFactor <= 1:
            self.ScalingFactor = 1
        elif self.ScalingFactor > 4:
            self.ScalingFactor = 1.2 ** 8

        self.display.SetSize(( self.w * self.ScalingFactor,
                               self.h * self.ScalingFactor ))
        self.display.SetMinSize(( self.w * self.ScalingFactor,
                               self.h * self.ScalingFactor ))
        self.refresh_buf()

        sizer.Add(self.display, proportion=1, flag=wx.SHAPED|wx.EXPAND|wx.ALL, border=2)
        self.SetSizer(sizer)
        self.mainsizer = sizer

        self.Fit()  # Fit first and Layout!!
        self.Layout()
        self.Refresh()
        self.b4resize = self.display.GetSizeTuple()
        wb4, hb4 = self.b4resize
        ww, hw = sizer.ComputeFittingWindowSize(self)
        self.xmargin = abs(ww - wb4)

        self.placing = False
        #print 'placepanels: self.GetSize, ScalingFactor', self.GetSizeTuple(), self.ScalingFactor

    def frame_resize(self, event):

        if self.need_resize:
            wc, hc = self.GetSizeTuple()
            dw, dh = self.DispSize
            w = wc - self.xmargin
            if hc > dh * 0.85:
                w = dh * 0.85 * self.w / self.h

        if event is not None:
            if event.GetId() == self.ID_fitw:
                space_for_btns = None
            elif event.GetId() == self.ID_scaling1:
                self.ScalingFactor = 1.0
                space_for_btns = self.ScalingFactor * self.w
            else:
                space_for_btns = w

        self.placepanels(space_for_btns)
        self.need_resize = False

    def insideROI(self, x, y):
        roi_in = []
        z = self.changetitle(wantz=True)

        for ind, poly in enumerate(self.ROI.data):
            if self.ROI.z[ind] == z:
                p = matplotlib.path.Path(poly)
                if p.contains_point((x+0.5,y+0.5)):
                    roi_in.append(ind)

        return roi_in

    def normxy(self, event):
        x,y = event.GetPosition()
        fr_w, fr_h = self.display.GetSizeTuple()
        # normalize cordinates to the zoomed image size
        x1, y1, x2, y2 = self.zoomrect
        nx = x / float(fr_w) * (x2-x1) + x1
        ny = y / float(fr_h) * (y2-y1) + y1
        if nx > self.w:
            nx = self.w
        elif nx < 0:
            nx = 0
        if ny > self.h:
            ny = self.h
        elif ny < 0:
            ny = 0

        return int(nx), int(ny)

    def manualscale(self, frame, Hi=None, Lo=None):

        if frame.dtype != np.float32:
            frame = np.array(frame, dtype=np.int32)

        if Hi is None:
            Hi = self.scH.GetValue()
            Lo = self.scL.GetValue()
        if Hi <= Lo:
            Hi = Lo+1
        frame[frame>Hi] = Hi
        frame[frame<Lo] = Lo

        return np.array((frame-Lo)*255/(Hi-Lo), dtype=np.uint8)

    def plot(self, subplot, data, raw=False, label=None):
        fontBold = FontProperties()
        fontBold.set_weight('bold')
        fontBold.set_size('large')

        if not label:
            label = ['cell'+str(n+1) for n in range(data.shape[1])]

        markers = ('None', 'None', '.')
        linestyles = ('-', '-.', '--')
        colors = ('b', 'g', 'r', 'c', 'm', 'y')
        for n in range( data.shape[1] ):
            color = colors[np.mod(n,6)]
            linestyle = linestyles[int(np.mod(np.floor(n/6),3))]
            marker = markers[int(np.mod(np.floor(n/6),3))]
            _trace = data[:,n]
            subplot.plot(_trace, linestyle=linestyle, color=color, marker=marker )
            marker_pos = np.abs(_trace[self.durpre[0]:]).argmax()+self.durpre[0]
            subplot.text(marker_pos, _trace[marker_pos]*1.2, label[n], color=color, alpha=0.7) #fontproperties=fontBold

        subplot.set_xlabel('Frames')
        subplot.set_xlim([0, data.shape[0]])

        if raw:
            subplot.set_ylabel('Raw pixel value')
        else:
            subplot.set_ylabel('dFoF (%)')
        if self.autoY.GetValue():
            Ymax = data.max()*1.1
            if raw:
                Ymin = data.min()*0.8
            else:
                Ymin = data.min()*1.1
        else:
            Ymax = self.scYmax.GetValue()
            Ymin = self.scYmin.GetValue()
        subplot.set_ylim([Ymin, Ymax])

        subplot.plot(self.durpre,[Ymin*0.99, Ymin*0.99], color='blue', linewidth=2)
        subplot.plot(self.durres,[Ymin*0.99, Ymin*0.99], color='red', linewidth=2)
        plt.tight_layout()

    def Plugin(self, event):

        _id = event.GetId()
        obj = CntxPlugin[_id][0]
        name = CntxPlugin[_id][1]
        #print 'Plugin ID = ', _id, 'name =', name
        obj.Cntx_run(self)

    def refreshch(self, z=None):

        self.scz.SetRange(0, self.img.shape[2]-1)
        if self.curframe > self.img.shape[2]:
            self.curframe = self.img.shape[2]-1

        def _planechange(z):
            zz = self.changetitle(wantz=True)
            if zz != z:
                if self.curframe > 0:
                    self.curframe -= 1
                else:
                    self.curframe = self.img.shape[2]-1
            return zz==z

        if not _planechange(z):
            while 1:
                if _planechange(z):
                    break

        self.scz.SetValue(self.curframe)
        self.changetitle()

    def reset_cursor(self):
        self.SetCursor(wx.StockCursor(wx.CURSOR_DEFAULT))
        self.refresh_buf()
        self.Refresh()
        self.display.SetFocus()

    def refresh_buf(self, update_zoomrect=False):
        
        # clip out the zoomd region
        x1, y1, x2, y2 = self.zoomrect
        if self.dragging:
            offsetx, offsety = self.boarder_check()
            frame = self.img[self.h-y2-offsety : self.h-y1-offsety,
                            x1+offsetx : x2+offsetx,
                            self.curframe].copy() # copy important for manualscaling
            if update_zoomrect:
                self.zoomrect = (x1+offsetx, y1+offsety, x2+offsetx, y2+offsety)
        else:
            offsetx, offsety = 0, 0
            frame = self.img[self.h-y2:self.h-y1, x1:x2, self.curframe].copy() # copy important for manualscaling

        if SDthrs and self.TVch in [1, 3, 6]:
            thrs = self.img[:,:,self.curframe].std() * 2.5
            self.param.sc_cutoff.SetValue( thrs )
        
        # color look up
        if self.TVch in [1,3,6,7,8]: # dFoF movie, dFoF frame avg (response maps), dFoF trial avg, mean / max projections
            
            if cutoffON:
                frame[frame<cutoff] = 0
            buf = gray2clut2b(frame[::-1,:].copy(), cmin, cmax)

            if Overlay:
                # look for the corresponding anatomy in the same z plane
                z = self.changetitle(wantz=True)
                ind = [t[1] for t in self.tag].index(z)
                anat = self.imgdict['anatomy'][ self.h-y2-offsety:self.h-y1-offsety, 
                                                x1+offsetx:x2+offsetx, ind].copy()
               
                # normalize color scale
                if self.ManScaling.IsChecked():
                    anat = self.manualscale(anat)
                else:
                    anat = self.manualscale(anat, anat.max(), anat.min())
                # now replace below cutoff with anatomy
                anat = np.tile(anat[:,:,np.newaxis], (1,1,3))
                buf[::-1,:,:][frame<cutoff] = anat[frame<cutoff]
       
        # gray scale
        else: # unshifted frames | F | anatomy
            if self.ManScaling.IsChecked(): # Manual contrast adjust
                frame = self.manualscale(frame)
            else:                           # Auto contrast adjust
                frame = self.manualscale(frame, frame.max(), frame[frame>0].min())
            buf = np.tile(frame[::-1,:,np.newaxis].copy(), (1,1,3))

        imgbuf = wx.ImageFromBuffer(frame.shape[1], frame.shape[0], buf)
        # re-scale bmp
        self.bmp = wx.BitmapFromImage(
                imgbuf.Rescale(self.ScalingFactor*self.w, self.ScalingFactor*self.h))
        #self.draw()

        if self.playing and self.record:

            bitmap = self.copyBMP(None)
            buf = bitmap.ConvertToImage().GetData()

            w = int(self.w*self.ScalingFactor)
            h = int(self.h*self.ScalingFactor)
            im = Image.frombytes('RGB',(w,h), buf)
            self.p.stdin.write(im.tobytes('jpeg','RGB'))

    def autoPSFplot(self, blobthrs, blobsize, zstep, ROImax):

        fp, Foffset = self.changetitle(wantfp_offset=True)
        z = self.changetitle(wantz=True)

        tif = tifffile.TIFFfile(fp)
        _, h, w = tif.series[0]['shape']

        img_info = get_tags(fp)
        nch = img_info['nch']
        nframes = img_info['nframes']

        # set up the list of frame numbers to read
        ch = self.ch
        F1, F2 = 0, nframes-1
        rng = np.arange(F1, F2+1) * nch + ch
        proj = tif.asarray()[rng,:,:].std(axis=0)

        beads = proj>proj.std()*blobthrs
        labeled, nbeads = ndimage.label(beads)
        #print 'nbeads', nbeads
        figure = plt.figure(figsize=[6,6*h/w])
        subplot = figure.add_subplot(111)
        subplot.imshow(beads)
        plt.subplots_adjust(left=0, right=1, top=1, bottom=0, wspace=0, hspace=0)
        figure.show()

        no_extreme = []
        for n in range(nbeads):
            _size = (labeled == n).sum()
            if 10 < _size < w*h * 0.01:
                no_extreme.append( _size )
        MEDIAN = np.median(no_extreme)
        SD = np.std(no_extreme)
        r = np.sqrt(MEDIAN/np.pi) + 1 # ensure 1 pixel margin
        low = MEDIAN - SD*blobsize if MEDIAN - SD*blobsize > 10 else 10
        high = MEDIAN + SD*blobsize

        figure = plt.figure(figsize=[6,4])
        subplot = figure.add_subplot(111)
        frq, _x, ptch = subplot.hist(no_extreme)
        subplot.plot([MEDIAN, MEDIAN],[0, frq.max()])
        subplot.plot([high, high],[0, frq.max()])
        subplot.plot([low, low],[0, frq.max()])
        figure.show()
        #print '# of no_extreme, MEDIAN, SD, r', len(no_extreme), MEDIAN, SD, r

        for n in range(nbeads):

            y,x = (labeled==n).nonzero()
            _size = (labeled == n).sum()

            if low < _size < high and \
                r < y.mean() < h - r and \
                r < x.mean() < w - r:
                print n,
                points = np.array([y,x]).T

                hull = ConvexHull(points)
                roibuf = [(x,y) for y,x in points[hull.vertices]]
                self.ROI.add(roibuf, str(z))
        print '\n'

        # get raw fluorescent traces (not dF/F)
        traces = self.getdFoF(fp, dtype=np.uint16, offset=Foffset, raw=True)[0]
        #print 'traces', traces, fp, traces.shape

        #np.savez('debug.npz', traces=traces)

        # compute half-width
        peaks = np.max(traces, axis=0)

        #baselines = stats.mode(np.round(traces))[0]
        # Let's do without scipy!
        u,  ind = np.unique(np.round(traces), return_inverse=True)
        axis = 0
        baselines = u[np.argmax(
                np.apply_along_axis(
                                    np.bincount,
                                    axis,
                                    ind.reshape(traces.shape),
                                    None,
                                    np.max(ind)+1
                                    ),
                    axis=axis
                    )
            ]
        baselines = baselines.reshape(1,traces.shape[1])

        #print baselines
        half_height = (peaks - baselines)/2.0
        thrs = (peaks - half_height).ravel()

        n_cell = traces.shape[1]
        PSF = []

        # (1) just pick bright ones
        #maxcell = traces.shape[1] if traces.shape[1] < ROImax else ROImax
        #good_cells = half_height[0].argsort()[::-1][:maxcell].tolist()
        #print good_cells

        # (2) peak should not be too close to start and end
        #     and single peak only.
        removeByPeakLoc = (traces.argmax(axis=0) <= F2/5) + (F2*4/5 <= traces.argmax(axis=0))
        half_height[:,removeByPeakLoc] = 0
        maxcell = ROImax if (removeByPeakLoc==False).sum()>ROImax else (removeByPeakLoc==False).sum()
        by_height = half_height[0].argsort()[::-1]
        #by_singlepeakness =
        good_cells = by_height[:maxcell]
        #print good_cells.tolist()
        self.ROI.remove( [n for n in range(n_cell) if n not in good_cells] )

        for n in good_cells:
            trace = traces[...,n]
            print n, trace
            x = np.nonzero([trace > thrs[n]])[1]
            y = trace[x]

            # extrapolate and find the crossings
            if x.min()>0:
                slopeL = trace[x.min()] - trace[x.min()-1]
            else:
                slopeL = trace[x.min()+1] - trace[x.min()]
            if x.max()+1 < trace.shape[0]:
                slopeR = trace[x.max()+1] - trace[x.max()]
            else:
                slopeR = trace[x.max()] - trace[x.max()-1]
            dxL = (thrs[n] - trace[x.min()]) / slopeL
            dxR = (thrs[n] - trace[x.max()]) / slopeR

            x = np.concatenate((x.min()+dxL, x, x.max()+dxR),axis=None)
            y = np.concatenate((thrs[n], y, thrs[n]),axis=None)
            psf = x.ptp()/2.0
            #psf = x.ptp() * zstep
            PSF.append(psf)


        # modify getPSF plugin
        figure = plt.figure(figsize=[6,4])
        subplot = figure.add_subplot(111)
        plt.subplots_adjust(left=0, right=1, top=1, bottom=0, wspace=0, hspace=0)

        fontP = FontProperties()
        fontP.set_size('small')

        # for legend, plot lines first
        for _n, n in enumerate(good_cells):
            trace = traces[...,n]
            # readable and fast np iter
            # http://stackoverflow.com/questions/1589706/iterating-over-arbitrary-dimension-of-numpy-array
            color = cm.hsv(255*_n/(maxcell+1))
            subplot.plot(trace, color=color)

        for _n, n in enumerate(good_cells):
            trace = traces[...,n]
            x = np.nonzero([trace > thrs[n]])[1]
            y = trace[x]
            color = cm.hsv(255*_n/(maxcell+1))
            subplot.plot (x, y, color=color, linewidth=3)
            subplot.text(x.min()+1.2, thrs[n]-2, 'Cell%d = %3.2f' % (_n+1, psf), color='k', fontsize=9)

            subplot.plot(np.tile(baselines, (traces.shape))[:,n], color=color)
            subplot.plot(x,np.tile(thrs[n],x.shape), color=color)

        label = ['Cell%d' % (n+1) for n in range(maxcell)]
        subplot.legend(label, loc='upper left', frameon=False, ncol=5, prop=fontP)
        subplot.set_title('Mean PSF = %3.2f micron (%0.2f micron z-step)' % (np.median(PSF), zstep), fontsize=9)
        subplot.set_ylabel('Raw fluorescence value')
        subplot.set_xlabel('Frames')

        plt.tight_layout()
        figure.show()

        for n, psf in enumerate(PSF):
            print 'Cell%d: %f micron' % (n+1,psf)

        self.Refresh()


    # CONTEXT MENU
    def OnCtxMenu(self, event):

        if not hasattr(self, 'ID_ROInumber'):
            self.ID_lock = wx.NewId()
            self.ID_openfolder = wx.NewId()
            self.ID_closeall = wx.NewId()
            self.ID_baseline = wx.NewId()
            self.ID_ROI = wx.NewId()
            self.ID_ROInumber = wx.NewId()
            self.ID_ROIoutlines = wx.NewId()
            self.ID_AutoPSF = wx.NewId()

            self.Bind(wx.EVT_MENU, self.OnCtxROImode, id=self.ID_lock)
            self.Bind(wx.EVT_MENU, self.parent.OnCloseAll, id=self.ID_closeall)
            self.Bind(wx.EVT_MENU, self.OnCtxOpenFolder, id=self.ID_openfolder)
            self.Bind(wx.EVT_MENU, self.frame_resize, id=self.ID_fitw)
            self.Bind(wx.EVT_MENU, self.frame_resize, id=self.ID_scaling1)
            self.Bind(wx.EVT_MENU, self.OnCtxROImode, id=self.ID_baseline)
            self.Bind(wx.EVT_MENU, self.OnCtxROImode, id=self.ID_ROI)
            self.Bind(wx.EVT_MENU, self.OnCtxROImode, id=self.ID_ROInumber)
            self.Bind(wx.EVT_MENU, self.OnCtxROImode, id=self.ID_ROIoutlines)
            self.Bind(wx.EVT_MENU, self.OnCtxAutoPSF, id=self.ID_AutoPSF)

            self.ID_CopyROIs = wx.NewId()
            self.ID_PrintROIs = wx.NewId()
            self.ID_PasteROIs = wx.NewId()
            self.ID_ROIimport = wx.NewId()
            self.ID_ROIexport = wx.NewId()
            self.ID_ClearROI = wx.NewId()
            self.ID_ROIsort = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnCtxCopyROIs, id=self.ID_CopyROIs)
            self.Bind(wx.EVT_MENU, self.OnCtxPrintROIs, id=self.ID_PrintROIs)
            self.Bind(wx.EVT_MENU, self.OnCtxCopyROIs, id=self.ID_PasteROIs)
            self.Bind(wx.EVT_MENU, self.ROIio, id=self.ID_ROIimport)
            self.Bind(wx.EVT_MENU, self.ROIio, id=self.ID_ROIexport)
            self.Bind(wx.EVT_MENU, self.OnCtxSortROIs, id=self.ID_ROIsort)
            self.Bind(wx.EVT_MENU, self.OnCtxClearROIs, id=self.ID_ClearROI)

            self.ID_plot = wx.NewId()
            self.ID_hist = wx.NewId()
            self.ID_report = wx.NewId()
            self.ID_saveBMP = wx.NewId()
            self.ID_copyBMP = wx.NewId()
            self.ID_recmovie = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnQuickPlot, id=self.ID_plot)
            self.Bind(wx.EVT_MENU, self.OnShowHist, id=self.ID_hist)
            self.Bind(wx.EVT_MENU, self.OnQuickPlot, id=self.ID_plotraw)
            self.Bind(wx.EVT_MENU, self.export, id=self.ID_report)
            self.Bind(wx.EVT_MENU, self.saveBMP, id=self.ID_saveBMP)
            self.Bind(wx.EVT_MENU, self.copyBMP, id=self.ID_copyBMP)
            self.Bind(wx.EVT_MENU, self.OnCtxRec, id=self.ID_recmovie)

            if hasattr(self, 'imgdict'):
                self.ID_ch0 = wx.NewId()
                self.ID_ch1 = wx.NewId()
                self.ID_ch2 = wx.NewId()
                self.ID_ch3 = wx.NewId()
                self.ID_ch4 = wx.NewId()
                self.ID_ch5 = wx.NewId()
                self.ID_ch6 = wx.NewId()
                self.ID_ch7 = wx.NewId()
                self.ID_ch8 = wx.NewId()
                self.Bind(wx.EVT_MENU, self.OnCtxRadioChange, id=self.ID_ch0)
                self.Bind(wx.EVT_MENU, self.OnCtxRadioChange, id=self.ID_ch1)
                self.Bind(wx.EVT_MENU, self.OnCtxRadioChange, id=self.ID_ch2)
                self.Bind(wx.EVT_MENU, self.OnCtxRadioChange, id=self.ID_ch3)
                self.Bind(wx.EVT_MENU, self.OnCtxRadioChange, id=self.ID_ch4)
                self.Bind(wx.EVT_MENU, self.OnCtxRadioChange, id=self.ID_ch5)
                self.Bind(wx.EVT_MENU, self.OnCtxRadioChange, id=self.ID_ch6)
                self.Bind(wx.EVT_MENU, self.OnCtxRadioChange, id=self.ID_ch7)
                self.Bind(wx.EVT_MENU, self.OnCtxRadioChange, id=self.ID_ch8)

        ctxmenu = wx.Menu()
        ctxmenu.Append(self.ID_lock, 'Resistant to \'Close all plots and images\'', '', wx.ITEM_CHECK)
        ctxmenu.Check(self.ID_lock, self.lock)
        ctxmenu.Append(self.ID_openfolder, 'Open the data folder in explorer, finder etc')
        ctxmenu.Append(self.ID_closeall, 'Close all plots and images')
        ctxmenu.Append(self.ID_fitw, 'Fit to the tool bar width')
        ctxmenu.Append(self.ID_scaling1, 'Fit to the original image width')
        ctxmenu.AppendSeparator()
        ctxmenu.Append(self.ID_ROI, 'ROI mode (ROIs visible)', '', wx.ITEM_CHECK)
        ctxmenu.Append(self.ID_ROInumber, 'Show ROI number', '', wx.ITEM_CHECK)
        ctxmenu.Append(self.ID_ROIoutlines, 'Show ROI outlines while drawing', '', wx.ITEM_CHECK)
        ctxmenu.Check(self.ID_ROI, self.ROImode)
        ctxmenu.Check(self.ID_ROInumber, self.ROInumbers)
        ctxmenu.Check(self.ID_ROIoutlines, self.ROIoutlines)
        ctxmenu.AppendSeparator()
        ctxmenu.Append(self.ID_ch0, '(1) Raw frames (not aligned)', '', wx.ITEM_RADIO)
        ctxmenu.Append(self.ID_ch1, '(2) dF/F movie', '', wx.ITEM_RADIO)
        ctxmenu.Append(self.ID_ch2, '(3) F', '', wx.ITEM_RADIO)
        ctxmenu.Append(self.ID_ch3, '(4) dF/F map', '', wx.ITEM_RADIO)
        ctxmenu.Append(self.ID_ch4, '(5) Anatomy (all frames in trial)', '', wx.ITEM_RADIO)
        ctxmenu.Append(self.ID_ch5, '(6) Trial average F', '', wx.ITEM_RADIO)
        ctxmenu.Append(self.ID_ch6, '(7) Trial average dF/F map', '', wx.ITEM_RADIO)
        ctxmenu.Append(self.ID_ch7, '(8) Average projection (all stimuli)', '', wx.ITEM_RADIO)
        ctxmenu.Append(self.ID_ch8, '(9) Max projection (all stimuli)', '', wx.ITEM_RADIO)
        ctxmenu.Check(self.ID_ch0, self.TVch==0)
        ctxmenu.Check(self.ID_ch1, self.TVch==1)
        ctxmenu.Check(self.ID_ch2, self.TVch==2)
        ctxmenu.Check(self.ID_ch3, self.TVch==3)
        ctxmenu.Check(self.ID_ch4, self.TVch==4)
        ctxmenu.Check(self.ID_ch5, self.TVch==5)
        ctxmenu.Check(self.ID_ch6, self.TVch==6)
        ctxmenu.Check(self.ID_ch7, self.TVch==7)
        ctxmenu.Check(self.ID_ch8, self.TVch==8)
        ctxmenu.Enable(self.ID_ch1, ('dFoFfil' in self.imgdict.keys()))
        ctxmenu.Enable(self.ID_ch7, ('avg projection' in self.imgdict.keys()))
        ctxmenu.Enable(self.ID_ch8, ('max projection' in self.imgdict.keys()))

        if self.ROImode:
            ctxmenu.AppendSeparator()
            ctxmenu.Append(self.ID_ClearROI, 'Clear all ROIs')
            ctxmenu.Append(self.ID_PasteROIs, 'Import ROIs from clipboard')
            if self.parent.appendROI.IsChecked():
                ctxmenu.Append(self.ID_ROIimport, 'Load && Append ROIs from a mat file')
            else:
                ctxmenu.Append(self.ID_ROIimport, 'Load && Initialize ROIs from a mat file')
            ctxmenu.AppendSeparator()
            if self.ROI.data != []:
                ctxmenu.Append(self.ID_CopyROIs, 'Export ROIs to clipboard')
            if self.ROI.data != []:
                ctxmenu.Append(self.ID_ROIexport, 'Save ROIs to a mat file')
                ctxmenu.Append(self.ID_ROIsort, 'Sort ROIs')
                ctxmenu.Append(self.ID_PrintROIs, 'Print ROI data')
            if self.ROI.data != []:
                ctxmenu.AppendSeparator()
                ctxmenu.Append(self.ID_baseline, 'Baseline on/off', '', wx.ITEM_CHECK)
                ctxmenu.Check(self.ID_baseline, self.baseline)
                ctxmenu.Append(self.ID_plot, 'Quick dF/F traces plot (Q)')
                ctxmenu.Append(self.ID_plotraw, 'Raw fluorescent traces plot')
                ctxmenu.Append(self.ID_report, 'Summary PDF, export to MATLAB')

        if 'hist' in self.imgdict:
            fp, offsets = self.changetitle(wantfp_offset=True)
            if type(fp) != list:
                if fp in self.imgdict['hist']:
                    ctxmenu.Append(self.ID_hist, 'Show pixel value histogram')

        ctxmenu.AppendSeparator()
        ctxmenu.Append(self.ID_saveBMP, 'Export image as BMP')
        ctxmenu.Append(self.ID_copyBMP, 'Copy image to clipboard (Ctrl+C)')
        ctxmenu.Append(self.ID_recmovie, 'Record a movie', '', wx.ITEM_CHECK)
        ctxmenu.Check(self.ID_recmovie, self.record)

        ctxmenu.AppendSeparator()
        ctxmenu.Append(self.ID_AutoPSF, 'AutoPSF')

        if CntxPlugin.keys() != []:

            ctxmenu.AppendSeparator()

            for _id in CntxPlugin.keys():
                key = CntxPlugin[_id][1]
                ctxmenu.Append(_id, key)
                self.Bind(wx.EVT_MENU, self.Plugin, id=_id)

        self.PopupMenu(ctxmenu)
        ctxmenu.Destroy()

    def OnCtxOpenFolder(self, event):

        if self.TVch in [2,3,4,7,8]: # F, each dF/F map, anatomy
            data_path = self.tag[self.curframe][-1]
        elif self.TVch in [5,6]: # avg odor maps, avg_F
            z, odorname = self.imgdict['avg_odormap odornames'][self.curframe]
            eachplane = [ tag for tag in self.tag if z == tag[1] and tag[2] == odorname]
            data_path = eachplane[0][-1]
        else: # [0] raw or [1] dF/F filtered
            zsize = self.z / len(self.tag)
            _tag = self.tag[int(self.curframe / zsize)]
            data_path = _tag[-1]

        webbrowser.open(data_path)

    def OnCtxAutoPSF(self, event):

        # prepare the figure window
        dlg = beads_param(self.parent)
        dlg.CentreOnParent()

        if dlg.ShowModal() == wx.ID_OK:
            blobthrs = float( dlg.blobthrs.GetValue() )
            blobsize = float( dlg.blobsize.GetValue() )
            zstep = float( dlg.zstep.GetValue() )
            ROImax = int( dlg.ROImax.GetValue() )
            self.autoPSFplot(blobthrs, blobsize, zstep, ROImax)
            dlg.Destroy()

    def OnCtxRec(self, event):

        if myOS != 'Windows':
            'only windows suported at the moment'
            return

        if self.record:
            # cancel rec
            self.record = False
            self.p.stdin.close()
            self.zoominbtn.Enable(True)
            self.zoomoutbtn.Enable(True)
            self.playbtn.SetBitmapLabel(self.play_bmp)

        else:
            dlg = Movie_dialog(self)
            dlg.CentreOnParent()
            self.SetFocus()

            if dlg.ShowModal() == wx.ID_OK:
                qscale = str(dlg.slider.GetValue())
                vrate = dlg.vrate.GetValue()
                dlg.Destroy()

                defaultDir = path_check(self.imgdict['data_path'])
                defaultFile = 'movie.avi'
                dlg = wx.FileDialog(self,
                                message="Save movie as ...",
                                defaultDir=defaultDir,
                                defaultFile=defaultFile,
                                wildcard='movei files (*.avi)|*.avi',
                                style=wx.SAVE
                                )

                if dlg.ShowModal() == wx.ID_OK:

                    avi_fp = dlg.GetPath()

                    cmdstring = ('resources/ffmpeg.exe',
                                '-y',
                                '-qscale', qscale,  # 1 best quality (variable bit rate). no noticiable change at 5 half the file size
                                '-r', vrate,
                                #'-s', '%dx%d' % (w, h),
                                '-an',                  # no sound
                                '-f', 'image2pipe',
                                '-vcodec', 'mjpeg',
                                '-i', 'pipe:',

                                #'-vcodec', 'libxvid',
                                '-vtag', 'xvid',
                                '-vcodec', 'mpeg4',

                                '-g', '200',
                                '-bf', '0',
                                avi_fp)

                    self.p = subprocess.Popen(
                                cmdstring,
                                stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, # for packing purpose, cant be None
                                stderr=subprocess.PIPE, # for packing purpose
                                bufsize=-1,
                                shell=False,
                                creationflags = CREATE_NO_WINDOW
                                )

                    dlg.Destroy()
                    self.record = True
                    self.playbtn.SetBitmapLabel(self.rec_bmp)
                    self.zoominbtn.Enable(False)
                    self.zoomoutbtn.Enable(False)
                else:
                    print 'caneled'
            else:
                print 'caneled'


    def OnCtxClearROIs(self, event):
        self.ROI = ROI()
        self.Refresh()

    def OnCtxCopyROIs(self, event):

        _id = event.GetId()
        if _id == self.ID_PasteROIs:
            do = wx.TextDataObject()
            if wx.TheClipboard.Open():
                wx.TheClipboard.GetData(do)
                wx.TheClipboard.Close()
            inputs = do.GetText()
            if inputs.startswith('[') and inputs.endswith(']'):
                _inputs = eval(inputs)
                # work around for now to import ROIs on different planes
                if len(_inputs[0]) == 2:
                    self.ROI = ROI()
                    for _z, _poly in _inputs:
                        self.ROI.add(_poly,_z)
                else: # default behav
                    z = self.changetitle(wantz=True)
                    self.ROI = ROI( _inputs, z )
            else:
                print 'No relevant text buffer'
        else:
            do = wx.TextDataObject()
            do.SetText(str(self.ROI.data))
            if wx.TheClipboard.Open():
                wx.TheClipboard.SetData(do)
                wx.TheClipboard.Close()

        self.Refresh()

    def OnCtxPrintROIs(self, event):
        self.parent.log.SetInsertionPointEnd()
        for n, data in enumerate(self.ROI.data):
            print n+1, self.ROI.z[n], data


    def OnCtxROImode(self, event):

        if not event:  # pressing 'x' key
            self.ROImode = self.ROImode is False
        else:
            id = event.GetId()
            if id == self.ID_lock:
                self.lock = self.lock is False
            elif id == self.ID_ROI:
                self.ROImode = self.ROImode is False
            elif id == self.ID_ROInumber:
                self.ROInumbers = self.ROInumbers is False
            elif id == self.ID_ROIoutlines:
                self.ROIoutlines = self.ROIoutlines is False
            elif id == self.ID_baseline:
                self.baseline = self.baseline is False
        self.changetitle()

    def OnCtxRadioChange(self, event):

        z = self.changetitle(wantz=True)
        id = event.GetId()
        # switch channel
        if id == self.ID_ch0:
            self.TVch = 0
        elif id == self.ID_ch1:
            self.TVch = 1
        elif id == self.ID_ch2:
            self.TVch = 2
        elif id == self.ID_ch3:
            self.TVch = 3
        elif id == self.ID_ch4:
            self.TVch = 4
        elif id == self.ID_ch5:
            self.TVch = 5
        elif id == self.ID_ch6:
            self.TVch = 6
        elif id == self.ID_ch7:
            self.TVch = 7
        elif id == self.ID_ch8:
            self.TVch = 8
        elif id == self.ID_ch9:
            self.TVch = 9

        self.img = self.imgdict[ img_keys[self.TVch] ]

        self.refreshch(z)
        self.refresh_buf()
        self.Refresh()

    def OnCtxSortROIs(self, event):

        txt = ['Specify the ROIs to move to the end or empty list for auto sorting by area',
                'Enter the new ROI index as a list (indexed from 1)']
        newind = self.ROIdialog(txt)
        self.ROI.sort(newind)
        self.Refresh()

    def ROIdialog(self, txt, defvalue='[]'):

        dlg = wx.TextEntryDialog(self,txt[0],txt[1])
        dlg.SetValue(defvalue)

        if dlg.ShowModal() == wx.ID_OK:
            inputs = dlg.GetValue()
            if inputs.startswith('[') and inputs.endswith(']'):
                newind = eval(inputs)
                if len(newind)>0:
                    newind = [ind-1 for ind in newind]
            elif inputs.startswith('(') and inputs.endswith(')'):
                newind = eval(inputs)

        dlg.Destroy()
        self.Refresh()
        return newind

    def saveBMP(self, event):

        path = self.imgdict['data_path']
        
        fname = ''.join([ s if s not in ['*', ':', ' ', '.'] else '_' for s in self.GetTitle()])[1:]
        fp = os.path.join(path, os.path.basename(path)+fname+'.bmp')

        dlg = wx.FileDialog(self, message="Save as ...",
                defaultDir=os.getcwd(), defaultFile=fp,
                wildcard='All files (*.bmp)|*.bmp',
                style=wx.SAVE )

        if dlg.ShowModal() == wx.ID_OK:
            fp = dlg.GetPath()
            bmp = self.copyBMP(None)
            bmp.SaveFile(fp, wx.BITMAP_TYPE_BMP)

        dlg.Destroy()
        self.Refresh()

    def copyBMP(self, event):

        context = wx.ClientDC(self.display)
        memory = wx.MemoryDC()

        if context.Ok() and memory.Ok():
            w = self.w*self.ScalingFactor
            h = self.h*self.ScalingFactor
            bitmap = wx.EmptyBitmap(w,h,-1)

            memory.SelectObject(bitmap)
            memory.Blit(0,0, w,h, context, 2,2) # 2 for boarder of display panel
            memory.SelectObject(wx.NullBitmap)

            if event is not None:
                bmpdo = wx.BitmapDataObject(bitmap)
                if wx.TheClipboard.Open():
                    wx.TheClipboard.SetData(bmpdo)
                    wx.TheClipboard.Close()

            return bitmap

    def ROIio(self, event):

        _id = event.GetId()
        data_path = self.imgdict['data_path']
        fppdf = os.path.join(data_path,
                        os.path.basename(data_path)+
                        time.strftime('.mat'))
        wildcard = 'ROI data files (*.mat,*.npz)|*.mat;*_ROIs.npz'
        if _id == self.ID_ROIimport:
            dlg = wx.FileDialog(
                self, message='Load ...', defaultDir=data_path,
                defaultFile=fppdf, wildcard=wildcard,
                style=wx.FD_OPEN )
            if dlg.ShowModal() == wx.ID_OK:
                fp = dlg.GetPath()
                #_matD = matDrop(self)
                self.loadROI(fp)

        elif _id == self.ID_ROIexport:
            dlg = wx.FileDialog(
                self, message="Save file as ...", defaultDir=data_path,
                defaultFile=fppdf, wildcard=wildcard,
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
            if dlg.ShowModal() == wx.ID_OK:
                fp = dlg.GetPath()
                roicell, roiplane, roicategory = pack2npobj(self.ROI)
                dct = {'ROI_polygons':roicell, 'ROI_Field_of_views':roiplane, 'ROI_categories':roicategory}
                fname = os.path.basename(fp)[:-4]
                sname = self.validate_sname(fname)
                sio.savemat(fp,{sname : dct}, oned_as='row', do_compression=True)

        dlg.Destroy()
        self.Refresh()

    def OnShowHist(self, event):

        fp, Foffset = self.changetitle(wantfp_offset=True)
        a,b = self.imgdict['hist'][fp]

        figure = plt.figure(figsize=[6,4])

        if a[2:].sum():
            subplot2 = figure.add_subplot(122)
            subplot2.bar(b[2:-1], a[2:], width=40)
            subplot2.set_title('without first two bars')
            subplot2.set_xlabel('Bins)')
            subplot2.set_ylabel('Counts')
            subplot2.set_ylim( 0, int(a[2:].max()*1.1) )

            subplot1 = figure.add_subplot(121)
        else:
            subplot1 = figure.add_subplot(111)

        subplot1.bar(b[:-1], a, width=40)
        subplot1.set_title('all bars')
        subplot1.set_xlabel('Bins')
        subplot1.set_ylabel('Counts')
        subplot1.set_ylim( 0, int(a.max()) )
        figure.show()


    def OnQuickPlot(self, event):

        if self.ROI.data == []:
            print 'no ROIs found.'
            return
        
        global ch, ref_ch
        ch_bak, ref_ch_bak = ch, ref_ch
        ch, ref_ch = self.ch, self.ref_ch

        self.plotbtn.Enable(False)

        Fnoise = self.parent.ParamsPane.sc_Fnoise.GetValue()
        raw = (event.GetId() == self.ID_plotraw)

        fp, Foffset = self.changetitle(wantfp_offset=True)
        if type(fp) == list and type(Foffset) == list:  # ploting for "avg odormaps"
            eachplane = fp
            ROIfound, ROIpolys = [], []
            z = self.changetitle(wantz=True)
            for n,zz in enumerate(self.ROI.z):
                if zz == z:
                    ROIfound.append(n+1)
                    ROIpolys.append(self.ROI.data[n])
            Foffset = np.array(Foffset)
            Foffset[:,0] = -Foffset[:,0] # flix y-axis for shift function

            dFoF = ComputeThisPlane(
                                    data_path=self.imgdict['data_path'], 
                                    tags=eachplane, 
                                    # most are dummy when ROIpoly_n is provided
                                    howmanyframe=0,
                                    need_AvgTr=False, 
                                    need_MaxPr=False,
                                    anatomy_method=False,
                                    Fnoise=Fnoise, # !important
                                    fastLoad=False,
                                    verbose=verbose, # !important
                                    durpre=durpre, # !important
                                    durres=durres, # !important
                                    ch=ch,         # !important
                                    ref_ch=ref_ch, 
                                    reftr=None,
                                    margin=margin,
                                    # these 3 ask for dF/F or raw traces for ROIs
                                    ROIpoly_n=(ROIpolys, ROIfound),
                                    Foffsets=Foffset,
                                    wantsraw=raw )

        else:
            dFoF, ROIfound = self.getdFoF(fp, dtype=np.uint16, offset=Foffset, raw=raw, Fnoise=Fnoise)

        if ROIfound == []:
            return

        # plotting
        self.changetitle()
        title = 'Quick plot ' + self.GetTitle()

        figure = plt.figure(figsize=[6,3.5])

        subplot = figure.add_subplot(111)
        self.plot(subplot, dFoF, raw=raw, label=ROIfound)

        plt.tight_layout()
        figure.show()


        if verbose:
            if npz: # numpy friendly output
                pprint (dFoF.T)
            else:  # MATLAB friendly output
                print dFoF.T

        ch, ref_ch = ch_bak, ref_ch_bak

        self.plotbtn.Enable(True)

    def getdFoF(self, fp, dtype=np.uint16, offset=None, z=False, raw=False, Fnoise=0):

        if z is False:
            z = self.changetitle(wantz=True) # get current plane
        

        masks = []
        ROIfound = []
        for n, poly in enumerate(self.ROI.data):
            if self.ROI.z[n] == z:
                ROIfound.append(n+1)
                mask = getmask(poly, (self.h, self.w))
                if offset is not None:
                    y,x = offset
                    mask = np.roll(mask, int(y), axis=0)  # Pymagor2.0 -y 1.0 y
                    mask = np.roll(mask, int(x), axis=1)
                masks.append(mask)

        if fp.endswith(('tif','ior')):  # now opentif takes care of ior also
            img = opentif(fp, dtype=dtype, filt=None, ch=self.ch)
            if Autoalign:
                data_path = self.imgdict['data_path']
                fname = os.path.basename(fp)
                withinTrOffsets = get_offset_within_trial_img(
                    img, data_path, fname, durpre, margin, (SpatMed, SpatMed2), Fnoise)
                img = Shift(img.copy(), withinTrOffsets)
        else:
            return None, None
        
        if masks:
            dFoFtraces = getdFoFtraces(img, durpre, masks, raw=raw, baseline=self.baseline, Fnoise=Fnoise)
            return dFoFtraces, ROIfound
        else:
            return None, None


    def export(self, event):

        if verbose:
            print self.tag

        if self.ROI.data == []:
            self.parent.showmessage('At least one ROI is required for export')
            return

        data_path = path_check(self.imgdict['data_path'])

        defaultDir = None

        self.curframe = 0
        if self.Launcher:
            defaultDir = path_check(os.path.dirname(self.Launcher.csvname))
        if defaultDir == None:
            defaultDir = data_path

        fppdf = 'pymg_'+os.path.basename(data_path)+'.pdf'
        dlg = wx.FileDialog( self, message='Save file as ...',
                defaultDir=defaultDir, defaultFile=fppdf,
                wildcard='All files (*.*)|*.pdf',
                style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT )

        if dlg.ShowModal() == wx.ID_OK:

            print 'Saving a PDF summary and data as mat/npz files...'
            fname = dlg.GetPath()
            if not fname.endswith('pdf'):
                fname[:-3] = 'pdf'

            Pooled = self.PDF(fname, data_path)
            self.savemat(fname, Pooled)

        dlg.Destroy()
        
        dlg = wx.MessageDialog(None, 'Exported successfully. Close plots?', style=wx.YES_NO)
        if dlg.ShowModal() == wx.ID_YES:
            self.Parent.OnCloseAll(None)
        dlg.Destroy()

        # generating PDF means the user like the current parameters. Let's update durpre, durres, Fnoise 
        # settings stored in offset file, by calling this with None to img arg
        Fnoise = self.parent.ParamsPane.sc_Fnoise.GetValue()
        print Fnoise
        get_offset_within_trial_img(None, data_path, 'dummy', durpre, margin, (SpatMed, SpatMed2), Fnoise)


    def PDF(self, fname, data_path):
        " generate a PDF report "

        pp = PdfPages(fname)
        size = (560,420)
        nfiles = len(self.tag)
        ncol = np.ceil(np.sqrt(nfiles))
        nrow = np.ceil(nfiles/ncol)
        Fnoise = self.parent.ParamsPane.sc_Fnoise.GetValue()
        _figsize = [9.9,7] # A4 paper aspect ratio of sqrt(2)
        colors = ('b', 'g', 'r', 'c', 'm', 'y')
        

        def gethilo(frame):
            if self.ManScaling.IsChecked():
                Hi = self.scH.GetValue()
                Lo = self.scL.GetValue()
            else:
                Hi = frame.max()
                Lo = frame.min()
            return Hi,Lo

        def myimshow(figure, ax, frame, title=''):
            if len(frame.shape) == 2:   # gray scale image
                mappable = ax.imshow(frame, cmap=matplotlib.cm.gray)
                lo, hi = frame.min(), frame.max()
                ticks = [lo, (hi-lo)/2+lo, hi]
                clabel = [lo, (hi-lo)/2+lo, hi]
            else:                       # color image
                mappable = ax.imshow(frame)
                clabel = [cmin, (cmax-cmin)/2+cmin, cmax]
                ticks = [255*(a-cmin)/(cmax-cmin) for a in clabel]
                clabel = ['%3.1f%%' % a for a in clabel]
            ax.axis('off')
            ax.set_title(title, fontsize=min_fontsize)
            if self.parent.export_transpose_collage.IsChecked():
                _orientation = 'horizontal'
            else:
                _orientation = 'vertical'
            cbar = figure.colorbar(mappable, ticks=ticks, 
                    orientation=_orientation, fraction=0.049, pad=0.02)
            cbar.ax.set_xticklabels(clabel)
            cbar.ax.tick_params(labelsize=min_fontsize)
            cbar.outline.set_visible(False)

        # Last but one to show ROIs for each plane on large anatomy canvas
        seen = set() # this way we can preserve the original order which np.unique will destroy 
        uniquePlanes = [x for x in [t[1] for t in self.tag] if x not in seen and not seen.add(x)]

        for z in uniquePlanes:
            # just pick the first matching plane tag
            _ind = [n for n,t in enumerate(self.tag) if t[1] == z][0]
            
            ROIdistribution = plt.figure(figsize=_figsize)
            axROIdst = ROIdistribution.add_subplot(111)
            frame = self.imgdict['anatomy'][::-1,:,_ind]
            frame[frame==0] = frame[frame.nonzero()].min()
            Hi, Lo = gethilo(frame)
            frame = self.manualscale(frame, Hi, Lo)

            title = 'ROI distribution %s' % fname
            myimshow(ROIdistribution, axROIdst, frame, title)
            fontsize = int(min_fontsize+(30-nfiles)/30)-(len(title)>25)
            for ind2, roi in enumerate(self.ROI.data):
                color = colors[np.mod(ind2,6)]
                if self.ROI.z[ind2] == z:
                    roi = [(x-0.5,y-0.5) for x,y in roi] # -0.5 seems needed for the difference between vector and image
                    axROIdst.add_patch(Polygon(roi, edgecolor=color, closed=True, fill=False))
                    x, y = np.median(np.array(roi), axis=0)
                    axROIdst.text(x*1.15, y, str(ind2+1), color=color, fontsize=fontsize)
            plt.tight_layout()
            ROIdistribution.canvas.draw()
            ROIdistribution.savefig(pp, format='pdf')
            if self.parent.export_needplotting.IsChecked():
                ROIdistribution.show()

        # prepare collage which comes after pages for individual trials
        collage = plt.figure(figsize=_figsize)
        collage.suptitle('Response maps')

        dFoFtracesPool = []
        rawtracesPool = []
        for ind, tag in enumerate(self.tag):

            if os.path.exists(tag[-1]): # pymagor2
                fp = os.path.join(tag[-1], tag[0])
            else:
                fp = os.path.join(data_path, tag[0])
            print 'Processing: ', fp
            if type(self.imgdict['Foffset']) == int:
                Foffset = None
            else:
                Foffset = self.imgdict['Foffset'][ind,0:2]

            z = self.tag[ind][1]
            dFoFtraces, ROIfound = self.getdFoF(fp, np.uint16, offset=Foffset, z=z, Fnoise=Fnoise)
            rawtraces, ROIfound = self.getdFoF(fp, np.uint16, offset=Foffset, z=z, raw=True, Fnoise=Fnoise)
            title = ', '.join(tag[1:3])[:21] + ', ' + tag[3]

            eachtrial = plt.figure(figsize=_figsize)
            eachtrial.suptitle(title)

            subplot1 = eachtrial.add_subplot(221)
            frame = self.imgdict['F'][::-1,:,ind]
            frame[frame==0] = frame[frame.nonzero()].min()
            Hi, Lo = gethilo(frame)
            frame = self.manualscale(frame, Hi, Lo)
            myimshow(eachtrial, subplot1, frame, os.path.basename(os.path.dirname(fp)))

            subplot2 = eachtrial.add_subplot(222)
            bmp = gray2clut2b(self.imgdict['dFoFavg'][::-1,:,ind].copy(), cmin, cmax)
            myimshow(eachtrial, subplot2, bmp, os.path.basename(fp))

            
            found_ROIs = []
            fontsize = int(min_fontsize+(30-nfiles)/30)-(len(title)>25)
            
            for ind2, roi in enumerate(self.ROI.data):
                color = colors[np.mod(ind2,6)]
                if self.ROI.z[ind2] == self.tag[ind][1]:
                    found_ROIs.append(ind2+1)
                    roi = [(x-0.5,y-0.5) for x,y in roi]
                    subplot1.add_patch(Polygon(roi, edgecolor=color, closed=True, fill=False))
                    subplot2.add_patch(Polygon(roi, edgecolor=color, closed=True, fill=False))
                    x, y = np.median(np.array(roi), axis=0)
                    # subplot1.text(x*1.15+self.w, y, str(ind2+1), color=color, fontsize=fontsize)

            dFoFtracesPool.append([dFoFtraces, z, found_ROIs])
            rawtracesPool.append([rawtraces, z, found_ROIs])

            subplot = eachtrial.add_subplot(212)
            if dFoFtraces is not None:
                sb_trace = self.plot(subplot, dFoFtraces, label=found_ROIs)
            subplot.set_title(title)
            plt.tight_layout()

            if self.parent.export_eachfile.IsChecked():
                eachtrial.savefig(pp, format='pdf')
            if self.parent.export_needplotting.IsChecked():
                eachtrial.show()

            wx.Yield()

            # use this bmp for collage
            if self.parent.export_transpose_collage.IsChecked():
                cllg = collage.add_subplot(int(ncol), int(nrow), ind+1)
            else:
                cllg = collage.add_subplot(int(nrow), int(ncol), ind+1)
            cllg.imshow(bmp)
            cllg.set_title(title, fontsize=fontsize)
            cllg.title.set_y(0.95)
            collage.canvas.draw()
            cllg.axis('off')
            plt.tight_layout()

        collage.savefig(pp, format='pdf')
        if self.parent.export_needplotting.IsChecked():
            collage.show()

        ## Last two pages   summary of F and dF/F avg fil
        # average across trials for each odor

        collage_avg = plt.figure(figsize=_figsize)
        collage_avg.suptitle('Averaged response maps for each plane-stimlus pair')

        collage_F = plt.figure(figsize=_figsize)
        collage_F.suptitle('F for each plane-stimulus pair')

        Z_Odor = [(t[1],t[2]) for t in self.tag]
        seen = set()
        Z_Odor = np.array([x for x in Z_Odor if x not in seen and not seen.add(x)])
        #print Z_Odor, Z_Odor.size
        ## convert odor names of concentrtion series to sortable numbers (assuming only one odor has a conc series)

        #print np.__version__, versiontuple(np.__version__), Z_Odor

        ## odor centered (no concentration series)
        if self.parent.export_group_odor.IsChecked():
            odors = np.sort(np.unique(Z_Odor[:,1]))
            index2 = ([n for n,(z,o) in enumerate(Z_Odor) if o == odor] for odor in odors)
            index = [ind for sub in index2 for ind in sub]

        # plane centered (default. odor concentration series considered)
        else:
            if np.all([z.startswith('z') for z,o in Z_Odor]):
                print 'z prefix found. convert plane names to numbers following z'
                try:
                    planes = z_prefix( Z_Odor[:,0] )
                except:
                    planes = Z_Odor[:,0]
            else:
                planes = Z_Odor[:,0]
            odors = [int(re.search('10(\-)[0-9]+M', z).group(0)[2:-1])
                    if re.search('10(\-)[0-9]+M', z) is not None else n*100
                    for n, (z,o) in enumerate(Z_Odor)]
            index = np.lexsort((odors, planes))

        ncol = np.ceil(np.sqrt(len(Z_Odor)))
        nrow = np.ceil(len(Z_Odor)/ncol)

        data_path = self.imgdict['data_path']
        durs = (self.imgdict['durpre'], self.imgdict['durres'])
        avgdFoF_acrosstrials = []
        avgF_acrosstrials = []
        names4avgdFoF_acrosstrials = []
        avg_tracesP = []

        #print Z_Odor, index, Z_Odor[index]

        for ind2, (z, odor) in enumerate(Z_Odor[index]):
            _ind = [n for n,t in enumerate(self.tag) if t[1] == z and t[2] == odor]
            tag = [self.tag[__ind] for __ind in _ind]

            Foffset = np.array([self.imgdict['Foffset'][__ind,:] for __ind in _ind])
            Foffset[:,0] = -Foffset[:,0]

            ROIpolys = [roi for roi,zz in zip(self.ROI.data, self.ROI.z) if zz == z]
            found_ROIs = [n+1 for n, zz in enumerate(self.ROI.z) if zz == z]

            results = ComputeThisPlane(
                                    data_path=data_path, 
                                    tags=tag, 
                                    howmanyframe=0,
                                    need_AvgTr=False, 
                                    need_MaxPr=False,
                                    anatomy_method=False,
                                    Fnoise=Fnoise, # !important
                                    fastLoad=False,
                                    verbose=verbose, # !important
                                    durpre=durs[0], # !important
                                    durres=durs[1], # !important
                                    ch=ch,         # !important
                                    ref_ch=ref_ch, 
                                    reftr=None,
                                    margin=margin,
                                    )
            F, dFoFmap, odornames = results[-3:]  # last 3 contain what we want

            avg_traces = ComputeThisPlane(
                                    data_path=data_path, 
                                    tags=tag, 
                                    # most are dummy when ROIpoly_n is provided
                                    howmanyframe=0,
                                    need_AvgTr=False, 
                                    need_MaxPr=False,
                                    anatomy_method=False,
                                    Fnoise=Fnoise, # !important
                                    fastLoad=False,
                                    verbose=verbose, # !important
                                    durpre=durs[0], # !important
                                    durres=durs[1], # !important
                                    ch=ch,         # !important
                                    ref_ch=ref_ch, 
                                    reftr=None,
                                    margin=margin,
                                    # these 3 ask for dF/F or raw traces for ROIs
                                    ROIpoly_n=(ROIpolys, found_ROIs),
                                    Foffsets=Foffset,
                                    wantsraw=False )


            avgdFoF_acrosstrials.append( dFoFmap )
            avgF_acrosstrials.append( F )
            names4avgdFoF_acrosstrials.append( (z,odor) )
            avg_tracesP.append([avg_traces, z, found_ROIs, odornames])

            bmp = gray2clut2b(dFoFmap[::-1,:,0].copy(), cmin, cmax)
            title = ', '.join(tag[0][1:3])[:42]

            if self.parent.export_transpose_collage.IsChecked():
                cllg = collage_avg.add_subplot(int(ncol), int(nrow), ind2+1)
            else:
                cllg = collage_avg.add_subplot(int(nrow), int(ncol), ind2+1)
            cllg.imshow(bmp)
            cllg.set_title(title, fontsize=fontsize)
            cllg.axis('off')

            if self.parent.export_transpose_collage.IsChecked():
                cllg2 = collage_F.add_subplot(int(ncol), int(nrow), ind2+1)
            else:
                cllg2 = collage_F.add_subplot(int(nrow), int(ncol), ind2+1)
            F[F==0] = F[F.nonzero()].min()
            Hi, Lo = gethilo(F[::-1,:,0])
            cllg2.imshow(self.manualscale(F[::-1,:,0], Hi, Lo), cmap=matplotlib.cm.gray)
            cllg2.set_title(title, fontsize=fontsize)
            cllg2.axis('off')

            # avg traces
            if self.parent.export_avgtraces.IsChecked():
                avg_trace_fig = plt.figure(figsize=_figsize)
                avg_trace_fig.suptitle(title)

                subplot1 = avg_trace_fig.add_subplot(221)
                Hi, Lo = gethilo(F[::-1,:,0])
                frame = self.manualscale(F[::-1,:,0], Hi, Lo)
                myimshow(avg_trace_fig, subplot1, frame, title)

                subplot2 = avg_trace_fig.add_subplot(222)
                myimshow(avg_trace_fig, subplot2, bmp)

                subplot3 = avg_trace_fig.add_subplot(212)
                if avg_traces.shape[1] > 0:
                    self.plot(subplot3, avg_traces, label=found_ROIs)
                subplot3.set_title(title)

                plt.tight_layout()
                avg_trace_fig.savefig(pp, format='pdf')
                if self.parent.export_needplotting.IsChecked():
                    #avgtraces.Show(True)
                    avg_trace_fig.show()


        txt='Pymagor v%s (rev %s)\ndurpre = [%d, %d], durres = [%d, %d]\nBackground noise offset= %d;margin ' % (release_version,__version__, durpre[0],durpre[1],durres[0],durres[1], Fnoise)
        txt += ', '.join([': '.join((key,str(item))) for key,item in self.imgdict['margin'].items()])
        cllg2.annotate(txt, (0,0), xytext=(0.03, 0.03), textcoords='figure fraction', fontsize=7)

        collage_avg.savefig(pp, format='pdf')
        collage_F.savefig(pp, format='pdf')
        if self.parent.export_needplotting.IsChecked():
            collage_avg.show()
            collage_F.show()

        pp.close()

        return dFoFtracesPool, rawtracesPool, avgdFoF_acrosstrials, \
            avgF_acrosstrials, names4avgdFoF_acrosstrials, avg_tracesP


    def savemat(self, fname, Pooled):
        """ saving into mat file """

        dFoFtracesPool, rawtracesPool, avgdFoF_acrosstrials, \
        avgF_acrosstrials, names4avgdFoF_acrosstrials, avg_tracesP = Pooled

        # sanity check for frame number consistency
        if len(np.unique([d.shape[0] for d,z,r in dFoFtracesPool if d is not None])) > 1:
            txt = 'The frame rates are not consistent across all files. abort mat file saving.'
            MainFrame.showmessage(self.parent, txt)
            return

        # putting tag into a MATLAB cell
        tagcell = np.zeros((len(self.tag), len(self.tag[0])), dtype=np.object)
        for ind, tag in enumerate(self.tag):
            for ind2, t in enumerate(tag):
                tagcell[ind, ind2] = t

        Foffset = self.imgdict['Foffset'].copy()

        names4eachtrialCell = np.zeros(len(self.tag), dtype=np.object)
        names4eachtrialCell[:] = [ele[2] for ele in self.tag]
        names4avgdFoF_acrosstrialsCell = np.zeros((len(names4avgdFoF_acrosstrials),), dtype=np.object)
        names4avgdFoF_acrosstrialsCell[:] = names4avgdFoF_acrosstrials

        # traces into MATLAB cell with plane and roi# info
        uniq_z = set([z for d,z,r in dFoFtracesPool if d is not None])
        dFoFtracesCell = np.zeros( (len(uniq_z), 4), dtype=np.object )
        rawtracesCell = np.zeros( (len(uniq_z),  4), dtype=np.object )
        avg_tracesCell = np.zeros( (len(uniq_z), 4), dtype=np.object )


        for n, zz in enumerate(uniq_z):
            dFoFtemp = [d for d,z,r in dFoFtracesPool if z == zz and d is not None]
            rawtemp = [d for d,z,r in rawtracesPool if z == zz and d is not None]
            avg_tracestemp = [d for d,z,r,o in avg_tracesP if z == zz and d is not None]
            odors = [o for z,o in names4avgdFoF_acrosstrials if z==zz]
            odorsCell = np.array(odors, dtype=np.object)

            roin = [r for d,z,r in dFoFtracesPool if z == zz and d is not None]
            print 'Packing dF/F traces for ROIs %s on the plane %s' % (roin[0], zz)

            if len(dFoFtemp)>1:
                dFoFtracesCell[n,0] = np.dstack(dFoFtemp)
                rawtracesCell[n,0] = np.dstack(rawtemp)
                avg_tracesCell[n,0] = np.dstack(avg_tracestemp)
            else:
                nframes, ncells = dFoFtemp[0].shape
                dFoFtracesCell[n,0] = dFoFtemp[0].reshape(nframes, ncells, 1)
                rawtracesCell[n,0] = rawtemp[0].reshape(nframes, ncells, 1)
                avg_tracesCell[n,0] = avg_tracestemp[0].reshape(nframes, ncells, 1)

            dFoFtracesCell[n,1] = zz
            dFoFtracesCell[n,2] = roin[0]
            dFoFtracesCell[n,3] = names4eachtrialCell
            rawtracesCell[n,1] = zz
            rawtracesCell[n,2] = roin[0]
            rawtracesCell[n,3] = names4eachtrialCell
            avg_tracesCell[n,1] = zz
            avg_tracesCell[n,2] = roin[0]
            avg_tracesCell[n,3] = odorsCell

        matpoly, matplane, matctgr = pack2npobj(self.ROI)

        if not self.imgdict.has_key('avg projection'):
            self.imgdict['avg projection'] = np.zeros((1,1,1))
        if not self.imgdict.has_key('max projection'):
            self.imgdict['max projection'] = np.zeros((1,1,1))

        dct =   {
                'meta' : {
                    'version' : release_version,
                    'data_path': self.imgdict['data_path'],
                    'tag': tagcell,
                    'durpre': self.imgdict['durpre'],
                    'durres': self.imgdict['durres'],
                    'Foffset': Foffset,
                    },
                'img_eachtrial' : {
                    'F' : self.imgdict['F'][::-1,:,:],
                    'anatomy' : self.imgdict['anatomy'][::-1,:,:],
                    'resmap' : self.imgdict['dFoFavg'][::-1,:,:],
                    },
                'img_trailavg' : {
                    'F_avg' : np.dstack(avgF_acrosstrials)[::-1,:,:],
                    'resmap_avg' : np.dstack(avgdFoF_acrosstrials)[::-1,:,:],
                    'stim_labels_avg' : names4avgdFoF_acrosstrialsCell,
                    },
                'projections' : {
                    'avg_projection': self.imgdict['avg projection'][::-1,:,:],
                    'max_projection': self.imgdict['max projection'][::-1,:,:]
                    },
                'traces' : {
                    'traces' : dFoFtracesCell,
                    'traces_raw' : rawtracesCell,
                    'traces_avg' : avg_tracesCell,
                    },
                'ROIs' : {
                    'ROI_polygons' : matpoly,
                    'ROI_Field_of_views' : matplane,
                    'ROI_categories' : matctgr,
                    }
                }
        sname = self.validate_sname(os.path.basename(fname[:-4]))

        if npz:
            np.savez_compressed(fname[:-4]+'_meta.npz', **dct['meta'])
            np.savez_compressed(fname[:-4]+'_img_eachtrial.npz', **dct['img_eachtrial'])
            np.savez_compressed(fname[:-4]+'_img_trailavg.npz', **dct['img_trailavg'])
            np.savez_compressed(fname[:-4]+'_projections.npz', **dct['projections'])
            np.savez_compressed(fname[:-4]+'_traces.npz', **dct['traces'])
            np.savez_compressed(fname[:-4]+'_ROIs.npz', **dct['ROIs'])
        else:
            fname = fname[:-3]+'mat'
            sio.savemat(fname, {sname : dct}, oned_as='row', do_compression=mat_compress)
        print 'successfully saved as '+fname
    

    def validate_sname(self, name):

        if name.startswith('pymg'):
            return name.replace('-','_').replace(' ','_')
        else:
            return 'pymg'+name.replace('-','_').replace(' ','_')


    # EVENTS

    def OnQuit(self, event):
        self.abortEvent.set()
        self.Destroy()

    def OnTimer(self, event):

        if self.playing:
            if self.curframe < self.scz.GetMax():
                self.curframe += 1
            elif self.curframe == self.scz.GetMax():
                self.playing = False

                if self.record:
                    #print 'closed p'
                    self.p.stdin.close()
                    self.record = False
                    self.zoominbtn.Enable(True)
                    self.zoomoutbtn.Enable(True)

                if self.parent.verbose.IsChecked():
                    dt = time.time()-self.t0
                    dfr = self.z - self.st_fr
                    print '{0} s for {1} frames = {2} fps'.format(
                                dt, dfr, dfr/dt)
                self.curframe = self.b4play
                self.playbtn.SetBitmapLabel(self.play_bmp)

            self.scz.SetValue(self.curframe)
            self.refresh_buf()
            self.Refresh(False)

    def OnResizeBorder(self, event):  # EVT_SIZE on self
        if not self.placing:
            self.need_resize = True

    def OnCheckSize(self, event): # EVT_ENTER_IDLE on self
        if self.need_resize:
            self.frame_resize(event)

    def checkhist(self, fp):
        if not self.workers[fp]:
            self.workers[fp] = True
            self.abortEvent.clear()
            self.jobID += 1
            delayedresult.startWorker(
                            self._resultConsumer,
                            self.gethist,
                            wargs=(self.jobID, self.abortEvent, fp),
                            jobID=self.jobID    )

    def gethist(self, jobID, abortEvent, fp):
        a, b = opentif(fp, frames2load=False, check8bit=abortEvent)
        return fp, a, b

    def _resultConsumer(self, delayedResult):
        jobID = delayedResult.getJobID()
        #assert jobID == self.jobID  # dont really need this
        try:
            fp, a,b = delayedResult.get()
        except Exception, exc:
            print "Result for job %s raised exception: %s" % (jobID, exc)
            return

        self.imgdict['hist'][fp] = (a,b)
        if a.sum()>0:
            rate = 100.0 * a[:4].sum() / a.sum()
            if verbose:
                print '8-bit coverage (%s) = %f (%%)' % (fp, rate)
                print ', '.join(['%d-%d: %d' % (b[n], b[n+1], aa) for n, aa in enumerate(a) if aa][2:] )
            if rate < 99.75 and self.imgdict['fastLoad']:
                MainFrame.showmessage(self.parent, (
                'Image data is not in 8-bit range (255).\n'+
                'Re-open with \"Load as unit8\" box uncheched.'))
        else:
            if verbose:
                print '8-bit coverage (%s) = 0 (%%)'


    def OnMouse(self, event):    # ALL mouse events on display

        event.Skip() # important

        if self.playing:
            return

        nx, ny = self.normxy(event)
        delta = event.GetWheelRotation()
        if delta:
            delta = delta/abs(delta)  # limit to -1 to +1 range

        if (not event.IsButton() and ## only when mouse moved
            event.GetWheelDelta() == 0):
            # print 'OnMouse nx, ny', nx, ny
            self.curx, self.cury = nx, ny # update current position
            self.refresh_buf()

        ## scaling frame mode
        elif self.scaling and delta:  # mouse did not move then...
            self.ScalingFactor *= 1.2 ** delta
            self.frame_resize(event)

        ## zooming mode
        if self.zoomingmode:
            if event.LeftDown() and self.st_x is None:  # state change (not LeftIsDown)
                self.st_x, self.st_y = nx, ny
                #print 'zooming rect drawing started'
            elif event.LeftUp() and self.st_x is not None and self.st_y is not None:  
                # LeftUp is for state change flag (LeftIsUp for status)
                # self.st_x can be 0 which is valid input so check if it's None
                # cancel when too small 
                if self.st_x-2 < nx < self.st_x+2 and self.st_y-2 < ny < self.st_y+2:
                    self.zoomrect = (0,0,self.w,self.h)
                else:
                    ex, ey = self.assure_box(nx, ny)
                    self.zoomrect = (self.st_x, self.st_y, ex, ey)
                    self.st_x = self.st_y = None
                self.OnZoomMode(None)
            elif self.st_x is not None:
                self.curx, self.cury = self.assure_box(nx, ny)
                self.refresh_buf()

        ## panning mode
        elif self.panmode:
            if event.LeftDown(): # start dragging
                self.st_x, self.st_y = nx, ny
                self.dx, self.dy = 0, 0
                self.dragging = True  # flag needed for draw()
            elif event.LeftUp(): # finish draggin
                self.dx = int(nx-self.st_x)
                self.dy = int(ny-self.st_y)
                self.refresh_buf(True)
                self.dragging = False
            elif self.dragging:  # while draggin
                self.dx = int(nx-self.st_x)
                self.dy = int(ny-self.st_y)
                self.refresh_buf()

        ## ROI drawing mode
        elif self.drawing:
            if event.LeftIsDown():
                self.roibuf.append((self.curx, self.cury))
        elif self.moving:
            if event.LeftDown(): # initialize dragging
                self.st_x, self.st_y = nx, ny
                self.dx, self.dy = 0, 0
            elif event.Dragging():
                roi_in = self.insideROI(nx,ny)
                dx = int(nx-self.st_x)
                dy = int(ny-self.st_y)
                self.ROI.shift((dx,dy), roi_in)
                self.st_x, self.st_y = nx, ny
        elif self.trashing:
            if event.LeftDown():
                roi_in = self.insideROI(nx,ny)
                self.ROI.remove(roi_in)
                self.refresh_buf()

        ## Z-Spin Control
        elif delta and event.RightIsDown():
            lo, hi = self.scz.GetMin(), self.scz.GetMax()
            if (lo < self.curframe and delta<0) or \
                (self.curframe<hi and delta>0):
                self.curframe += delta
                self.changetitle()
                self.scz.SetValue(self.curframe)
            self.refresh_buf()

        ## Flip gesture to switch TVch
        elif event.Dragging() and event.LeftIsDown():
            self.flipxy.append((nx,ny))
        elif event.LeftUp():  # end of Flip gesture

            if len(self.flipxy) > 1:
                traj = np.array( self.flipxy )
                dx, dy = traj[-2,:] - traj[1,:]

                x1, y1, x2, y2 = self.zoomrect
                zoomfactor = ((x2-x1) * (y2-y1)) / float(self.h*self.w)
                z = self.changetitle(wantz=True)

                if dx > 10*zoomfactor and -5*zoomfactor < dy < 5*zoomfactor:
                    diff = 1
                    while self.TVch + diff <= max(self.TVch_found)-1:
                    # "self.TVch_found" starts from 1. like [1, 2, 3, 4, 0, 0, 7]
                    # So that zero element means undetected channel
                    # TVch starts from 0, so -1 for max(self.TVch_found)
                        if not self.TVch_found[self.TVch + diff]:
                            diff += 1
                        else:
                            break

                    if self.TVch + diff > max(self.TVch_found)-1:  # wrapping
                        self.TVch = 0
                    else:
                        self.TVch += diff

                elif dx < -10*zoomfactor and -5*zoomfactor < dy < 5*zoomfactor:
                    diff = -1
                    while self.TVch + diff >= 0:
                        if not self.TVch_found[self.TVch + diff]:
                            diff -= 1
                        else:
                            break

                    if self.TVch + diff < 0:
                        self.TVch = max(self.TVch_found)-1
                    else:
                        self.TVch += diff

                self.img = self.imgdict[ img_keys[self.TVch] ]
                self.refreshch(z)
                self.refresh_buf()

            self.flipxy = []
        ## if not in these modes, then check for left double-click
        elif event.LeftDClick():
            self.OnPlay(None)

        # update (x, y, pixel value) in the parameter pane
        if 0<=nx<self.w and 0<=ny<self.h:
            value = self.img[self.h-(ny+1),nx,self.curframe]
            label = '(x,y,value) = (%d, %d, %1.2f)' % (nx,ny,value)

            roi_in = self.insideROI(nx,ny)  # show some ROI info also
            if roi_in != []:                # when hovering over a ROI
                for n in roi_in:
                    z = self.changetitle(wantz=True)
                    if self.ROI.z[n] == z:
                        label += '\n ROI %02d at %s' % (n+1, z)
            self.param.xyz.SetLabel(label)

        self.Refresh(False)

    def OnJumpButtons(self, event):

        z = self.changetitle(wantz=True)
        _id = event.GetId()
        if _id == self.ID_jump2anat:

            if self.TVch == 4:
                self.TVch = 3
                self.jump2anat.SetLabel('Anatomy')
            else:
                self.TVch = 4
                self.jump2anat.SetLabel('dF/F')

        elif _id == self.ID_jump2avgmap:

            if self.TVch==6:
                self.TVch = 5
                self.jump2avgmap.SetLabel('avg_dF/F')
            else:
                self.TVch = 6
                self.jump2avgmap.SetLabel('avg_F')

        self.btnbar.Fit()
        self.img = self.imgdict[ img_keys[self.TVch] ]
        self.refreshch(z)
        self.refresh_buf()
        self.Refresh()

    def OnKeyDown(self, event):
        event.Skip() # important
        key = event.GetKeyCode()

        if 49<= key <= 57:  # switch TVch by 1-9 number keys
            if key == 50 and 'dFoFfil' not in self.imgdict.keys():
                print 'no dF/Ffil data'
            elif key == 56 and 'avg projection' not in self.imgdict.keys():
                print 'no average projection data'
            elif key == 57 and 'max projection' not in self.imgdict.keys():
                print 'no max projection data'
            else:
                z = self.changetitle(wantz=True)
                self.TVch = key - 49

                print 'Switched to :'+img_keys[self.TVch], key

                self.img = self.imgdict[ img_keys[self.TVch] ]
                self.refreshch(z=z)
                self.refresh_buf()

        elif key == 67 and event.ControlDown(): # Cntl+C to copy image
            self.copyBMP(event)
        elif key == 90: # 'z' for "Z"oom in
            self.OnZoomMode(None)
        elif key == 69: # 'e' for zoom-out to entire view
            self.OnZoomReset(None)
        elif key == 72: # 'h' for "H"and pan tool
            self.OnPanMode(None)
        elif key == 86: # 'v' for Play / stop video
            self.OnPlay(None)
        elif key == 66: # 'b' for "B"ack to the beggining
            self.OnRewind(None)
        elif key == 82: # 'r' for "R"OI drawing
            self.OnROIDraw(None)
        elif key == 83: # 's' for Shifting ROIs
            self.OnROIMove(None)
        elif key == 68: # 'd' for "D"eleting ROIs
            self.OnROITrash(None)
        elif key == 81: # 'q' for "Q"uick plot
            self.OnQuickPlot(event)
        elif (key == 87 # 'w' for wheel scaling the window
              and not self.scaling):
            self.SetCursor(wx.StockCursor(wx.CURSOR_SIZENWSE))
            self.scaling = True
        elif key == 88: # 'x' for ROI toggling mode
            self.OnCtxROImode(None)
        elif self.moving:
            nx, ny = self.normxy(event)
            roi_in = self.insideROI(nx,ny)
            if not roi_in:  # if no ROI selected, then all ROIs on this plane
                z = self.changetitle(wantz=True) # get current plane
                roi_in = [n for n,zz in enumerate(self.ROI.z) if zz == z]
            if   key == 314: # 'left' for ROI shift
                dx,dy = -1, 0
            elif key == 315: # 'up' for ROI shift
                dx,dy = 0, -1
            elif key == 316: # 'right' for ROI shift
                dx,dy = 1, 0
            elif key == 317: # 'down' for ROI shift
                dx,dy = 0, 1
            else: # in case other keys are pressed.
                dx,dy = 0, 0
            self.ROI.shift((dx,dy), roi_in)

        self.Refresh()

    def OnKeyUp(self, event):
        event.Skip() # important
        if event.GetKeyCode() == 87:  # 'w' for wheel scaling
            self.reset_cursor()
            self.scaling = False
            self.display.SetFocus()

    # BOTTONS
    def OnCheckBoxes(self, event):
        self.scH.Enable( self.ManScaling.IsChecked() )
        self.scL.Enable( self.ManScaling.IsChecked() )
        self.scYmax.Enable( self.autoY.IsChecked() == False)
        self.scYmin.Enable( self.autoY.IsChecked() == False)
        self.refresh_buf()
        self.Refresh()

    def OnSpin_z(self, event):
        self.scz.SetRange(0, self.img.shape[2]-1)
        self.curframe = self.scz.GetValue()
        self.refresh_buf()
        self.Refresh()
        self.changetitle()

    def OnSpin_ManSc(self, event):
        hi = self.scH.GetValue()
        lo = self.scL.GetValue()
        if hi<lo:
                self.scL.SetValue(hi-1)
        self.refresh_buf()
        self.Refresh()

    def OnReload(self, event):

        data_path = self.imgdict['data_path']
        data_tags = self.tag

        print 'data_path', data_path
        print 'data_tags', data_tags
        print 'Loading the channel#%d' % self.ch

        if self.Launcher is not None:
            howmanyframe = self.Launcher.rb1.GetSelection()
            need_AvgTr = self.Launcher.cbAvgTr.IsChecked()
            need_MaxPr = self.Launcher.cbMaxPr.IsChecked()
        else:
            howmanyframe = 0  # 0 for all frame, 1 for during res and F, 2 for the first in F
            need_AvgTr = need_MaxPr = False

        global ch, ref_ch
        ch_bak, ref_ch_bak = ch, ref_ch
        ch, ref_ch = self.ch, self.ref_ch

        Fnoise = self.parent.ParamsPane.sc_Fnoise.GetValue()
        
        if self.parent.reftr:
            reftr = None
        else:
            refty = 0

        imgdict, tag = pack(
            data_path, data_tags, howmanyframe, need_AvgTr, need_MaxPr, anatomy_method, 
            Fnoise, fastLoad, verbose, durpre, durres, ch, ref_ch, reftr, margin
        )

        ch, ref_ch = ch_bak, ref_ch_bak

        # overwrite the image data. (self.tag does not change)
        self.img = imgdict['unshifted frames']
        if self.img.dtype == np.uint8:
            self.scH.SetRange(1, 255)
            self.scL.SetRange(0, 254)
        else:
            self.scH.SetRange(1, 256**2-1)
            self.scL.SetRange(0, 255**2-2)
        inputmax = self.img.max()
        inputmin = self.img.min()
        self.scH.SetValue(inputmax)
        self.scL.SetValue(inputmin)

        self.imgdict = imgdict
        self.imgdict['hist'] = {}

        self.TVch = 0
        self.init_workers()
        self.changetitle()
        self.refresh_buf()
        print 'File(s) reloaded.'

    def OnZoomMode(self, event):
        if not self.record:
            self.dx, self.dy = 0,0
            if self.zoomingmode:
                self.zoomingmode = False
                self.st_x = self.st_y = None
                self.reset_cursor()
            else:
                self.zoomingmode = True
                self.st_x = self.st_y = None
                self.panmode = False
                self.SetCursor(wx.StockCursor(magnifier))
                self.display.SetFocus()
        #print 'zooming mode is ', self.zoomingmode

    def OnZoomReset(self, event):  # bound to the minum magfier btn
        self.zoomrect = (0, 0, self.w, self.h)
        self.zoomingmode = False
        self.st_x = self.st_y = None
        self.reset_cursor()
        self.display.SetFocus()

    def OnPanMode(self, event):
        if self.panmode:
            self.panmode = False
            self.st_x = self.st_y = None
            self.reset_cursor()
        elif not self.zoomingmode and self.zoomrect != (0,0,self.w,self.h):
            self.panmode = True
            self.SetCursor(wx.StockCursor(wx.CURSOR_HAND))
            self.display.SetFocus()
        #print 'pan mode is ', self.panmode

    def OnPlay(self, event):
        if self.playing:
            self.playing = False
            self.playbtn.SetBitmapLabel(self.play_bmp)
        else:
            self.playing = True
            self.b4play = self.scz.GetValue()
            self.playbtn.SetBitmapLabel(self.stop_bmp)
            self.st_fr = self.scz.GetValue()
            if self.parent.verbose.IsChecked():
                self.t0 = time.time()

    def OnRewind(self, event):
        self.playing = False
        self.playbtn.SetBitmapLabel(self.play_bmp)
        self.scz.SetValue(0)
        self.OnSpin_z(None)

    def OnROIDraw(self, event):
        # turn off other modes
        if self.ROImode and not self.ROImngr.GetValue():
            if self.zoomingmode:
                self.OnZoomMode(None)
            elif self.panmode:
                self.OnPanMode(None)
            elif self.moving:
                self.OnROIMove(None)
            elif self.trashing:
                self.OnROITrash(None)

            elif self.drawing:
                # print 'ROI drawing fisnished'
                self.drawing = False
                self.reset_cursor()
                if len(self.roibuf) > 2:
                    z = self.changetitle(wantz=True)
                    self.ROI.add(self.roibuf, str(z))
            else:
                # print 'Start drawing ROI'
                self.SetCursor(wx.StockCursor(wx.CURSOR_PENCIL))
                self.drawing = True
                self.roibuf = []
            self.display.SetFocus()

    def OnROIMove(self, event):
        # turn off other modes
        if self.ROImode and not self.ROImngr.GetValue():
            if self.zoomingmode:
                self.OnZoomMode(None)
            elif self.panmode:
                self.OnPanMode(None)
            elif self.trashing:
                self.OnROITrash(None)

            elif self.moving:
                self.moving = False
                self.reset_cursor()
            elif not self.drawing:
                self.moving = True
                self.SetCursor(wx.StockCursor(wx.CURSOR_SIZING))
                self.display.SetFocus()

    def OnROITrash(self, event):
        # turn off other modes
        if self.ROImode and not self.ROImngr.GetValue():
            if self.zoomingmode:
                self.OnZoomMode(None)
            elif self.panmode:
                self.OnPanMode(None)
            elif self.moving:
                self.OnROIMove(None)

            elif self.trashing:
                self.reset_cursor()
                self.trashing = False
            elif not self.drawing:
                self.trashing = True
                self.SetCursor(wx.CursorFromImage(self.trash_img))


class MainFrame(wx.Frame):
    def __init__(self, parent, id):
        title = 'Pymagor%s (rev %s)' % (release_version, __version__)
        size = (950, 630)
        style = wx.DEFAULT_FRAME_STYLE | wx.NO_FULL_REPAINT_ON_RESIZE
        wx.Frame.__init__(self, parent, id, title, size=size, style=style)

        self.SetIcon(fishicon)
        self.Bind(wx.EVT_SIZE, self.OnSize)

        ## AUI Manager
        self._mgr = AUI.AuiManager()
        self._mgr.SetManagedWindow(self)
        pi=AUI.AuiPaneInfo()

        ## Controls to put in
        # Notebook

        self.sheet = BaseListCtrl(self, columns=5, name='Online analysis sheet')
        self.sheet.InsertColumn(0, "File")
        self.sheet.InsertColumn(1, "Field_of_View")
        self.sheet.InsertColumn(2, "Stimulus")
        self.sheet.InsertColumn(3, "Repeat")
        self.sheet.InsertColumn(4, "Folder")
        self.sheet.InsertColumn(5, "Date")
        self.sheet.InsertColumn(6, "Memo")

        self.sheet.Bind(wx.EVT_CONTEXT_MENU, self.OnCtxMenu)
        self.sheet.Bind(wx.EVT_LIST_ITEM_SELECTED, self.OnItemSelected)
        self.sheet.Bind(wx.EVT_KEY_UP, self.OnKeys)
        self.sheet.Bind(wx.EVT_LEFT_DCLICK, self.OnCtxOpen)

        info = 'Drop file(s) here to open'
        self.sheet.SetToolTip(wx.ToolTip(info))
        agwStyle = AUI.AUI_NB_DEFAULT_STYLE | AUI.AUI_NB_TAB_EXTERNAL_MOVE | wx.NO_BORDER
        Notebook = AUI.AuiNotebook(self, style=agwStyle)
        Notebook.AddPage(self.sheet, 'Online analysis sheet')
        Notebook.Bind(AUI.EVT_AUINOTEBOOK_PAGE_CLOSE, self.OnPageClose)

        # Log
        self.log = wx.TextCtrl(self,
                    style = wx.TE_MULTILINE|wx.TE_READONLY|wx.HSCROLL)
        self.log.SetMinSize((900,250))
        self.log.SetToolTip(wx.ToolTip(info))
        sys.stdout = RedirectText(self.log)

        if myOS is not 'Windows':
            self.log.SetFont(wx.Font(9, wx.SWISS, wx.NORMAL, wx.NORMAL))
        if verbose:
            print 'Running on %s' % sys.version
            print ini_log


        # ParamsPane
        self.ParamsPane = ParamsPanel(self)
        self.ParamsPane.SetMinSize((200,245))

        # adding panes
        self._mgr.AddPane(Notebook, pi.Center().Name('Notebook').CloseButton(False).Caption('Notebook pane').CaptionVisible(False))
        self._mgr.AddPane(self.ParamsPane,
            pi.FloatingSize((200,245)).MinSize((200,245)).Left().Name('ParamsPane').Caption('Parameter pane') )
        self._mgr.AddPane(self.log, pi.MinSize((900,170+30)).Bottom().Name('Log').Caption('Log pane'))
        self._mgr.Update()

        # File drop
        self.log.SetDropTarget(FileDrop(self, open_flag=True, dlg=False))
        self.ParamsPane.SetDropTarget(FileDrop(self, open_flag=False, dlg=True))
        self.sheet.SetDropTarget(FileDrop(self, open_flag=True, dlg=False))


        self.Bind(wx.EVT_CLOSE, self.OnQuit)

        # File menu
        File = wx.Menu()

        File.Append(102, '&Open supported file (tif, ior, csv, offset)\tCtrl+O')
        self.Bind(wx.EVT_MENU, self.OnOpen, id=102)
        File.Append(103, 'Show all meta data in an image file')
        self.Bind(wx.EVT_MENU, self.OnTagDisp, id=103)
        File.Append(104, 'Create a template v2 Pymagor sheet from a data folder')
        self.Bind(wx.EVT_MENU, self.OnCreateCSV, id=104)
        File.Append(105, 'Create a template v2 Pymagor sheet including subfolders')
        self.Bind(wx.EVT_MENU, self.OnCreateCSV, id=105)
        File.AppendSeparator()
        File.Append(106, '&Close all plots and images\tAlt+Ctrl+A')
        self.Bind(wx.EVT_MENU, self.OnCloseAll, id=106)
        File.Append(107, 'Open Py&Shell\tAlt+Ctrl+S')
        self.Bind(wx.EVT_MENU, self.OnShowConsole, id=107)
        File.Append(101, '&Quit\tCtrl+Q', 'Exit')
        self.Bind(wx.EVT_MENU, self.OnQuit, id=101)

        # File history
        self.filehistory = wx.FileHistory()
        self.config = wx.Config('Pymagor', style=wx.CONFIG_USE_LOCAL_FILE)
        self.filehistory.Load(self.config)
        self.filehistory.UseMenu(File)
        self.filehistory.AddFilesToMenu()
        self.Bind(wx.EVT_MENU_RANGE, self.OnFileHistory,
                        id=wx.ID_FILE1, id2=wx.ID_FILE9)

        # Tool menu
        tool = wx.Menu()

        self.verbose = tool.Append(201, 'Verbose log output', kind=wx.ITEM_CHECK)
        self.verbose.Check(verbose)
        self.Bind(wx.EVT_MENU, self.OnCheckItems, id=201)

        self.fitw = tool.Append(203, 'Fit the image window to the toolbar width', kind=wx.ITEM_CHECK)
        self.fitw.Check(fit2Toolbar_width)
        self.Bind(wx.EVT_MENU, self.OnCheckItems, id=203)

        self.selectiveWeightedAvgFilter = tool.Append(211, 'Use a denoise filter for raw and dF/F movie', kind=wx.ITEM_CHECK)
        self.selectiveWeightedAvgFilter.Check(selectiveWeightedAvgFilter)
        self.Bind(wx.EVT_MENU, self.OnCheckItems, id=211)

        self.anatomy_method = tool.Append(206, 'Use SD instead of mean for anatomy view', kind=wx.ITEM_CHECK)
        self.Bind(wx.EVT_MENU, self.OnCheckItems, id=206)

        self.corr_in_use = tool.Append(204, 'Use a fast alignment algorithm', kind=wx.ITEM_CHECK)
        self.corr_in_use.Check(corr2use)
        self.Bind(wx.EVT_MENU, self.OnCheckItems, id=204)

        tool.AppendSeparator()

        self.usecsv = tool.Append(208, 'Use csv instead of xls for online analysis sheet', kind=wx.ITEM_CHECK)
        self.usecsv.Check(usecsv)
        self.Bind(wx.EVT_MENU, self.OnCheckItems, id=208)

        self.npz = tool.Append(205, 'Save as compressed npz instead of mat file', kind=wx.ITEM_CHECK)
        self.npz.Check(npz)
        self.Bind(wx.EVT_MENU, self.OnCheckItems, id=205)

        self.matcomp = tool.Append(210, 'Use the compression option for mat file', kind=wx.ITEM_CHECK)
        self.matcomp.Check(mat_compress)
        self.Bind(wx.EVT_MENU, self.OnCheckItems, id=210)

        self.appendROI = tool.Append(207, 'Append ROIs from a mat file', kind=wx.ITEM_CHECK)
        self.appendROI.Check(True)

        self.tool = tool

        # Plugins
        manager = PluginManager()
        manager.setPluginPlaces(["plugins"])
        manager.collectPlugins()

        plugins = {}
        plugin_menu = wx.Menu()
        for plugin in manager.getAllPlugins():
            _id = wx.NewId()
            name = plugin.plugin_object.name
            target = plugin.plugin_object.target
            if target == 'MDIChildFrame':
                chkb = plugin_menu.Append(_id, name)
            else:
                chkb = plugin_menu.Append(_id, name, kind=wx.ITEM_CHECK)
            self.Bind(wx.EVT_MENU, self.OnPlugin, id=_id)
            plugins[_id] = [name, target, plugin.plugin_object, chkb]
            if verbose:
                print '   Plugin found: '+ name + ' (targeting:' + target + ')'

        self.plugins = plugins

        # Export Option
        Export = wx.Menu()
        self.export_needplotting = Export.Append(401, 'Show plots while creating PDF', kind=wx.ITEM_CHECK)
        Export.AppendSeparator()
        self.export_eachfile = Export.Append(402, 'Include individual traces', kind=wx.ITEM_CHECK)
        self.export_avgtraces = Export.Append(403, 'Include trial-average traces', kind=wx.ITEM_CHECK)
        self.export_group_odor = Export.Append(404, 'Group by stimulus condition (rather than field-of-view)', kind=wx.ITEM_CHECK)
        self.export_transpose_collage = Export.Append(405, 'Transpose collage', kind=wx.ITEM_CHECK)

        self.export_needplotting.Check(EXPORT_needplotting)
        self.export_eachfile.Check(EXPORT_eachfile)
        self.export_avgtraces.Check(EXPORT_avgtraces)
        self.export_group_odor.Check(EXPORT_group_odor)
        self.export_transpose_collage.Check(EXPOSE_transpose_collage)

        # Colormap menu
        Cmaps = wx.Menu()
        for n,(k,v) in enumerate(colormapOptions.items()):
            cmMenu = Cmaps.Append(500+n, k, kind=wx.ITEM_CHECK)
            if k == ColorMapName:  # default option saved in ini file
                cmMenu.Check(True)
            self.Bind(wx.EVT_MENU, self.OnCmaps, id=500+n)

        # Help
        Help = wx.Menu()
        Help.Append(302, 'Download page on GitHub')
        Help.Append(303, '&Online documentation (wiki)')
        Help.Append(304, '&Go to User file folder (error log here)')
        Help.Append(301, 'About / Shortcut-keys')
        self.Bind(wx.EVT_MENU, self.OnHelp, id=301)
        self.Bind(wx.EVT_MENU, self.OnHelp, id=302)
        self.Bind(wx.EVT_MENU, self.OnHelp, id=303)
        self.Bind(wx.EVT_MENU, self.OnHelp, id=304)

        menubar = wx.MenuBar()
        menubar.Append(File, '&File')
        menubar.Append(tool, '&Options')
        menubar.Append(plugin_menu, '&Plugins')
        menubar.Append(Export, '&PDF')
        menubar.Append(Cmaps, '&Colormap')
        menubar.Append(Help, '&Help')
        self.SetMenuBar(menubar)

        self.opened_data = {}

        if os.path.exists(lastdir):
            self.lastdir = lastdir
        else:
            self.lastdir = homedir
        print '(If plotting does not work, exit Pymagor and delete fontList.cache in %s)\n' % MPLcache

        # default setting
        self.reftr = True
        self.HowManyFrames = 2

        self.lastplane = 'Type in field-of-view label here'
        self.lastodor = 'Or, pick from pulldown menu'
        self.lastmemo = 'comment here'

        self.customROIcategory = customROIcategory

        self.ID_edit = wx.NewId()
        self.OnCheckItems(None)

    # General methods
    def get_current_selection(self):

        items = []
        items.append( self.sheet.GetFirstSelected() )
        while items[-1] != -1:
            items.append( self.sheet.GetNextSelected(items[-1]) )

        items.pop()  # last item is -1 which we dont need.
        return items

    def loadcsv(self, event, fp=None):

        if fp:
            csvname = fp
        else:
            csvname = self.fp

        global csvdict, fromlauncher
        csvdict={}  # load csv data into a dict
        fromlauncher = []  # initialize the selection buffer

        if csvname.endswith('csv'):
            try:
                with open(csvname,'rb') as f:
                    dialect = csv.Sniffer().sniff(f.read(2024))
                    print 'delimiter detected: (%s)' % ( dialect.delimiter ),
                    if dialect.delimiter not in [',',';','.','\t']:
                        self.showmessage('unknown delimiter (%s) detected. forcing comma delimiter'% (dialect.delimiter))
                        dialect.delimiter = ','
                    f.seek(0)
                    csvReader = csv.reader(f, dialect=dialect)

                    for ind, row in enumerate(csvReader):
                        csvdict[ind+1] = row
            except EnvironmentError:
                self.showmessage('IO error.')

        elif csvname.endswith('xls'):
            try:
                book = xlrd.open_workbook(csvname)
                sh = book.sheet_by_index(0)

                for ind in range(sh.nrows):
                    csvdict[ind+1] = [unicode(cell.value) for cell in sh.row(ind)]
            except EnvironmentError:
                self.showmessage('IO error.')

        msg = ''
        csv_folder = csvdict[1][0]
        if csv_folder == '.':
            csv_folder = os.path.dirname(csvname)
            csvdict[1][0] = csv_folder

        if not os.path.exists(csv_folder):
            msg += "The data path in the top-left field does not exist.\n"

        ver = csvdict[1][1]
        if ver >= 2.0:  # simple sanity check
            if 3 in csvdict.keys():

                for k,v in csvdict.items():
                    if v[-1] == '.':
                        csvdict[k][-1] = os.path.dirname(csvname)

                data_folder = csvdict[3][-1]
                if not os.path.exists(data_folder):
                    msg += "The data path for the 1st image file does not exist.\n"

        if msg:
            self.showmessage(msg)
            return

        if verbose:
            print csvdict.items()

        self.csvname = csvname
        self.OnBatchLauncher(None)

    def open_filetype(self, open_flag=True, packingflag=[], dlg=False, opencb=False):

        if not os.path.exists(self.fp):
            self.showmessage('File not found.')
            return 0

        self.filehistory.AddFileToHistory(self.fp)
        self.filehistory.Save(self.config)
        self.config.Flush()

        if os.path.isdir(self.fp) and self.fp.count('_'):
            micro_manger = os.path.basename(self.fp).split('_')[-2] + '_images.tif'
            fp = os.path.join(self.fp, micro_manger)
            if os.path.exists(fp):
                if verbose:
                    print 'Micro-manager image found in the sub-folder', fp
                self.fp = fp

        fname = os.path.basename(self.fp)
        dirname = os.path.dirname(self.fp)

        fp_offset, offset_dict, Lastdurres, LastFnoise = get_saved_offsets(dirname)
        show_offsetinfo(fp_offset, offset_dict, Lastdurres, LastFnoise)

        if fname.endswith(('tif','ior')):
            if open_flag:
                # check if this key has already values
                if (fname,dirname) not in self.opened_data:
                    self.opened_data[fname,dirname] = ['','','']
            else:
                items = self.get_current_selection()
                for item in items: # de-select all to avoid overwring the previous selection
                    self.sheet.SetItemState(item, 0, wx.LIST_STATE_SELECTED|wx.LIST_STATE_FOCUSED)

                plane, odor, memo, open_flag = self.OnSheetEdit(None, dlg=dlg, opencb=opencb)
                self.opened_data[fname,dirname] = [plane,odor,memo]

            if not packingflag:
                self.refresh_sheet(None)

        if open_flag:
            if fname.endswith(('csv', 'xls')):
                self.loadcsv(self.fp)
            elif fname.endswith(('tif','ior')):
                if packingflag:
                    data_path, data_files, all_frame, AvgTr, MaxPr, reftr = packingflag
                    self.PrepareTrial2(data_files, all_frame, AvgTr, MaxPr)
                else:
                    self.PrepareTrial2()
            elif fname.endswith('offset'):
                pass
            else:
                self.showmessage('Pymagor couldn''t recognize the file.\nAvoid special characters like camma dot etc in the file name' )


    def refresh_sheet(self, event, focuson=None):

        self.sheet.DeleteAllItems()
        keys = self.opened_data.keys()
        #keys.sort()
        # here using getmtime instead of ctime because copying will cahnge ctime but not mtime
        index = np.argsort([os.path.getmtime(os.path.join(pth,fname))
                            for fname, pth in keys])
        keys = [keys[ind] for ind in index]
        if keys: # emplty list is False
            count = {}
            for (fname, dirname) in keys:
                plane, odor, memo = self.opened_data[(fname, dirname)]

                if count.has_key((plane,odor)):
                    count[(plane,odor)] += 1
                else:
                    count[(plane,odor)] = 1

                repeat = str(count[(plane,odor)])

                index = self.sheet.InsertStringItem(sys.maxint, fname)
                self.sheet.SetStringItem(index,1, plane)
                self.sheet.SetStringItem(index,2, odor)
                self.sheet.SetStringItem(index,3, repeat)
                self.sheet.SetStringItem(index,4, dirname)
                fp = os.path.join(dirname, fname)
                ctime = time.strftime('%m/%d/%Y %X', time.gmtime(os.path.getmtime(fp)))
                self.sheet.SetStringItem(index,5, ctime)
                self.sheet.SetStringItem(index,6, memo)

            self.sheet.SetColumnWidth(0, wx.LIST_AUTOSIZE)
            # always column 0 is bit short. increase by 5
            self.sheet.SetColumnWidth(0, self.sheet.GetColumnWidth(0)+5)

            self.sheet.SetColumnWidth(4, wx.LIST_AUTOSIZE)

            self.currentItem = index  # focus on the bottom
            if focuson != None:
                self.sheet.Focus(focuson)
            else:
                self.sheet.Focus(index)

        elif hasattr(self, 'currentItem'): # no items remain in the sheet.
            del self.currentItem


    def PrepareTrial2(self, tags=[], all_frame=0, AvgTr=False, MaxPr=False, lock=False):

        # all_frame [0: all, 1: F and dur, 2: first frame]

        data_path = os.path.dirname(self.fp)
        if not tags: # empty list is False
            tags = [[os.path.basename(self.fp), 'field-of-view_1', 'stim_1', '1', data_path]]
        if self.reftr:
            reftr = None
        else:
            refty = 0
        
        Fnoise = self.ParamsPane.sc_Fnoise.GetValue()

        imgdic, sorted_tag = pack(
                data_path, tags, all_frame, AvgTr, MaxPr, anatomy_method, 
                Fnoise, fastLoad, verbose, durpre, durres, ch, ref_ch, reftr, margin
                )

        if imgdic is not None:
            if imgdic['F'].any():  # check if images are loaded ok
                self.OnNewChild2(imgdic, tag=sorted_tag, lock=lock)

    def showmessage(self, txt):
        dlg = wx.MessageDialog(self, txt, 'A Message Box',
                           wx.OK | wx.ICON_INFORMATION )
        dlg.ShowModal()
        dlg.Destroy()


    ## Event handlars
    # File
    def OnOpen(self, event):
        dlg = wx.FileDialog(self, 'Select a file', '', '',
            'file types (*.tif;*.ior;*.csv;*.xls;*.offset)|*.tif;*.ior;*.csv;*.xls;*.offset',
                            wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            self.fp = dlg.GetPath()
            self.open_filetype()
        dlg.Destroy()

    def OnNewChild2(self, imgdic, tag, lock=False):

        win = trial2(self, -1, imgdic, tag, lock)
        win.Show(True)

        if hasattr(self, 'win'):
            self.win.append(win)
        else:
            self.win=[win]

    def OnFileHistory(self, event):
        fileNum = event.GetId() - wx.ID_FILE1
        self.fp = self.filehistory.GetHistoryFile(fileNum)
        self.open_filetype()

    def OnTagDisp(self, event):
        dlg = wx.FileDialog(self, 'Select a file', '', '',
                                'file types (*.tif;*.ior)|*.tif;*.ior', wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            fp = dlg.GetPath()
            tag = get_all_tags(fp)
            print 'Meta data found in : %s' % fp
            for k,t in tag.items():
                print k,'=',t

        dlg.Destroy()

    def OnCloseAll(self, event):
        if csvdict is not None:
            tablename = csvdict[1][0]
        else:
            tablename = None
        bringfocus = None
        for child in self.GetChildren():
            if isinstance(child, wx.Frame):
                title = child.GetTitle()
                if title.startswith('*'):
                    print title+' is locked.'
                elif hasattr(child, 'ID_closeall'):
                    if event.GetId() == child.ID_closeall:
                        bringfocus = child
                elif title not in ['Parameter panel', tablename,
                                    'Batch Launcher (Alt+B)'] and not\
                                    title.startswith('CSV'):
                    child.Destroy()

        plt.close('all')

        if bringfocus:
            app.SetTopWindow(bringfocus)


    def OnShowConsole(self, event):
        #crustFrame = wx.py.crust.CrustFrame(parent = self)
        #crustFrame.Show()
        if hasattr(self, 'win'):
            shellFrame = wx.py.shell.ShellFrame(parent = self)
            shellFrame.Show()
            print "Pymagor2.win[%d].imgdict" % (len(self.win)-1)
        else:
            print "No trial viewer opened."

    def OnQuit(self, event):
        self.saveini()
        self._mgr.UnInit()
        self.Destroy()

    # @staticmethod
    def saveini(self):
        data = {
            'Parameter panel' :
                {'durpre' : durpre,
                 'durres' : durres,
                 'cmax' : cmax,
                 'cmin' : cmin,
                'margin' : margin,
                'SpatMed' : SpatMed,
                'SpatMed2' : SpatMed2,
                'fastLoad': fastLoad,
                'Autoalign': Autoalign
                },
            'General setting' :
                {'min_fontsize' : min_fontsize,
                'pickle_stacked' : pickle_stacked,
                'verbose' : verbose,
                'fit2Toolbar_width' : fit2Toolbar_width,
                'lastdir' : '\'%s\'' % '\\\\'.join(lastdir.split('\\')),
                'npz' : npz,
                'mat_compress' : mat_compress,
                'selectiveWeightedAvgFilter' : selectiveWeightedAvgFilter,
                'corr2use' : corr2use,
                'usecsv' : usecsv,
                'ColorMapName' : '\'%s\'' % ColorMapName,
                },
            'PDF export' :
                {'EXPORT_group_odor' : EXPORT_group_odor,
                'EXPORT_needplotting' : EXPORT_needplotting,
                'EXPORT_eachfile' : EXPORT_eachfile,
                'EXPORT_avgtraces' : EXPORT_avgtraces,
                'EXPOSE_transpose_collage' : EXPOSE_transpose_collage
                },
            'ROI manager' :
                {'customROIcategory' : self.customROIcategory
                },
            }

        config = ConfigParser.RawConfigParser()
        config.optionxform = str
        for key, item in data.items():
            config.add_section(key)
            for varname, value in item.items():
                config.set(key, varname, value)
        with open(os.path.join(homedir,'Pymagor.ini'), 'w') as f:
            config.write(f)

        # odor and plane names will go to a separate csv file
        with open(os.path.join(homedir,'Stim_FieldOfView_Names.csv'), 'wb') as f:
            csvWriter = csv.writer(f)
            for line in itertools.izip_longest(PlaneList, ConditionList):
                csvWriter.writerow(line)

    def OnCheckItems(self, event):
        global verbose, corr2d, corr2use, fit2Toolbar_width, npz, \
                mat_compress, anatomy_method, usecsv, \
                selectiveWeightedAvgFilter

        verbose = self.verbose.IsChecked()

        if self.corr_in_use.IsChecked():
            corr2d = corr.fast_corr
            corr2use = True
        else:
            corr2d = corr.pearson
            corr2use = False

        usecsv = self.usecsv.IsChecked()
        fit2Toolbar_width = self.fitw.IsChecked()
        npz = self.npz.IsChecked()
        anatomy_method = self.anatomy_method.IsChecked()
        mat_compress = self.matcomp.IsChecked()
        selectiveWeightedAvgFilter = self.selectiveWeightedAvgFilter.IsChecked()

    def OnCreateCSV(self, event, ver=None):
        '''Create a template csv for the opened folder'''

        dlg = wx.DirDialog(self, 'Select a data folder:', self.lastdir,
                    style=wx.DD_DEFAULT_STYLE | wx.DD_NEW_DIR_BUTTON)
        if dlg.ShowModal() == wx.ID_OK:
            fpth = dlg.GetPath()

            name = os.path.basename(fpth)

            if usecsv:
                ext = 'csv'
            else:
                ext = 'xls'
            csvname = os.path.join(fpth,
            'PymagorSheet_v%s_%s.%s' % ('_'.join(release_version.split('.')), name, ext))

            if event:
                include_subfolders = (event.GetId() == 105)
            if ver == None: # called only from File menu
                create_csv(csvname, fpth,
                            include_subfolders=include_subfolders,
                            ver=release_version)
            else:           # from online analysis sheet
                self.sheet.SetItemState(0, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED) # go to the top col
                files=[]
                for n in range( self.sheet.GetItemCount() ):
                    fname = self.sheet.GetItemText(n)
                    dirname = self.sheet.GetItem(n, 4).GetText()
                    files.append( os.path.join(dirname, fname) )
                self.sheet.SetItemState(0, wx.LIST_STATE_SELECTED, wx.LIST_STATE_SELECTED)

                # ver2 uses one comon header for tif and ior
                header = ['File', 'Field-of-View', 'Odor', 'Repeat', 'Memo', 'Zoom',
                        'ScanAmplitudes','Channels','Sampling rate', 'Time created', 'Folder path']
                line01  = [[] for a in header] # ensure the first line has the same dimention as follows
                #line01[0] = fpth
                line01[0] = '.'
                line01[1] = str(ver)

                if usecsv:
                    with open(csvname,'wb') as f:
                        csvWriter = csv.writer(f)
                        csvWriter.writerow(line01) # 1st row: file path (ver 1.0 needs this), pymagor version number
                        csvWriter.writerow(header) # 2nd row: col labels

                        for n, infile in enumerate(files):
                            info = get_tags(infile)
                            if 'version' in info:
                                if float(info['version']) >= 3.8:
                                    scanXY = info['scanAngleMultiplierFast'], info['scanAngleMultiplierSlow']
                                else:
                                    scanXY = info['scanAmplitudeX'], info['scanAmplitudeY']
                            else:
                                scanXY = info['scanAmplitudeX'], info['scanAmplitudeY']

                            csvWriter.writerow([
                                os.path.basename(infile),                                               #fname,
                                self.sheet.GetItem(n, 1).GetText(),                                     #plane,
                                self.sheet.GetItem(n, 2).GetText(),                                     #odor,
                                self.sheet.GetItem(n, 3).GetText(),                                     #repeat,
                                self.sheet.GetItem(n, 6).GetText(),                                     #memo
                                info['zoomFactor'],                                                     #zoom,
                                '%sx%s' % scanXY,              #scanAmplitudes,
                                '_'.join(info['recorded_ch']),                                          #recorded_ch,
                                info['frameRate'],                                                      #frameRate,
                                time.strftime('%m/%d/%Y %X', time.gmtime(os.path.getmtime(infile))),    #ctime,
                                #os.path.dirname(infile)                                                 #data_folder
                                '.'                                                                     #data_folder
                                ])
                else: # excel
                    book = xlwt.Workbook()
                    sh1 = book.add_sheet('analysissheet')
                    for c,t in enumerate(line01):
                        sh1.write(0, c, t)
                    for c,t in enumerate(header):
                        sh1.write(1, c, t)

                    for n, infile in enumerate(files):
                        info = get_tags(infile)
                        if 'version' in info:
                            scanimage_version = float(''.join(s for s in info['version'] if s.isdigit()))
                            if scanimage_version == 3.8:
                                scanXY = info['scanAngleMultiplierFast'], info['scanAngleMultiplierSlow']
                            elif scanimage_version in [3.6, 4.0]:
                                scanXY = info['scanAmplitudeX'], info['scanAmplitudeY']

                        else:
                            scanXY = info['scanAmplitudeX'], info['scanAmplitudeY']

                        sh1.write(2+n, 0, os.path.basename(infile))                                 #fname,
                        sh1.write(2+n, 1, self.sheet.GetItem(n, 1).GetText())                       #plane,
                        sh1.write(2+n, 2, self.sheet.GetItem(n, 2).GetText())                       #odor,
                        sh1.write(2+n, 3, self.sheet.GetItem(n, 3).GetText())                       #odor,
                        sh1.write(2+n, 4, self.sheet.GetItem(n, 6).GetText())                       #memo,
                        sh1.write(2+n, 5, info['zoomFactor'])                                       #zoom,
                        sh1.write(2+n, 6, '%sx%s' % scanXY)                                         #scanAmplitudes,
                        sh1.write(2+n, 7, '_'.join(info['recorded_ch']) )                             #recorded_ch,
                        sh1.write(2+n, 8, info['frameRate'])                                       #frameRate,
                        sh1.write(2+n, 9, time.strftime('%m/%d/%Y %X', time.gmtime(os.path.getmtime(infile))))    #ctime,
                        #sh1.write(2+n, 10, os.path.dirname(infile))                                 #data_folder
                        sh1.write(2+n, 10, '.')                                                     #data_folder

                    book.save(csvname)

            self.showmessage('%s saved.\t\nPlz fill in stimulus and plane fields.' % os.path.basename(csvname))
            self.lastdir = fpth
            global lastdir
            lastdir = fpth

        dlg.Destroy()


    def OnBatchLauncher(self, event):

        fname = os.path.basename( self.csvname )
        blpagename = 'Batch Launcher'

        if hasattr(self, 'bl'):
            self.nb.DeletePage(1)
            self.nb.DeletePage(1)

        self.bl = BatchLauncher(self, -1, self.csvname)
        self.pymagorsheet = BaseListCtrl(self,3, name='PymagorSheet')

        # Insert Columns
        for ind, data in enumerate(csvdict[2]):
            self.pymagorsheet.InsertColumn(ind, data)

        # Putting data in
        for ind in range(3,len(csvdict)+1):

            index = self.pymagorsheet.InsertStringItem(sys.maxint, csvdict[ind][0])
            for i,d in enumerate(csvdict[ind]):
                self.pymagorsheet.SetStringItem(index, i, d)
            self.pymagorsheet.SetItemData(index, ind)

        self.pymagorsheet.SetColumnWidth(0, wx.LIST_AUTOSIZE)

        # add these tabs to the nootbook
        self.nb = self._mgr.GetPane('Notebook').window
        self.nb.AddPage(self.bl, blpagename)
        self.nb.AddPage(self.pymagorsheet, fname)
        self.bl.SetFocus()

        # now commit the chages
        self._mgr.Update()

    # Plugin
    def OnPlugin(self, event):
        '''
        General plugin activation function
        3 categories of plugin:
            function in global scope
            MDI children frame
            Context Menu in trial2
        '''
        _id = event.GetId()
        if _id in self.plugins:
            name = self.plugins[_id][0]
            target = self.plugins[_id][1]
            plg_obj = self.plugins[_id][2]
            flag = event.IsChecked()
            print name, '(id=%s) is' % str(_id), flag

            if target == 'MDIChildFrame':
                if flag:
                    plg_obj.spawnMDIframe(self, name)
                else:
                    pass

            elif target == 'ContextMenu':
                global CntxPlugin
                if flag:
                    CntxPlugin[_id] = (plg_obj, name)
                else:
                    key = [k for k,v in CntxPlugin.iteritems() if v[1] == name]
                    del CntxPlugin[key[0]]

            else: # target is global function
                if flag:
                    # store the default and overwrite with the plugin
                    statement = 'global '+target+', default_'+target+'; '
                    statement += 'default_'+target+' = '+target+'; '
                    statement += target+' = plg_obj.'+name
                else:
                    # restrore the default
                    statement = 'global '+target+'; '+target+' = default_'+target

                #print statement
                exec(statement)

    def OnCmaps(self, event):
        global cmap, ColorMapName
        _id = event.GetId()
        mb = self.GetMenuBar()
        for n,(k,v) in enumerate(colormapOptions.items()):
            theID = 500+n
            menuItem = mb.FindItemById(theID)
            if _id == theID:
                print 'colormap is switched to:', k
                menuItem.Check(True)
                cmap = v
                ColorMapName = k
            else:
                menuItem.Check(False)

    # Help
    def OnHelp(self, event):

        _id = event.GetId()
        if _id == 301:
            info = wx.AboutDialogInfo()
            info.SetIcon(fishicon)
            info.Name = 'Pymagor%s' % release_version
            info.Version = 'rev%s' % __version__
            info.Copyright = '(C) 2011- Iori Namekawa'
            info.Developers  = ['Iori Namekawa', 'Otto Fajardo']
            info.WebSite = (documentationURL, "Pymagor online documentation")
            info.AddArtist('Janik Baumgartner (play/stop rewind pencil graph zoom-in zoom-out)')
            info.AddArtist('Alexander Kiselev (hand icon)')
            info.AddArtist('David Hopkins (move arrow)')
            info.AddArtist('Supratim Nayak (eraser)')
            info.AddArtist('Tango Desktop (floppy disk)')
            info.AddArtist('Iori Namekawa (Pymagor fish icon)')
            #Janik Baumgartner at findicons.com/pack/2428/woocons/1
            #Alexander Kiselev at findicons.com/pack/2652/gentleface
            #David Hopkins at findicons.com/pack/1688/web_blog
            #Supratim Nayak at findicons.com/pack/2339/eloquence
            #Tango Desktop at Project findicons.com/pack/1150/tango
            info.Description = '''Supported Image Formats:
- ScanImage 3.6-3.8, MATLAB tiff (Iori Namekawa).
- Imagor3 acquired camera data (ior file), Micro-Manager tiff, ImageJ tiff (Otto Fajardo)
- and possibly what PIL/pillow can open... (especially single channel data)

"clut2b" is a custum made jet-like colormap created by Rainer Friedrich.

Key bindings
R : start / stop ROI drawing mode
S : start / stop ROI shifting mode
D : start / stop ROI deleting mode
Z : start zooming mode
E : zoom-out to the entire view
H : start hand panning mode. Drag to move around
V : play / stop the video
B : rewind back to the beginning
Q : quickly plot the dF/F traces only for the current image
W : enable scaling mode with the mouse wheel while holding 'W'
Ctrl+C: Copy image to clipboard
Ctrl+O: Open file dialog for image or csv file
1-9 : jump to one of 9 view modes.
 (1) Raw image (unshifted)
 (2) dF/F movies
 (3) F images
 (4) Individual dF/F maps
 (5) Anatomy
 (6) Trial-average F
 (7) Trial-average dF/F maps
 (8) Average projection across all stimuli
 (9) Max projection across all stimuli

Mouse gestures
- Swipe to left or right with left-button:
    switch between the view modes
- Wheel up/down while holding right-button:
    increase/decrease the spin control "z" on the top-left to
    switch between trials or frames'''

            info.License = '''Copyright (c) 2011-, Iori Namekawa.
All rights reserved.

Pymagor is licensed under BSD license (3-clause, see LICENSE.txt)

Video support provided by FFMEPG

Icon arts from findicons.com (more detail in source code resources folder)
'''

            wx.AboutBox(info)

        elif _id == 302:
            webbrowser.open(bindir)
        elif _id == 303:
            webbrowser.open(documentationURL)
        elif _id == 304:
            webbrowser.open(homedir)


    ## General events

    def OnKeys(self, event):
        event.Skip() # important
        key = event.GetKeyCode()
        if key == wx.WXK_DELETE:
            #print 'delete'
            self.OnCtxDelete(None)


    def OnPageClose(self, event):

        ctrl = event.GetEventObject()
        name = ctrl.GetPage(event.GetSelection()).GetName()
        if name == 'Online analysis sheet':
            event.Veto()
        elif name == 'BatchLauncher':
            global working_singles, need_abort_singles, working, need_abort
            working_singles, need_abort_singles = False, False
            working, need_abort = False, False
            del self.bl

        elif name == 'PymagorSheet':
            del self.pymagorsheet

    def OnSize(self, event):
        self._mgr.Update()
        self.Layout()

    # Context menu
    def OnCtxMenu(self, event):

        if not hasattr(self, 'ID_stack'):
            self.ID_stack = wx.NewId()
            self.ID_ctxopen = wx.NewId()
            self.ID_delete = wx.NewId()
            self.ID_HowManyFrames0 = wx.NewId()
            self.ID_HowManyFrames1 = wx.NewId()
            self.ID_HowManyFrames2 = wx.NewId()
            self.ID_AutoRefTr = wx.NewId()
            self.ID_export = wx.NewId()
            self.ID_appendcsv = wx.NewId()

            self.sheet.Bind(wx.EVT_MENU, self.OnCtxOpen, id=self.ID_ctxopen)
            self.sheet.Bind(wx.EVT_MENU, self.OnCtxStack, id=self.ID_stack)
            self.sheet.Bind(wx.EVT_MENU, self.OnCtxDelete, id=self.ID_delete)
            self.sheet.Bind(wx.EVT_MENU, self.OnCtxCheckItems, id=self.ID_AutoRefTr)
            self.sheet.Bind(wx.EVT_MENU, self.OnCtxRadioChange, id=self.ID_HowManyFrames0)
            self.sheet.Bind(wx.EVT_MENU, self.OnCtxRadioChange, id=self.ID_HowManyFrames1)
            self.sheet.Bind(wx.EVT_MENU, self.OnCtxRadioChange, id=self.ID_HowManyFrames2)
            self.sheet.Bind(wx.EVT_MENU, self.OnCtxExport, id=self.ID_export)
            self.sheet.Bind(wx.EVT_MENU, self.OnSheetEdit, id=self.ID_edit)
            self.sheet.Bind(wx.EVT_MENU, self.OnAppendCSV, id=self.ID_appendcsv)

        ctxmenu = wx.Menu()
        ctxmenu.Append(self.ID_ctxopen, 'Open each image (Double-click)')
        ctxmenu.Append(self.ID_stack, 'Stack selected images')
        ctxmenu.AppendSeparator()
        ctxmenu.Append(self.ID_edit, 'Edit Field-of-View/Stimulus')
        ctxmenu.Append(self.ID_delete, 'Remove items from sheet (Del)')
        ctxmenu.AppendSeparator()
        ctxmenu.Append(self.ID_AutoRefTr, 'Use AUTO Ref Tr (otherwise RefTr is the first file)', '', wx.ITEM_CHECK)
        ctxmenu.Check(self.ID_AutoRefTr, self.reftr)
        ctxmenu.AppendSeparator()
        ctxmenu.Append(self.ID_HowManyFrames0, 'Stack all raw frames', '', wx.wx.ITEM_RADIO)
        ctxmenu.Append(self.ID_HowManyFrames1, 'Stack only pre(F) and res raw frames', '', wx.wx.ITEM_RADIO)
        ctxmenu.Append(self.ID_HowManyFrames2, 'Stack only the first raw frame of pre (F)', '', wx.wx.ITEM_RADIO)
        ctxmenu.Check(self.ID_HowManyFrames0, self.HowManyFrames==0)
        ctxmenu.Check(self.ID_HowManyFrames1, self.HowManyFrames==1)
        ctxmenu.Check(self.ID_HowManyFrames2, self.HowManyFrames==2)

        ctxmenu.Append(self.ID_appendcsv, 'Append from csv/xls', '')

        if self.opened_data:
            ctxmenu.AppendSeparator()
            if usecsv:
                ctxmenu.Append(self.ID_export, 'Export as csv file')
            else:
                ctxmenu.Append(self.ID_export, 'Export as xls file')

        self.sheet.PopupMenu(ctxmenu)
        ctxmenu.Destroy()

    def OnAppendCSV(self, event):
        # de-select all to avoid overwring the previous selection
        for item in self.get_current_selection():
            self.sheet.SetItemState(item, 0, wx.LIST_STATE_SELECTED|wx.LIST_STATE_FOCUSED)

        dlg = wx.FileDialog(self, 'Select a csv/excel file', '', '',
                            'file type (*.csv, *.xls)|*.csv;*.xls',
                            wx.OPEN)
        if dlg.ShowModal() == wx.ID_OK:
            fp = dlg.GetPath()
        else:
            dlg.Destroy()
            return
        dlg.Destroy()

        basefolder = os.path.dirname(fp)

        if fp.endswith('csv'):

            with open(fp,'rb') as f:
                dialect = csv.Sniffer().sniff(f.read(2024))
                f.seek(0)
                csvReader = csv.reader(f, dialect=dialect)
                csvReader.next() # trash header
                csvReader.next() # in the first two lines

                for fname, plane, odor, _,memo,_,_,_,_,_, dirname in csvReader:
                    if dirname == '.':
                        dirname = basefolder
                    self.opened_data[fname,dirname] = [plane,odor,memo]

        elif fp.endswith('xls'):
            book = xlrd.open_workbook(fp)
            sh = book.sheet_by_index(0)

            for n in range(2, sh.nrows):
                fname, plane, odor, _,memo,_,_,_,_,_, dirname = sh.row(n)
                if dirname.value == '.':
                    dirname.value = basefolder
                self.opened_data[fname.value,dirname.value] = [plane.value,odor.value,memo.value]

        self.refresh_sheet(None)

    def OnCtxExport(self, event):
        dirname = self.sheet.GetItem(0, 4).GetText()
        if dirname:
            self.lastdir = dirname
            #print 'Exporting the current sheet in %s:' % self.lastdir
            self.OnCreateCSV(event=None, ver=release_version)

    def OnCtxRadioChange(self, event):
        id = event.GetId()
        if id == self.ID_HowManyFrames0:
            self.HowManyFrames = 0
        elif id == self.ID_HowManyFrames1:
            self.HowManyFrames = 1
        elif id == self.ID_HowManyFrames2:
            self.HowManyFrames = 2

    def OnCtxCheckItems(self, event):
        id = event.GetId()
        if id == self.ID_AutoRefTr:
            self.reftr = (self.reftr == False)

    def OnCtxOpen(self, event, items=None):
        if not items:
            items = self.get_current_selection()

        for item in items:
            fp = self.sheet.GetItemText(item)
            plane = self.sheet.GetItem(item, 1).GetText()
            odor = self.sheet.GetItem(item, 2).GetText()
            repeat = 'tr'+ self.sheet.GetItem(item, 3).GetText()
            dirname = self.sheet.GetItem(item, 4).GetText()

            self.fp = path_check(os.path.join(dirname,fp)) # open_filetype needs this
            #print 'fullpath: ', self.fp
            if self.fp == None:
                self.showmessage('%s was not found.' % os.path.join(dirname,fp) )
            else:
                if self.fp.endswith(('tif','ior')):

                    #data_path, fp = os.path.split(self.fp)
                    #print 'passed to open_filetype ', data_path, fp
                    data_files = [[fp, plane, odor, repeat, dirname]]
                    all_frame = 0 # forcing all frame. packing option is only when we stack trials
                    AvgTr = False
                    MaxPr = False
                    if self.reftr:
                        reftr = None
                    else:
                        refty = 0
                    packingflag = dirname, data_files, all_frame, AvgTr, MaxPr, reftr

                    #print 'data_files from CtxOpen: ', data_files

                    self.open_filetype(open_flag=True, packingflag=packingflag, dlg=False)

    def OnCtxStack(self, event):

        print 'Stacking selected trials:', self.HowManyFrames

        data_files = []
        for item in self.get_current_selection():
            fname = self.sheet.GetItemText(item)
            plane = self.sheet.GetItem(item, 1).GetText()
            odor = self.sheet.GetItem(item, 2).GetText()
            repeat = 'tr'+self.sheet.GetItem(item, 3).GetText()
            dirname = self.sheet.GetItem(item, 4).GetText()
            data_files.append([fname, plane, odor, repeat, dirname])

        all_frame = self.HowManyFrames
        AvgTr = True
        MaxPr = True
        lock = True
        self.PrepareTrial2(data_files, all_frame, AvgTr, MaxPr, lock)

    def OnCtxDelete(self, event):
        items = self.get_current_selection()
        for item in items:
            fname = self.sheet.GetItemText(item)
            dirname = self.sheet.GetItem(item, 4).GetText()

            self.opened_data.pop((fname, dirname))

        self.refresh_sheet(None)

    def OnItemSelected(self, event):
        self.currentItem = event.m_itemIndex
        #print 'current selection', self.currentItem

        if not hasattr(self, 'fp'):
            items = self.get_current_selection()
            for item in items:
                fname = self.sheet.GetItemText(item)
                dirname = self.sheet.GetItem(item, 4).GetText()
            self.fp = os.path.join(dirname, fname)

    def OnSheetEdit(self, event, dlg=False, opencb=False):

        if hasattr(self, 'currentItem') or dlg == True:

            title = 'Enter meta data for %s' % os.path.basename(self.fp)
            _plane = self.lastplane
            _odor = self.lastodor
            _memo = self.lastmemo

            if event is not None:
                if event.GetId() == self.ID_edit:
                    items = self.get_current_selection()
                    for item in items:
                        _plane = self.sheet.GetItem(item, 1).GetText()
                        _odor = self.sheet.GetItem(item, 2).GetText()
                        _memo = self.sheet.GetItem(item, 6).GetText()

            dlg = PlaneOdor_dialog(self, -1, title, _plane,
                            _odor, _memo, opencb=opencb)

            dlg.CentreOnParent()
            self.SetFocus()

            val = dlg.ShowModal()

            if val == wx.ID_OK:
                odor = dlg.odor.GetValue()
                plane = dlg.plane.GetValue()
                memo = dlg.memo.GetValue()
                self.lastplane = plane
                self.lastodor = odor
                self.lastmemo = memo
                opencb = dlg.opencb.IsChecked()
                dlg.Destroy()
            else:
                dlg.Destroy()
                return '', '', '', False

            if hasattr(self, 'currentItem'):
                self.sheet.SetStringItem(self.currentItem,1, plane)
                self.sheet.SetStringItem(self.currentItem,2, odor)
                # may need to update the dict
                items = self.get_current_selection()
                for item in items:
                    fname = self.sheet.GetItemText(item)
                    dirname = self.sheet.GetItem(item, 4).GetText()
                    self.opened_data[(fname, dirname)] = [plane, odor, memo]

            global PlaneList, ConditionList
            if plane != 'Type in field-of-view label here':
                PlaneList.append(plane)
                seen = set()
                PlaneList = [x for x in PlaneList if x not in seen and not seen.add(x)]
            if odor != 'Or, pick from pulldown menu':
                ConditionList.append(odor)
                ConditionList = list(set(ConditionList))
                ConditionList.sort()

            if event is None:
                if val != wx.ID_OK:
                    opencb = False
                if memo == 'comment here':
                    memo = ''
                return plane, odor, memo, opencb
            else:
                self.refresh_sheet(None, focuson=item)

            if opencb and val == wx.ID_OK:
                self.OnCtxOpen(event, items=items)


class Movie_dialog(wx.Dialog):
    def __init__(self, parent):

        style = wx.DEFAULT_DIALOG_STYLE|wx.STAY_ON_TOP
        wx.Dialog.__init__(self, parent, -1, 'Movie parameters', style=style)

        self.slider = wx.Slider(
                    self,
                    -1,
                    value=5,
                    minValue=1,
                    maxValue=31,
                    style=wx.SL_HORIZONTAL | wx.SL_AUTOTICKS | wx.SL_LABELS
                    )

        self.vrate = wx.TextCtrl(
                    self,
                    -1,
                    "30",
                    size=(80, -1))
        self.vrate.SetWindowStyleFlag(wx.TE_RIGHT)

        gbs = wx.GridBagSizer(2,2)
        gbs.Add( wx.StaticText(self,-1,'Quality (best = 1)'), (0,0), flag=wx.ALIGN_CENTRE)
        gbs.Add( self.slider, (0,1), flag=wx.ALIGN_CENTRE)
        gbs.Add( wx.StaticText(self,-1,'Frame rate (Hz)'), (1,0), flag=wx.ALIGN_CENTRE)
        gbs.Add( self.vrate, (1,1),  flag=wx.ALIGN_CENTRE)

        btnsizer = self.CreateButtonSizer(wx.OK|wx.CANCEL)

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(gbs, 0, wx.ALIGN_CENTRE|wx.ALL, 5)
        vbox.Add(btnsizer, 0, wx.ALIGN_CENTRE|wx.ALL, 5)
        self.SetSizer(vbox)
        self.Fit()


class beads_param(wx.Dialog):

    def __init__(self, parent):
        wx.Dialog.__init__(self, parent,
                        title='PSF auto detection',
                        style=wx.DEFAULT_DIALOG_STYLE|wx.STAY_ON_TOP)
        # default
        blobthrs = '4' # 2 SD for thresholding the blob image
        blobsize = '1.5'   # 1-4 x std of blob sizes, determine blob detection range
        zstep = '0.5'  # 0.5 micron step in z
        ROImax = '10'  # max

        self.blobthrs = wx.TextCtrl(self, -1, blobthrs, style=wx.TE_RIGHT)
        self.blobsize = wx.TextCtrl(self, -1, blobsize, style=wx.TE_RIGHT)
        self.zstep = wx.TextCtrl(self, -1, zstep, style=wx.TE_RIGHT)
        self.ROImax = wx.TextCtrl(self, -1, ROImax, style=wx.TE_RIGHT)

        gbs = wx.GridBagSizer(3,2)
        gbs.Add( wx.StaticText(self,-1,'Threshold as SD x'), (0,0), flag=wx.ALIGN_CENTRE)
        gbs.Add( self.blobthrs, (0,1), flag=wx.ALIGN_CENTRE)
        gbs.Add( wx.StaticText(self,-1,'Blob size range as SD x'), (1,0), flag=wx.ALIGN_CENTRE)
        gbs.Add( self.blobsize, (1,1),  flag=wx.ALIGN_CENTRE)
        gbs.Add( wx.StaticText(self,-1,'step in z'), (2,0), flag=wx.ALIGN_CENTRE)
        gbs.Add( self.zstep, (2,1),  flag=wx.ALIGN_CENTRE)
        gbs.Add( wx.StaticText(self,-1,'ROImax'), (3,0), flag=wx.ALIGN_CENTRE)
        gbs.Add( self.ROImax, (3,1),  flag=wx.ALIGN_CENTRE)

        btnsizer = self.CreateButtonSizer(wx.OK|wx.CANCEL)

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(gbs, 0, wx.ALIGN_CENTRE|wx.ALL, 5)
        vbox.Add(btnsizer, 0, wx.ALIGN_CENTRE|wx.ALL, 5)
        self.SetSizer(vbox)
        self.Fit()


class PlaneOdor_dialog(wx.Dialog):
    def __init__(self, parent, ID, title,
                lastplane='',
                lastodor='',
                lastmemo='',
                opencb=True):
        style = wx.DEFAULT_DIALOG_STYLE|wx.STAY_ON_TOP
        wx.Dialog.__init__(self, parent, ID, title, style=style)

        self.ID_plane = wx.NewId()
        self.ID_odor = wx.NewId()
        plane_choices = wx.Choice(self, self.ID_plane, (100, 50), choices = PlaneList)
        odor_choices = wx.Choice(self, self.ID_odor, (100, 50), choices = ConditionList)

        self.plane = wx.TextCtrl(self, -1, lastplane, size=(180,-1))
        self.odor = wx.TextCtrl(self, -1, lastodor, size=(180,-1))
        self.memo = wx.TextCtrl(self, -1, lastmemo, size=(300,40))

        plane_choices.Bind(wx.EVT_CHOICE, self.OnChoice)
        odor_choices.Bind(wx.EVT_CHOICE, self.OnChoice)

        # sizer
        gbs = wx.GridBagSizer(2,3)
        gbs.Add( wx.StaticText(self,-1,'Filed of view label'),(0,0) )
        gbs.Add( plane_choices,(0,1) )
        gbs.Add( self.plane,(0,2) )
        gbs.Add( wx.StaticText(self,-1,'Stimulus label'),(1,0) )
        gbs.Add( odor_choices,(1,1) )
        gbs.Add( self.odor,(1,2) )

        btnsizer = self.CreateButtonSizer(wx.OK|wx.CANCEL)
        self.opencb = wx.CheckBox(self, -1, 'Open file after dialog')
        self.opencb.SetValue(opencb)

        vbox = wx.BoxSizer(wx.VERTICAL)
        vbox.Add(gbs, 0, wx.ALIGN_CENTRE|wx.ALL, 5)
        vbox.Add(wx.StaticText(self,-1,'Memo:'), 0, wx.ALIGN_CENTRE|wx.ALL, 5)
        vbox.Add(self.memo, 0, wx.ALIGN_CENTRE|wx.ALL, 5)

        vbox.Add(btnsizer, 0, wx.ALIGN_CENTRE|wx.ALL, 5)
        vbox.Add(self.opencb, 0, wx.ALIGN_CENTRE|wx.ALL, 5)
        self.SetSizer(vbox)
        self.Fit()

    def OnChoice(self, event):
        _id = event.GetId()
        if _id == self.ID_plane:
            self.plane.SetValue(event.GetString())
        elif _id == self.ID_odor:
            self.odor.SetValue(event.GetString())


class ParamsPanel(wx.Panel):

    def __init__(self, parent):
        '''use or not to use sizers, thats the question---
            some layout issues between XP and 7 and Ubuntu
            hard coding is probably easiest way to get around...
        '''

        wx.Panel.__init__(self, parent, -1, size=(202,245))
        self.parent = parent
        if myOS is not 'Windows':
            self.SetFont(wx.Font(7, wx.SWISS, wx.NORMAL, wx.NORMAL))

        x,y = 5, 20
        #scsize = (48,20)
        scsize = (60,20)
        wx.StaticBox(self, -1, 'Pre- (F) and During-stimulus frames', (x,3), (193,68+25))
        # DurPre Start
        wx.StaticText(self, -1, 'F period', (x+5,y+3))
        self.IDsc_preS = wx.NewId()
        self.sc_preS = wx.SpinCtrl(self, self.IDsc_preS, '', (x+55+5,y), scsize)
        self.sc_preS.SetRange(0,256**2-1)
        self.sc_preS.SetValue(durpre[0])
        self.sc_preS.Bind(wx.EVT_SPINCTRL, self.OnSpin)
        # DurPre End
        wx.StaticText(self, -1, '- ', (x+120+3,y))
        self.IDsc_preE = wx.NewId()
        self.sc_preE = wx.SpinCtrl(self, self.IDsc_preE, '', (x+126+5,y), scsize)
        self.sc_preE.SetRange(0,256**2-1)
        self.sc_preE.SetValue(durpre[1])
        self.sc_preE.Bind(wx.EVT_SPINCTRL, self.OnSpin)
        # DurRes Start
        wx.StaticText(self, -1, 'During stim', (x+5,y+28))
        self.IDsc_resS = wx.NewId()
        self.sc_resS = wx.SpinCtrl(self, self.IDsc_resS, '', (x+55+5,y+25), scsize)
        self.sc_resS.SetRange(0,256**2-1)
        self.sc_resS.SetValue(durres[0])
        self.sc_resS.Bind(wx.EVT_SPINCTRL, self.OnSpin)
        # DurRes End
        wx.StaticText(self, -1, '-', (x+120+3,y+28))
        self.IDsc_resE = wx.NewId()
        self.sc_resE = wx.SpinCtrl(self, self.IDsc_resE, '', (x+126+5,y+25), scsize)
        self.sc_resE.SetRange(0,256**2-1)
        self.sc_resE.SetValue(durres[1])
        self.sc_resE.Bind(wx.EVT_SPINCTRL, self.OnSpin)

        wx.StaticText(self, -1, 'Background noise offset', (x+5,y+28+25))
        self.IDsc_Fnoise = wx.NewId()
        self.sc_Fnoise = wx.SpinCtrl(self, self.IDsc_Fnoise, '', (x+126+5,y+25+25), scsize)
        self.sc_Fnoise.SetRange(0,256**2-1)

        h = 73 + 25
        wx.StaticBox(self, -1, 'Colormap range', (x,h), (193,50+30+25))
        # cmap min
        txt_cmin = wx.StaticText(self, -1, 'dF/F (%)', (x+5, y+h+3))
        self.IDsc_cmin = wx.NewId()
        if platform.system() == 'Linux':
            self.sc_cmin = FS.FloatSpin(self, self.IDsc_cmin, min_val=-999/4,
                max_val=-0.5, size=(63,20), increment=0.1, value=cmin, style=FS.FS_LEFT)
        else:
            self.sc_cmin = FS.FloatSpin(self, self.IDsc_cmin, min_val=-999/4,
                max_val=-0.5, increment=0.1, value=cmin, agwStyle=FS.FS_LEFT)
            self.sc_cmin.SetSize((63,20))

        self.sc_cmin.SetFormat("%f")
        self.sc_cmin.SetDigits(1)
        self.sc_cmin.SetPosition((65,y+h))
        self.sc_cmin.Bind(FS.EVT_FLOATSPIN, self.OnSpin)
        # cmap max
        wx.StaticText(self, -1, '-', (129,y+h+3))
        self.IDsc_cmax = wx.NewId()
        self.sc_cmax = wx.SpinCtrl(self, self.IDsc_cmax, '', (136,y+h), scsize)
        self.sc_cmax.SetValue(cmax)
        self.sc_cmax.SetRange(0,999)
        self.sc_cmax.Bind(wx.EVT_SPINCTRL, self.OnSpin)

        h += 30
        self.cutoff = wx.CheckBox(self, -1, 'Cutoff dF/F below:',(x+8,h+y))
        self.Bind(wx.EVT_CHECKBOX, self.OnCheck, self.cutoff)
        
        if platform.system() == 'Linux':
            self.sc_cutoff = FS.FloatSpin(self, -1, min_val=-999/4,
                size=(63,20), increment=0.1, value=cutoff, style=FS.FS_LEFT)
        else:
            self.sc_cutoff = FS.FloatSpin(self, -1, min_val=-999/4,
                increment=0.1, value=cutoff, agwStyle=FS.FS_LEFT)
            self.sc_cutoff.SetSize((63,20))
        self.sc_cutoff.SetFormat("%f")
        self.sc_cutoff.SetDigits(1)
        self.sc_cutoff.SetPosition((133,y+h-3))
        self.sc_cutoff.Bind(FS.EVT_FLOATSPIN, self.OnSpin)
        self.sc_cutoff.Enable(False)

        h += 25
        self.overlay = wx.CheckBox(self, -1, 'Overlay anatomy',(x+8,h+y))
        self.Bind(wx.EVT_CHECKBOX, self.OnCheck, self.overlay)
        
        self.SDthrs = wx.CheckBox(self, -1, '2.5 SD thrs',(x+118,h+y))
        self.Bind(wx.EVT_CHECKBOX, self.OnCheck, self.SDthrs)

        h += 30
        wx.StaticBox(self, -1, 'Load', (x,h+y), (193,45))
        # select ch to load
        wx.StaticText(self, -1, 'Channel', (x+5,h+y+20))
        self.ID_ch = wx.NewId()
        self.ch = wx.SpinCtrl(self, self.ID_ch, '',(50+5,h+y+17), (40,20))
        self.ch.SetToolTip(wx.ToolTip('zero-indexed! ex) If ch1 & ch3 are recorded in scanimage,\nspecify 1 to open ch3.'))
        self.ch.SetRange(0,100)
        self.ch.SetValue(ch)
        self.ch.Bind(wx.EVT_SPINCTRL, self.OnSpin)
        # Load as uint8
        self.fastLoad = wx.CheckBox(self, -1, 'Load as uint8',(97+5,h+y+20))
        self.fastLoad.SetValue(fastLoad)
        self.Bind(wx.EVT_CHECKBOX, self.OnCheck, self.fastLoad)
        h += 45
        # Align Margin range
        wx.StaticBox(self, -1, 'Alignment', (x,h+y), (192,45+19))
        wx.StaticText(self,-1,'Shift', (x+5,h+y+20))
        self.IDmargin = wx.NewId()
        self.margin = wx.SpinCtrl(self, self.IDmargin, '', (34,h+y+17), (43,20))
        self.margin.SetRange(0,50)
        self.margin.SetValue(margin)
        self.Bind(wx.EVT_SPINCTRL, self.OnSpin, self.margin)
        # Spatial Median filter for the F
        self.SpaMed = wx.CheckBox(self, -1, 'Median on ref tr', (79,h+y+11))
        self.SpaMed.SetValue(SpatMed)
        self.SpaMed2 = wx.CheckBox(self, -1, 'Median on target tr', (79,h+y+27))
        self.SpaMed2.SetValue(SpatMed2)
        self.Bind(wx.EVT_CHECKBOX, self.OnCheck, self.SpaMed)
        self.Bind(wx.EVT_CHECKBOX, self.OnCheck, self.SpaMed2)

        wx.StaticText(self, -1,'Ref ch', (x+5,h+y+5+37))
        self.IDalignch = wx.NewId()
        self.alignch = wx.SpinCtrl(self, self.IDalignch, '0', (43,h+y+39), (34,20))
        self.alignch.Bind(wx.EVT_SPINCTRL, self.OnSpin)
        #self.alignch.Enable(False)
        self.Autoalign = wx.CheckBox(self, -1, 'Auto-align within tr',(79,h+y+44))
        self.Autoalign.SetValue(Autoalign)
        self.Autoalign.Bind(wx.EVT_CHECKBOX, self.OnCheck)

        h += 45
        # xy and pixel value
        self.xyz = wx.StaticText(self, -1,'(x,y,value) =', (15,h+y+5+16+3))
        self.xyz.SetForegroundColour((0,100,0))

        # drophere = wx.StaticBox(self, -1,
        #     "Add to the analysis sheet", (5,h+y+25+16+5), (192,70+13-16))
        self.SetToolTip(wx.ToolTip('Drop files here to add to the sheet without openning them'))
        self.Refresh()


    def OnSpin(self, event):

        global durpre, durres, cmin, cmax, gmin, gmax, margin, ch, ref_ch, cutoff

        _id = event.GetId()
        if _id == self.IDsc_cmin:
            cmin = float(self.sc_cmin.GetValue())
            cmax = abs(cmin)*4.0
            self.sc_cmax.SetValue(cmax)
        elif _id == self.IDsc_cmax:
            cmax = float(self.sc_cmax.GetValue())
            cmin = -abs(cmax)/4.0
            self.sc_cmin.SetValue(cmin)
        durpre[0] = self.sc_preS.GetValue()
        durpre[1] = self.sc_preE.GetValue()
        durres[0] = self.sc_resS.GetValue()
        durres[1] = self.sc_resE.GetValue()
        margin = self.margin.GetValue()
        ch = self.ch.GetValue()
        ref_ch = self.alignch.GetValue()
        cutoff = self.sc_cutoff.GetValue()
        self.updateImages(event)


    def OnCheck(self, event):

        global SpatMed, SpatMed2, fastLoad, Autoalign, Overlay, cutoffON, SDthrs
        SpatMed = self.SpaMed.IsChecked()
        SpatMed2 = self.SpaMed2.IsChecked()
        fastLoad = self.fastLoad.IsChecked()
        Autoalign = self.Autoalign.IsChecked()
        Overlay = self.overlay.IsChecked()
        SDthrs = self.SDthrs.IsChecked()
        
        if Overlay: 
            self.cutoff.SetValue(True)
        cutoffON = self.cutoff.IsChecked()
        
        self.sc_cutoff.Enable(cutoffON)
        self.updateImages(None)


    def updateImages(self, event):

        for child in self.parent.GetChildren():
            if isinstance(child, wx.Frame):
                #print 'frame found: ', child.GetTitle()
                if hasattr(child, 'refresh_buf'):
                    child.refresh_buf()
                    child.Refresh()


class BatchLauncher(wx.Panel):

    def __init__(self, parent, id, csvname):

        max_column = max([len(d) for __,d in csvdict.items()][2:])
        max_column = max([max_column, 5]) # 4th col needs twice width
        width = 140
        size = (width*4.5, 350+14+ymargin[1]-30)
        lbsize = (130,175)

        wx.Panel.__init__(self, parent, id, size=size, name='BatchLauncher')

        if platform.system() == 'Linux':
            self.SetFont(wx.Font(7, wx.SWISS, wx.NORMAL, wx.NORMAL))

        self.parent = parent
        self.csvname = csvname

        try:
            verstr = csvdict[1][1]
            ver = float(verstr)
        except (IndexError, ValueError):
            ver = 1.0
        print 'Pymagor Sheet ver = %1.1f' % (ver)
        self.ver = ver

        # ignore header in the first 2 lines.
        files   = [s[0] for _, s in csvdict.items()][2:]
        planes  = [s[1] for _, s in csvdict.items()][2:]
        odors   = [s[2] for _, s in csvdict.items()][2:]
        repeats = [s[3] for _, s in csvdict.items()][2:]
        fpaths  = [s[-1] for _, s in csvdict.items()][2:]

        dd = [item for __, sublist in csvdict.items() for item in sublist]
        if ver > 1.0:
            path2img = dd[max_column*2+max_column-1::max_column]
            self.path2img = path2img

        self.datalb1 = list(set(planes))
        self.datalb1.sort()
        self.datalb2 = list(set(odors))
        self.datalb2.sort()
        self.datalb3 = repeats
        self.datalb4 = files
        self.fpaths = fpaths

        wx.StaticText(self, -1, dd[max_column+1]+' (1st filter)', (8, 10))
        self.IDlb1 = wx.NewId()
        w = lbsize[0] * max([len(d) for d in self.datalb1]) / 20.0
        w1 = lbsize[0]*(w<=lbsize[0]) + w*(w>lbsize[0])
        self.lb1 = wx.ListBox(self, self.IDlb1, (8, 30),
                            (w1,lbsize[1]), self.datalb1, wx.LB_EXTENDED)
        self.Bind(wx.EVT_LISTBOX, self.OnMultiListBox, self.lb1)
        self.lb1.SetSelection(0)

        wx.StaticText(self, -1, dd[max_column+2]+' (2nd filter)', (w1+8+4, 10))
        self.IDlb2 = wx.NewId()
        w = lbsize[0] * max([len(d) for d in self.datalb2]) / 20.0
        w2 = lbsize[0]*(w<=lbsize[0]) + w*(w>lbsize[0])
        self.lb2 = wx.ListBox(self, self.IDlb2, (w1+12, 30),
                            (w2,lbsize[1]), self.datalb2, wx.LB_EXTENDED)
        self.Bind(wx.EVT_LISTBOX, self.OnMultiListBox, self.lb2)
        self.lb2.SetSelection(0)

        wx.StaticText(self, -1, dd[max_column+3], (w1+w2+16, 10))
        self.IDlb3 = wx.NewId()
        w = lbsize[0] * max([len(d) for d in self.datalb3]) / 20.0
        w3 = 0.5*lbsize[0]*(w<=lbsize[0]/2) + w*(w>lbsize[0]/2)
        self.lb3 = wx.ListBox(self, self.IDlb3, (w1+w2+16, 30),
                        (w3,265), self.datalb3, wx.LB_EXTENDED)
        self.Bind(wx.EVT_LISTBOX, self.OnMultiListBox, self.lb3)
        self.lb3.SetSelection(0)

        wx.StaticText(self, -1, dd[max_column], (w1+w2+w3+20, 10))
        self.IDlb4 = wx.NewId()
        w = lbsize[0] * max([len(d) for d in self.datalb4]) / 20.0
        w4 = 2*lbsize[0]*(w<=lbsize[0]) + w*(w>lbsize[0])
        if w1+w2+w3+w4 < self.GetSizeTuple()[0]-15:
            w4 = self.GetSizeTuple()[0] - w1 -w2 -w3 -15
        self.lb4 = wx.ListBox(self, self.IDlb4, (w1+w2+w3+20, 30),
                    (w4, 265), self.datalb4, wx.LB_EXTENDED)

        self.Bind(wx.EVT_LISTBOX, self.OnFileSelect, self.lb4)
        self.lb4.SetSelection(0)

        self.SetSize((w1+w2+w3+w4+4*3+8+8+16, size[1]))

        self.oepneach = wx.Button(self, -1, 'Open each file', (7, 215))
        self.Bind(wx.EVT_BUTTON, self.OnOpenSelected, self.oepneach)
        self.oepneach.SetSize(self.oepneach.GetBestSize())

        b4 = wx.Button(self, -1, 'Reload csv sheet',(107,215),style=wx.NO_BORDER)
        self.Bind(wx.EVT_BUTTON, self.OnReload, b4)

        wx.StaticBox(self, -1, 'Stack mode', (5,240),(216,95))
        self.IDallfr = wx.NewId()
        self.stacknow = wx.Button(self, self.IDallfr, 'Stack now!', (19, 259))
        self.Bind(wx.EVT_BUTTON, self.OnStackPlanes, self.stacknow)
        self.stacknow.SetSize(self.stacknow.GetBestSize())

        self.rb1 = wx.RadioBox(self, -1, 'Frames to stack', (109, 248),
                        wx.DefaultSize, ['All raw + dF/F','F and response', 'one frame each'],
                        1, wx.RA_SPECIFY_COLS)
        self.rb1.SetSelection(2)

        self.IDAvgTr = wx.NewId()
        self.IDMaxPr = wx.NewId()
        self.cbAvgTr = wx.CheckBox(self, self.IDAvgTr, "Avg projection", (12,287))
        self.cbMaxPr = wx.CheckBox(self, self.IDMaxPr, "Max projection", (12,302))
        self.cbAvgTr.SetValue(False)
        self.cbMaxPr.SetValue(False)

        self.cb = wx.CheckBox(self, -1, 'Auto align trials', (w1+w2-25, 295))
        self.Bind(wx.EVT_CHECKBOX, self.OnAuto, self.cb)

        wx.StaticText(self, -1, 'Ref tr#:', (w1+w2-25,313))
        self.IDsp_ref = wx.NewId()
        self.sp_ref = wx.SpinCtrl(self, self.IDsp_ref, '0', (w1+w2+16,310), (62,20))
        self.Bind(wx.EVT_SPINCTRL, self.OnSpin, self.sp_ref)

        self.reftrial = wx.TextCtrl(self, -1, "None", pos=(w1+w2+w3+20,310),
                                size=(w4, 20), style = wx.TE_READONLY)
        # default for auto ref picker
        cb = True
        self.cb.SetValue(cb)
        self.sp_ref.Enable(cb==False)
        self.reftrial.Enable(cb==False)

    # Event handlers

    def OnAuto(self, event):
        cb = self.cb.GetValue()
        self.sp_ref.Enable(cb==False)
        self.reftrial.Enable(cb==False)

    def OnFileSelect(self, event):

        self.parent.log.SetInsertionPointEnd()
        filt = csvdict.items()
        selection4 = self.lb4.GetSelections()

        filtered = []
        for ind in selection4:
            fname = self.datalb4[ind]
            fpath = self.fpaths[ind]
            filtered.append( [s for _,s in filt if fname is s[0] and fpath is s[-1]] )

        filtered = [item for sublist in filtered for item in sublist]
        #print 'filtered', filtered

        global fromlauncher
        fromlauncher = []
        if filtered:

            for data in filtered:
                fromlauncher.append(data)

            if verbose:
                print 'Selected files:'
                print fromlauncher

            print '%d fils(s) selected.' % (len(fromlauncher))
            self.sp_ref.SetRange(0, len(fromlauncher)-1)

        self.OnSpin(event)

    def OnReload(self, event):

        print 'Reloading excel sheet...'
        MainFrame.loadcsv(self.parent, event, self.csvname)

    def OnOpenSelected(self, event):

        global working_singles, need_abort_singles

        if fromlauncher is not None and fromlauncher != []:
            if not working_singles:
                working_singles = True
                self.oepneach.SetLabel('Abort')

                for data in fromlauncher:
                    if not need_abort_singles:
                        self.OnStackPlanes(event, [data], True)
                        wx.Yield()

                # back to normal
                self.oepneach.SetLabel('Open each file')
                need_abort_singles = False
                working_singles = False
            else: # try to abort
                need_abort_singles = True
                self.oepneach.SetLabel('Aborting..')
                print 'Aborting...'
        else:
            print 'No files selected.'

    def OnMultiListBox(self, event):

        global fromlauncher
        fromlauncher = []
        selection1 = self.lb1.GetSelections()
        selection2 = self.lb2.GetSelections()
        selection3 = self.lb3.GetSelections()
        filt = list( csvdict.items() )

        id = event.GetId()
        if id == self.IDlb3:
            for ind in range(len(filt)-2):
                self.lb4.SetSelection(ind, (ind in selection3) )
        elif id == self.IDlb1 or id == self.IDlb2:
            filtered = []
            for ind in selection1:
                key1 = self.datalb1[ind]
                temp= [s for s in filt if key1 in s[1]]
                for ind2 in selection2:
                    key2 = self.datalb2[ind2]
                    temp2 = [s for s in temp if key2 in s[1]]
                    filtered.append([s for s in temp2 if not 'nan' in s[1]])

            # this magic flattens the nested list.
            filtered_index = [item[0] for sublist in filtered for item in sublist]

            for ind in range(len(filt)-2):
                flag = (ind+3 in filtered_index)
                self.lb3.SetSelection(ind, flag)
                self.lb4.SetSelection(ind, flag)

        self.OnFileSelect(event)

    def OnSpin(self, event):

        if fromlauncher is not None and fromlauncher != []:
            ref = self.sp_ref.GetValue()
            reftrial = fromlauncher[ref][0]
            self.reftrial.SetValue(reftrial)

    def OnStackPlanes(self, event, datafiles=None, lock=True):
        # there are only two sources calling this.
        # (1) the Stack now! button. datafiles, lock will be empty.
        # (2) Open each file event handler which provide datafiles and lock
        self.parent.log.SetInsertionPointEnd()
        print time.strftime('Packing files: %b %d, %Y (%a) %X')

        global working_singles, need_abort_singles, working, need_abort
        global ch, ref_ch

        if ch != ref_ch:
            Pymagor2.showmessage('Caution! Reference channel is different from loading channel.')

        if not working:

            if (fromlauncher is not None and fromlauncher != []) or datafiles is not None:
                working = True
                if not working_singles:
                    self.stacknow.SetLabel('Abort')

                if not need_abort:
                    data_path = csvdict[1][0]  # in ver2 this only means where the sheet is.
                    if datafiles is None:
                        datafiles = fromlauncher
                    howmanyframe = self.rb1.GetSelection()
                    AvgTr = self.cbAvgTr.IsChecked()
                    MaxPr = self.cbMaxPr.IsChecked()
                    Fnoise = self.parent.ParamsPane.sc_Fnoise.GetValue()

                    if self.cb.GetValue(): # auto align
                        reftr = None
                    else:
                        reftr = self.sp_ref.GetValue()

                    imgdic, tag = pack(
                        data_path, datafiles, howmanyframe, AvgTr, MaxPr, anatomy_method, 
                        Fnoise, fastLoad, verbose, durpre, durres, ch, ref_ch, reftr, margin
                        )
                    if not need_abort and imgdic is not None and imgdic and tag:
                        Pymagor2.OnNewChild2(imgdic, tag=tag, lock=lock)
                        if pickle_stacked:
                            with open('test_'+tag[0][0]+'.pkl','wb') as f:
                                pickle.dump(imgdic, f)
                                pickle.dump(tag, f, -1)
                    else:
                        print 'Aborted.'

                # back to normal
                self.stacknow.SetLabel('Stack now!')
                need_abort = False
                working = False
            else:
                print 'No files selected.'

        else:  # try to abort
            need_abort = True
            if not working_singles:
                self.stacknow.SetLabel('Aborting..')
            print 'Aborting...'


# Global function

def loadmat(fp):
    data = sio.loadmat(fp)
    ind = [key.startswith('pymg') for key in data.keys()].index(True)
    return data[data.keys()[ind]]

def gray2clut2b(img, cmin, cmax):
    '''
    apply a clut2b colormap to dF/F map
    '''
    
    # Strech dFoF value to 8-bit range in order to use the full color map space.
    img[np.isnan(img)] = cmin  # cmin < 0 will fail if nan is there
    img[img>cmax] = cmax
    img[img<cmin] = cmin
    img = ((img-cmin) * 255.0 / (cmax-cmin)).astype(np.uint8)
    
    return cmap[img]


def path_check(fullpath, verbose=True):
    
    try:
        if os.path.exists(fullpath):
            return fullpath
        else:
            for D in ['C','F','R']:
                driveletter, rest = fullpath.split(':')
                fullpath = os.path.join(D+':', rest)
                if os.path.exists(fullpath):
                    if verbose:
                        print 'The path was changed to %s' % (fullpath)
                    return fullpath
            return None
    except ValueError:
        return None

def Shift(ImgP, Foffset, padding=True):
    
    maxShift = int(np.abs(Foffset[:,0:2]).max()) # max shift
    if not maxShift:
        return ImgP
    else:
        ImgPshited = np.zeros((ImgP.shape), dtype=ImgP.dtype)
        
        for y,x,c,ind in Foffset: # [1:] # yoff, xoff, correlation, ind
            #print 'offset (y=%d, x=%d), corr=%f, index=%d' % (y,x,c,ind)
            ind = int(ind)
            if y: 
                ImgP[:,:,ind] = np.roll(ImgP[:,:,ind], int(-y), axis=0)
            if x:
                ImgP[:,:,ind] = np.roll(ImgP[:,:,ind], int(-x), axis=1)
        
        # 0 padding the margin
        if padding:
            ImgPshited[maxShift:-maxShift,maxShift:-maxShift,:] = ImgP[maxShift:-maxShift,maxShift:-maxShift,:]
            return ImgPshited
        else:
            return ImgP


def pad_imgseq(img):
    '''
    img : frames by height by width array of image sequence
    
    returns sequence of 1 px mirror reflection padded image 
    '''
    n,h,w = img.shape
    padded = np.zeros((n,h+2, w+2))
    padded[:, 1:-1, 0] = img[:,:,0]
    padded[:, 1:-1, w+1] = img[:,:,w-1]
    padded[:, 0, 1:-1] = img[:,0,:]
    padded[:, h+1, 1:-1] = img[:,h-1,:]
    padded[:, 0, 0] = img[:,0,0]
    padded[:, h+1, 0] = img[:,h-1,0]
    padded[:, 0, w+1] = img[:,0,w-1]
    padded[:, h+1, w+1] = img[:,h-1,w-1]
    padded[:,1:-1,1:-1] = img

    return padded

def pad_img(img):
    '''
    img : height x width array of image
    
    returns 1 px mirror reflection padded array
    '''
    h,w = img.shape
    padded = np.zeros((h+2, w+2))
    padded[1:-1, 0] = img[:,0]
    padded[1:-1, w+1] = img[:,w-1]
    padded[0, 1:-1] = img[0,:]
    padded[h+1, 1:-1] = img[h-1,:]
    padded[0, 0] = img[0,0]
    padded[h+1, 0] = img[h-1,0]
    padded[0, w+1] = img[0,w-1]
    padded[h+1, w+1] = img[h-1,w-1]
    padded[1:-1,1:-1] = img

    return padded


def _applymask(img, maxShift):
    
    if maxShift: # [maxShift:-maxShift] indexing would not work if maxShift = 0
        mask = np.zeros((img.shape), dtype=np.bool)
        maxShift = int(maxShift)
        if len(mask.shape) == 3:
            mask[maxShift:-maxShift,maxShift:-maxShift,:] = True
        elif len(mask.shape) == 2:
            mask[maxShift:-maxShift,maxShift:-maxShift] = True
        else:
            print 'not supported dimmention'
            return img
        
        img[mask==False] = 0
    
    return img


def shiftmask(mask, (yoff,xoff)):
    
    # Foffset: yoff, xoff, correlation, ind
    maxShift = np.abs([yoff, xoff]).max() # max shift
    if maxShift:
        mask = np.roll(mask, int(yoff), axis=0)
        mask = np.roll(mask, int(xoff), axis=1)
        
        # 0 padding the margin
        shifted = np.zeros((mask.shape), dtype=mask.dtype)
        shifted[maxShift:-maxShift,maxShift:-maxShift] = mask[maxShift:-maxShift,maxShift:-maxShift]
        
        return shifted
    else:
        return mask


def getdFoFtraces(img, durpre, masks, raw=False, baseline=False, offset=None, needflip=True, Fnoise=0):
    
    if needflip:
        img = img[::-1,:,:] # pymagor1.0 flip y-axis of the ROI buffer. v2.0's ROI buf does not.
    img -= Fnoise

    nframes = img.shape[2]
    F = img[:, :, durpre[0]:durpre[1]+1].mean(axis=2)  # dure[1]+1 because np indexing needs the first number that you dont want
    F[F==0] = F[F.nonzero()].min()  # replaced with non zero minimum value (important for dFoF movie but here needed?)
    
    if baseline:
        masks.append( (np.dstack(masks).max(axis=2) == False) )
    
    waves = np.zeros((nframes,len(masks)))
    for ind, mask in enumerate(masks):
        if offset:
            mask = shiftmask(mask, offset)
        if raw:
            for n in range(nframes):
                waves[n, ind] = np.mean(img[mask,n])
        else:
            Favg = np.mean(F[mask])   # Get one number for F
            for n in range(nframes):
                waves[n, ind] = np.mean(100.0*(img[mask,n]-Favg)/Favg)
    
    if baseline:
        w = np.ones(nframes/10,'d')/(nframes/10) # flat window for moving average
        waves[:,ind] = np.convolve(w, waves[:,ind], mode='same')
    
    return waves


def getmask(poly, (h,w)): # nx is depreciated after matplotlib 1.2.0
    poly = np.array(poly)
    ymax = int(np.ceil(poly[:,1].max()))
    xmax = int(np.ceil(poly[:,0].max()))
    ymin = int(np.floor(poly[:,1].min()))
    xmin = int(np.floor(poly[:,0].min()))
    # sanity check for ymin, ymax, xmin, xmax
    if ymin<0: ymin = 0
    if xmin<0: xmin = 0
    if ymax>=h: ymax = h-1
    if xmax>=h: xmax = w-1
    
    x, y = np.meshgrid(np.arange(xmin, xmax+1), np.arange(ymin, ymax+1))
    x, y = x.flatten()+0.5, y.flatten()+0.5  # +0.5 enables to pick up 1x1 pixel ROI
    xypoints = np.vstack((x,y)).T 
    
    mask = np.zeros((h,w), dtype=np.bool8)
    mask[ymin:ymax+1, xmin:xmax+1]  = \
       Path(poly).contains_points(xypoints).reshape(ymax+1-ymin, xmax+1-xmin)
    
    return mask


def get_offset_within_trial_img(img, data_folder, fname, durpre, margin, SpaMeds, Fnoise):
    '''normaly retrive or compute within trial frame alignment offset data but when None is 
        passed to img from PDF export, update Lastdurres, LastFnoise in offset file.
    '''
    durpre = tuple(durpre) # checkdurs returns durpre as tuple but global var is a list
    fp_offset, offset_dict, Lastdurres, LastFnoise = get_saved_offsets(data_folder)
    if Lastdurres is None or (img is None):
        Lastdurres = durres
    if LastFnoise is None or (img is None):
        LastFnoise = Fnoise # Pymagor2.ParamsPane.sc_Fnoise.GetValue()
    
    key = (fname, ref_ch, durpre, SpaMeds, margin)

    if key in offset_dict.keys():
        return offset_dict[key]
    
    # otherwise we need to compute it
    if img is not None:
        offsets = corr.fast_corr(img, margin=margin, dur=durpre, SpaMed=SpaMeds, verbose=True)
        offset_dict[key] = offsets

        # cleaning old version (without margin in the key)
        for k in offset_dict.keys():
            if len(k) == 4:
                offset_dict.pop(k)

        with open(fp_offset, 'wb') as f:
            pickle.dump({   'offset_dict':offset_dict, 
                            'Lastdurres':Lastdurres, 
                            'LastFnoise': LastFnoise    }, f, protocol=2)
        return offset_dict[key]
    else: # just update Lastdurres and LastFnoise when img=None passed from PDF export
        with open(fp_offset, 'wb') as f:
            pickle.dump({   'offset_dict':offset_dict, # this is what is loaded above. can be an empty dict
                            'Lastdurres':Lastdurres, 
                            'LastFnoise': LastFnoise    }, f, protocol=2)
        return None


def get_saved_offsets(data_folder):
    fname = os.path.basename(data_folder)+'.offset'
    fp_offset = os.path.join(data_folder, fname)
    
    if os.path.exists(fp_offset):

        loaded = np.load(fp_offset) # np can load pickle :)
        if 'offset_dict' in loaded.keys():
            offset_dict = loaded['offset_dict']
            Lastdurres = loaded['Lastdurres']
            LastFnoise = loaded['LastFnoise']

        else:
            offset_dict = loaded
            Lastdurres = None
            LastFnoise = None
    else:
        offset_dict = {}
        Lastdurres = None
        LastFnoise = None
    
    return fp_offset, offset_dict, Lastdurres, LastFnoise


def show_offsetinfo(fp_offset, offset_dict, Lastdurres, LastFnoise):
    
    print 'Offset file: ', fp_offset
    for k in sorted(offset_dict.keys()):
        if Lastdurres:
            message = '\t%s\t\tRef ch=%d\t\tPre-stimulus period=%s\t\tSpatial filters=%s\t\tmargin=%d' % k
        else: # old ver, may not have margin saved.
            message = '\t%s\t\tRef ch=%d\t\tPre-stimulus period=%s\t\tSpatial filters=%s' % k[:4]
            if len(k) == 5:
                message += '\t\tmargin=%d' % k[4]
        print message
    
    # Pre-stim is for each file because it affest alignment. Stim period just helps users repeat the same analysis
    if Lastdurres:
        print 'Last stimulus period=(%d,%d)' % tuple(Lastdurres)
    if LastFnoise is not None: # Often this is 0 which is evaluated as False
        print 'Last Background noise offset=%d' % LastFnoise

def _shift_a_frame(img, (yoff, xoff)):
    img = np.roll(img, int(-yoff), axis=0)
    img = np.roll(img, int(-xoff), axis=1)
    return img


def checkdurs(fp, parent=None):
    
    img_info = get_tags(fp)
    nframes = img_info['nframes']
    nch = img_info['nch']

    if nframes <= max(max(durres, durpre)):
        Pymagor2.showmessage(
        '%d is larger than the max frame number (%d) for %s\n' % 
        (max(max(durres, durpre)), nframes-1, fp) )
        return None, None
        # _durpre = [fr if fr < nframes-1 else nframes-1 for fr in durpre]
        # _durres = [fr if fr < nframes-1 else nframes-1 for fr in durres]
    else:
        _durpre, _durres = durpre, durres

    return tuple(_durpre), tuple(_durres), nframes, nch


def path2img(data_path, tag):
    ''' Get the full path to the image data. '''
    # print 'path2img : ', len(tag), tag, data_path
    path_in_tag = path_check(tag[-1], False)
    if path_in_tag and (len(tag) in [4,5] or len(tag) > 10):
            # from context menu or version v2 pymagor sheet.
        data_path = path_in_tag
    else:   # from v1 pymagor sheet.
        data_path = path_check(data_path, verbose)

    if not data_path or need_abort: # something went wrong
        return None, None, None, None, None

    return os.path.join(data_path, tag[0])


def pack2npobj(ROI, height=False):
    ' Prepare numpy obj to be saved as matlab cell '

    matpoly = np.zeros((len(ROI.data),), dtype=np.object)
    matplane = np.zeros((len(ROI.z),), dtype=np.object)
    matctgr = np.zeros((len(ROI.category),), dtype=np.object)

    for n in range(len(ROI.data)):
        matpoly[n] = ROI.data[n]
        matplane[n] = ROI.z[n]
        matctgr[n] = ROI.category[n]

    return matpoly, matplane, matctgr


def versiontuple(v):
    return tuple([int(vv) if len(vv)==1 else int(vv[0])  for vv in v.split(".") ])


def getIndicesInWhole(part, whole):
    'compare two different size vectors and return the indices of part elements in whole'
    return [np.argmax(whole == element) for element in part]


def ComputeThisPlane(data_path, tags, howmanyframe, need_AvgTr, need_MaxPr, anatomy_method, 
        Fnoise, fastLoad, verbose, durpre, durres, ch, ref_ch, reftr=None, margin=9, 
        ROIpoly_n=False, Foffsets=None, wantsraw=False):
    '''This is a dual-purpose function:
        1. When called from pack, it takes exactly the same args as pack except that 
        tags is now filtered for one plane (field-of-view). For this mode optional ROIpoly_n 
        and Foffsets should be omitted. 
        It does everything for this plane (i.e., load images, compute F, F_ref, res etc, 
        align F_ref, then compute trial average for each odor, do avg/max projections)
        
        2. When ROIpoly_n and Foffsets are provided, we only want trial average dF/F traces 
        for a stimulus-plane combination. [tags] and [Foffsets] are already filtered for
        one stimulus-plane combination.
        ROIpoly_n : [roipolys, cellnumbers]
        Foffsets  : a numpy array of [yoff, xoff, r, nn] for each file in tags (e.i., the same order with tags)
        wantsraw  : bool. indicate raw pixel value output instead of dF/F (%)
    '''

    if fastLoad:
        dtype = np.uint8
    else:
        dtype = np.uint16
    
    nframesP = []
    rawP, durresrawP, F_P, F_refP, anatomyP, resmapP, DFoFmovieP = [],[],[],[],[],[],[]
    z = tags[0][1] # current plane name (all the same)
    maxShiftWithinTrP = []

    # First, we need F_ref from each image. This is used for trial alignment (simple x,y translation only, Foffset).
    # Since we are opening those file anyway, we will also compute nframes, raw, F, anatomy, resmap, DFoFmovie. 
    # Using Foffset to shift images, we can finally compute trial average of F (F_travg), 
    # response map (resmap_travg). We will also create a list (odors_travg) containing odor names 
    # in the same order as F_travg and resmap_travg. 
    
    if ROIpoly_n:
        raw4trialAvg = None
    
    for n, tag in enumerate(tags): # n is used for Foffsets

        if need_abort:
            return None

        fp = path2img(data_path, tag)
        img_info = get_tags(fp) # let's access file just once for meta data
        nframes = img_info['nframes']
        nch = img_info['nch']
        # we make use of nframes and nch to find out which frames we do need to load from file.
        # 'anatomy' is defined as the average of all frames.
        # if more than 100 frames, we pick 100 frames eaqually spaced from the entire file.
        fr2load_pre = np.arange(durpre[0], durpre[1]+1) * nch + ch
        fr2load_res = np.arange(durres[0], durres[1]+1) * nch + ch
        if nframes<100 or Autoalign or ROIpoly_n:  # Autoalign (within trial) or ROIpoly_n needs all frames
            fr2load_anat = np.arange(0, nframes) * nch + ch
            frames2load = fr2load_anat
        else: # pick 100 frames eaqually spaced for anatomy
            tmp = np.arange(0, nframes) * nch + ch
            ind = np.linspace(0, tmp.size-1, 100).astype(int) 
            fr2load_anat = tmp[ind]
            frames2load = np.unique(np.hstack((fr2load_anat, fr2load_pre, fr2load_res)))
        loadedframes = opentif(fp, dtype, filt=None, frames2load=frames2load, ch=ch, nch=nch, nframes=nframes) - Fnoise

        if Autoalign:
            if verbose:
                print 'Autoalign is on.'
            # when Autoalign = True, loadedframes has all frames
            withinTrOffsets = get_offset_within_trial_img(loadedframes, tag[-1], tag[0], durpre, margin, (SpatMed, SpatMed2), Fnoise)
            loadedframes = Shift(loadedframes.copy(), withinTrOffsets, padding=False)
            maxShiftWithinTr = np.abs(withinTrOffsets[:,0:2]).max() # max shift
            maxShiftWithinTrP.append(maxShiftWithinTr)
            # during dF/F computation, gausian filter will smear out the margin zero padding
            # remove margin at the end before appending
 
        if ROIpoly_n:  # we only need dF/F traces for one stim-plane combination
            # use Foffsets to align raw frames for trial average
            yoff, xoff, r, nn = Foffsets[n]
            if yoff: loadedframes = np.roll(loadedframes, int(-yoff), axis=0)
            if xoff: loadedframes = np.roll(loadedframes, int(-xoff), axis=1)

            if raw4trialAvg is not None:
                raw4trialAvg += loadedframes  
            else: # images we deal are usually 16 bit. 64-16=48 bit to buffer overflow. should be safe.
                raw4trialAvg = loadedframes.astype(np.float64)

        else: # normal operation, computing F, response, etc

            # raw
            if howmanyframe == 0:   # load all frames
                raw = loadedframes
            elif howmanyframe == 1: # only durpre + durpre
                ind = getIndicesInWhole(np.hstack((fr2load_pre, fr2load_res)), frames2load)
                raw = loadedframes[:,:,ind]
            elif howmanyframe == 2: # the first frame of F
                ind = getIndicesInWhole([fr2load_pre[0]], frames2load)
                raw = loadedframes[:,:,ind]

            # F and ref_F
            Find = getIndicesInWhole(fr2load_pre, frames2load)
            F = loadedframes[:,:,Find].mean(axis=2).astype(np.float32)
            F[F==0] = F[F.nonzero()].min() # avoid zero division when creating movie

            if ch != ref_ch:
                print 'Reference channel (%d) is different from loading channel (%d).' % (ref_ch, ch)
                frames2load_ref = np.arange(durpre[0], durpre[1]+1) * nch + ref_ch
                F_ref = opentif(fp, dtype, filt=None, frames2load=frames2load_ref, ch=ref_ch).mean(axis=2).astype(np.float32) - Fnoise
                F_ref[F_ref==0] = F_ref[F_ref.nonzero()].min()
            else:
                F_ref = F # pointer seems enough (no np.copy() needed)
            
            # anatomy
            _ind = getIndicesInWhole(fr2load_anat, frames2load)
            if anatomy_method:  # global anatomy_method flag
                anatomy = loadedframes.std(axis=2).astype(np.float32)
            else:
                anatomy = loadedframes.mean(axis=2).astype(np.float32)

            # resmapP (dF/F frame average for the response period)
            resind = getIndicesInWhole(fr2load_res, frames2load)
            res = loadedframes[:,:,resind]
            dFoF = 100.0 * (res.mean(axis=2) - F) / F
            resmap = ndimage.filters.convolve(dFoF, kernel, mode='nearest').astype(np.float32)

            # DFoFmovieP
            if howmanyframe == 0:   # load all frames
                try:
                    DFoFmovie = np.zeros(raw.shape, dtype=np.float32)
                    # we use 2D filter, less peak memory and more similar result 
                    # to IgorPro with our custum gaussian kernel
                    for n in range(raw.shape[2]): 
                        temp = 100.0 * (raw[:,:,n] - F)/F
                        DFoFmovie[:,:,n] = ndimage.filters.convolve(
                                        temp, kernel, mode='nearest'
                                        ).astype(np.float32)
                except:
                    print 'Not sufficient memory. dF/F movie skipped.'
                    DFoFmovie = None
            else:
                DFoFmovie = None

            # now append everything
            rawP.append(raw)
            if howmanyframe > 0: # we need this later again
                durresrawP.append(res)
            F_P.append(F)
            F_refP.append(F_ref)
            anatomyP.append(anatomy)
            resmapP.append(resmap)
            DFoFmovieP.append(DFoFmovie)
            nframesP.append(nframes) # legacy stuff for compatibility (sorted_tag)

            wx.Yield()
    # end of for tag in tags

    if ROIpoly_n: # continue on computing trial average dF/F
        roipolys, cellnumbers = ROIpoly_n
        masks = []
        maxShift = np.abs(Foffsets[:,:2]).max()
        h,w,_ = raw4trialAvg.shape
        for roi in roipolys:
            masks.append(getmask(roi,(h,w)))
        
        # normalize raw4trialAvg by # of trials per stimulus (i.e., averaging)
        raw4trialAvg /= len(tags) # tags is filtered for this stim-plane
        rawimg = _applymask(raw4trialAvg, maxShift)
        
        waves = getdFoFtraces(rawimg, durpre, masks, 
                raw=wantsraw, baseline=False, offset=None, needflip=True)

        return waves

    # Foffset (Align trials)
    # now that we have all F_ref. we can compute x,y offset.
    
    # lazy but fast concatination for corr2d function which need numpy array
    # rawP = np.dstack(rawP) do this after trial averaging 
    F_P = np.dstack(F_P)
    F_refP = np.dstack(F_refP)  # np.array(rawP) would be x10 slower
    anatomyP = np.dstack(anatomyP)
    resmapP = np.dstack(resmapP)
    if howmanyframe == 0:
        DFoFmovieP = np.dstack(DFoFmovieP)

    if len(tags) == 1:  # only 1 trial
        Foffset = np.array([[0,0,0,0]])
        margin4dict = 0

    else:  # need to align trials
        if verbose:
            print 'Spatial median filter option being used: Template=%s, Target=%s' % (SpatMed, SpatMed2)

        if reftr is not None:   # reftr can be 0 when manually specified
            Foffset = corr2d( F_refP, margin, reftr, (SpatMed, SpatMed2) )
        else:  # auto ref trial on, try  the first trial as ref and optimize
            Foffset = corr2d( F_refP, margin, 0, (SpatMed, SpatMed2) )
            total_offset = [ abs(e).max(axis=0).sum() for e in
                            [Foffset[:,0:2] - Foffset[n,0:2] for n in
                            range(Foffset.shape[0])] ]
            tr = total_offset.index(min(total_offset))
            print 'For the ref trial at plane (%s) Ref ch=(%d), trial #%d (%s) was used.' % (z, ref_ch, tr, tags[tr][0])
            if tr != 0: # re-do alignment with the best ref trial if needed
                Foffset = corr2d( F_refP, margin, tr, (SpatMed, SpatMed2) )
        
        wx.Yield()
        margin4dict = np.abs(Foffset[:,:2]).max()
        if margin4dict: # need to shift and re-checek?
            print 'Offset before alignment:\n  [y, x, corr, index]\n', Foffset
            print '0 padding margin = ', margin4dict

            F_P      = Shift(F_P.copy(), Foffset)
            F_refP   = Shift(F_refP.copy(), Foffset)
            resmapP  = Shift(resmapP.copy(), Foffset)
            anatomyP = Shift(anatomyP.copy(), Foffset)
            if howmanyframe==0:  # this option means "all frames"
                DFoFmovieP = Shift(DFoFmovieP.copy(), Foffset)

            # re-check
            if reftr is not None:  # reftr can be 0 when manually specified
                Foffset2 = corr2d(F_refP, margin, reftr, (SpatMed, SpatMed2))
            else:    # auto-on
                Foffset2 = corr2d(F_refP, margin, tr, (SpatMed, SpatMed2))
                print '\nSuggested ref trial at plane %s is #%s  %s\n' % (z, tr, tags[tr][0])

            print 'After alignment:\n  [y, x, corr, index]\n', Foffset2
            if abs(Foffset2[:,0:2]).max() > 1:
                txt = 'The current shift range setting (=%d) may not be large enough for plane %s.\nOr, try again without Median filter' % (margin, z)
                Pymagor2.showmessage(txt)

    # F_travg, resmap__travg, stimnames_travg
    F_travgP, resmap_travgP, stimnames_travgP = [], [], []

    # remove all the duplicates while preserving the order
    # http://stackoverflow.com/questions/480214/how-do-you-remove-duplicates-from-a-list-in-python-whilst-preserving-order
    seen = set()  # empty set object
    stimuli = [x for x in ([dd[2] for dd in tags]) if x not in seen and not seen.add(x)]
    for stim in stimuli:
        thisStimInd = [n for n,t in enumerate(tags) if t[2] == stim]
        RF_F = F_P[:,:,thisStimInd].mean(axis=2)
        RF_F[RF_F==0] = RF_F[RF_F.nonzero()].min()
        
        F_travgP.append(RF_F)

        # now re-calculate response using new RF_F
        n_resframes = durres[1]-durres[0]+1
        FF = np.tile(RF_F[:,:,np.newaxis], (1,1, len(thisStimInd) * n_resframes))

        # Autoalign guarantee all frames, howmanyframe == 0 means response frames should be in rawP
        if howmanyframe == 0:
            dFoF = np.dstack([r[:,:,resind] for n,r in enumerate(rawP) if n in thisStimInd]).astype(np.float32)
        else: # when howmanyframe>0, raw frames for response period kept aside in durresrawP
            dFoF = np.dstack([r for n,r in enumerate(durresrawP) if n in thisStimInd]).astype(np.float32)
        
        # apply Foffset to all frames. we need to modify Foffset though.
        _Foffset = np.vstack([np.tile(fo, (n_resframes,1)) for fo in Foffset[thisStimInd,:]])
        _Foffset[:,3] = np.arange(len(thisStimInd) * n_resframes)
        dFoF = Shift(dFoF.copy(), _Foffset)
        
        dFoF -= FF  # in-place operation is faster
        dFoF /= FF
        dFoF *= 100.0
        # resmap_travgP.append(dFoF.mean(axis=2).astype(np.float32))
        dFoF = dFoF.mean(axis=2)
        dFoF = _applymask(dFoF, margin4dict) # w/o this, filtering will smear out artifact
        responsemap = ndimage.filters.convolve(dFoF, kernel, mode='nearest').astype(np.float32)
        resmap_travgP.append(responsemap)
        
        stimnames_travgP.append(stim)
        wx.Yield()
    
    if len(resmap_travgP)>1:
        resmap_travgP = np.dstack(resmap_travgP)
        F_travgP = np.dstack(F_travgP)
    else:
        h,w = resmap_travgP[0].shape
        resmap_travgP = resmap_travgP[0].reshape(h,w,1) # dig out from the list
        F_travgP = F_travgP[0].reshape(h,w,1)
    
    
    resmap_travgP = _applymask(resmap_travgP, margin4dict) # removing filtering artifacts.
    F_travgP = _applymask(F_travgP, margin4dict)

    # finally convert rawP list into numpy array
    rawP = np.dstack(rawP)
    
    # apply margin zero-padding
    if Autoalign:
        for n, _maxShift in enumerate(maxShiftWithinTrP):
            if _maxShift:
                rawP[:,:,n] = _applymask(rawP[:,:,n], _maxShift)
                if howmanyframe > 0: # we need this later again
                    res = _applymask(res, _maxShift)
                F_P[:,:,n] = _applymask(F_P[:,:,n], _maxShift)
                F_refP[:,:,n] = _applymask(F_refP[:,:,n], _maxShift)
                anatomyP[:,:,n] = _applymask(anatomyP[:,:,n], _maxShift)
                resmapP[:,:,n] = _applymask(resmapP[:,:,n], _maxShift)
                if howmanyframe==0:
                    DFoFmovieP[:,:,n] = _applymask(DFoFmovieP[:,:,n], _maxShift)

    
    return nframesP, rawP, F_P, F_refP, anatomyP, resmapP, DFoFmovieP, Foffset, \
            margin4dict, F_travgP, resmap_travgP, stimnames_travgP

def pack(data_path, tags, howmanyframe, need_AvgTr, need_MaxPr, anatomy_method, 
        Fnoise, fastLoad, verbose, durpre, durres, ch, ref_ch, reftr=None, margin=9):
    '''refactored pack and its friends
    (LPMavg, LPMresmap, lowpeakmemload, checkdurs, LoadImage, average_odormaps)

    data_path: usually the parent folder path of the image files which can be in subfolders.
    tags: a list of image file meta data [fname, plane, stim, trial, ..., folder]
    howmanyframe: int. option for raw frames to pack.   0:all raw frames. 1: only pre(F) and res raw frames, 2: only the first raw frame of pre (F)
    need_AvgTr: bool. average projection through all trials for the field-of-view
    need_MaxPr: bool. max projection through all trials for the field-of-view
    anatomy_method: bool. If True, std is used instead of mean

    Fnoise: int specifying the background noise to subtract from F
    fastLoad: bool. if True, dtype=np.uint8 otherwise uint16
    verbose: bool. if True, show more debugging/processing message
    durpre: tuple of (int, int) specifying frame numbers (beggining and end of F baseline period)
    durres: tuple of (int, int) specifying frame numbers (beggining and end of response period)
    
    ch: int specifying channel to load
    ref_ch: int specifying the reference channel for trial alignment to load
    reftr: (optional) int specifying the index of the reference trial in [tag]
    margin: max pixel shift range for alignment
    '''
    
    if verbose:
        t0 = time.time()

    # we assume all files have the same number of frames 
    fp = path2img(data_path, tags[0]) # so just check the first image
    # maxFrames = get_tags(fp)['nframes']
    durpre, durres, maxFrames, nch = checkdurs(fp, parent=None)
    if durpre is None:
        return None, None

    # find unique field-of-views (planes)
    planes = np.unique([items[1] for items in tags])
    if np.all([a.startswith('z') for a in planes]):
        print '\t !!!!All filed-of-view names starting with z. Special sorting method applied. !!!!'
        index = np.argsort( z_prefix(planes) )
        unique_planes = planes[index]
    else:  # general sorting. may not be what you expect. name planes carefully...
        unique_planes = np.sort(planes).tolist()

    sorted_tag = []
    rawP, F_P, F_refP, anatomyP, resmapP, DFoFmovieP = [], [], [], [], [], []
    FoffsetP = []
    margin_dict = {}
    AvgProj, MaxProj = [],[]
    F_travgP, resmap_travgP, stimnames_travgP = [], [], []
    for z in unique_planes:     # field-of-views (ex. planes at different z levels)
        eachplane = [ items for items in tags if z == items[1] ]
        trials =    [ dd[3] for dd in eachplane ]
        odors =     [ dd[2].lower() for dd in eachplane ] # we want case insensitive sort
        # then lexsort for odors first (1st factor) and trials (2nd factor)
        eachplane = [ eachplane[ind] for ind in np.lexsort((trials, odors)) ]

        results = ComputeThisPlane(  data_path, eachplane, howmanyframe, need_AvgTr, need_MaxPr, 
            anatomy_method, Fnoise, fastLoad, verbose, durpre, durres, ch, ref_ch, reftr, margin)
        if results is not None: # None when aborted
            nframes, raw, F, F_ref, anatomy, resmap, DFoFmovie, Foffset, margin4dict, \
            F_travg, resmap_travg, stimnames_travg = results
        else:
            return None, None

        # append for different planes.
        rawP.append(raw)
        F_P.append(F)
        F_refP.append(F_ref)
        anatomyP.append(anatomy)
        resmapP.append(resmap)
        if howmanyframe == 0:
            DFoFmovieP.append(DFoFmovie)
        
        F_travgP.append(F_travg)
        resmap_travgP.append(resmap_travg)
        stimnames_travgP.append([(z,o) for o in stimnames_travg])

        if need_AvgTr:
            AvgProj.append( np.mean(np.dstack(resmapP),2) )
        if need_MaxPr:
            MaxProj.append( np.max(np.dstack(resmapP),2) )
        
        for n, nframe in enumerate(nframes): # insert # of frame found in image into tag
            eachplane[n].insert(-1, nframe)  # this goes to imgdict
        sorted_tag.append(eachplane)
        
        if len(eachplane) > 1:
            # filp y-axis due to the design changes in Pymagor v2.0
            Foffset[:,0] = -Foffset[:,0]
        FoffsetP.append(Foffset)
        margin_dict[z] = margin4dict

    # flatten
    sorted_tag = [item for sublist in sorted_tag for item in sublist]
    stimnames_travgP = [item for sublist in stimnames_travgP for item in sublist]

    # packing
    imgdict = dict()

    if len(rawP)>1:
        try:
            imgdict['unshifted frames'] = np.dstack(rawP)
        except MemoryError:
            print 'Memory Error. Packing only one frame per trial'
            imgdict['unshifted frames'] = rawP[:,:,0::len(eachplane)]
    else:
        imgdict['unshifted frames'] = rawP[0]

    if howmanyframe == 0:
        if len(DFoFmovieP) == 1:
            imgdict['dFoFfil'] = DFoFmovieP[0]  # avoid over flattening
        else:
            imgdict['dFoFfil'] = np.dstack(DFoFmovieP)

    # common stuff
    imgdict['data_path'] = data_path
    imgdict['durpre'] = durpre
    imgdict['durres'] = durres
    imgdict['fastLoad'] = fastLoad
    imgdict['uniquekey'] = unique_planes
    imgdict['F'] = np.dstack(F_P)
    imgdict['F_ref'] = np.dstack(F_refP) # new!
    imgdict['anatomy'] = np.dstack(anatomyP)
    imgdict['dFoFavg'] = np.dstack(resmapP)
    if resmap_travgP:
        imgdict['avg_F'] = np.dstack(F_travgP)
        imgdict['avg_odormaps'] = np.dstack(resmap_travgP)
        imgdict['avg_odormap odornames'] = stimnames_travgP
    if need_AvgTr:
        imgdict['avg projection'] = np.dstack(AvgProj)
    if need_MaxPr:
        imgdict['max projection'] = np.dstack(MaxProj)
    
    if len(FoffsetP)>1:
        Foffsets = np.vstack(FoffsetP)
    else:
        Foffsets = FoffsetP[0]
    if FoffsetP:
        imgdict['Foffset'] = Foffsets
    else:
        imgdict['Foffset'] = 0
    imgdict['margin'] = margin_dict

    if verbose:
        _sizeof = np.sum([ele.nbytes for ele in imgdict.values() if type(ele) == np.ndarray])
        print '\nAbout %2.2f s to load. %2.3f MB' % (time.time() - t0, _sizeof/1024.0/1024.0)

    return imgdict, sorted_tag

if __name__ == "__main__":
    app = wx.App(0)
    fishicon = wx.Icon(os.path.join('resources','fish2.ico'), wx.BITMAP_TYPE_ICO)
    ## for wx.Icon, wx.App object must be created first!
    Pymagor2 = MainFrame(None, -1)
    Pymagor2.Show(True)
    app.MainLoop()





