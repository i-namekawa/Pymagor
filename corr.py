import numpy as np
from scipy.stats.stats import pearsonr
from scipy.ndimage.filters import median_filter


def pearson(img, margin=3, dur=(0,25), SpaMed=False):
    ''' img     : numpy array
        margin  : shift range setting
        dur     : to define F in frames
        SpaMed  : can be a list of two boolean values or just a bool
    '''
    height, width, nframes = img.shape
    
    offsetxy = np.zeros((nframes,4), dtype=np.float)
    c = np.zeros((margin*2+1, margin*2+1), dtype=np.float)
    
    # clip out subimage at the center of img.
    x1, y1 = margin, margin
    x2, y2 = width-margin, height-margin
    if type(dur)==int:
        ref = img[y1:y2, x1:x2, dur]
        ref[np.isnan(ref)] = 0
    else:
        ref = np.mean(img[y1:y2, x1:x2, dur[0]:dur[1]], 2)
    
    if type(SpaMed) is bool:
        Filt_ref, Filt_sub = SpaMed, False
    elif type(SpaMed) is list:
        Filt_ref, Filt_sub = SpaMed
    
    if Filt_ref:
        ref = median_filter(ref, (3,3), mode='nearest')
    
    ref = ref.ravel()
    
    for z in range(nframes):
        if Filt_sub:
            target = median_filter(img[:,:,z], (3,3), mode='nearest')
        else:
            target = img[:,:,z]
            
        for xoff in range(-margin, margin+1):
            for yoff in range(-margin, margin+1):
                
                sub = target[y1+yoff:y2+yoff, x1+xoff:x2+xoff].ravel() # fastest
                #sub = img[y1+yoff:y2+yoff, x1+xoff:x2+xoff,z].flat
                #sub = img[y1+yoff:y2+yoff, x1+xoff:x2+xoff,z].reshape(-1)
                #sub = img[y1+yoff:y2+yoff, x1+xoff:x2+xoff,z].flatten()
                c[margin+yoff, margin+xoff] = pearsonr(ref,sub)[0]
        
        offset = np.nonzero(c.max() == c)
        #print offset, c.max(), c
        
        offsetxy[z,:] = [offset[0][0]-margin,\
                         offset[1][0]-margin,\
                         c.max(),
                         z]
    
    return offsetxy


