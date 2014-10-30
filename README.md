Pymagor
=======

![PymagorScreenshot](https://github.com/i-namekawa/Pymagor/blob/images/images/Main-OnlineAnalysisSheet.jpg)

Pymagor: a Python based ROI definition tool for calcium imaging data

Pymagor is a tool (windows binary runs without python installed) to draw region-of-interest manually on the multi-page TIFF and other supported image files and quickly get a dF/F trace. With user provided meta-data, Pymagor will automatically align multiple image files for each stimulus condition and field-of-view combinations. You can export a PDF summary report and a mat file (or npz) for later analysis.

Supported platforms
------
Pymagor is built upon Python and cross-platform libraries, meaning that it will be relatively easy to support Linux and Mac.
However, at moment, only Windows XP/7 is supported.
* MS-Windows 7, XP (win8 seems fine too. [windows93](http://www.windows93.net/) not supported.)
* Ubuntu 14.04 (Working ok but with some GTK errors)
* (Mac? I do not have one to test)


Installation
------

### Recommended way (no Python required!)

* Get the [binary installer](https://github.com/i-namekawa/Pymagor/releases) and follow the instructions in the installation wizard. You **do not** need Python to run Pymagor.

### Hard way (for dev)

1. Install the latest Python 2.7 series. Python(x,y) recommended on Windows.
2. Install all the Dependencies. Python(x,y) covers most of these.
  * pillow
  * numpy
  * scipy
  * matplotlib
  * xlrd
  * xlwt
  * wx
  * win32process (MS-Windows only)
  * yapsy
  * tifffile
3. Clone the git repogitory (https://github.com/i-namekawa/Pymagor.git) and you are ready to go. 

Note: Please **don't** attempt to `python setup.py install`. `setup.py` is for py2exe packaging only. Pymagor is a stand-alone program not a module. Just run Pymagor2.py. To build an executable using py2exe, you will need git.exe in the system path.


License
-------

Pymagor is licensed under a 3-clause BSD style license - see the LICENSE.txt file.


Screenshots
------
![TrialViewer](https://github.com/i-namekawa/Pymagor/blob/images/images/TrialViewer.jpg)
![QuickPlot](https://github.com/i-namekawa/Pymagor/blob/images/images/QuickPlot.jpg)
![BatchLauncher](https://github.com/i-namekawa/Pymagor/blob/images/images/BatchLauncher.jpg)





