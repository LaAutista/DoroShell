"""Private UI fixture: uses the production guard, but all driver calls are fake."""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from display import backend as b

path=Path(os.environ['DOROSHELL_DISPLAY_FIXTURE'])
def read():return json.loads(path.read_text())
def save(value):
    temporary=path.with_suffix(".tmp");temporary.write_text(json.dumps(value));temporary.replace(path)
def query():
    value=read()
    if value.get('unexpected_exit'):os._exit(2)
    if value.get('error'):raise b.DisplayError('Synthetic query failure')
    return value['state']
def execute(args):
    value=read();value.setdefault('calls',[]).append(args)
    if value.get('fail'):
        value['fail']=False;save(value);raise b.DisplayError('Synthetic driver failure')
    if args[0]=='xrandr':value['state']['outputs'][0]['current']=args[-1]
    else:value['state']['vsync']=int(args[-1].split('=')[-1])
    save(value)

# Exercise the production CLI, lock and signal handling with fake driver functions.
transaction=b.Transaction
b.Transaction=lambda request: transaction(request,query,execute)
b.snapshot=query
b.main()
