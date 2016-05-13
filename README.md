Pymagor: a Python based calcium imaging data analysis tool.
=======

![PymagorScreenshot](https://github.com/i-namekawa/Pymagor/blob/images/images/Main-OnlineAnalysisSheet.jpg)
![TrialViewer](https://github.com/i-namekawa/Pymagor/blob/images/images/TrialViewer.jpg)

### "ROI drawing made fun"

Pymagor is a stand alone application that aims to automate many of labor intensive steps of calcium imaging data analysis and provide a user friendly environment for manual ROI drawing. Pymagor can open any multi-page TIFF files (and other supported files) and you can quickly check dF/F image (either as frame average or movie) and the basal fluorescence image for morphology (raw frame or frame average). Pymagor will automatically align multiple image files for each stimulus and field-of-view combination. You can export a PDF summary report and a mat file (or npz) for later analysis.

For more details, check [the wiki documentation] (https://github.com/i-namekawa/Pymagor/wiki).

Supported platforms
------
Pymagor is built upon Python and cross-platform libraries (all 64-bit ready). Alghough the main target platform is Windows 7, Ubuntu and MacOSX (darwin) seem to work ok with some minor problems.
* MS-Windows XP/7/8 (Win10? never tested)
* (Ubuntu 14.04: It can run from source with some GTK warnings)
* (Mac: It runs from source on Darwin with wxPython v3.0 but with some minor wxPython errors. 


Installation
------

### Easy way to test Pymgaor on Windows (no Python required! but 32-bit version only)

* Get the [Windows 32-bit binary installer](https://github.com/i-namekawa/Pymagor/releases) and follow the instructions in the installation wizard. Please __do not__ install in "Program files" folder as Pymagor needs the write access to produce an error log file in the same folder. It comes with an uninstaller. The binary "pymagor.exe" is flagged as LARGEADDRESSAWARE so that it goes over the 2GB memory allocation limit by Windows on 32-bit Python. So, the peformance of this binary is better than running the source on 32-bit python (unless python.exe is flagged too).

The 64-bit binary is possible to build but was too huge (>200 MB, due to numpy/scipy dlls). For 64-bit, run from source.

### Run from source (for development, on Linux/Mac, and to run on 64-bit Python)

1. Install the latest Python 2.7 series. Anaconda 64-bit Python 2.7 is recommended. WinPython is no longer recommended because the latest WinPython2.7 still uses numpy 1.9.3 but the latest tifffile.py needs numpy 1.10.

2. Install all the dependencies (see below for Anaconda example)
  * pillow
  * numpy (1.10 or newer)
  * scipy (v0.12.0 or newer. For anaconda, 0.16.0 recommended due to scipy.io.loadmat bug in anaconda)
  * matplotlib (may need 1.4.* on Mac)
  * xlrd
  * xlwt
  * wx (v3.0.0.0 or newer)
  * yapsy
  * tifffile.py (ver 2016.4.13 or newer. pip will install a slightly older version which may require an older numpy API)

3. Clone the git repogitory (https://github.com/i-namekawa/Pymagor.git or download zip) and run Pymagor2.py. On MaxOS, run with `pythonw` rather than `python`.

#### Conda command to set up Python 2.7.* (64-bit) for Pymagor

* Install Miniconda (or full anaconda) for conda command line tool
* `conda create -n pymagor_env python=2.7 xlrd xlwt matplotlib scipy=0.16.0 pillow wxpython`
* `activate pymagor_env` (win) or `source activate pymagor_env` (Linux/Mac)
* On the pymagor_env activated console, install 2 more libralies as follows:
 * yapsy: `pip install yapsy`
 * tifffile: `pip install tifffile-2016.4.13-cp27-cp27m-win_amd64.whl` (or newer) from Gohlke's site at http://www.lfd.uci.edu/~gohlke/pythonlibs/#vlfd Or, simply copy tifffile.py to `site-packages`. Compilation of tifffile.c is optional but recommended for compressed tif.


Bug report
-------
Please use [Issue tracker](https://github.com/i-namekawa/Pymagor/issues) and paste the content of pymagor.log whenever possible. pymagor.log can be found from Help menu -> Go to User folder.


License
-------

Pymagor is licensed under a 3-clause BSD style license - see the LICENSE.txt file.


Screenshots
------
![QuickPlot](https://github.com/i-namekawa/Pymagor/blob/images/images/QuickPlot.jpg)
![BatchLauncher](https://github.com/i-namekawa/Pymagor/blob/images/images/BatchLauncher.jpg)
