import os

# PIL
from PIL import Image # it's pillow
from PIL import TiffImagePlugin
#from PIL import iorImagePlugin  # ior is our internal image format on IgorPro.

import numpy as np

import tifffile


def _count_frames(im):
    ' fallback method '
    n = 0
    while True:
        try:
            im.seek(n)
            n += 1
        except:
            break
    return n


def get_all_tags(fp):
    
    meta_data_dict = dict()
    
    try:  # try to open anything that PIL can open
        im = Image.open(fp)
    except IOError:
        print 'IOError: file(s) not found.'
        return None
    
    if hasattr(im, 'tag'):
        
        tagkeys = im.tag.tagdata.keys()
        
        if 51123 in tagkeys:
            
            meta_data_dict['acqsoftware'] = 'micromanager'
            meta_data_dict['nframes'] = _count_frames(im)
            
            #tags = im.tag.tagdata[51123][1] [1:-2] no longer work. newer Pillow parse differently
            tags = im.tag.tagdata[51123]
            for tag in tags.split(','):
                split = tag.split(':')
                key = ''.join(split[0].split('\"'))
                if len(split) >2:
                    value = ':'.join(split[1:])
                else:
                    value = split[1]
                value = ''.join(value.split('\"'))
                meta_data_dict[key] = value

        elif 270 in tagkeys: # scanimage or ImageJ tif
            #tags = im.tag.tagdata[270][1] no longer work. newer Pillow parse differently
            tags = im.tag.tagdata[270]
            
            if tags.startswith('ImageJ'):
                meta_data_dict['acqsoftware'] = 'ImageJ'
                sepstr = '\n'
            else:
                meta_data_dict['acqsoftware'] = 'scanimage'
                sepstr = '\r'
                
            for tag in tags.split(sepstr):
                splitted = tag.split('=')
                if len( splitted ) == 2:
                    key, value = splitted
                    meta_data_dict[key] = value
        
        elif tagkeys == [274, 277, 279]:
            meta_data_dict['acqsoftware'] = 'MATLAB'
            meta_data_dict['frames'] = _count_frames(im)
            
        else: # unknown file type
            return _count_frames(im)
    
    elif fp.endswith('ior'):
        with open(fp, 'rb', 16) as f:
            buf = f.read(584)
            header = np.fromstring(buf, 'u2')
        
        meta_data_dict['acqsoftware'] = 'Imagor3'
        meta_data_dict['nframes'] = int(header[194])
        meta_data_dict['frameRate'] = 1000 / float(header[195])

    else: # if no meta data exists, then return the frame number only
        return _count_frames(im)
    
    return meta_data_dict


