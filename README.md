Pymagor: a Python based calcium imaging data analysis tool.
=======

![PymagorScreenshot](https://github.com/i-namekawa/Pymagor/blob/images/images/Main-OnlineAnalysisSheet.jpg)

### "ROI drawing made fun"

Pymagor is a stand alone application that aims to automate many of labor intensive steps of calcium imaging data analysis and provide a user friendly environment for manual ROI drawing. Pymagor can open any multi-page TIFF files (and other supported files) and you can quickly check dF/F image (either as frame average or movie) and the basal fluorescence image for morphology (raw frame or frame average). Pymagor will automatically align multiple image files for each stimulus and field-of-view combination. You can export a PDF summary report and a mat file (or npz) for later analysis.

For more details, check [the wiki documentation] (https://github.com/i-namekawa/Pymagor/wiki).

Supported platforms
------
Pymagor is built upon Python and cross-platform libraries, meaning that it will be relatively easy to support Linux and Mac.
However, only Windows 7 will be supported. All libraries used in Pymagor are ready for 64-bit (except on Mac until I upgrade to wxPython3.0).
* MS-Windows XP/7/8 ([Windows93](http://www.windows93.net/) not supported)
* (Ubuntu 14.04: It can run from source with some GTK warnings)
* (Mac: It manages to run from source on Darwin but it needs some more GUI element adjustments. wxPython2.8 on Mac requires 32-bit Python. So, it's better to install a separate Python2.7 32-bit and install all the dependencies there.)


Installation
------

### Recommended way for Windows (no Python required!)

* Get the [Windows 32-bit binary installer](https://github.com/i-namekawa/Pymagor/releases) and follow the instructions in the installation wizard. You **do not** need Python to run Pymagor. It comes with an uninstaller. The binary "pymagor.exe" is flagged as LARGEADDRESSAWARE so that it goes over the 2GB memory allocation limit by Windows up to 4GB on 32-bit Python. So, the peformance of this binary is better than running the source on 32-bit python. (unless python.exe is flagged too)

The 64-bit binary is possible to build but was too huge (>200 MB, due to numpy/scipy dlls). So, if you need 64-bit, you should run from source.

### Hard way (for development, on Linux/Mac, and to run on 64-bit Python)

1. Install the latest Python 2.7 series. For Windows, Python(x,y) for 32-bit and WinPython for 64-bit are recommended.
2. Install all the Dependencies. Python(x,y) covers most of these.
  * pillow
  * numpy
  * scipy (v0.12.0 or greater)
  * matplotlib
  * xlrd
  * xlwt
  * wx (v2.8.12.1)
  * win32process (MS-Windows only)
  * yapsy
  * tifffile
3. Clone the git repogitory (https://github.com/i-namekawa/Pymagor.git) and run Pymagor2.py

Bug report
-------
Please use [Issue tracker](https://github.com/i-namekawa/Pymagor/issues) and paste the content of pymagor.log whenever possible. pymagor.log can be found from Help menu -> Go to User folder.


License
-------

Pymagor is licensed under a 3-clause BSD style license - see the LICENSE.txt file.


Screenshots
------
![TrialViewer](https://github.com/i-namekawa/Pymagor/blob/images/images/TrialViewer.jpg)
![QuickPlot](https://github.com/i-namekawa/Pymagor/blob/images/images/QuickPlot.jpg)
![BatchLauncher](https://github.com/i-namekawa/Pymagor/blob/images/images/BatchLauncher.jpg)
