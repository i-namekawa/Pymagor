import re, sys

import numpy as np

import matplotlib
import matplotlib.pyplot as plt

import wx
import wx.grid as gridlib
import wx.lib.gridmovers as gridmovers

import ROI

defaultCategory = ["Cell", "Neuropil", "Beads"]

def z_prefix(planes):
    
    _planes = []
    for z in planes:
        m = re.search('^z([\+\-]){0,1}[0-9]{1,4}', z)
        if m:
            _planes.append( float(m.group(0)[1:]) )
        else:
            _planes.append( z )
    return _planes


def ordersafe_set(data):
    seen = set()
    return [d for d in data if d not in seen and not seen.add(d)]

class CustomDataTable(gridlib.PyGridTableBase):
    def __init__(self, roi):
        gridlib.PyGridTableBase.__init__(self)
        
        self._updatedata(roi)
        self.colLabels = ["ROI#", "Field-of-View", "Polygon", "Area", "Center", "Category"]
        
        self._editor = {
            1: gridlib.GridCellChoiceEditor(ordersafe_set(roi.z), False),
            5: gridlib.GridCellChoiceEditor(ordersafe_set([]), True)
                        }

    def _updatedata(self, roi):
        self.data = [
            [n+1, z, poly, area, center, catg] 
                for n, (z, poly, area, center, catg) 
                    in enumerate(zip(   roi.z, 
                                        roi.data, 
                                        roi.areas, 
                                        roi.centers,
                                        roi.category
                                    )
                                )
                    ]
        self.rowLabels = [str(n+1) for n in range(len(roi.data))]
    
    def _update(self):
        self.data = [ 
            [nn+1, z, poly, area, cntm, ctgr] 
                for nn, (n, z, poly, area, cntm, ctgr) 
                in enumerate(self.data)
                    ]
        self.rowLabels = [str(n+1) for n in range(len(self.data))]
    
    def GetAttr(self, row, col, kind):
        
        attr = gridlib.GridCellAttr()
        if col in [1, 5]:
            self._editor[col].IncRef()
            attr.SetEditor( self._editor[col] )
        if col in [0, 3, 4]:
            attr.SetReadOnly(True)
        if col != 2:
            attr.SetAlignment(wx.ALIGN_CENTRE, wx.ALIGN_CENTRE)
        
        return attr
    
    def GetNumberRows(self):
        return len(self.data)

    def GetNumberCols(self):
        return len(self.colLabels)

    def IsEmptyCell(self, row, col):
        return not self.data[row][col]

    def GetValue(self, row, col):
        return self.data[row][col]

    def SetValue(self, row, col, value):
        self.data[row][col] = value
    
    def GetColLabelValue(self, col):
        return self.colLabels[col]

    def GetRowLabelValue(self,row):
        return self.rowLabels[row]
    
    def _autosort(self):
        centers = [d[4][0] for d in self.data]
        z = [d[1] for d in self.data]
        if np.all([_z.startswith('z') for _z in z]):
            z = z_prefix(z)
        
        category = [d[5] for d in self.data]
        index = np.lexsort((centers, z, category))
        self.data = [ self.data[ind] for ind in index ]
    
    def _sortbyarea(self):
        areas = [d[3] for d in self.data]
        z = [d[1] for d in self.data]
        if np.all([_z.startswith('z') for _z in z]):
            z = z_prefix(z)
        
        category = [d[5] for d in self.data]
        index = np.lexsort((areas, z, category))
        self.data = [ self.data[ind] for ind in index ]

    def _DeleteRow(self, row):
        grid = self.GetView()
        if grid:
            self.rowLabels.pop(row)
            self.data.pop(row)
            
            msg = gridlib.GridTableMessage(
                    self,
                    gridlib.GRIDTABLE_NOTIFY_ROWS_DELETED,
                    row,
                    1)
            grid.ProcessTableMessage(msg)
        
    def MoveRow(self,frm,to):
        grid = self.GetView()
        if grid:
            # Move the rowLabels and data rows
            oldLabel = self.rowLabels[frm]
            oldData = self.data[frm]
            self.rowLabels.pop(frm)
            self.data.pop(frm)
            
            if to > frm:
                self.rowLabels.insert(to-1,oldLabel)
                self.data.insert(to-1,oldData)
            else:
                self.rowLabels.insert(to,oldLabel)
                self.data.insert(to,oldData)
            # Notify the grid
            grid.BeginBatch()
            
            msg = gridlib.GridTableMessage(
                    self, gridlib.GRIDTABLE_NOTIFY_ROWS_INSERTED, to, 1
                    )
            grid.ProcessTableMessage(msg)

            msg = gridlib.GridTableMessage(
                    self, gridlib.GRIDTABLE_NOTIFY_ROWS_DELETED, frm, 1
                    )
            grid.ProcessTableMessage(msg)
            
            grid.EndBatch()