def get_tags(fp):
    '''
    Put following meta data into a dictionary:
        nch, nframes, avg_flag, frameRate, 
        scanAmplitudeX, scanAmplitudeY, zoomFactor,
        absXPosition, absYPosition, absZPosition,
        relXPosition, relYPosition, relZPosition
    '''
    
    Metadata = get_all_tags(fp)
    if type(Metadata) == dict:
        acqsoftware = Metadata['acqsoftware']
    elif type(Metadata) == int:
        acqsoftware = 'unknown'
    elif Metadata == None: # failed to open
        return
    
    img_info = dict()
    float_keys = [
                'state.acq.frameRate',
                'state.acq.scanAmplitudeX',
                'state.acq.scanAmplitudeY',
                'state.motor.absXPosition',
                'state.motor.absYPosition',
                'state.motor.absZPosition',
                'state.motor.relXPosition',
                'state.motor.relYPosition',
                'state.motor.relZPosition'
                ]
    
    if acqsoftware == 'ImageJ' or acqsoftware == 'MATLAB':
        img_info['nch'] = 1
        img_info['zoomFactor'] = 0
        img_info['averaging'] = 0
        img_info['recorded_ch'] = ['1','0','0','0']
        img_info['nframes'] = int(Metadata['frames'])
        img_info['scanAmplitudeX'] = 0
        img_info['scanAmplitudeY'] = 0
        img_info['frameRate'] = 0
    
    elif acqsoftware == 'micromanager':
        img_info['nch'] = 1
        img_info['zoomFactor'] = 0
        img_info['averaging'] = 0
        img_info['recorded_ch'] = ['1','0','0','0']
        img_info['nframes'] = Metadata['nframes']
        img_info['scanAmplitudeX'] = 0
        img_info['scanAmplitudeY'] = 0
        img_info['frameRate'] = 1000 / float( Metadata['Exposure-ms'] )
        
    elif acqsoftware == 'Imagor3':
        img_info['nch'] = 1
        img_info['zoomFactor'] = 0
        img_info['averaging'] = 0
        img_info['recorded_ch'] = ['1','0','0','0']
        img_info['nframes'] = Metadata['nframes']
        img_info['scanAmplitudeX'] = 0
        img_info['scanAmplitudeY'] = 0
        img_info['frameRate'] = Metadata['frameRate']
        
    elif acqsoftware == 'scanimage':
        
        if type(Metadata) != dict:
            raise(Exception("invalid scanimage tif"))
        
        ver = Metadata['state.software.version']
        img_info['version'] = ver
        
        if float(ver) > 3.6:
            # rename some keys
            float_keys[1] = 'state.acq.scanAngleMultiplierFast'
            float_keys[2] = 'state.acq.scanAngleMultiplierSlow'
        
        zdim = int(Metadata['state.acq.numberOfZSlices'])
        frames = int(Metadata['state.acq.numberOfFrames'])
        
        img_info['nch'] = int(Metadata['state.acq.numberOfChannelsSave'])
        img_info['zoomFactor'] = float(Metadata['state.acq.zoomFactor'])
        img_info['averaging'] = int(Metadata['state.acq.averaging'])
        img_info['recorded_ch'] = [Metadata['state.acq.savingChannel1'],
                        Metadata['state.acq.savingChannel2'],
                        Metadata['state.acq.savingChannel3'],
                        Metadata['state.acq.savingChannel4']]
        
        for key in float_keys:
            value = Metadata[key]
            key = key.split('.')[-1]
            if value == '[]':
                img_info[key] = 'NA'
            else:
                img_info[key] = float(value)
        
        # z-stack typically has 10 frames and 50 zdim.
        # odor res has 160 frames and 1 zdim.
        if float(ver) > 3.6:
            n = int(Metadata['state.acq.numAvgFramesSave'])
            img_info['nframes'] = frames / n * zdim
        else:
            if Metadata['state.acq.averaging'] == '1': # each plane averaged
                img_info['nframes'] = zdim
            else:
                img_info['nframes'] = frames*zdim
    
    else:  # unrecognized file types
        img_info['nch'] = 1
        img_info['zoomFactor'] = 'NA'
        img_info['averaging'] = 'NA'
        img_info['recorded_ch'] = 'NA'
        img_info['nframes'] = Metadata
        img_info['scanAmplitudeX'] = 'NA'
        img_info['scanAmplitudeY'] = 'NA'
        img_info['frameRate'] = 'NA'
        
        for key in float_keys:
            img_info[key] = 'NA'
        
    return img_info

