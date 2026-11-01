"""Run on each target OS with Python and PyInstaller installed."""
import subprocess,sys,os
from pathlib import Path
root=Path(__file__).resolve().parents[1]
subprocess.run([sys.executable,'-m','PyInstaller','--noconfirm','--clean','--onedir','--name','ledgerly-backend','--distpath',str(root/'backend-dist'),'--add-data',str(root/'app')+os.pathsep+'app',str(root/'backend'/'server.py')],cwd=root,check=True)
