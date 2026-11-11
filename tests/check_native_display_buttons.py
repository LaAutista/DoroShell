"""Real native Apply/OK under private X11; production guard with fake CLI drivers."""
import argparse,configparser,json,os,shlex,shutil,subprocess,sys,tempfile,time
from pathlib import Path
from x11_isolation import isolated
ROOT=Path(__file__).resolve().parents[1]
DRIVER='''#!/usr/bin/python3
import json,os,sys
from pathlib import Path
p=Path(os.environ['DORO_NATIVE_FIXTURE']);d=json.loads(p.read_text());args=sys.argv[1:]
if Path(sys.argv[0]).name=='xrandr':
 if args==['--current','--verbose']:
  if d.get('slow_query'):
   import time;time.sleep(1)
  mode=d['mode'];print('Screen 0: minimum 8 x 8, current 2560 x 1440, maximum 32767 x 32767')
  print(f'DP-0 connected primary 2560x1440+0+0 ({mode}) normal (normal left inverted right x axis y axis) 500mm x 300mm\\n\\tCRTC: 0')
  print('\\tBrightness: '+('0.8' if d.get('external') and mode=='0x12' else '1.0'))
  for ident,rate in [('0x11','479.99'),('0x12','59.95')]:
   print(f'  2560x1440 ({ident}) 148.500MHz +HSync +VSync'+(' *current' if ident==mode else '')+(' +preferred' if ident=='0x12' else ''))
   print(f'        h: width 2560 start 2600 end 2700 total 2800 skew 0 clock 67.50KHz\\n        v: height 1440 start 1444 end 1449 total 1500 clock {rate}Hz')
 elif len(args)==4 and args[:3]==['--output','DP-0','--mode'] and args[3] in ('0x11','0x12'):
  if d.get('fail'):
   print('Synthetic driver failure',file=sys.stderr);sys.exit(1)
  d['mode']=args[3];d['calls'].append(args)
  tmp=p.with_suffix('.tmp');tmp.write_text(json.dumps(d));tmp.replace(p)
 else:raise RuntimeError('Unexpected fake RandR command')
else:
 if args==['-t','-q','[screen:0]/SyncToVBlank']:print('1')
 else:raise RuntimeError('Unexpected fake NVIDIA command')
'''
def worker(binary,hook):
 assert os.environ['DISPLAY']==os.environ['DOROSHELL_TEST_DISPLAY'] and os.environ['DISPLAY']!=':0'
 home=Path.home();bin=home/'fake-bin';bin.mkdir()
 for name in ('xrandr','nvidia-settings'):
  p=bin/name;p.write_text(DRIVER);p.chmod(0o755)
 fixture=home/'fixture.json';result=home/'result'
 for scenario in os.environ.get('DORO_NATIVE_SCENARIOS','unchanged,apply-revert,apply-keep,ok-revert,ok-keep,timeout,error,external,close,query-close').split(','):
  shutil.rmtree(home/'.config/pcmanfm-qt',ignore_errors=True)
  fixture.write_text(json.dumps({'mode':'0x11','calls':[],'fail':scenario=='error','external':scenario=='external','slow_query':scenario=='query-close'}));result.unlink(missing_ok=True)
  env=dict(os.environ,PATH=str(bin)+':'+os.environ['PATH'],LD_PRELOAD=str(hook),DORO_NATIVE_FIXTURE=str(fixture),DORO_NATIVE_SCENARIO=scenario,DORO_NATIVE_RESULT=str(result))
  proc=subprocess.run([str(binary),'--desktop-pref','--profile='+scenario],env=env,capture_output=True,text=True,timeout=30)
  if proc.returncode:raise AssertionError(scenario+f' exit={proc.returncode}: '+proc.stderr)
  if scenario=='close':
   deadline=time.monotonic()+6
   while json.loads(fixture.read_text())['mode']!='0x11' and time.monotonic()<deadline:time.sleep(.05)
   assert json.loads(fixture.read_text())['mode']=='0x11','close must restore original'
  else:assert result.read_text()=='PASS',scenario+': '+proc.stderr
  if scenario=='query-close':
   assert result.read_text()=='PASS' and not json.loads(fixture.read_text())['calls']
   print('PASS actual native dialog:',scenario,flush=True);continue
  settings=list((home/'.config/pcmanfm-qt').rglob('settings.conf'))
  assert len(settings)==1, 'one isolated settings profile'
  config=configparser.ConfigParser();config.read(settings[0])
  assert config.getboolean('Desktop','NoItemTooltip') == (scenario in ('unchanged','apply-revert','apply-keep','ok-keep')), 'ordinary preference Apply/OK/Cancel semantics'
  print('PASS actual native dialog:',scenario,flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--run',action='store_true');p.add_argument('--worker',action='store_true');p.add_argument('--xvfb',type=Path);p.add_argument('--binary',type=Path,required=True);p.add_argument('--hook',type=Path);a=p.parse_args()
 if a.worker:worker(a.binary.resolve(),a.hook.resolve())
 elif a.run and a.xvfb:
  with tempfile.TemporaryDirectory(prefix='native-display-hook-') as tmp:
   hook=Path(tmp)/'driver.so';flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Widgets','Qt6Test'],text=True))
   subprocess.run(['c++','-shared','-fPIC','-std=c++17',str(ROOT/'tests/native_display_buttons.cpp'),*flags,'-o',str(hook)],check=True)
   isolated(a.xvfb.resolve(),[sys.executable,__file__,'--worker','--binary',str(a.binary.resolve()),'--hook',str(hook)])
 else:p.error('Use --run --xvfb PATH --binary PRIVATE_CANDIDATE')