count = 0
def opentif(fp, 
            dtype=np.uint8, 
            filt=None, 
            skip=False, 
            ch=0, 
            check8bit=False            
            ):
    '''
    fp: file pointer. full path strings
    dtype:  np.unit8 or np.uint16 or np.float32
    filt: PIL filter object.  ex. im.filter(ImageFilter.MedianFilter)
    skip: a list of durpre and durres to set frames to read.
    '''
    img_info = get_tags(fp)
    if img_info == None:
        return None
    nch = img_info['nch']
    if ch+1 > nch:
        print 'channel%d not found in %s' % (ch, fp)
        if check8bit is not False:
            return None, None
        else:
            return None
    nframes = img_info['nframes']
    im = Image.open(fp)
    w,h = im.size
    
    if skip:  
        if len(skip) == 2:  # load only pre-stimulus and response periods
            durpre, durres = skip
            zsize = np.diff(durpre) + np.diff(durres) + 2
            size = ( h, w, zsize )
            
            fr2load_pre = np.arange(durpre[0], durpre[1]+1) * nch + ch
            fr2load_res = np.arange(durres[0], durres[1]+1) * nch + ch
            rng = np.hstack( (fr2load_pre, fr2load_res) )
        else:               # load only the 1st frame during pre-stimulus
            durpre = skip # unpacking...
            size = ( h, w, 1 )
            rng = [(durpre[0]+ch) * nch]
    else:   # load all frames
        size = ( h, w, nframes )
        rng = xrange(0+ch, nframes*nch, nch)
    
    if check8bit is not False: # either True or AbortEvent object but,
    # wx.lib.delayedresult.AbortEvent object is not considered as "True"
        if type(check8bit) == bool:
            abortEvent = lambda : False
        else:
            abortEvent = check8bit
        
        if fp.endswith(('TIF','tif','TIFF','tiff')):
            return _check8bit_tifffile(fp, rng, nframes, abortEvent)
        else:
            return _check8bit_PIL(im, rng, nframes, abortEvent)
        
    if fp.endswith(('TIF','tif','TIFF','tiff')) and dtype == np.uint16:
        with tifffile.TIFFfile(fp) as tif: # faster for tiff 8 and 16 bit
            img = tif.asarray()
            if len(img.shape) == 3:
                img = img[rng,:,:].transpose((1,2,0))
            elif len(img.shape) == 4:
                img = img[rng,0,:,:].transpose((1,2,0))
            else:
                print 'unknown tif input. axes may be wrong.'
    else:
        img = np.zeros(size, dtype=dtype)
        if dtype == np.uint8: # faster than im.getdata but slower than tifffile
            for n, fr in enumerate(rng):
                im.seek(fr)
                img[:,:,n] = np.array(im.convert('L'))
            
        else:   # general but slower method
            for n, fr in enumerate(rng):
                im.seek(fr)
                img[:,:,n] = np.array(im.getdata()).reshape(h,w)
    

    return img[::-1,:,:] # for wx, openGL cordinate. y=0 is on top


def _check8bit_tifffile(fp, rng, nframes, abortEvent):
    mx = []
    _cnt = 0
    with tifffile.TIFFfile(fp) as tif:
        while _cnt < nframes-1 and not abortEvent():
            fr = rng[_cnt]
            img = tif[fr].asarray()
            c, bins = np.histogram(img, bins=16, range=(0,1023))
            mx.append( c )
            _cnt += 1
    
    mx = np.array(mx)
    return (mx.sum(axis=0) , bins)

def _check8bit_PIL(im, rng, nframes, abortEvent): # slower
    mx = []
    _cnt = 0
    while _cnt < nframes-1 and not abortEvent():
        fr = rng[_cnt]
        im.seek(fr)
        c, bins = np.histogram(np.array(im.getdata()), bins=16, range=(0,1023))
        mx.append( c )
        _cnt += 1
    
    mx = np.array(mx)
    return (mx.sum(axis=0) , bins)

if __name__ == '__main__':
    
    ## micromanager
    #fp = r'testdata\EngGCaMP2xOL_images.tif'
    
    ## ImageJ
    fp = r"testdata\Untitled-1.tif"
    
    ## ScanImage 3.8 z-stack
    #fp = r'testdata\beads004.tif'
    
    ## ScanImage 3.8 time series
    #fp = r'testdata\40frames001.tif'
    
    info = get_tags(fp)
    durpre = [1,8]
    durres = [10,25]
    
    #img = opentif(fp, dtype=np.uint16, skip=[durpre, durres])
    img = opentif(fp, dtype=np.uint16, skip=False, ch=0)
    print img.shape
    
    import time
    t0 = time.time()
    a, b = opentif(fp, skip=False, check8bit=True, ch=1)
    print time.time() - t0
    
    #from pylab import *
    #bar(b[1:], a)
    #show()
    print a, b
    
    

    
    