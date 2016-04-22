from __future__ import division
import cPickle as pickle
import os, platform

import numpy as np
import scipy.io as sio
import scipy.ndimage as ndimage
#import matplotlib.nxutils as nx
from matplotlib.path import Path

from opentif import *
import corr

sigma = 1.208729540502
kernel = \
   [[0.0075, 0.0211, 0.0296, 0.0211, 0.0075],
    [0.0211, 0.0588, 0.0828, 0.0588, 0.0211],
    [0.0296, 0.0828, 0.1166, 0.0828, 0.0296],
    [0.0211, 0.0588, 0.0828, 0.0588, 0.0211],
    [0.0075, 0.0211, 0.0296, 0.0211, 0.0075]]

def loadmat(fp):
    data = sio.loadmat(fp)
    ind = [key.startswith('pymg') for key in data.keys()].index(True)
    return data[data.keys()[ind]]

# "clut2b" color look up table 2b (8-bit)
clut2b_numpy = "\x00\x01\r\x00\x02\x14\x00\x03\x1b\x00\x03!\x00\x03'\x00\x04-\x00\x053\x00\x069\x00\t?\x00\tE\x00\nK\x00\x0cQ\x00\x0cW\x00\r]\x00\rc\x00\x0ei\x00\x0fo\x00\x0fu\x00\x12{\x00\x15\x81\x00\x18\x87\x00\x1a\x8d\x00\x1d\x93\x00 \x99\x00#\x9f\x00&\xa5\x00)\xab\x00,\xb1\x00/\xb7\x002\xbd\x005\xc2\x007\xc8\x009\xce\x00;\xd4\x00=\xda\x00?\xe0\x00@\xe5\x00A\xea\x00B\xef\x00C\xf5\x00D\xfb\x00E\xff\x00F\xff\x00G\xff\x00H\xff\x00I\xff\x00J\xff\x00K\xff\x00L\xff\x00M\xff\x00N\xff\x00O\xff\x00P\xff\x00T\xff\x00W\xff\x00[\xff\x00^\xff\x00b\xff\x00e\xff\x00i\xff\x00l\xff\x00p\xff\x00s\xff\x00w\xff\x00z\xff\x00~\xff\x00\x81\xff\x00\x85\xff\x00\x88\xff\x00\x8c\xff\x00\x8f\xff\x00\x93\xf7\x00\x96\xf0\x00\x9a\xe8\x00\x9d\xe0\x00\xa1\xd8\x00\xa4\xd1\x00\xa8\xc9\x00\xab\xc1\x00\xaf\xb9\x00\xb2\xb2\x00\xb6\xaa\x00\xb9\xa2\x00\xbd\x9b\x00\xc0\x93\x00\xc4\x8b\x00\xc7\x83\x00\xcb|\x00\xcet\x00\xd2l\x00\xd5d\x00\xd9]\x00\xdcU\x00\xe0M\x00\xe3F\x00\xe7>\x07\xea6\r\xee.\x14\xf1'\x1a\xf5\x1f!\xf8\x17'\xfc\x0f.\xff\x084\xff\x00;\xff\x00A\xff\x00H\xff\x00N\xff\x00U\xff\x00\\\xff\x00b\xff\x00i\xff\x00o\xff\x00v\xff\x00|\xff\x00\x83\xff\x00\x89\xff\x00\x90\xff\x00\x96\xff\x00\x9d\xff\x00\xa3\xff\x00\xaa\xff\x00\xb1\xff\x00\xb7\xff\x00\xbe\xff\x00\xc4\xff\x00\xcb\xff\x00\xd1\xff\x00\xd8\xff\x00\xde\xff\x00\xe5\xff\x00\xeb\xff\x00\xf2\xff\x00\xf8\xff\x00\xfe\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xff\x00\xff\xfe\x00\xff\xfa\x00\xff\xf8\x00\xff\xf4\x00\xff\xf0\x00\xff\xed\x00\xff\xe9\x00\xff\xe6\x00\xff\xe2\x00\xff\xde\x00\xff\xdb\x00\xff\xd7\x00\xff\xd3\x00\xff\xd0\x00\xff\xcc\x00\xff\xc8\x00\xff\xc5\x00\xff\xc1\x00\xff\xbd\x00\xff\xba\x00\xff\xb6\x00\xff\xb2\x00\xff\xaf\x00\xff\xab\x00\xff\xa8\x00\xff\xa4\x00\xff\xa0\x00\xff\x9d\x00\xff\x99\x00\xff\x95\x00\xff\x92\x00\xff\x8e\x00\xff\x8a\x00\xff\x87\x00\xff\x83\x00\xff\x80\x00\xff|\x00\xffx\x00\xffu\x00\xffq\x00\xffm\x00\xffj\x00\xfff\x00\xffb\x00\xff_\x00\xff[\x00\xffW\x00\xffT\x00\xffP\x00\xffL\x00\xffI\x00\xffE\x00\xffB\x00\xfd>\x00\xff:\x00\xff7\x00\xff3\x00\xff/\x00\xff,\x00\xff(\x00\xff$\x00\xff!\x00\xff\x1d\x00\xff\x1a\x00\xff\x16\x00\xff\x12\x00\xff\x0f\x00\xff\x0b\x00\xff\x07\x00\xff\x04\x04\xff\x00\x07\xff\x00\x0b\xff\x00\x0f\xff\x00\x13\xff\x00\x16\xff\x00\x1a\xff\x00\x1e\xff\x00!\xff\x00%\xff\x00)\xff\x00,\xff\x000\xff\x004\xff\x008\xff\x00;\xff\x00?\xff\x00C\xff\x00F\xff\x00J\xff\x00N\xff\x00Q\xff\x00U\xff\x00Y\xff\x00]\xff\x00`\xff\x00d\xff\x00\xff\xff\xff\xff"
cmap = np.fromstring(clut2b_numpy, dtype=np.uint8).reshape((256,3))

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