def fast_corr(img, margin=3, dur=(0,25), SpaMed=False, verbose=False):
    '''
    the original algorithm developed in MATLAB 
    by Adrian Wanner (adrian.wanner@fmi.ch)
    '''
    
    # sanity check
    if type(margin) != int or margin < 0:
        raise(Exception('margin needs to be int greater than 0.'))
    
    if type(dur) == int:
        T = img[:,:,dur]
    elif hasattr(dur, '__iter__') and len(dur) == 2:
        lo, hi = dur
        if 0 <= lo and hi+1 < img.shape[2]:
            T = np.mean(img[:,:,lo:hi+1], axis=2)
        else:
            raise(Exception('Averaging setting is out of range.'))
    else:
        raise(Exception('The type of dur needs to be int or tuple.'))
    
    if type(SpaMed) is bool:
        Filt_T, Filt_A = SpaMed, False
    elif hasattr(SpaMed, '__iter__') and len(SpaMed) == 2:
        Filt_T, Filt_A = SpaMed
    else:
        raise(Exception('SpaMed should be either a bool or a tuple of two bools'))
    
    h,w,nframes = img.shape
    
    def _nextbin(x):
        
        count = 0
        while x > 2**count:
            count += 1
        
        return 2**count
    
    ffth = _nextbin(h*2-1)
    fftw = _nextbin(w*2-1)
    fftsize = (ffth,fftw)
    
    MaxOffset = [   min(margin, h),
                    min(margin, h),
                    min(margin, w),
                    min(margin, w)  ]
    centerHeight=h+np.array([-(MaxOffset[0]-1),(MaxOffset[1]-1)])
    centerWidth =w+np.array([-(MaxOffset[2]-1),(MaxOffset[3]-1)])
    #print MaxOffset, fftsize
    if Filt_T:
        T = median_filter(T, 3, mode='nearest')
    
    
    def _norm_per_line(img):
        
        w = img.shape[1]
        _mean = img.mean(axis=1)
        _subt = np.tile(_mean[:,np.newaxis], (1,w))
        img_mean = img.astype(np.float) - _subt
        
        _norm = np.sqrt( np.dot(img_mean**2, np.ones((w,1))/w ) )
        _norm[_norm==0.] = 1.
        _norm = 1./_norm
        
        return img_mean * _norm.dot( np.ones((1,w)) )
    
    
    TT = _norm_per_line(T)
    TT = np.fft.fft2(TT[::-1,::-1], s=fftsize, axes=(0,1))
    
    offsets = []
    
    adjustx = 1.0 - np.diff(centerHeight)[0]/2.0
    adjusty = 1.0 - np.diff(centerWidth )[0]/2.0
    
    # redundant for performance
    if (MaxOffset[0]+MaxOffset[1])*fftsize[1] <= \
        (MaxOffset[2]+MaxOffset[3])*fftsize[0]:
        # ifft only the center part
        for n in xrange(nframes):
            A = img[:,:,n]
            if Filt_A:
                A = median_filter(A, 3, mode='nearest')
            AA = _norm_per_line(A)
            AA = np.fft.fft2(AA, s=fftsize, axes=(0,1))
            
            AT = np.fft.ifft(AA*TT, fftsize[0], axis=0)
            AT = AT.transpose([1,0])
            AT = AT[:,centerHeight[0]:centerHeight[1]]
            AT = np.fft.ifft(AT, fftsize[1], axis=0)
            AT = np.real(AT).transpose([1,0])
            C = AT[:,centerWidth[0]:centerWidth[1]]
            yoff, xoff = np.nonzero(C==C.max())
            
            offsets.append(( yoff[0] + adjustx,
                             xoff[0] + adjusty,
                             C.max(),
                             n  ))
            if verbose:
                print '%d: %d,%d ' % ( n, offsets[-1][0], offsets[-1][1] ),
                if np.remainder(n, 20) == 19:
                    print ''
    
    else:  # ifft the whole
        for n in xrange(nframes):
            A = img[:,:,n]
            if Filt_A:
                A = median_filter(A, 3, mode='nearest')
            AA = _norm_per_line(A)
            AA = np.fft.fft2(AA, s=fftsize, axes=(0,1))
            
            AT = AA*TT
            AT = AT.transpose([1,0])
            AT = np.fft.ifft(AT, fftsize[1], axis=0)
            AT = AT.transpose([1,0])
            AT = AT[:,centerWidth[0]:centerWidth[1]]
            AT = np.fft.ifft(AT, fftsize[0], axis=0)
            AT = np.real(AT)
            AT = AT.transpose([1,0])
            AT = AT[:,centerHeight[0]:centerHeight[1]]
            C = AT.transpose([1,0])
            yoff, xoff = np.nonzero(C==C.max())
            
            offsets.append(( yoff[0] + adjustx,
                             xoff[0] + adjusty,
                             C.max(),
                             n  ))
            if verbose:
                print '%d: %d,%d ' % ( n, offsets[-1][0], offsets[-1][1] ),
                if np.remainder(n, 20) == 19:
                    print ''
    
    offsets = np.array(offsets)
    offsets[:,2] = offsets[:,2] / offsets[:,2].max()
    
    return offsets


if __name__ == '__main__':
    T = np.zeros((26,22))
    T[3:6,3:6] = [[1, 50, 1], [50, 50, 50], [1, 50, 1]]
    noise = np.random.randint(0,2,T.shape)
    T[noise == 1] += 1
    A = np.roll(T, 5, axis=0)
    A = np.roll(A, 3, axis=1)
    
    img = np.dstack((T,A))
    offsets = fast_corr(img, margin=6, dur=0)
    print offsets
    
    offsets2 = pearson(img, margin=6, dur=0)
    print offsets2
