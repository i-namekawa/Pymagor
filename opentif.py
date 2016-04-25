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

        elif 270 in tagkeys: # scanimage or ImageJ tif or tifffile.TiffWriter
            #tags = im.tag.tagdata[270][1] no longer work. newer Pillow parse differently
            tags = im.tag.tagdata[270]
            
            if tags.startswith('ImageJ'):
                meta_data_dict['acqsoftware'] = 'ImageJ'
                sepstr = '\n'
            elif tags.startswith('scanimage'):
                if [l for l in tags.splitlines() if l.find('framerate_user')>0]:
                    # Peter's SoundCoil resonance Z scan version
                    meta_data_dict['acqsoftware'] = 'scanimage4B' 
                else:
                    meta_data_dict['acqsoftware'] = 'scanimage4'
                sepstr = '\n'
            elif tags.startswith('state.configPath'):
                meta_data_dict['acqsoftware'] = 'scanimage3.8'
                sepstr = '\r'
            elif tags.startswith('state.configName'):
                meta_data_dict['acqsoftware'] = 'scanimage3.6'
                sepstr = '\r'
            elif tags.startswith('{"shape"') and 305 in tagkeys: # tifffile.py?
                if im.tag.tagdata[305].split('\x00')[0] == 'tifffile.py':
                    meta_data_dict['acqsoftware'] = 'tifffile.py'
                    tmp = tags[tags.find('[')+1:tags.find(']')].split(',')
                    meta_data_dict['nframes'] = int(tmp[0])
                    return meta_data_dict
                else: # unknown file type
                    return _count_frames(im)
            else:
                meta_data_dict['acqsoftware'] = 'unknown'
                meta_data_dict['nframes'] = _count_frames(im)
                sepstr = '\n'
            
            for tag in tags.split(sepstr):
                splitted = tag.split('=')
                if len( splitted ) == 2:
                    key, value = splitted
                    #print key, value
                    meta_data_dict[key] = value
        
        elif tagkeys in [ [274, 277, 279],  # PIL 1.17 / pillow 2.3.0
                          [256, 257, 258, 259, 262, 296, 320, 273, 274, 277, 278, 279, 282, 283, 284]]: # pillow 3.2.0
            meta_data_dict['acqsoftware'] = 'MATLAB'
            meta_data_dict['nframes'] = _count_frames(im)
            
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
    float_keys = [ # ver 3.6-3.8
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
    
    if acqsoftware == 'ImageJ':
        img_info['nch'] = 1
        img_info['zoomFactor'] = 0
        img_info['averaging'] = 0
        img_info['recorded_ch'] = ['1','0','0','0']
        img_info['nframes'] = int(Metadata['images'])
        img_info['scanAmplitudeX'] = 0
        img_info['scanAmplitudeY'] = 0
        img_info['frameRate'] = 0
    
    elif acqsoftware == 'MATLAB':
        img_info['zoomFactor'] = 0
        img_info['averaging'] = 0
        img_info['nch'] = 1
        img_info['recorded_ch'] = ['1','0','0','0']
        img_info['nframes'] = int(Metadata['nframes'])
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
        
    elif acqsoftware.startswith('scanimage'):
        
        if type(Metadata) != dict:
            raise(Exception("invalid scanimage tif"))
        
        if 'state.software.version' in Metadata.keys():
            ver = float(Metadata['state.software.version'])
        else:
            verstr = acqsoftware.split('scanimage')[-1]
            try:    # most likely '4'
                ver = float(verstr)
            except: # but can be 4B
                ver = verstr

        img_info['version'] = ver

        if ver == 3.8:
            # rename some keys
            float_keys[1] = 'state.acq.scanAngleMultiplierFast'
            float_keys[2] = 'state.acq.scanAngleMultiplierSlow'
        elif ver == 4.0 or ver == '4B':
            float_keys = []
            
        
        if ver == 3.6 or ver == 3.8:
            zdim = int(Metadata['state.acq.numberOfZSlices'])
            frames = int(Metadata['state.acq.numberOfFrames'])
            img_info['nch'] = int(Metadata['state.acq.numberOfChannelsSave'])
            img_info['zoomFactor'] = float(Metadata['state.acq.zoomFactor'])
            img_info['averaging'] = int(Metadata['state.acq.averaging'])
            img_info['recorded_ch'] = [Metadata['state.acq.savingChannel1'],
                                        Metadata['state.acq.savingChannel2'],
                                        Metadata['state.acq.savingChannel3'],
                                        Metadata['state.acq.savingChannel4']]
        
        elif ver == 4.0 or ver == '4B':
            zdim = int(Metadata['scanimage.SI4.stackNumSlices '])
            frames = int(Metadata['scanimage.SI4.acqNumFrames '])
            
            img_info['zoomFactor'] = float(Metadata['scanimage.SI4.scanZoomFactor '])
            img_info['averaging'] = int(Metadata['scanimage.SI4.acqNumAveragedFrames '])
            img_info['recorded_ch'] = Metadata['scanimage.SI4.channelsSave ']
            
            img_info['scanAmplitudeX'] = Metadata['scanimage.SI4.scanAngleMultiplierFast ']
            img_info['scanAmplitudeY'] = Metadata['scanimage.SI4.scanAngleMultiplierSlow ']
            
            if ver == '4B':
                img_info['frameRate'] = Metadata['scanimage.SI4.framerate_user ']
                resonancescan = int(Metadata['scanimage.SI4.fastZEnable '])
                if resonancescan == 1:
                    # treat z planes from soundcoil z-scan as separate channels
                    img_info['nch'] = int(Metadata['scanimage.SI4.fastz_cont_nbplanes '])
                else:
                    img_info['nch'] = int(Metadata['scanimage.SI4.channelsSave '])
            else: # ver 4.0
                img_info['frameRate'] = 'NA'
                img_info['nch'] = int(Metadata['scanimage.SI4.channelsSave '])
            
        for key in float_keys:
            value = Metadata[key]
            key = key.split('.')[-1]
            if value == '[]':
                img_info[key] = 'NA'
            else:
                img_info[key] = float(value)
        
        # Lastly, figure out the number of frames
        # e.g. z-stack may has 10 frames (but averaged) and 50 z plane (zdim).
        # odor res has 160 frames and 1 zdim.
        if ver == 3.8:
            n = int(Metadata['state.acq.numAvgFramesSave'])
            img_info['nframes'] = frames / n * zdim
        elif ver == 3.6:
            if Metadata['state.acq.averaging'] == '1': # each plane averaged
                img_info['nframes'] = zdim
            else:
                img_info['nframes'] = frames * zdim
        elif ver == 4:
            n = int(Metadata['scanimage.SI4.acqNumAveragedFrames ']) # typically 1 unless ztstack
            img_info['nframes'] = frames / n * zdim
        elif ver == '4B':
            n = int(Metadata['scanimage.SI4.acqNumAveragedFrames '])
            img_info['nframes'] = frames / n * zdim / img_info['nch']

    elif acqsoftware == 'tifffile.py':
        
        img_info['nch'] = 1
        img_info['zoomFactor'] = 'NA'
        img_info['averaging'] = 'NA'
        img_info['recorded_ch'] = 'NA'
        img_info['nframes'] = Metadata['nframes']
        img_info['scanAmplitudeX'] = 'NA'
        img_info['scanAmplitudeY'] = 'NA'
        img_info['frameRate'] = 'NA'

    else:  # unrecognized file types
        
        print 'unrecognized file types'
        
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
            frames2load=False, 
            ch=0, 
            check8bit=False,
            nch=None,
            nframes=None
            ):
    '''
    fp      : file full path strings
    (optional args)
    dtype   :  np.unit8 or np.uint16 or np.float32
    filt    : PIL filter object.  ex. im.filter(ImageFilter.MedianFilter)
    frames2load : a list of durpre and durres to set frames to read. or numpy array of slice indices
    ch      : channel to read (every n th frame offset by ch, n being total # of channels)
    check8bit : flag to indicate that we want a histogram of pixel values in 8 bit range.
    nch     : total # of channels in the image file
    nframes : total # of frames per channel in the image file
    '''
    if nch is None or nframes is None:
        img_info = get_tags(fp)
        if img_info is None:
            return None
        if nframes is None:
            nframes = img_info['nframes']
        if nch is None:
            nch = img_info['nch']
    
    if ch+1 > nch:
        print 'channel%d not found in %s' % (ch, fp)
        if check8bit:
            return None, None
        else:
            return None
    
    im = Image.open(fp)
    w,h = im.size
    
    if frames2load is not False:  # "if frames2load" will result in ValueError.
        if len(frames2load) == 2:  # load only pre-stimulus and response periods
            durpre, durres = frames2load
            zsize = np.diff(durpre) + np.diff(durres) + 2
            size = ( h, w, zsize )
            
            fr2load_pre = np.arange(durpre[0], durpre[1]+1) * nch + ch
            fr2load_res = np.arange(durres[0], durres[1]+1) * nch + ch
            rng = np.hstack( (fr2load_pre, fr2load_res) )
        elif type(frames2load) == np.ndarray: #we can give ready to use numpy indices as wll
            rng = frames2load
            size = ( h, w, rng.size )
        else:               # load only the 1st frame during pre-stimulus
            durpre = frames2load # unpacking...
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
            img = tif.asarray(rng)
            
            if len(img.shape) == 3:
                img = img.transpose((1,2,0))
            elif len(img.shape) == 4:
                img = img[:,0,:,:].transpose((1,2,0))
            elif len(img.shape) == 2:  # packing option = 2 (only first raw frame)
                img = img[np.newaxis,:,:].transpose((1,2,0))
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
    #fp = r"testdata\Untitled-1.tif"
    
    # MATLAB
    # fp = r'testdata\test50to100.tif'
    
    ## ScanImage 3.6 z-stack
    # fp = r"testdata\scanimage36\PSF001.tif"

    ## ScanImage 3.8 z-stack
    #fp = r'testdata\beads004.tif'
    
    ## ScanImage 3.8 time series
    #fp = r'testdata\40frames001.tif'
    
    ### ScanImage4B for resonance scan (forked by Peter)
    #fp = r'testdata\ScanImageBTestFiles\Test01_005_.tif'
    ## ScanImage 4B for resonance scan zstack
    #fp = r"testdata\ScanImageBTestFiles\beads_005_.tif"
    ## ScanImage 4B 9 planes x 110 = 990 frames hw=512x512
    # fp = r"R:\Data\itoiori\scanimage\2016\2016-03-11\positive01\IN26tested_008_.tif"
    ## ScanImage 4B 5 planes x 200 = 1000 frames hw=512x512
    # fp = r'R:/Data/itoiori/scanimage/2016/2016-03-22/IN26-pair01-fish04_001_.tif'
    ## ScanImage 4B zstack
    # fp = 'R:/Data/itoiori/scanimage/2016/2016-03-11/positive01/IN26tested_025_.tif'
    

    # toy data by tifffile.TiffWriter.save
    fp = r'R:/MoonshipTDPS2/projects/namekawa-san/git/Pymagor/testdata/temp.tif'

    info = get_tags(fp)
    print info

    meta_data_dict = get_all_tags(fp)
    print meta_data_dict['acqsoftware']
    
    durpre = [1,10]
    durres = [13,20]
    #img = opentif(fp, dtype=np.uint16, frames2load=[durpre, durres])
    img = opentif(fp, dtype=np.uint16, frames2load=False, ch=0)
    print img.shape
    
    import time
    t0 = time.time()
    a, b = opentif(fp, frames2load=False, check8bit=True, ch=0)
    print time.time() - t0
    
    print a, b
    
    

    
    
