
# ======================================================== #
# File automagically generated by GUI2Exe version 0.5.3
# Copyright: (c) 2007-2012 Andrea Gavana
# ======================================================== #

# Let's start with some default (for me) imports...

from distutils.core import setup
from py2exe.build_exe import py2exe

import glob
import os
import zlib
import shutil



# /* Added by Iori Namekawa
import matplotlib # for data_files
from getver import *
create_infofile()
import opentif
# */




# Remove the build folder
shutil.rmtree("build", ignore_errors=True)


class Target(object):
    """ A simple class that holds information on our executable file. """
    def __init__(self, **kw):
        """ Default class constructor. Update as you need. """
        self.__dict__.update(kw)
        
# Ok, let's explain why I am doing that.
# Often, data_files, excludes and dll_excludes (but also resources)
# can be very long list of things, and this will clutter too much
# the setup call at the end of this file. So, I put all the big lists
# here and I wrap them using the textwrap module.

data_files = [
  ('.', ['LICENSE.txt', 'README.md']),
  ('resources', ['resources/ffmpeg.exe',
                 'resources/version.info',
                 'resources/fish2.ico'  ]),
  ('resources/Baumgartner', ['resources/Baumgartner/button_pause_24.ico',
                             'resources/Baumgartner/button_play_24.ico',
                             'resources/Baumgartner/button_previous_24.ico',
                             'resources/Baumgartner/Button_Record_24.ico',
                             'resources/Baumgartner/chart_24.ico',
                             'resources/Baumgartner/chart_24_selected.bmp',
                             'resources/Baumgartner/pencil_24.ico',
                             'resources/Baumgartner/zoomin_24.ico',
                             'resources/Baumgartner/zoomin_disabled_24.ico',
                             'resources/Baumgartner/zoomout_24.ico',
                             'resources/Baumgartner/zoomout_disabled_24.ico']),
  ('resources/David_Hopkins',  ['resources/David_Hopkins/arrow_move_24.ico']),
  ('resources/gentleface.com', ['resources/gentleface.com/cursor_drag_hand_icon.ico']),
  ('resources/Nayak',       ['resources/Nayak/eraser.ico']),
  ('resources/Tango',       ['resources/Tango/save.ico',
                             'resources/Tango/saving.ico']),
    ]

for data in matplotlib.get_py2exe_datafiles():
    data_files.append( data )


includes = ['matplotlib.backends.backend_qt4agg', 
            '_tifffile', 
            'tifffile', 
            'scipy.io.matlab.streams', 
            'scipy.special._ufuncs_cxx',
            'opentif', 
            ]
excludes = ['_gtkagg', '_ssl', '_tkagg', 'bsddb', 'curses', 'doctest',
            'email', 'pdb', 'pyreadline', 'pywin.debugger',
            'pywin.debugger.dbgcon', 'pywin.dialogs', 'tcl',
            'Tkconstants', 'Tkinter']
packages = ['xml']
dll_excludes = ['libgdk-win32-2.0-0.dll', 'libgobject-2.0-0.dll', 'tcl84.dll',
                'tk84.dll', 'w9xpopen.exe']
icon_resources = [(1, 'resources/fish2.ico')]
bitmap_resources = []

manifest = '''
<?xml version='1.0' encoding='UTF-8' standalone='yes'?>
<assembly xmlns='urn:schemas-microsoft-com:asm.v1' manifestVersion='1.0'>
  <trustInfo xmlns="urn:schemas-microsoft-com:asm.v3">
    <security>
      <requestedPrivileges>
        <requestedExecutionLevel level='asInvoker' uiAccess='false' />
      </requestedPrivileges>
    </security>
  </trustInfo>
  <dependency>
    <dependentAssembly>
      <assemblyIdentity
     type='win32'
     name='Microsoft.VC90.CRT'
     version='9.0.21022.8'
     processorArchitecture='*'
     publicKeyToken='1fc8b3b9a1e18e3b' />
    </dependentAssembly>
  </dependency>
  <dependency>
    <dependentAssembly>
      <assemblyIdentity
         type="win32"
         name="Microsoft.Windows.Common-Controls"
         version="6.0.0.0"
         processorArchitecture="*"
         publicKeyToken="6595b64144ccf1df"
         language="*" />
    </dependentAssembly>
  </dependency>
</assembly>
'''
other_resources = [(24, 1, manifest)]

# This is a place where the user custom code may go. You can do almost
# whatever you want, even modify the data_files, includes and friends
# here as long as they have the same variable name that the setup call
# below is expecting.

# No custom code added


# Ok, now we are going to build our target class.
# I chose this building strategy as it works perfectly for me :-D

GUI2Exe_Target_1 = Target(
    # what to build
    script = "Pymagor.py",
    icon_resources = icon_resources,
    bitmap_resources = bitmap_resources,
    other_resources = other_resources,
    dest_base = "Pymagor",    
    version = "2.7",
    #company_name = "",
    copyright = "BSD-new",
    name = "Pymagor",
    )

dist_dir = os.path.join( 'C:/temp/pymagor', "rev%03d" % int(getver()) )

# No custom class for UPX compression or Inno Setup script

# That's serious now: we have all (or almost all) the options py2exe
# supports. I put them all even if some of them are usually defaulted
# and not used. Some of them I didn't even know about.

setup(

    # No UPX or Inno Setup

    data_files = data_files,

    options = {"py2exe": {"compressed": 2, 
                          "optimize": 2,
                          "includes": includes,
                          "excludes": excludes,
                          "packages": packages,
                          "dll_excludes": dll_excludes,
                          "bundle_files": 2,
                          "dist_dir": dist_dir[:40],
                          "xref": False,
                          "skip_archive": False,
                          "ascii": False,
                          #"custom_boot_script": 'custom-boot-script.py',  # instead boot_common.py modified directly...
                          "custom_boot_script": '',
                         }
              },

    zipfile = None,
    console = [],
    windows = [GUI2Exe_Target_1],
    service = [],
    com_server = [],
    ctypes_com_server = []
    )

# This is a place where any post-compile code may go.
# You can add as much code as you want, which can be used, for example,
# to clean up your folders or to do some particular post-compilation
# actions.

# No post-compilation code added


# And we are done. That's a setup script :-D


## Note by Iori Namekawa
## actual binary for distribution will be UPX compressed and then 
## IMAGE_FILE_LARGE_ADDRESS_AWARE flag will be checked.





