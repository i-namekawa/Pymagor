import csv, os, time
from opentif import *


def _get_fullpaths(data_folder, include_subfolders=False):
    ' why not glob?????? sure...'
    files = []
    for f in os.listdir(data_folder):
        fullpath = os.path.join(data_folder,f)
        if f.endswith(('tif','ior')):
            files.append(fullpath)
        elif os.path.isdir(fullpath):
            if include_subfolders:
                files += _get_fullpaths(fullpath)
    
    return files


def _produce_list(data_folder, include_subfolders):
    
    buf = []
    filelist = _get_fullpaths(data_folder, include_subfolders)
    for f in filelist:
        info = get_tags(f)
        
        if 'version' in info:
            if float(info['version']) >= 3.8:
                scanXY = info['scanAngleMultiplierFast'], info['scanAngleMultiplierSlow']
            else:
                scanXY = info['scanAmplitudeX'], info['scanAmplitudeY']
        else:
            scanXY = info['scanAmplitudeX'], info['scanAmplitudeY']
        
        
        buf.append([
            os.path.basename(f),                                            # fname
            '',                                                             # field-of-view
            '',                                                             # odor
            '',                                                             # repeat
            '',                                                             # memo
            info['zoomFactor'],                                             # zzom
            '%sx%s' % (scanXY),                                             # scanAmplitudes
            '_'.join(info['recorded_ch']),                                  # recorded_ch
            info['frameRate'],                                              # frameRate
            time.strftime('%m/%d/%Y %X', time.gmtime(os.path.getmtime(f))), # ctime
            os.path.dirname(f)                                              # data_path
            ])
    
    return buf


def create_csv(csvname, data_folder, include_subfolders=False, ver=2):
    '''
    csvname can be a full path or just a file name (os.path.join will take care of it)
    data_folder is the parent folder
    include_subfolders: if true, all the subfolders will be recursively checked and included.
    '''
    
    header = ['File', 'Field-of-View', 'Stimulus', 'Repeat', 'Memo', 
                'Zoom', 'ScanAmplitudes','Channels','Sampling rate', 
                'Time created', 'Folder path']
    # ensure the first line has the same number of col as header
    line01  = [[] for a in header] 
    line01[0] = data_folder
    line01[1] = str(ver)
    
    buf = []
    buf.append(line01)
    buf.append(header)
    buf += _produce_list(data_folder, include_subfolders)
    
    if csvname.endswith('xls'): # force csv for this operation.
        csvname = csvname[:-4] + '.csv'
    
    with open(os.path.join(data_folder, csvname),'wb') as f:
        csvWriter = csv.writer(f)
        csvWriter.writerows(buf)


if __name__ == '__main__':
    csvname = 'test.csv'
    data_folder = r'.'
    include_subfolders = False
    create_csv(csvname, data_folder, include_subfolders)