def Shift(ImgP, Foffset):
    
    maxShift = np.abs(Foffset[:,0:2]).max() # max shift
    if not maxShift:
        return ImgP
    else:
        ImgPshited = np.zeros((ImgP.shape), dtype=ImgP.dtype)
        
        for y,x,c,ind in Foffset: # [1:] # yoff, xoff, correlation, ind
            #print 'offset (y=%d, x=%d), corr=%f, index=%d' % (y,x,c,ind)
            ImgP[:,:,ind] = np.roll(ImgP[:,:,ind], int(-y), axis=0)
            ImgP[:,:,ind] = np.roll(ImgP[:,:,ind], int(-x), axis=1)
        
        # 0 padding the margin
        ImgPshited[maxShift:-maxShift,maxShift:-maxShift,:] = ImgP[maxShift:-maxShift,maxShift:-maxShift,:]
        
        return ImgPshited


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


def average_odormaps(   
                        data_path, 
                        tags, 
                        Foffsets, 
                        Autoalign,
                        durs, 
                        margin, 
                        SpatMeds,
                        ch=0, 
                        ref_ch=None, 
                        needF=False, 
                        ROIpoly_n=False, 
                        dtype=np.uint16, 
                        raw=False,
                        Fnoise=0
                    ):
    '''
    Follow Rainer's way of getting average odor map:
      For each odor-plane combination, get the most acurate F (RF_F) 
      by averaging raw frames over frames and across trials and 
      use this common F for all trials.
    
    tags    : a list containing files from one plane only and already in a desired order
    Foffsets: a numpy arrary matching to tags
    ch      : channel for multi channel recording
    needF   : Flag to get average F instead of odormap
    ROIpoly_n: a tupple of (list of ROI polygons, list of cell numbers). flag to return dF/F traces instead of image
    raw     : when ROIpoly_n is not False, return raw pixel values instead of dF/F value
    Fnoise  : a constant to subtract from pixel values for dark/read noise from PMD
    '''
    
    if len(tags[0])>10:                                     # Pymagor v2.0 or later
        ver = 2
    elif len(tags[0]) in [5, 6] and os.path.exists(tags[0][-1]): # from online analysis
        ver = 2
    else:                                                   # Pymagor v1.0
        ver = 1
    durpre, durres = durs
    prest, preend = durpre
    resst, resend = durres
    if not ref_ch:
        ref_ch = ch
    # remove all the duplicates while preserving the order
    # http://stackoverflow.com/questions/480214/how-do-you-remove-duplicates-from-a-list-in-python-whilst-preserving-order
    seen = set()  # empty set object
    odors = [x for x in ([dd[2] for dd in tags])
              if x not in seen and not seen.add(x)]
    if type(Foffsets) is list:
        Foffsets = np.array(Foffsets)
    maxShift = np.abs(Foffsets[:,:2]).max() # max shift
    
    odormaps = []
    RF_F = []
    
    for odor in odors:

        if ver == 2:

            file_path = [( dd[0], path_check(dd[-1]) ) for dd in tags if dd[2] == odor]
        else:
            file_path = [( dd[0], path_check(data_path) ) for dd in tags if dd[2] == odor]
        
        temp = None
        withinoffmax = []
        # looping trials
        for n, ((fname, fpath), (yoff, xoff, r, nn)) in enumerate(zip(file_path, Foffsets.tolist())): 
            fp = os.path.join(fpath, fname)
            # by definition 'anatomy view' requires averaging all the frames... this should be cached in file
            img = opentif(fp, ch=ch, dtype=dtype, filt=None, skip=False) - Fnoise
            
            if Autoalign:
                within_offsets = get_offset_within_trial(fp, ref_ch, durpre, margin, SpatMeds)
                img = Shift(img, within_offsets)
                withinoffmax.append( np.abs(within_offsets[:,:2]).max() )
            
            if yoff: img = np.roll(img, int(-yoff), axis=0)
            if xoff: img = np.roll(img, int(-xoff), axis=1)
            
            if temp is None:
                temp = np.zeros(img.shape, dtype=np.float64)
            else: # align across trials
                sofar = _applymask(temp.mean(axis=2), maxShift)
                new = _applymask(img.mean(axis=2), maxShift)
                Foffset = corr.fast_corr(np.dstack((sofar, new)), margin=margin, dur=0, SpaMed=SpatMeds)
                yoff = int(Foffset[1,0])
                xoff = int(Foffset[1,1])
                if yoff: img = np.roll(img, -yoff, axis=0)
                if xoff: img = np.roll(img, -xoff, axis=1)
            
            temp += img
        
        h, w, nframes = img.shape
        rawimg = temp / (n+1)
        
        if ROIpoly_n:  # export will call this for every (field-of-view, odor) pair. better pack outside
        # no need to shift ROIs because ROIs cordinates are on ref tr.
        # when ROIpoly_n true, we are doing this for only one odor. no need to append
            roipolys, cellnumbers = ROIpoly_n
            masks = []
            for roi in roipolys:
                masks.append(getmask(roi,(h,w)))
                rawimg = _applymask(rawimg, maxShift)
            
            waves = getdFoFtraces(rawimg, durpre, masks, 
                    raw=raw, baseline=False, offset=None, needflip=True) # Fnoise is taken care of
            
            odormaps.append(waves)
            
        else:   # this is the part that produces odor maps!
            F = rawimg[:,:,prest:preend+1].mean(axis=2)
            RF_F.append(_applymask(F.copy(), maxShift))
            
            #if needF:
                #odormaps.append(_applymask(F, maxShift))
            #else:  # odor maps
            if len(F[F==0])>0:
                F[F==0] = F[F.nonzero()].min()
            
            FF = np.tile(F[:,:,np.newaxis], (1,1,durres[1]-durres[0]+1))
            dFoF = rawimg[:,:,resst:resend+1]
            dFoF -= FF  # in-place operation is faster
            dFoF /= FF
            dFoF *= 100.0
            odormap = ndimage.filters.convolve(
                        dFoF.mean(axis=2), kernel, mode='nearest'
                        ).astype(np.float32)
            odormaps.append(odormap)
    
    if ROIpoly_n:
        traces = odormaps[0]
        return traces, odors
    
    #if withinoffmax:
        #maxShift = max(maxShift, np.max(withinoffmax))
    
    if len(odormaps)>1:
        odormaps = np.dstack(odormaps)
        RF_F = np.dstack(RF_F)
    else:
        odormaps = odormaps[0].reshape(h,w,1) # dig out from the list
        RF_F = RF_F[0].reshape(h,w,1)
    
    odormaps = _applymask(odormaps, maxShift)
    RF_F = _applymask(RF_F, maxShift)
    
    return RF_F, odormaps, odors


