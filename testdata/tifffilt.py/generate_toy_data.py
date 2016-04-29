import os

from pylab import *

import tifffile

os.chdir(r'R:\MoonshipTDPS2\projects\namekawa-san\git\Pymagor\testdata\tifffilt.py')

# image depth, height (length), width, and samples
data = np.ones((160, 40, 60), dtype=np.uint8) * 125

data[:, 12:15, 22:25] = 125+20
data[100:130, 12:15, 22:25] = 175

data[:, 5-3:5+4, 5] = 55
data[:, 5, 5-3:5+4] = 55

# imshow(img1[:,:,0], 'gray', interpolation='none')

with tifffile.TiffWriter('temp.tif') as tif:
    tif.save(data)

for n in np.random.randint(0,160,20):
    d = np.random.choice([0,0,0,0,0,0,0,1,-1])
    data[n] = np.roll(data[n,:,:], d, axis=0)
    d = np.random.choice([0,0,0,0,0,0,0,1,-1])
    data[n] = np.roll(data[n,:,:], d, axis=1)

with tifffile.TiffWriter('temp2.tif') as tif:
    tif.save(data)

data = np.ones((160, 40, 60), dtype=np.uint8) * 125

data[:, 12:15, 22:25] = 125+20
data[101:130, 12:15, 22:25] = 175+20

data[:, 5-3:5+4, 5] = 55
data[:, 5, 5-3:5+4] = 55


for n in np.random.randint(0,160,20):
    d = np.random.choice([0,0,0,0,0,0,0,1,-1])
    data[n] = np.roll(data[n,:,:], d, axis=0)
    d = np.random.choice([0,0,0,0,0,0,0,1,-1])
    data[n] = np.roll(data[n,:,:], d, axis=1)

with tifffile.TiffWriter('temp3.tif') as tif:
    tif.save(data)