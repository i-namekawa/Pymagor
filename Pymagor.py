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


# STANDARD libraries
from __future__ import with_statement
from pprint import pprint
import ConfigParser, csv, getpass, itertools, os, platform
import re, subprocess, sys, time, webbrowser
myOS = platform.system()

# 3rd party libraries
from PIL import Image
from PIL import ImageDraw
from PIL import TiffImagePlugin  # for py2exe

import numpy as np
import scipy.ndimage
import scipy.io as sio
from scipy.sparse.csgraph import _validation  # # for py2exe
from scipy.spatial import ConvexHull
#import scipy.stats as stats

import matplotlib
matplotlib.use('Qt4Agg')
import matplotlib.cm as cm
import matplotlib.pyplot as plt

from matplotlib.patches import Polygon
from matplotlib.backends.backend_pdf import PdfPages
from matplotlib.font_manager import FontProperties
matplotlib.rcParams['figure.facecolor'] = 'w'
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

if myOS == 'windows':
    from win32process import CREATE_NO_WINDOW

from yapsy.PluginManager import PluginManager


# User libraries (sub-package of Pymagor2)
import corr, ROImanager
from ROImanager import z_prefix
from ROI import ROIv3 as ROI
from opentif import *
from misc import *
from create_pymagorsheet_v2 import *

# Global variables
release_version = '2.7'
with open('resources/version.info', 'r') as f:
    __version__ = f.readline().splitlines()[0]

# hardcoding the difference between xp and win7
# because wx2.8 does not support vista and above yet
# until I managed to update to wx3.0
if myOS == 'Windows':
    magnifier = wx.CURSOR_MAGNIFIER
    if 'HOMESHARE' in os.environ.keys():
        homedir = os.path.join(os.environ['HOMESHARE'], 'pymagor')
        # using HOMESHARE rather than USERPROFILE here, because
        # Group policy may redirect USERPROFILE to HOMESHARE when exists
    else:
        homedir = os.path.join(os.environ['USERPROFILE'], 'Documents\\pymagor')
    if platform.win32_ver()[0] == 'XP':  # resizable boarder is thin on XP.
        ymargin = (24, 32)
        xmargin = 12
    else:  # resizable boarder is thicker on windows 7.
        ymargin = (25, 32+8)  # 60
        xmargin = 12+8
elif myOS == 'Linux':
    magnifier = wx.CURSOR_SIZEWE
    homedir = os.path.join(os.path.expanduser('~'), 'pymagor')

if not os.path.exists(homedir):
    os.mkdir(homedir)

## if Pymagor.ini exists, use some parameters defined there.
MPLcache = matplotlib.get_configdir()
bindir = r'https://github.com/i-namekawa/Pymagor/releases'
documentationURL = 'https://github.com/i-namekawa/Pymagor/wiki'



cfg = ConfigParser.ConfigParser()
cfg.optionxform = str
results = cfg.read(os.path.join(homedir,'Pymagor.ini'))
if results: ## if Pymagor.ini exists, use it for user params
    for section in cfg.sections():
        for key, value in cfg.items(section):
            exec key + '=' + value
    ini_log = 'Pymagor.ini file found.'
else:
    ## default parameters that are normally defined in Pymagor.ini
    ini_log = 'No Pymagor.ini found.'
    
    durpre, durres = [0,25], [40,70]
    cmax = 70
    cmin = -cmax/4.0
    margin = 9
    SpatMed, SpatMed2, fastLoad = True, True, False
    
    min_fontsize = 7
    pickle_stacked = False
    verbose = True
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
    
anatomy_method = False

working_singles, need_abort_singles = False, False
working, need_abort = False, False

ch = 0           # default channel to load from tiff
ref_ch = 0       # default channel to use for alignment
csvdict = None   # Pymagor sheet
CntxPlugin = {}  # plugin objects dictionary for context menu

img_keys = ['unshifted frames', 'dFoFfil', 'F', 'dFoFavg', 'anatomy', 
            'avg_F', 'avg_odormaps', 'avg projection', 'max projection']