def _applymask(img, maxShift):
    
    if maxShift: # [maxShift:-maxShift] indexing would not work if maxShift = 0
        mask = np.zeros((img.shape), dtype=np.bool)
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
    ymax = np.ceil(poly[:,1].max())
    xmax = np.ceil(poly[:,0].max())
    ymin = np.floor(poly[:,1].min())
    xmin = np.floor(poly[:,0].min())
    
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


def get_offset_within_trial(fp, ref_ch, durpre, margin, SpaMeds):
    
    durpre = tuple(durpre)
    imgfile = os.path.basename(fp)
    data_folder = os.path.dirname(fp)
    
    fp_offset, offset_dict = get_saved_offsets(data_folder)
    
    if (imgfile, ref_ch, durpre, SpaMeds) not in offset_dict.keys():
        img = opentif(fp, dtype=np.uint16, ch=ref_ch)
        if img is not None:
            offsets = corr.fast_corr(
                                        img, 
                                        margin=margin, 
                                        dur=durpre, 
                                        SpaMed=SpaMeds, 
                                        verbose=True
                                        )
            offset_dict[(imgfile, ref_ch, durpre, SpaMeds)] = offsets
            with open(fp_offset, 'wb') as f:
                pickle.dump(offset_dict, f, protocol=2)
        else:
            return None
    
    return offset_dict[(imgfile, ref_ch, durpre, SpaMeds)]


