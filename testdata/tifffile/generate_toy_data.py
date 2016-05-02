import os
# from pylab import *
import numpy as np
import tifffile


# frames, height, width
nframes = 160
Fnoise = 100
data = np.ones((nframes, 40, 60), dtype=np.uint8) * Fnoise
# dF/F change should be ((50+90+100) - (90+100)) / (100+90) = 26.31578947368421 %

F = 90
res = F+50
data[:, 12:15, 22:25] = F+Fnoise
data[100:130, 12:15, 22:25] = res+Fnoise
# cross hair to visualize the shift, centered at (5,5)
data[:, 5-3:5+4, 5] = 55
data[:, 5, 5-3:5+4] = 55

# imshow(data3[100,:,:], 'gray', interpolation='none')
with tifffile.TiffWriter('temp.tif') as tif:
    tif.save(data)



# temp2 ocasionally introduces within trial jitters (x,y translation) to 10 frames, weaker response
data2 = data.copy()
data2[100:130, 12:15, 22:25] = res+Fnoise-10
# dF/F change should be ((50+90+100-10) - (90+100)) / (100+90) = 21.052631578947366 %

for n in np.random.randint(0, nframes, 10):
    d = np.random.choice([0,0,0,0,0,0,0,1,-1])
    data2[n] = np.roll(data2[n,:,:], d, axis=0)
    d = np.random.choice([0,0,0,0,0,0,0,1,-1])
    data2[n] = np.roll(data2[n,:,:], d, axis=1)

with tifffile.TiffWriter('temp2.tif') as tif:
    tif.save(data2)





# temp3 has a drift, stronger response
data3 = data.copy()
data3[100:130, 12:15, 22:25] = res+Fnoise+10
# dF/F change should be ((50+90+100-10) - (90+100)) / (100+90) = 31.57894736842105 %

data3 = np.roll(data3, +1, axis=1) # y -1   y axis is flipped
data3 = np.roll(data3, -1, axis=2) # x -1
# imshow(data3[100,:,:], 'gray', interpolation='none')

with tifffile.TiffWriter('temp3.tif') as tif:
    tif.save(data3)

# trial average mean(50,40,60) = 50 so 50/190 -> 26.31578947 again
# 26.31578947 %

if __name__ == '__main__':
    'test for within and across tirla alignment and dF/F computation with toy data'

    import os, sys

    os.chdir('../..')
    print os.getcwd()

    sys.path.append(os.getcwd())


    import Pymagor
    data_path = 'testdata/tifffile'
    tags = [[u'temp.tif', u'z0', u'stim1', u'1.0', u'50% response at 100-130 frames', u'NA', u'NAxNA', u'N_A', u'NA', u'04/25/2016 15:49:04', u'R:\\MoonshipTDPS2\\projects\\namekawa-san\\git\\Pymagor\\testdata\\tifffile'], [u'temp2.tif', u'z0', u'stim1', u'2.0', u'within tr jitter, weaker res', u'NA', u'NAxNA', u'N_A', u'NA', u'04/25/2016 15:49:04', u'R:\\MoonshipTDPS2\\projects\\namekawa-san\\git\\Pymagor\\testdata\\tifffile'], [u'temp3.tif', u'z0', u'stim1', u'3.0', u'across trial jitter, stronger res', u'NA', u'NAxNA', u'N_A', u'NA', u'04/25/2016 15:49:04', u'R:\\MoonshipTDPS2\\projects\\namekawa-san\\git\\Pymagor\\testdata\\tifffile']]

    anatomy_method = False

    howmanyframe = 2
    need_AvgTr = True
    need_MaxPr = True
    Fnoise = 125 * 0.8
    fastLoad = False
    verbose = True
    durpre = [50, 95]
    durres = [100, 130]
    ch = 0
    ref_ch = 0
    reftr = None # auto mode
    margin = 20

    # when images are updated, old offset info will not be useful.    
    if os.path.exists('testdata/tifffile/tifffile.offset'):
        os.remove('testdata/tifffile/tifffile.offset')

    imgdict, sorted_tag = Pymagor.pack( data_path, tags, howmanyframe, need_AvgTr, need_MaxPr, anatomy_method, 
        Fnoise, fastLoad, verbose, durpre, durres, ch, ref_ch, reftr=None, margin=margin )
    app = Pymagor.wx.App(0)

    _stdout = sys.stdout # Pymagor will re-direct stdout.
    Pymagor2 = Pymagor.MainFrame(None, -1)
    sys.stdout = _stdout
    trial2 = Pymagor.trial2(Pymagor2, -1, imgdict, sorted_tag, lock=False)
    ROIdata = 'testdata/tifffile/tifffile.mat'
    trial2.loadROI(ROIdata)
    fname = 'testdata/tifffile/export_from_script.pdf'
    # color scale in PDF seems messed up but values are ok. these settins correct trial average only
    trial2.ManScaling.SetValue(True)
    trial2.scH.SetValue(190)
    trial2.scL.SetValue(0)
    trial2.changetitle()
    trial2.Refresh()
    Pooled = trial2.PDF(fname, data_path) 
    dFoFtracesPool, rawtracesPool, avgdFoF_acrosstrials, avgF_acrosstrials, names4avgdFoF_acrosstrials, avg_tracesP = Pooled

    # Pymagor2.showmessage( 'dFoFtracesPool %d' % len(dFoFtracesPool) )
    print [np.max(d) for d,z,r in dFoFtracesPool]
    assert [np.max(d) for d,z,r in dFoFtracesPool] == [26.315789473684209, 21.05263157894737, 31.578947368421055]
    
    print [np.max(d) for d,z,r,o in avg_tracesP]
    assert [np.max(d) for d,z,r,o in avg_tracesP] == [26.315789473684209]

