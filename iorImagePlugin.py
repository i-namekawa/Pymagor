from PIL import Image, ImageFile
import numpy as np

#data = np.fromstring(header, 'u2') # u2 is uint16
#data = np.frombuffer(header, np.uint16) # same
#x, y, z, dt = data[192:196]
#self.size = int(x), int(y)  # 348*260
#self.nframe = int(z)

'''
For installation, this shold be copied in:
    \Lib\site-packages\PIL
'''


def i16(c):
    return ord(c[0]) + (ord(c[1])<<8)
    
class iorImageFile(ImageFile.ImageFile):
    
    format = "IOR"
    format_description = "Imagor Camera Image"
    
    def _open(self):
        
        self.__offset = 584
        header = self.fp.read(self.__offset)
        #self.fp.seek(0)
        if header[92:105] != 'CamDataSeries':
            raise SyntaxError, "not an ior file"
        
        ## size in pixels (width, height)
        self.size = i16(header[384:386]), i16(header[386:388])
        self.nframe = i16(header[388:390])
        #print self.size, self.nframe
        
        # mode setting
        self.mode = 'I;16'
        
        # data descriptor
        self.tile = [
            ("raw",             # decoder
            (0, 0) + self.size, # 4-tuple to indicate the region
            self.__offset,  # offset to the image data in bytes
            (self.mode, 0, 1))  # parameters for decoder (mode, stride, orientation)
        ]                           # mode: I;16
                                    # stride 0 : no padding between lines
                                    # orientation 1 : the first line is the top line on the screen
        
        self.step = self.size[0] * self.size[1] * 2  # 16 bit so 2 bytes
        ## image data in byte = 14476800 when (348,260) 
        #print self.step  # 180960
        
        self.__frame = -1  # current frame to show when tell is called
        self.__fp = self.fp
        self.seek(0)
        
    def seek(self, frame):
        "Select a given frame as current image"

        if frame < 0:
            frame = 0
        elif frame >= self.nframe:
            raise IOError, 'No more frame available at %d in the ior file' % frame
        self.__frame = frame
        
        self.fp = self.__fp  # self.fp may be overwritten by im.show() etc
        self.fp.seek(self.__offset)
        self.tile = [("raw", (0,0)+self.size, self.__offset, (self.mode, 0, 1))]
        
        self.__offset = self.step * self.__frame + 584
        
    def tell(self):
        
        return self.__frame


Image.register_open("IOR", iorImageFile)
Image.register_extension("IOR", ".ior")