def get_saved_offsets(data_folder):
    fname = os.path.basename(data_folder)+'.offset'
    fp_offset = os.path.join(data_folder, fname)
    if os.path.exists(fp_offset):
        with open(fp_offset, 'rb') as f:
            offset_dict = pickle.load(f)
    else:
        offset_dict = {}
    
    return fp_offset, offset_dict


def show_offsetinfo(fp_offset, offset_dict):
    
    print 'Offset file: ', fp_offset
    _keys = offset_dict.keys()
    fnames = [_fname for _fname,_,_,_ in _keys]
    durpres = [str(_pre) for _,_,_pre,_ in _keys]
    for k in [_keys[_n] for _n in np.lexsort((fnames, durpres))]:
        print '\t%s\t\tRef ch=%d\t\tPre-stimulus frame range=%s\t\tSpatial filters=%s' % k


if __name__ == '__main__':
    
    data_path = r'.\testdata'
    tags = [['test50to100.tif', 'z0','testpulse','1',''],
            ['test50to100_shift x5 y-9.tif', 'z0','testpulse','2','']]
    offsets = np.array([[ 0,  0,  1,  0],
                        [ 5,  9,  1,  1]])
    Autoalign = False
    durs = ( [1, 8], [12, 25] )
    margin = 25
    SpatMeds = True
    RF_F, odormaps, odors = average_odormaps(data_path, tags, offsets, Autoalign, durs, margin, SpatMeds, ch=0)
    print odormaps.shape
    print odormaps.max()
    
    ROIpoly_n = ([[(11, 125), (11, 135), (21, 135), (21, 135), (21, 125)]], [0])
    waves = average_odormaps(data_path, tags, offsets, Autoalign, durs, margin, SpatMeds, ch=0, ROIpoly_n=ROIpoly_n)
    print waves
    
    RF_F, odormaps, odors = average_odormaps(data_path, tags, offsets, Autoalign, durs, margin, SpatMeds, ch=0, needF=True)
    print RF_F.shape
    print RF_F.max()
