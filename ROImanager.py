import re, sys

import numpy as np

import matplotlib
import matplotlib.pyplot as plt

if not hasattr(sys, 'frozen'):
    import wxversion
    wxversion.select(('2.8'))
import wx
import wx.grid as gridlib
import wx.lib.gridmovers as gridmovers

import ROI
from misc import average_odormaps


def z_prefix(planes):
    
    _planes = []
    for z in planes:
        m = re.search('^z([\+\-]){0,1}[0-9]{1,4}', z)
        if m:
            _planes.append( float(m.group(0)[1:]) )
    
    return _planes


class CustomDataTable(gridlib.PyGridTableBase):
    def __init__(self, roi):
        gridlib.PyGridTableBase.__init__(self)
        
        self._updatedata(roi)
        #self.rowLabels = [str(n+1) for n in range(len(roi.data))]
        self.colLabels = ["ROI#", "Field-of-View", "Polygon", "Area", "Center", "Category"]
        defaultCategory = ["Cell", "Neuropil", "Bead"]
        
        def ordersafe_set(data):
            seen = set()
            return [d for d in data if d not in seen and not seen.add(d)]
        
        self._editor = {
            1: gridlib.GridCellChoiceEditor(ordersafe_set(roi.z), True),
            5: gridlib.GridCellChoiceEditor(ordersafe_set(roi.category+defaultCategory), True)
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
    def __init__(self, parent, roi):
        gridlib.Grid.__init__(self, parent, -1)
        
        table = CustomDataTable(roi)
        self.SetTable(table, True)
        self.selected = []
        
        gridmovers.GridRowMover(self)
        self.Bind(gridmovers.EVT_GRID_ROW_MOVE, 
                        self.OnRowMove, self)
        self.Bind(gridlib.EVT_GRID_RANGE_SELECT, 
                        self.OnSelect, self)
        
    def OnSelect(self,event):
        self.selected = [_+1 for _ in self.GetSelectedRows()]
    
    def OnRowMove(self,event):
        frm = event.GetMoveRow()          # Row being moved
        to = event.GetBeforeRow()         # Before which row to insert
        self.GetTable().MoveRow(frm,to)


class ROImanager(wx.Frame):
 
    def __init__(self, parent, roi, pos):
        style = wx.DEFAULT_MINIFRAME_STYLE
        wx.Frame.__init__(self, parent, -1, "ROI manager", style=style, pos=pos)
        self.parent = parent
        
        panel = wx.PyScrolledWindow(self, wx.ID_ANY)
        panel.SetToolTip(wx.ToolTip('Close this from the button on the image window.'))
        self.grid = DragableGrid(panel, roi)
        self.grid.Bind(gridlib.EVT_GRID_CELL_RIGHT_CLICK,
                       self.showPopupMenu)
        width, height = panel.GetSize()
        self.unit = 1
        panel.SetScrollbars( 0, self.unit, 0, height/self.unit )
        
        self.confirmbtn = wx.Button(panel, -1, 'Confirm', style=wx.BU_EXACTFIT)
        self.confirmbtn.Bind(wx.EVT_BUTTON, self.OnConfirm)
        self.autosortbtn = wx.Button(panel, -1, 'AutoSort', style=wx.BU_EXACTFIT)
        self.autosortbtn.Bind(wx.EVT_BUTTON, self.OnAutoSort)
        
        sizer = wx.BoxSizer(wx.VERTICAL)
        hbox = wx.BoxSizer(wx.HORIZONTAL)
        hbox.Add(self.confirmbtn, 0)
        hbox.Add(self.autosortbtn, 0)
        sizer.Add(hbox, 0, wx.ALIGN_CENTER, 5)
        sizer.Add(self.grid, 1, wx.EXPAND, 5)
        panel.SetSizer(sizer)
        panel.Fit()
        
        framesizer = wx.BoxSizer(wx.VERTICAL)
        framesizer.Add(panel, 1, wx.EXPAND, 5)
        self.SetSizer(framesizer)
        self.Fit() # PyScrolledWindow seems to interfare with the height estimation
        w,h = self.GetSize()  # so, manually set y
        self.SetSize((w,h+300))
        
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
            ch = parent.ch
            data_path = parent.imgdict['data_path']
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
    
    def OnConfirm(self, event):
        self.grid.GetTable()._update()
        self.grid.ForceRefresh()
        
        data = self.grid.GetTable().data
        roi = ROI.ROIv3()
        for n, z, poly, area, center, category in data:
            #print 'OnConfirm', z, poly, category
            roi.add(poly, z=z, category=category)
        self.parent.ROI = roi
        self.parent.Refresh()


if __name__ == "__main__":
    class dummy(wx.Frame):
        def __init__(self):
            wx.Frame.__init__(self, None, -1, "dummy trial2")
            self.ROI = None
    
    app = wx.App()
    
    roi = ROI.ROIv3()
    roi.add([(92, 10), (94, 14), (94, 19), (90, 23)], 'z0','Skin')
    roi.add([(192, 110), (194, 124), (194, 129), (190, 133)], 'z0')
    roi.add([(66, 92), (63, 97), (56, 98), (55, 93), (57, 88), (60, 86), (65, 86), (67, 92)], 'z10')
    roi.add([(16, 112), (60, 86), (65, 86), (67, 92)], 'z-10')
    
    trial2 = dummy()
    
    frame = ROImanager(trial2, roi, pos=wx.DefaultPosition).Show()
    app.MainLoop()
    