# load odor and plane persistency file
PlaneList = [] 
ConditionList = []
try:
    with open(os.path.join(homedir,'Stimulus_FieldOfView_Labels.csv')) as f:
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
        self.scz = wx.SpinCtrl(self.toolbar1, -1, '0', size=(53,20))
        self.scz.SetRange(0, self.z-1)
        
        self.ManScaling = wx.CheckBox(self.toolbar1, -1, 'ManSc')
        self.ManScaling.SetSize( self.ManScaling.GetBestSize() )
        self.ManScaling.SetValue(True)
        
        txt_H = wx.StaticText(self.toolbar1, -1, ' hi:')
        self.scH = wx.SpinCtrl(self.toolbar1, -1, '', size=(53,20))
        
        txt_L = wx.StaticText(self.toolbar1, -1, ' lo:')
        self.scL = wx.SpinCtrl(self.toolbar1, -1, '', size=(53,20))
        
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
        self.scYmax.SetRange(-100,200)
        Ymax = 80
        self.scYmax.SetValue(Ymax)
        self.scYmax.Enable(False)

        txt_Ymin = wx.StaticText(self.toolbar2, -1, 'min:')
        self.scYmin = wx.SpinCtrl(self.toolbar2, self.IDscYmin, '', size=(48,20))
        self.scYmin.SetRange(-100,200)
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
        self.reportbtn.SetToolTip(wx.ToolTip('Make a PDF Report and export as matfile'))
        
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
        
        # setting to surpress flickering
        # self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
        # It will prevent the system from trying to erase the window before the paint event. 
        # wx.NO_FULL_REPAINT_ON_RESIZE should not be used together
        # http://groups.google.com/group/wxpython-users/browse_thread/thread/eb048ae6c1867fe8
        
        # self.SetDoubleBuffered(True) # magic to kill flockering on XP, causes flickering in win7.
        # http://wxpython-users.1045709.n5.nabble.com/SetDoubleBuffer-and-wx-TextCtrl-leads-to-continual-repaints-td4788560.html
        # setting SetDoubleBuffered to the whole frame seems bad thing to do
        # limit it to the area that has flickering
        # self.display.SetDoubleBuffered(True)
        # in the end, i had to separate display panel and write my custom OnPaint handler there.
        # writing bmp directly on frame cannot capture key events at all.
        # so, decided to capture them on display panel as it used to be.
        
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
                    
                else: # then probably roiv3 and mat file format of pymagor 2.7 or above
                    ROIs = a[sname][0][0]['ROIs'][0]
                    roiz = [str(aa[0]) for aa in ROIs['ROI_Field_of_views'][0][0]]
                    _ind = [n for n,aa in enumerate(roiz) if aa in planesfound]
                    if not _ind:
                        print 'Field-of-Views found in matfile:', roiz
                        print 'Current Field-of-Views opened:', planesfound
                        self.parent.showmessage('None of\n%s in the mat file were found in \n%s that are opened' % (roiz, list(planesfound)) )
                        return
                    roipoly = [zip(aa[:,0], aa[:,1]) for aa in ROIs['ROI_polygons'][0][0]]
                    roipoly = [roipoly[n] for n in _ind]
                    roiz = [roiz[n] for n in _ind]
                    
                    roi_ctgr = [ str(aa[0]) for aa in ROIs['ROI_categories'][0][0] ]
                    roi_ctgr = [roi_ctgr[n] for n in _ind]
                
            else: # for roi v1 file, use the current plane name
                
                roiz = self.changetitle(wantz=True)
                roi_ctgr = 'Cell'
                h = a['F'].shape[0]
                roipoly = [ zip(aa[:,0].astype('int'), h-aa[:,1].astype('int')) 
                            for aa in a['ROIs'][0] ]
        
        elif fp.endswith('npz'):
            
            a = np.load(fp)
            if 'ROI_Field_of_views' in a.keys():  # renamed after public release
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
        
        return self.st_x+w, self.st_y+h
    
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
                offsets = [ offset for tag,offset in zip(self.tag, self.imgdict['Foffset']) if z == tag[1] ]
                return eachplane, offsets
        else: # [0] raw or [1] dF/F filtered
            zsize = self.z / len(self.tag)
            _tag = self.tag[self.curframe / zsize]
            data_path = _tag[-1]
            
            z = _tag[1]
            fname = _tag[0]
            title = z + ' ' + fname
            Foffset = self.imgdict['Foffset'][self.curframe / zsize, 0:2]
        
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
        txt = 'Min and Max pixel values in image : %d, %d' % (img.min(), img.max() )
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
            marker_pos = np.abs(_trace[self.durpre[1]:]).argmax()+self.durpre[1]
            subplot.text(marker_pos, _trace[marker_pos], label[n], color=color, fontproperties=fontBold)
            
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
        
        # clip out the zoomed region 
        x1, y1, x2, y2 = self.zoomrect
        if self.dragging:
            offsetx, offsety = self.boarder_check()
            frame = self.img[self.h-y2-offsety : self.h-y1-offsety, 
                            x1+offsetx : x2+offsetx, 
                            self.curframe].copy() # copy important for manualscaling
            if update_zoomrect:
                self.zoomrect = (x1+offsetx, y1+offsety, x2+offsetx, y2+offsety)
        else:
            frame = self.img[self.h-y2:self.h-y1, x1:x2, self.curframe].copy() # copy important for manualscaling
        
        # color look up
        if self.TVch in [1, 3, 6, 7, 8] : # dFoF time-avg, dFoF movie, odormaps, avg or max projection
            buf = gray2clut2b(frame[::-1,:].copy(), cmin, cmax)
        # gray scale
        else: # unshifted frames | F | anatomy
            if self.ManScaling.IsChecked(): # Manual contrast adjust
                frame = self.manualscale(frame)
            else:                           # Auto contrast adjust
                frame = self.manualscale(frame, frame.max(), frame.min())
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
            im = Image.fromstring('RGB',(w,h), buf)
            self.p.stdin.write(im.tostring('jpeg','RGB'))
        
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
            self.ID_closeall = wx.NewId()
            self.ID_baseline = wx.NewId()
            self.ID_ROI = wx.NewId()
            self.ID_ROInumber = wx.NewId()
            self.ID_ROIoutlines = wx.NewId()
            self.ID_AutoPSF = wx.NewId()
            
            self.Bind(wx.EVT_MENU, self.OnCtxROImode, id=self.ID_lock)
            self.Bind(wx.EVT_MENU, self.parent.OnCloseAll, id=self.ID_closeall)
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
        fname = '-'.join(self.tag[self.curframe][1:])

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
        
        if _id == self.ID_ROIimport:
            dlg = wx.FileDialog(
                self, message='Load ...', defaultDir=data_path,
                defaultFile=fppdf, wildcard='All files (*.mat)|*.mat',
                style=wx.FD_OPEN )
            if dlg.ShowModal() == wx.ID_OK:
                fp = dlg.GetPath()
                #_matD = matDrop(self)
                self.loadROI(fp)
        
        elif _id == self.ID_ROIexport:
            dlg = wx.FileDialog(
                self, message="Save file as ...", defaultDir=data_path,
                defaultFile=fppdf, wildcard='All files (*.mat)|*.mat',
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
        
        global ch, ref_ch
        ch_bak, ref_ch_bak = ch, ref_ch
        ch, ref_ch = self.ch, self.ref_ch
        
        if self.ROI.data == []:
            print 'no ROIs found.'
            return
        
        fp, Foffset = self.changetitle(wantfp_offset=True)
        
        self.plotbtn.Enable(False)
        raw = (event.GetId() == self.ID_plotraw)
        if type(fp) == list and type(Foffset) == list:  # ploting for "avg odormaps"
            ROIfound, ROIpolys = [], []
            z = self.changetitle(wantz=True)
            for n,zz in enumerate(self.ROI.z):
                if zz == z:
                    ROIfound.append(n+1)
                    ROIpolys.append(self.ROI.data[n])
            tags = fp
            durs = (durpre, durres)
            data_path = self.imgdict['data_path']
            Foffset = np.array(Foffset)
            Foffset[:,0] = -Foffset[:,0] # flix y-axis for shift function
            dFoF, odornames = average_odormaps(data_path, 
                                                tags, 
                                                Foffset, 
                                                Autoalign, 
                                                durs, 
                                                margin, 
                                                (SpatMed, SpatMed2),
                                                ch=ch, 
                                                ROIpoly_n=(ROIpolys, ROIfound), 
                                                raw=raw)
        else:
            dFoF, ROIfound = self.getdFoF(fp, dtype=np.uint16, offset=Foffset, raw=raw)
        
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
        
        self.plotbtn.Enable(True)
        
        if verbose:
            if npz: # numpy friendly output
                pprint (dFoF.T)
            else:  # MATLAB friendly output
                print dFoF.T
        
        ch, ref_ch = ch_bak, ref_ch_bak
        
        
    def getdFoF(self, fp, dtype=np.uint16, offset=None, z=False, raw=False):
        
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
            img = opentif(fp, dtype=dtype, filt=None, skip=None, ch=self.ch)
        
        if masks:
            dFoFtraces = getdFoFtraces(img, durpre, masks, raw=raw, baseline=self.baseline)
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
            
            print 'Saving a PDF summary and data as mat files...'
            fname = dlg.GetPath()
            if not fname.endswith('pdf'):
                fname[:-3] = 'pdf'
            
            Pooled = self.PDF(fname, data_path)
            self.savemat(fname, Pooled)
        
        dlg.Destroy()


    def PDF(self, fname, data_path):
        " generate a PDF report "
        
        pp = PdfPages(fname)
        size = (560,420)
        nfiles = len(self.tag)
        ncol = np.ceil(np.sqrt(nfiles))
        nrow = np.ceil(nfiles/ncol)
        
        def gethilo(frame):
            if self.ManScaling.IsChecked():
                Hi = self.scH.GetValue()
                Lo = self.scL.GetValue()
            else:
                Hi = frame.max()
                Lo = frame.min()
            return Hi,Lo
        
        def myimshow(figure, sbplt, frame, title=''):
            if len(frame.shape) == 2:   # gray scale image
                mappable = sbplt.imshow(frame, cmap=matplotlib.cm.gray)
                lo, hi = frame.min(), frame.max()
                ticks = [lo, (hi-lo)/2+lo, hi]
                clabel = [lo, (hi-lo)/2+lo, hi]
            else:                       # color image
                mappable = sbplt.imshow(frame)
                clabel = [cmin, (cmax-cmin)/2+cmin, cmax]
                ticks = [255*(a-cmin)/(cmax-cmin) for a in clabel]
                clabel = ['%3.1f%%' % a for a in clabel]
            sbplt.axis('off')
            sbplt.set_title(title, fontsize=10)
            if self.parent.export_transpose_collage.IsChecked():
                cbar = figure.colorbar(mappable, ticks=ticks, orientation='horizontal')
            else:
                cbar = figure.colorbar(mappable, ticks=ticks)
            cbar.ax.set_xticklabels(clabel)
        
        # prepare collage which comes after pages for individual trials
        collage = plt.figure(figsize=[6,4])
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
            dFoFtraces, ROIfound = self.getdFoF(fp, np.uint16, offset=Foffset, z=z)
            rawtraces, ROIfound = self.getdFoF(fp, np.uint16, offset=Foffset, z=z, raw=True)
            title = ', '.join(tag[1:3])[:21] + ', ' + tag[3]
            
            eachtrial = plt.figure(figsize=[6,4])
            eachtrial.suptitle(title)
            
            subplot1 = eachtrial.add_subplot(221)
            frame = self.imgdict['F'][::-1,:,ind]
            Hi, Lo = gethilo(frame)
            frame = self.manualscale(frame, Hi, Lo)
            myimshow(eachtrial, subplot1, frame, os.path.basename(os.path.dirname(fp)))
            
            subplot2 = eachtrial.add_subplot(222)
            bmp = gray2clut2b(self.imgdict['dFoFavg'][::-1,:,ind].copy(), cmin, cmax)
            myimshow(eachtrial, subplot2, bmp, os.path.basename(fp))
            
            fontsize = int(min_fontsize+(30-nfiles)/30)-(len(title)>25)
            found_ROIs = []
            for ind2, roi in enumerate(self.ROI.data):
                if self.ROI.z[ind2] == self.tag[ind][1]:
                    found_ROIs.append(ind2+1)
                    roi = [(x,y) for x,y in roi]
                    subplot1.add_patch(Polygon(roi, edgecolor='w',
                                            closed=True, fill=False))
                    subplot2.add_patch(Polygon(roi, edgecolor='w',
                                            closed=True, fill=False))
                    x, y = np.median(np.array(roi),axis=0)
                    subplot1.text(x,y,str(ind2+1), color='r', fontsize=fontsize)
            
            dFoFtracesPool.append([dFoFtraces, z, found_ROIs])
            rawtracesPool.append([rawtraces, z, found_ROIs])
            
            subplot = eachtrial.add_subplot(212)
            if dFoFtraces is not None:
                sb_trace = self.plot(subplot, dFoFtraces, label=found_ROIs)
            subplot.set_title(title)
            
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
            
        collage.savefig(pp, format='pdf')
        if self.parent.export_needplotting.IsChecked():
            collage.show()

        ## Last two pages   summary of F and dF/F avg fil
        # average across trials for each odor
        
        collage_avg = plt.figure(figsize=[6,4])
        collage_avg.suptitle('Averaged response maps for each plane-stimlus pair')
        
        collage_F = plt.figure(figsize=[6,4])
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
                #planes = np.array(
                #[float(filter(lambda x: x == '-' or x.isdigit(), z)) for z,o in Z_Odor], 
                #dtype=np.float)
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
            F, dFoFmap, odornames = average_odormaps(
                                        data_path, 
                                        tag, 
                                        Foffset, 
                                        Autoalign, 
                                        durs, 
                                        margin, 
                                        (SpatMed, SpatMed2),
                                        ch=ch)
            
            avg_traces, odornames = average_odormaps(
                                        data_path, 
                                        tag, 
                                        Foffset, 
                                        Autoalign, 
                                        durs, 
                                        margin, 
                                        (SpatMed, SpatMed2),
                                        ch=ch, 
                                        ROIpoly_n=(ROIpolys, found_ROIs)
                                        )
            
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
            Hi, Lo = gethilo(F[::-1,:,0])
            cllg2.imshow(self.manualscale(F[::-1,:,0], Hi, Lo), cmap=matplotlib.cm.gray)
            cllg2.set_title(title, fontsize=fontsize)
            cllg2.axis('off')
            
            # avg traces
            if self.parent.export_avgtraces.IsChecked():
                avg_trace_fig = plt.figure(figsize=[6,4])
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
                
                avg_trace_fig.savefig(pp, format='pdf')
                if self.parent.export_needplotting.IsChecked():
                    #avgtraces.Show(True)
                    avg_trace_fig.show()
        
        txt='Pymagor v%s (rev %s);\ndurpre = [%d, %d], durres = [%d, %d];\nmargin ' % (release_version,__version__, durpre[0],durpre[1],durres[0],durres[1])
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
        self.Parent.showmessage('exported successfully.')
        
        
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
        a, b = opentif(fp, skip=False, check8bit=abortEvent)
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
        
        rate = 100.0 * a[:4].sum() / a.sum()
        if verbose:
            print '8-bit coverage (%s) = %f (%%)' % (fp, rate)
            print ', '.join(['%d-%d: %d' % (b[n], b[n+1], aa) for n, aa in enumerate(a)][2:])
        
        if rate < 99.75 and self.imgdict['fastLoad']:
            MainFrame.showmessage(self.parent, (
            'Image data is not in 8-bit range (255).\n'+
            'Re-open with \"Load as unit8\" box uncheched.'))
    
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
            self.curx, self.cury = nx, ny # update current position
            self.refresh_buf()
        
        ## scaling frame mode
        elif self.scaling and delta:  # mouse did not move then...
            self.ScalingFactor *= 1.2 ** delta
            self.frame_resize(event)
        
        ## zooming mode
        if self.zoomingmode:
            if event.LeftDown():  # state change (not LeftIsDown)
                self.st_x, self.st_y = nx, ny
                #print 'zooming rect drawing started'
            elif event.LeftUp() and self.st_x and self.st_y:  # state change (not LeftIsUp)
                if self.st_x-2 < nx < self.st_x+2 and \
                   self.st_y-2 < ny < self.st_y+2:
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
        datafiles = self.tag
        
        print 'data_path', data_path
        print 'datafiles', datafiles
        print 'Loading the channel#%d' % self.ch
        
        if self.Launcher is not None:
            #all_frame = (self.Launcher.rb1.GetSelection()==0)
            all_frame = self.Launcher.rb1.GetSelection()
            need_AvgTr = self.Launcher.cbAvgTr.IsChecked()
            need_MaxPr = self.Launcher.cbMaxPr.IsChecked()
        else:
            all_frame = 0  # 0 for all frame, 1 for during res and F, 2 for the first in F
            need_AvgTr = need_MaxPr = False
        
        global ch, ref_ch
        ch_bak, ref_ch_bak = ch, ref_ch
        ch, ref_ch = self.ch, self.ref_ch
        
        imgdict, tag = pack(
            data_path, datafiles, all_frame, need_AvgTr, need_MaxPr, self.parent
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
        
        if myOS == 'Linux':
            self.log.SetFont(wx.Font(9, wx.SWISS, wx.NORMAL, wx.NORMAL))
        if verbose:
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
        menubar.Append(Export, '&PDF_options')
        menubar.Append(Help, '&Help')
        self.SetMenuBar(menubar)
        
        self.opened_data = {}
        
        if os.path.exists(lastdir):
            self.lastdir = lastdir
        else:
            self.lastdir = homedir
        print '(If plotting does not work, exit pymagor and delete fontList.cache in %s)\n' % MPLcache
        
        # default setting
        self.reftr = True
        self.HowManyFrames = 2
        
        self.lastplane = 'Type in field-of-view label here'
        self.lastodor = 'Or, pick from pulldown menu'
        self.lastmemo = 'comment here'
        
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
        
        if fp is not None:
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
        
        fp_offset, offset_dict = get_saved_offsets(dirname)
        show_offsetinfo(fp_offset, offset_dict)
        
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
            tags = [[os.path.basename(self.fp), 
                            'field-of-view_1', 
                            'stim_1', 
                            '1', 
                            data_path]]
        if self.reftr:
            reftr = None
        else:
            refty = 0
        
        imgdic, sorted_tag = pack(data_path, tags, all_frame, AvgTr, MaxPr, self, reftr)
        
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
    
    @staticmethod
    def saveini():
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
                },
            'PDF export' : 
                {'EXPORT_group_odor' : EXPORT_group_odor, 
                'EXPORT_needplotting' : EXPORT_needplotting, 
                'EXPORT_eachfile' : EXPORT_eachfile,
                'EXPORT_avgtraces' : EXPORT_avgtraces,
                'EXPOSE_transpose_collage' : EXPOSE_transpose_collage
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
                            if float(info['version']) >= 3.8:
                                scanXY = info['scanAngleMultiplierFast'], info['scanAngleMultiplierSlow']
                            else:
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
- ScanImage 3.6, 3.8, MATLAB tiff (Iori Namekawa)
- Imagor3 acquired ior camera data, Micro-Manager tiff, ImageJ tiff (Otto Fajardo)     

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

Icon arts from findicons.com
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
        elif id == self.ID_HowManyFrames:
            self.HowManyFrames = self.HowManyFrames == False
    
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
                    all_frame = 0
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
        
        print 'Stacking selected trials:'
        
        data_files = []
        items = self.get_current_selection()
        for item in items:
            fname = self.sheet.GetItemText(item)
            plane = self.sheet.GetItem(item, 1).GetText()
            odor = self.sheet.GetItem(item, 2).GetText()
            repeat = 'tr'+ self.sheet.GetItem(item, 3).GetText()
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
        'use or not to use sizers, thats the question---'
        
        wx.Panel.__init__(self, parent, -1, size=(202,245))
        self.parent = parent
        if platform.system() == 'Linux':
            self.SetFont(wx.Font(7, wx.SWISS, wx.NORMAL, wx.NORMAL))
        
        x,y = 5, 20
        scsize = (48,20)
        wx.StaticBox(self, -1, 'Pre- (F) and During-stimulus frames', (x,3), (193,68))
        # DurPre Start
        wx.StaticText(self, -1, 'F period', (x+5,y+3))
        self.IDsc_preS = wx.NewId()
        self.sc_preS = wx.SpinCtrl(self, self.IDsc_preS, '', (x+65+5,y), scsize)
        self.sc_preS.SetValue(durpre[0])
        self.sc_preS.SetRange(0,999)
        self.sc_preS.Bind(wx.EVT_SPINCTRL, self.OnSpin)
        # DurPre End
        wx.StaticText(self, -1, '- ', (x+120+5,y))
        self.IDsc_preE = wx.NewId()
        self.sc_preE = wx.SpinCtrl(self, self.IDsc_preE, '', (x+131+5,y), scsize)
        self.sc_preE.SetValue(durpre[1])
        self.sc_preE.SetRange(0,999)
        self.sc_preE.Bind(wx.EVT_SPINCTRL, self.OnSpin)
        # DurRes Start
        wx.StaticText(self, -1, 'During stim.', (x+5,y+28))
        self.IDsc_resS = wx.NewId()
        self.sc_resS = wx.SpinCtrl(self, self.IDsc_resS, '', (x+65+5,y+25), scsize)
        self.sc_resS.SetRange(0,999)
        self.sc_resS.SetValue(durres[0])
        self.sc_resS.Bind(wx.EVT_SPINCTRL, self.OnSpin)
        # DurRes End
        wx.StaticText(self, -1, '-', (x+120+5,y+28))
        self.IDsc_resE = wx.NewId()
        self.sc_resE = wx.SpinCtrl(self, self.IDsc_resE, '', (x+131+5,y+25), scsize)
        self.sc_resE.SetRange(0,999)
        self.sc_resE.SetValue(durres[1])
        self.sc_resE.Bind(wx.EVT_SPINCTRL, self.OnSpin)

        h = 73
        wx.StaticBox(self, -1, 'Colormap range', (x,h), (193,50))
        # cmap min
        txt_cmin = wx.StaticText(self, -1, 'dF/F (%)', (x+5, y+h+3))
        self.IDsc_cmin = wx.NewId()
        if platform.system() == 'Linux':
            self.sc_cmin = FS.FloatSpin(self, self.IDsc_cmin, min_val=-999/4, 
                max_val=-0.5, size=(55,20), increment=0.1, value=cmin, style=FS.FS_LEFT)
        else:
            self.sc_cmin = FS.FloatSpin(self, self.IDsc_cmin, min_val=-999/4, 
                max_val=-0.5, increment=0.1, value=cmin, agwStyle=FS.FS_LEFT)
            self.sc_cmin.SetSize((55,20))
        
        self.sc_cmin.SetFormat("%f")
        self.sc_cmin.SetDigits(1)
        self.sc_cmin.SetPosition((70,y+h))
        self.sc_cmin.Bind(FS.EVT_FLOATSPIN, self.OnSpin)
        # cmap max
        wx.StaticText(self, -1, '-', (129,y+h+3))
        self.IDsc_cmax = wx.NewId()
        self.sc_cmax = wx.SpinCtrl(self, self.IDsc_cmax, '', (136,y+h), scsize)
        self.sc_cmax.SetValue(cmax)
        self.sc_cmax.SetRange(0,999)
        self.sc_cmax.Bind(wx.EVT_SPINCTRL, self.OnSpin)
        
        h += 30
        wx.StaticBox(self, -1, 'Load', (x,h+y), (193,45))
        # select ch to load
        wx.StaticText(self, -1, 'Channel', (x+5,h+y+20))
        self.ID_ch = wx.NewId()
        self.ch = wx.SpinCtrl(self, self.ID_ch, '',(50+5,h+y+17), (40,20))
        self.ch.SetToolTip(wx.ToolTip('ex) If ch1 & ch3 are recorded,\nspecify 1 to open ch3.'))
        self.ch.SetRange(0,3)
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
        self.SpaMed = wx.CheckBox(self, -1, 'Median on ref tr',(79,h+y+11))
        self.SpaMed.SetValue(SpatMed)
        self.SpaMed2 = wx.CheckBox(self, -1, 'Median on target tr',(79,h+y+27))
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
        self.xyz = wx.StaticText(self, -1,'(x,y,value) =', (15,h+y+5+16))
        self.xyz.SetForegroundColour((0,100,0))
        
        drophere = wx.StaticBox(self, -1, 
            "Add to the online analysis", (5,h+y+25+16+5), (192,110+13-16))
        self.SetToolTip(wx.ToolTip('Drop here to add to the sheet without openning image'))
        self.Refresh()
    
    
    def OnSpin(self, event):

        global durpre, durres, cmin, cmax, gmin, gmax, margin, ch, ref_ch

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
        self.updateImages(event)

    def OnCheck(self, event):
        
        global SpatMed, SpatMed2, fastLoad, Autoalign
        SpatMed = self.SpaMed.IsChecked()
        SpatMed2 = self.SpaMed2.IsChecked()
        fastLoad = self.fastLoad.IsChecked()
        Autoalign = self.Autoalign.IsChecked()
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
        # (1) one from the Stack now! button. datafiles, lock will be empty.  
        # datafiles=None is passed to pack which then use fromlauncher as datafiles
        # (2) the other is Open each file event handler which provide datafiles and lock
        self.parent.log.SetInsertionPointEnd()
        print time.strftime('Packing files: %b %d, %Y (%a) %X')
        
        global working_singles, need_abort_singles
        global working, need_abort, ch, ref_ch
        
        if ch != ref_ch:
            MainFrame.showmessage(self.parent, 'Caution! Reference channel is different from loading channel.')
        
        if not working:
            
            if (fromlauncher is not None and fromlauncher != [])\
                or datafiles is not None:
                working = True
                if not working_singles:
                    self.stacknow.SetLabel('Abort')
                
                if not need_abort:
                    data_path = csvdict[1][0]  # in ver2 this only means where the sheet is.
                    howmanyframe = self.rb1.GetSelection()
                    AvgTr = self.cbAvgTr.IsChecked()
                    MaxPr = self.cbMaxPr.IsChecked()
                    
                    if self.cb.GetValue():
                        reftr = None
                    else:
                        reftr = self.sp_ref.GetValue()
                    
                    imgdic, tag = pack(data_path, datafiles, howmanyframe, AvgTr, MaxPr, self.parent, reftr)
                    if not need_abort and imgdic != None:
                        MainFrame.OnNewChild2(self.parent, imgdic, tag=tag, lock=lock)
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

def _shift_a_frame(img, (yoff, xoff)):
    img = np.roll(img, int(-yoff), axis=0)
    img = np.roll(img, int(-xoff), axis=1)
    return img

def LPMavg(fp, rng, dtype, nch, offsets=None, ch2load=None): 
    '''low peak memoey average'''
    
    if not ch2load:
        ch2load = ch # ch is global var
    
    fr2load = np.arange(rng[0], rng[1]+1) * nch + ch2load
        
    # use tifffile for tiff
    if fp.endswith(('TIF','tif','TIFF','tiff')):
        
        imfile = tifffile.TIFFfile(fp)
        avg = imfile.asarray(fr2load[0]).astype(np.uint64)
        
    # use pillow for non-tiff
    else:
        im = Image.open(fp)
        w,h = im.size
        if dtype == np.uint8: # faster for non-tiff too?
            avg = np.array(im.convert('L')).astype(np.uint64)
        else:
            avg = np.array(im.getdata()).reshape(h,w).astype(np.uint64)

    if fr2load.size > 1:
        
        for n in fr2load[1:]:
            
            if fp.endswith(('TIF','tif','TIFF','tiff')):
                curframe = imfile.asarray(n)
            elif dtype == np.uint16:
                im.seek(n)
                curframe = np.array(im.getdata()).reshape(h,w)
            else:
                im.seek(n)
                curframe = np.array(im.convert('L'))
            
            if offsets is not None:
                fr = n/nch-ch
                yoff, xoff = offsets[fr, :2]
                curframe = _shift_a_frame(curframe, (-yoff, xoff))
            
            avg += curframe
    
    return (avg[::-1,:] / (np.diff(rng)+1) ).astype(np.float32)


def LPMresmap(fp, F, rng, dtype, nch, offsets=None):
    '''low peak memoey odor response map 
    (average dF/F over response frames)'''
    
    h,w = F.shape
    resmap = np.zeros( (h,w), dtype=np.float64 )
    fr2load = np.arange(rng[0], rng[1]+1) * nch + ch # ch is global var

    if fp.endswith(('TIF','tif','TIFF','tiff')):
        imfile = tifffile.TIFFfile(fp)
    else:
        im = Image.open(fp)
    
    F = F[::-1,:] # invert for loop
    for n in fr2load:
        
        if fp.endswith(('TIF','tif','TIFF','tiff')):
            curframe = imfile.asarray(n)
        elif dtype == np.uint8: # fast for 8 bit image
            im.seek(n)
            curframe = np.array(im.convert('L'))
        else: # slowest but general
            im.seek(n)
            curframe = np.array(im.getdata()).reshape(h,w)
        
        if offsets is not None:
            fr = n/nch-ch
            yoff, xoff = offsets[fr, :2]
            curframe = _shift_a_frame(curframe, (-yoff, xoff))
        
        resmap += (curframe - F)
        
    resmap /= (np.diff(rng)+1)
    resmap /= F
    resmap *= 100.0
    
    return  scipy.ndimage.filters.convolve(
                resmap[::-1,:], kernel, mode='nearest'
                ).astype(np.float32)  # slower but closer to Imagor3 result


def lowpeakmemload(fp, dtype, filt=None, skip=False, ch=0):
    '''
    return raw frames, average image and gaussian filtered image 
    for tif or ior image in a memory friendly manner
    '''
    
    _durpre, _durres = checkdurs(fp, parent=None)
    
    img_info = get_tags(fp)
    if img_info == None:
        return None
    nch = img_info['nch']
    nframes = img_info['nframes']
    
    if ch+1 > nch:
        print 'Channel %d does not exists.' % (ch)
        return None, None, None, None, None, None
    
    if Autoalign:
        if verbose:
            print 'Autoalign is on.'
        offsets = get_offset_within_trial(fp, ref_ch, _durpre, margin, (SpatMed, SpatMed2))
        if offsets is None:
            return None, None, None, None, None, None
    else:
        offsets = None
    
    F = LPMavg(fp, _durpre, dtype, nch, offsets, ch2load=ch)
    F[F==0] = F[F.nonzero()].min() # avoid zero division when creating movie
    
    if skip:                    # howmanyframe = 1, 2
        
        raw = opentif(fp, dtype, filt, skip=skip, ch=ch) # opentif can load ior also
        DFoFmovie = None
        anatomy = LPMavg(fp, [0, nframes-1], dtype, nch, offsets, ch2load=ch)
        
    else:                       # howmanyframe = 0
        raw = opentif(fp, dtype, filt, ch=ch)
        
        if offsets is not None:
            if offsets.any():
                raw = Shift(raw, offsets)
        if anatomy_method:
            anatomy = raw.std(axis=2).astype(np.float32)
        else:
            anatomy = raw.mean(axis=2).astype(np.float32)
        
        try:
            DFoFmovie = np.zeros(raw.shape, dtype=np.float32)
            for n in range(raw.shape[2]): # less memory required this way
                #DFoFmovie[:,:,n] = 100.0 * (raw[:,:,n] - F)/F
                temp = 100.0 * (raw[:,:,n] - F)/F
                DFoFmovie[:,:,n] = scipy.ndimage.filters.convolve(
                                temp, kernel, mode='nearest'
                                ).astype(np.float32)
        except:
            print 'Not sufficient memory. dF/F movie skipped.'
            DFoFmovie = None
        
    resmap = LPMresmap(fp, F, _durres, dtype, nch, offsets)
    
    if ch != ref_ch:
        print 'Reference channel (%d) is different from loading channel (%d).' % (ref_ch, ch)
    
    return nframes, raw, F, resmap, anatomy, DFoFmovie


def checkdurs(fp, parent=None):
    
    #print 'checkdurs: fp', fp, os.path.exists(fp)
    nframes = get_tags(fp)['nframes']
    #print 'nframes', nframes, 'durs', durpre, durres
    
    if nframes <= max(max(durres, durpre)):
        if parent:
            MainFrame.showmessage( parent, 
            '%d is too large and is replaced with the max frame number (%d) for %s\n' % \
            (max(max(durres, durpre)), nframes-1, fp) )
        
        _durpre = [fr if fr < nframes-1 else nframes-1 for fr in durpre]
        _durres = [fr if fr < nframes-1 else nframes-1 for fr in durres]
    else:
        _durpre, _durres = durpre, durres
    
    return tuple(_durpre), tuple(_durres)


def LoadImage(group, data_path, howmanyframe, dtype, parent=None):
    ''' Concatinate trial frame data in a 3D array '''
    
    filt = None # median filter no longer used other than alignment
    
    nframesP, rawP, DFoFfilP, Fpool, ref_Fpool, anatomyP, resP = [],[],[],[],[],[],[]
    for data in group:
        wx.Yield() # this magically make the app responsive
        
        fp = path2img(data_path, data)
        _durpre, _durres = checkdurs(fp, parent=parent)
        
        if howmanyframe==0:     # I need all frames!
            skip = False
        elif howmanyframe==1:   # only durs
            skip = [_durpre, _durres]
        elif howmanyframe==2:   # the first frame of durpre
            skip = [_durpre[0]]
        
        print 'Loading ', fp
        nframes, raw, F, resmap, anatomy, DFoFmovie = \
            lowpeakmemload(fp, dtype, skip=skip, ch=ch)
        if raw is None:
            return None, None, None, None, None, None
        
        if type(F) is tuple:
            F = F[0]
            ref_Fpool.append(F[1])
        nframesP.append(nframes)
        rawP.append(raw)
        Fpool.append(F)
        resP.append(resmap)
        anatomyP.append(anatomy)
        DFoFfilP.append(DFoFmovie)
        
    # lazy but fast concatination.
    rawP = np.dstack(rawP)  # np.array(rawP) would be x10 slower
    Fpool = np.dstack(Fpool)
    if ref_Fpool:
        ref_Fpool = np.dstack(ref_Fpool)
        Fpool = (Fpool, ref_Fpool)
    resP = np.dstack(resP)
    anatomyP = np.dstack(anatomyP)
    if howmanyframe == 0:
        DFoFfilP = np.dstack(DFoFfilP)
    else:
        DFoFfilP = None
    
    return nframesP, rawP, Fpool, anatomyP, resP, DFoFfilP


def path2img(data_path, tag):
    ''' Get the full path to the image data. '''
    #print 'path2img : ', len(tag), tag, data_path
    path_in_tag = path_check(tag[-1], False)
    if path_in_tag and (len(tag) == 4 or len(tag) > 10):
            # from context menu or version v2 pymagor sheet.
        data_path = path_in_tag
    else:   # from v1 pymagor sheet.
        data_path = path_check(data_path, verbose)
    
    if not data_path or need_abort: # something went wrong
        return None, None, None, None, None
    
    return os.path.join(data_path, tag[0])


def pack(data_path, tags, howmanyframe, need_AvgTr, need_MaxPr, parent, reftr=None):
    
    if verbose:
        t0 = time.time()
    
    if tags is None:
        tags = fromlauncher
    
    if fastLoad:
        dtype = np.uint8
    else:
        dtype = np.uint16
    
    rawpoolP, FpoolP, respoolP = [],[],[]
    anatomyP, FoffsetP, DFoFfilpoolP = [],[],[]
    odormapsP, RF_FsP, odormap_zodor = [],[],[]
    AvgTr, MaxPr = [],[]
    sorted_tag = []
    margin_dict = {}
    
    fp = path2img(data_path, tags[0])
    _durpre, _durres = checkdurs(fp, parent=None) # assuming the frame number matches in all files
    
    planes = np.unique([items[1] for items in tags])
    if np.all([a.startswith('z') for a in planes]):
        print '\t !!!!All filed-of-view names starting with z. Special sorting method applied. !!!!'
        index = np.argsort( z_prefix(planes) )
        unique_planes = planes[index]
        
    else:  # general sorting. may not be what you expect
        unique_planes = np.sort(planes).tolist()
    
    for z in unique_planes:     # plane
        
        # pre-sort concentration series of the same odor
        eachplane = [ items for items in tags if z == items[1] ]
        trials = [dd[3] for dd in eachplane]
        odors = [dd[2] for dd in eachplane]
        odors = [int(re.search('10(\-)[0-9]+M', odor).group(0)[2:-1]) 
                    if re.search('10(\-)[0-9]+M', odor) is not None else 100*n
                    for n,odor in enumerate(odors)]
        # then lexsort for odors first (1st factor) and trials (2nd factor)
        eachplane = [ eachplane[ind] for ind in np.lexsort((trials, odors)) ]
        
        nframesP, raw, F, anatomy, res, DFoF = LoadImage(
                        eachplane, data_path, howmanyframe, dtype, parent)
        
        for n, nframe in enumerate(nframesP):
            eachplane[n].insert(-1, nframe)
        print eachplane
        sorted_tag.append(eachplane)
        
        # LoadImage returns None when error or aborted
        if raw == None:
            return None, None
        
        if type(F) == tuple:
            F, ref_F = F
        else:
            ref_F = F
        
        # Align trials
        if len(eachplane) == 1:  # no need to align
            
            Foffset = np.array([[0,0,0,0]])
            margin_dict[z] = 0
        
        else:  # need alignment
            if verbose:
                print 'Spatial median filter option being used: Template=%s, Target=%s' % (SpatMed, SpatMed2)
            
            if reftr is not None:   # reftr can be 0 when manually specified
                Foffset = corr2d( ref_F, margin, reftr, (SpatMed, SpatMed2) )
            else:  # auto ref trial on, try  the first trial as ref and optimize
                Foffset = corr2d( ref_F, margin, 0, (SpatMed, SpatMed2) )
                total_offset = [ abs(e).max(axis=0).sum() for e in 
                                [Foffset[:,0:2] - Foffset[n,0:2] for n in 
                                range(Foffset.shape[0])] ]
                tr = total_offset.index(min(total_offset))
                print 'For the ref trial at plane (%s), # %d (%s) was used.' % (z, tr, eachplane[tr][0])
                Foffset = corr2d( ref_F, margin, tr, (SpatMed, SpatMed2) )
            
            if Foffset[:,:2].any(): # need to shift and re-checek?
                print 'Offset before alignment:\n  [y, x, corr, index]\n', Foffset
                margin_dict[z] = np.abs(Foffset[:,:2]).max()
                print '0 padding margin = ', margin_dict[z]
                
                F       = Shift(F.copy(), Foffset)
                ref_F   = Shift(ref_F.copy(), Foffset)
                res     = Shift(res.copy(), Foffset)
                anatomy = Shift(anatomy.copy(), Foffset)
                if howmanyframe==0:  # this option means "all frames"
                    DFoF = Shift(DFoF.copy(), Foffset)
                
                # re-check
                if reftr is not None:  # reftr can be 0 when manually specified
                    Foffset2 = corr2d(ref_F, margin, reftr, (SpatMed, SpatMed2))
                else:    # auto-on
                    Foffset2 = corr2d(ref_F, margin, tr, (SpatMed, SpatMed2))
                    print '\nSuggested ref trial at %s is #%s  %s\n' % (z, tr, eachplane[tr][0])
                
                print 'After alignment:\n  [y, x, corr, index]\n', Foffset2
                if abs(Foffset2[:,0:2]).max() > 1:
                    txt = 'The current shift range setting (=%d) may not be large enough for plane %s.\nOr, try again without Median filter' % (margin, z)
                    MainFrame.showmessage(parent, txt)
        
        RF_Fs, odormaps, odors = average_odormaps(
                            data_path, 
                            eachplane, 
                            Foffset, 
                            Autoalign, 
                            (_durpre,_durres), 
                            margin, 
                            (SpatMed, SpatMed2),
                            ch=ch, 
                            ref_ch=ref_ch,
                            dtype=dtype
                            )
        
        if len(eachplane) > 1:
            # filp y-axis due to the design changes in Pymagor v2.0
            Foffset[:,0] = -Foffset[:,0]
        FoffsetP.append(Foffset)
        
        # append for different planes.
        rawpoolP.append(raw)
        FpoolP.append(F)
        respoolP.append(res)
        anatomyP.append(anatomy)
        if howmanyframe == 0:
            DFoFfilpoolP.append(DFoF)
        odormapsP.append(odormaps)
        RF_FsP.append(RF_Fs)
        odormap_zodor.append([(z,o) for o in odors])
        
        if need_AvgTr:
            AvgTr.append( np.mean(np.dstack(respoolP),2) ) 
        if need_MaxPr:
            MaxPr.append( np.max(np.dstack(respoolP),2) )
        
    # flatten the list of sublist
    sorted_tag = [item for sublist in sorted_tag for item in sublist]
    odormap_zodor = [item for sublist in odormap_zodor for item in sublist]
    if len(FoffsetP)>1:
        Foffsets = np.vstack(FoffsetP)
    else:
        Foffsets = FoffsetP[0]
    
    # packing
    imgdict = dict()
    
    if len(rawpoolP)>1:
        try:
            imgdict['unshifted frames'] = np.dstack(rawpoolP)
        except MemoryError:
            print 'Memory Error. Packing only one frame per trial'
            imgdict['unshifted frames'] = rawpoolP[:,:,0::len(eachplane)]
    else:
        imgdict['unshifted frames'] = rawpoolP[0]
        
    if howmanyframe == 0:
        if len(DFoFfilpoolP) == 1:
            imgdict['dFoFfil'] = DFoFfilpoolP[0]  # avoid over flattening
        else:
            imgdict['dFoFfil'] = np.dstack(DFoFfilpoolP)
    
    # common stuff
    imgdict['data_path'] = data_path
    _durpre, _durres = checkdurs(fp)
    imgdict['durpre'] = _durpre
    imgdict['durres'] = _durres
    imgdict['fastLoad'] = fastLoad
    imgdict['uniquekey'] = unique_planes
    imgdict['F'] = np.dstack(FpoolP)
    imgdict['anatomy'] = np.dstack(anatomyP)
    imgdict['dFoFavg'] = np.dstack(respoolP)
    if odormapsP:
        imgdict['avg_odormaps'] = np.dstack(odormapsP)
        imgdict['avg_F'] = np.dstack(RF_FsP)
        imgdict['avg_odormap odornames'] = odormap_zodor
    if need_AvgTr:
        imgdict['avg projection'] = np.dstack(AvgTr)        
    if need_MaxPr:
        imgdict['max projection'] = np.dstack(MaxPr)
    if FoffsetP:
        imgdict['Foffset'] = Foffsets
    else:
        imgdict['Foffset'] = 0
    imgdict['margin'] = margin_dict
    
    if verbose:
        print '\nAbout %2.2f s to load.' % (time.time() - t0)
        
    return imgdict, sorted_tag


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

if __name__ == "__main__":
    app = wx.App(0)
    fishicon = wx.Icon(os.path.join('resources','fish2.ico'), wx.BITMAP_TYPE_ICO)
    ## for wx.Icon, wx.App object must be created first!
    Pymagor2 = MainFrame(None, -1)
    Pymagor2.Show(True)
    app.MainLoop()
