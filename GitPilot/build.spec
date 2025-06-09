# -*- mode: python ; coding: utf-8 -*-
# This is a draft PyInstaller spec file for GitPilot.
# You will likely need to adjust hiddenimports, datas, and other options.

block_cipher = None

a = Analysis(['main.py'],
             pathex=['.'],  # Ensure pathex points to your GitPilot source directory
             binaries=[],
             datas=[],  # Add any data files if needed, e.g. icons: [('path/to/icon.png', '.')]
             hiddenimports=[
                'PyQt5.sip',
                'PyQt5.QtCore',
                'PyQt5.QtGui',
                'PyQt5.QtWidgets'
                # Add other PyQt5 modules if specific ones are reported missing by PyInstaller
             ],
             hookspath=[],
             runtime_hooks=[],
             excludes=[],
             win_no_prefer_redirects=False,
             win_private_assemblies=False,
             cipher=block_cipher,
             noarchive=False)
pyz = PYZ(a.pure, a.zipped_data,
             cipher=block_cipher)
exe = EXE(pyz,
          a.scripts,
          [],
          exclude_binaries=True,
          name='GitPilot', # Name of the executable
          debug=False,
          bootloader_ignore_signals=False,
          strip=False,
          upx=True, # UPX compression can reduce file size, requires UPX installed
          console=False, # False for GUI applications, True for console applications
          icon='path/to/your/icon.ico' # Specify an icon for your application
          )
coll = COLLECT(exe,
               a.binaries,
               a.zipfiles,
               a.datas,
               strip=False,
               upx=True,
               upx_exclude=[],
               name='GitPilot') # Name of the output folder

# To build, run: pyinstaller build.spec
# Ensure PyInstaller is installed: pip install pyinstaller
# You might need to run `pyinstaller main.py --name GitPilot --windowed --add-data ... --hidden-import ...`
# once to generate an initial spec file, then customize it.