class DragableGrid(gridlib.Grid):
    def __init__(self, parent, roi, customROIcategory):
        gridlib.Grid.__init__(self, parent, -1)
        
        self.table = CustomDataTable(roi)
        self.SetTable(self.table, True)
        self.selected = []
        self.roi = roi
        self.parent = parent
        self.customROIcategory = customROIcategory

        gridmovers.GridRowMover(self)
        
        self.Bind(gridmovers.EVT_GRID_ROW_MOVE, self.OnRowMove, self)
        self.Bind(gridlib.EVT_GRID_RANGE_SELECT, self.OnSelect, self)
        
        # dynamically update menu  http://wiki.wxpython.org/GridCellChoiceEditor 
        self.index = None
        self.data = None
        self.Bind(wx.grid.EVT_GRID_EDITOR_CREATED, self.OnGridEditorCreated)
        self.Bind(wx.grid.EVT_GRID_EDITOR_HIDDEN, self.OnGridEditorHidden)
        
    def OnSelect(self,event):
        self.selected = [_+1 for _ in self.GetSelectedRows()]
    
    def OnRowMove(self,event):
        frm = event.GetMoveRow()          # Row being moved
        to = event.GetBeforeRow()         # Before which row to insert
        self.GetTable().MoveRow(frm,to)
    
    #  following 4 methods from http://wiki.wxpython.org/GridCellChoiceEditor
    def OnGridEditorCreated(self, event):
        Row = event.GetRow()
        Col = event.GetCol()
        if Col == 5: # 5th col is where GridCellChoiceEditors are
            self.comboBox = event.GetControl()
            self.comboBox.Bind(wx.EVT_COMBOBOX, self.OnGridComboBox)
            self.comboBox.Bind(wx.EVT_TEXT, self.OnGridComboBoxText)

            for data in ordersafe_set(self.roi.category+defaultCategory+self.customROIcategory):
                # Append(str to show in drop list, optional hidden PyObject associated with the str)
                self.comboBox.Append(data, None)
        event.Skip()

    def OnGridComboBox(self, event):
        #Save the index and client data for later use.
        self.index = self.comboBox.GetSelection()
        self.data = self.comboBox.GetClientData(self.index)
        event.Skip()

    def OnGridComboBoxText(self, event):
        # The index for text changes is always -1. This is how we can tell
        # that new text has been entered
        self.index = self.comboBox.GetSelection()
        event.Skip()

    def OnGridEditorHidden(self, event):
        #This method fires after editing is finished for any cell.
        Row = event.GetRow()
        Col = event.GetCol()
        if Col == 5 and self.index == -1: # new category is entered to GridCellChoiceEditors
            item = self.comboBox.GetValue()
            self.index = self.comboBox.GetCount()
            self.comboBox.Append(item, None) # we know item is new
        event.Skip()


