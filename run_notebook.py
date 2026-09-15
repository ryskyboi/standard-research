"""Execute the notebook offline; preserve editable cells and embedded outputs."""
import os
import argparse
from pathlib import Path
os.environ.setdefault('MPLCONFIGDIR',str(Path('/tmp/standard-research-mpl')))
os.environ.setdefault('IPYTHONDIR',str(Path('/tmp/standard-research-ipython')))
os.environ.setdefault('PYDEVD_DISABLE_FILE_VALIDATION','1')
import nbformat
from nbclient import NotebookClient

root=Path(__file__).resolve().parent
parser=argparse.ArgumentParser();parser.add_argument('notebook',nargs='?',default='rational_scenarios.ipynb');args=parser.parse_args()
path=root/args.notebook
nb=nbformat.read(path,as_version=4)
client=NotebookClient(nb,timeout=1200,kernel_name='python3',resources={'metadata':{'path':str(root)}})
client.on_cell_executed=lambda cell_index,**kw:print(f'Completed cell {cell_index+1}/{len(nb.cells)}',flush=True)
client.execute()
nbformat.write(nb,path)
print('Executed notebook saved:',path.name)
