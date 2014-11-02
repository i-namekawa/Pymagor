Pymagor: a Python based calcium imaging data analysis tool.
=======

![PymagorScreenshot](https://github.com/i-namekawa/Pymagor/blob/images/images/Main-OnlineAnalysisSheet.jpg)

### "ROI drawing made fun"

Pymagor is a stand alone application that aims to automate many of labor intensive steps of calcium imaging data analysis and provide a user friendly environment for manual ROI drawing. Pymagor can open any multi-page TIFF files (and other supported files) and you can quickly check dF/F image (either as frame average or movie) and the basal fluorescence image for morphology (raw frame or frame average). Pymagor will automatically align multiple image files for each stimulus and field-of-view combinations. You can export a PDF summary report and a mat file (or npz) for later analysis.

For more detail, check [the wiki documentation] (https://github.com/i-namekawa/Pymagor/wiki).

Supported platforms
------
Pymagor is built upon Python and cross-platform libraries, meaning that it will be relatively easy to support Linux and Mac.
However, at the moment, Windows 7 is recommended.
* MS-Windows XP/7/8 ([Windows93](http://www.windows93.net/) not supported)
* (Ubuntu 14.04: It can run from source with some GTK warnings)
* (Mac: It manages to run from source on Darwin but it needs some more GUI element adjustments. wxpython2.8 requires 32-bit Python. So, it's better to install a separate Python2.7 32-bit and install all the dependencies there.)


Installation
------

### Recommended way for Windows (no Python required!)

* Get the [Windows binary installer](https://github.com/i-namekawa/Pymagor/releases) and follow the instructions in the installation wizard. You **do not** need Python to run Pymagor.

### Hard way (for dev and Linux/Mac)

1. Install the latest Python 2.7 series. Python(x,y) recommended on Windows.
2. Install all the Dependencies. Python(x,y) covers most of these.
  * pillow
  * numpy
  * scipy (0.12.0 or greater)
  * matplotlib
  * xlrd
  * xlwt
  * wx (2.8 series)
  * win32process (MS-Windows only)
  * yapsy
  * tifffile
3. Clone the git repogitory (https://github.com/i-namekawa/Pymagor.git) and you are ready to go. 

Note: Pymagor is a stand-alone program not a module. Just run Pymagor2.py.


License
-------

Pymagor is licensed under a 3-clause BSD style license - see the LICENSE.txt file.


Screenshots
------
![TrialViewer](https://github.com/i-namekawa/Pymagor/blob/images/images/TrialViewer.jpg)
![QuickPlot](https://github.com/i-namekawa/Pymagor/blob/images/images/QuickPlot.jpg)
![BatchLauncher](https://github.com/i-namekawa/Pymagor/blob/images/images/BatchLauncher.jpg)