class ROImanager(wx.Frame):
 
    def __init__(self, parent, roi, pos):
        style = wx.DEFAULT_MINIFRAME_STYLE
        wx.Frame.__init__(self, parent, -1, "ROI manager", style=style, pos=pos)
        self.parent = parent
        
        panel = wx.PyScrolledWindow(self, wx.ID_ANY)
        panel.SetToolTip(wx.ToolTip('Close this from the button on the image window.'))
        self.grid = DragableGrid(panel, roi, parent.parent.customROIcategory)
        self.grid.Bind(gridlib.EVT_GRID_CELL_RIGHT_CLICK, self.showPopupMenu)

        width, height = panel.GetSize()
        self.unit = 1
        panel.SetScrollbars( 0, self.unit, 0, height/self.unit )
        
        self.autosortbtn = wx.Button(panel, -1, 'SortByPosition', style=wx.BU_EXACTFIT)
        self.autosortbtn.Bind(wx.EVT_BUTTON, self.OnAutoSort)
        
        self.sortbyAreabtn = wx.Button(panel, -1, 'SortByArea', style=wx.BU_EXACTFIT)
        self.sortbyAreabtn.Bind(wx.EVT_BUTTON, self.OnSortByArea)
        
        self.confirmbtn = wx.Button(panel, -1, 'Confirm', style=wx.BU_EXACTFIT)
        self.confirmbtn.Bind(wx.EVT_BUTTON, self.OnConfirm)
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(self.autosortbtn, 0)
        hbox.Add(self.sortbyAreabtn, 0)
        hbox.Add(self.confirmbtn, 0)
        sizer.Add(hbox, 0, wx.ALIGN_CENTER, 5)
        sizer.Add(self.grid, 1, wx.EXPAND, 5)
        sizer.AddSpacer(20)
        panel.SetSizer(sizer)
        panel.Fit()
        
        framesizer = wx.BoxSizer(wx.VERTICAL)
        framesizer.Add(panel, 1, wx.EXPAND, 5)
        self.SetSizer(framesizer)
        self.Fit() # PyScrolledWindow seems to interfare with the height estimation
        w,h = self.GetSize()  # so, manually set y
        self.SetSize((w+20,h+350)) #+20 prevent vertical scroll bar to appear in grid
        panel.SetBestSize()
        
        self.Show()
    
    def showPopupMenu(self, event):
        self.cur_row = event.GetRow()+1
        if not hasattr(self, "popupID1"):
            self.deleterowID = wx.NewId()
            self.plotSelectedID = wx.NewId()
            self.plotSelectedrawID = wx.NewId()
            self.Bind(wx.EVT_MENU, self.OnDeleteRow, id=self.deleterowID)
            self.Bind(wx.EVT_MENU, self.OnplotSelected, id=self.plotSelectedID)
            self.Bind(wx.EVT_MENU, self.OnplotSelected, id=self.plotSelectedrawID)
           
        menu = wx.Menu()
        menu.Append(self.deleterowID, "delete row%d" % (self.cur_row))
        menu.Append(self.plotSelectedID, "plot dF/F trace for ROIs: %s" % (self.grid.selected))
        menu.Append(self.plotSelectedrawID, "plot raw pixel value trace for ROIs: %s" % (self.grid.selected))
        self.PopupMenu(menu)
        menu.Destroy()
    
    def OnplotSelected(self, event):
        
        if not self.grid.selected:
            return
            
        parent = self.parent
        fp, Foffset = parent.changetitle(wantfp_offset=True)
        
        _id = event.GetId()
        if _id == self.plotSelectedrawID:
            raw = True
        else:
            raw = False
        
        if type(fp) == list and type(Foffset) == list: 
            
            ROIfound, ROIpolys = [], []
            if parent.__class__.__name__ == 'trial2':
                z = parent.changetitle(wantz=True)
            else:
                z, odorname, repeat = parent.changetitle(wantz=True)
                
            for n,zz in enumerate(parent.ROI.z):
                if zz == z:
                    ROIfound.append(n+1)
                    ROIpolys.append(parent.ROI.data[n])
            tags = fp
            Autoalign = parent.param.Autoalign.IsChecked()
            durs = (parent.durpre, parent.durres)
            margin = parent.param.margin.GetValue()
            SpatMed = parent.param.SpaMed.IsChecked()
            SpatMed2 = parent.param.SpaMed2.IsChecked()
            Fnoise = parent.param.sc_Fnoise.GetValue()
            ch = parent.ch
            data_path = parent.imgdict['data_path']
            Foffset = np.array(Foffset)
            Foffset[:,0] = -Foffset[:,0] # flix y-axis for shift function

            dFoF = ComputeThisPlane(
                                    data_path=data_path, 
                                    tags=tags, 
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
            dFoF, ROIfound = parent.getdFoF(fp, dtype=np.uint16, offset=Foffset, raw=raw)
        
        print 'selected:', self.grid.selected
        
        Tobereplaced = [n for n in ROIfound if n not in self.grid.selected]
        index = [ROIfound.index(t) for t in Tobereplaced if t in ROIfound]
        dFoF[:,index] = 0
        
        # plotting
        parent.changetitle()
        title = 'Selected ROIs plot ' + parent.GetTitle()
        
        figure = plt.figure(figsize=[6,4])
        
        subplot = figure.add_subplot(111)
        parent.plot(subplot, dFoF, raw=raw, label=ROIfound)
        
        plt.tight_layout()
        figure.show()
        
        parent.plotbtn.Enable(True)
        
    
    def OnDeleteRow(self, event):
        self.grid.GetTable()._DeleteRow(self.cur_row-1)

    def OnAutoSort(self, event):
        self.grid.GetTable()._autosort()
        self.grid.ForceRefresh()
    
    def OnSortByArea(self, event):
        self.grid.GetTable()._sortbyarea()
        self.grid.ForceRefresh()

    def OnConfirm(self, event):
        self.grid.GetTable()._update()
        self.grid.ForceRefresh()
        
        data = self.grid.GetTable().data
        roi = ROI.ROIv3()
        categoryP = []
        runok = True
        for n, z, poly, area, center, category in data:
            # print 'OnConfirm', n, z, poly, area, center, category
            if type(poly) == unicode:
                try:
                    poly = eval(poly)
                    roi.add(poly, z=z, category=category)
                except:
                    print 'ROI polygon data might be wrong for %d ...' % n
                    runok = False
            elif type(poly) == list:
                # meaning ROI polygon unchanged
                roi.add(poly, z=z, category=category)
            categoryP.append(category)

        if runok:
            self.parent.ROI = roi
            # saveini uses the main frame's customROIcategory attribute
            self.parent.parent.customROIcategory =  ordersafe_set(
                self.parent.parent.customROIcategory+[item for item in categoryP if item not in defaultCategory])
        self.parent.Refresh()



if __name__ == "__main__":
    class Main(wx.Frame):
        def __init__(self):
            wx.Frame.__init__(self, None, -1, "dummy Pymagor")
            self.customROIcategory = ['OB', 'TC']
            self.quit = wx.Button(self, -1, 'Kill the process')
            self.quit.Bind(wx.EVT_BUTTON, self.OnQuit)
            self.Show()
        
        def OnQuit(self, event):
            self.Destroy()

    class dummy(wx.Frame):
        def __init__(self, main):
            wx.Frame.__init__(self, main, -1, "dummy trial2")
            self.ROI = None
            self.parent = main
     
    app = wx.App(0)  # 0 to redirect error
    
    roi = ROI.ROIv3()
    roi.add([(92, 10), (94, 14), (94, 19), (90, 23)], 'z0','Skin')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(66, 92), (63, 97), (56, 98), (55, 93), (57, 88), (60, 86), (65, 86), (67, 92)], 'z10')
    roi.add([(16, 112), (60, 86), (65, 86), (67, 92)], 'z-10')
    
    pymagor = Main()
    trial2 = dummy(pymagor)
    
    frame = ROImanager(trial2, roi, pos=wx.DefaultPosition).Show()
    app.MainLoop()
    
