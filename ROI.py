from PIL import Image
from PIL import ImageDraw
import numpy as np
from scipy import ndimage


class ROIv3(object):
    
    def __init__(self, ROI=None, z='Plane', category='Cell'):
        
        self.data = []
        self.z = []
        self.category = []
        self.areas = []
        self.centers = []
        if ROI:
            self.add(ROI, z=z, category=category)
        
    # private methods (single underscore will hide them)
    @staticmethod
    def _check_ROIinput(ROI):
        if type(ROI[0]) == tuple:
            return [ROI]
        
        temp = ROI
        while type(temp[0]) != tuple:
            if type(temp[0][0]) == tuple:
                break
            temp = temp[0]
        
        #print temp
        return temp
    
    @staticmethod
    def _validate_metadata(meta, n):
        if type(meta) == str:
            return [meta] * n
        elif type(meta) in [unicode, np.unicode_, np.string_]:
            # print 'ROIv3:', meta, type(meta)
            return [str(meta)] * n
        elif type(meta) == list and len(meta) == n:
            return meta
        else:
            print 'data type invalid', type(meta), meta
    
    @staticmethod
    def _check_index(inputs):
        '''
        make sure that sorting index is a list.
        '''
        if inputs is None:
            return []
        elif type(inputs) is int:
            return [inputs]
        elif type(inputs) is list:
            return inputs
        else:
            raise(Exception('inputs should be a list'))
    
    @staticmethod
    def _get_area_center(poly):
        width, height = np.array(poly).max(axis=0)
        im = Image.new('L', (width, height),0)
        ImageDraw.Draw(im).polygon([(x,y) for x,y in poly], outline=1, fill=1)
        numimg = np.array(im)
        area = numimg.sum()
        y,x = map(lambda x:int(x), ndimage.measurements.center_of_mass(numimg))
        center = (x,y)
        return area, center
    
    
    # public methods
    def add(self, ROIs, z='Plane', category='Cell'):
        ROIs = self._check_ROIinput(ROIs)
        #print 'from add:', self.z, z, ROIs
        self.z += self._validate_metadata(z, len(ROIs))
        self.category += self._validate_metadata(category, len(ROIs))
        
        for poly in ROIs:
            
            self.data.append( poly )
            area, center_of_mass = self._get_area_center(poly)
            self.areas.append( area )
            self.centers.append( center_of_mass )
        
        
    def remove(self, ROI2rem):
        ROI2rem = self._check_index(ROI2rem)
        self.data = [d for n,d in enumerate(self.data) if n not in ROI2rem]
        self.z = [z for n,z in enumerate(self.z) if n not in ROI2rem]
        self.areas = [a for n,a in enumerate(self.areas) if n not in ROI2rem]
        self.centers = [c for n,c in enumerate(self.centers) if n not in ROI2rem]
        self.category = [c for n,c in enumerate(self.category) if n not in ROI2rem]
        
    def shift(self, (dx, dy), ROIs2mov=None):
        for n in self._check_index(ROIs2mov):
            self.data[n] = [ (x+dx, y+dy) for x,y in self.data[n] ]
        
    def sort(self, index=[]):
        
        if index == []: # auto-sort by area
            index = self.autosort()
        elif 0 < len(index) < len(self.data):
            [index.insert(0,a) for a in range(len(self.data)-1,-1,-1) if a not in index]
        else:
            raise(Exception('index is not in right format'))
        self.data = [ self.data[ind] for ind in index ]
        self.z = [self.z[ind] for ind in index]
        self.areas = [self.areas[ind] for ind in index]
        self.centers = [self.centers[ind] for ind in index]
        self.category = [self.category[ind] for ind in index]
        
    def autosort(self):
        return np.lexsort(([y for y,x in self.centers], self.z, self.category))


if __name__ == '__main__':
    import pprint
    pp = pprint.PrettyPrinter(indent=4)

    print '\nROIv3 testing\n'
    
    print '\n\tjust create without params'
    roi2 = ROIv3()
    print 'ROIdata'
    pp.pprint( roi2.data )
    print 'z'
    pp.pprint( roi2.z )
    print 'category'
    pp.pprint( roi2.category )
    
    print '\n\tnewly create one roi with a nested list of a list of tupples'
    data = [[(92, 10), (94, 14), (94, 19), (90, 23)]]
    roi2 = ROIv3(data)
    print 'ROIdata'
    pp.pprint( roi2.data )
    print 'z'
    pp.pprint( roi2.z )
    print 'category'
    pp.pprint( roi2.category )
    
    print '\n\tnow append one roi for one plane'
    data = [(92, 10), (94, 14), (94, 19), (90, 23)]
    z = 'z0'
    roi2.add(data,z)
    print 'ROIdata'
    pp.pprint( roi2.data )
    print 'z'
    pp.pprint( roi2.z )
    print 'category'
    pp.pprint( roi2.category )
    
    print '\n\tnewly create one roi with a list of tupples'
    roi2 = ROIv3(data,z)
    pp.pprint (roi2.data)
    pp.pprint ( roi2.z )
    pp.pprint( roi2.category )
    
    
    print '\n\tShift the roi(s)'
    shift = (-3,-3)
    ROI2mov = [0]
    roi2.shift(shift, ROI2mov)
    #print 'shift ROI %1d x=%2d, y=%3d' % (ROI2mov, shift[0],shift[1])
    pp.pprint (roi2.data)
    pp.pprint ( roi2.z )
    
    print 'creating multiples ROIs for different planes at once'
    roi2 = ROIv3([[(66, 92), (63, 97)],[(97, 94), (101, 91)],[(56, 98), (55, 93)]], ['z0','z-10','z10'])
    pp.pprint ( roi2.data )
    pp.pprint ( roi2.z )
            
    print 'auto sort'
    roi2.sort([])
    pp.pprint ( roi2.data )
    pp.pprint ( roi2.z )

    print 'reference ROI #0', roi2.data[0], roi2.z[0]
    
    print 'create new 3 ROIs for one common plane'
    roi2 = ROIv3([[(66, 92), (63, 97)],[(97, 94), (101, 91)],[(56, 98), (55, 93)]], 'z30')
    pp.pprint ( roi2.data )
    pp.pprint ( roi2.z )
    
    print 'remove 0'
    roi2.remove(0)
    pp.pprint (roi2.data)
    pp.pprint ( roi2.z )
    
    print roi2.autosort()
        





