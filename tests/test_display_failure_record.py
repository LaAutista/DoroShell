"""Compile the real native redactor; write only within disposable state homes."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]

class FailureRecordTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build = tempfile.TemporaryDirectory(prefix='display-record-test-')
        root = Path(cls.build.name)
        source = root/'record.cpp'
        source.write_text('''#include "dorodisplaycontrols.h"
#include <QCoreApplication>
int main(int argc,char **argv) {
 QCoreApplication app(argc,argv);
 QJsonArray fields;
 for(int i=0;i<10000;++i) fields.append(QJsonObject{{"field","EDID PRIVATE-SERIAL"},{"output","PRIVATE-MONITOR"},{"raw","PRIVATE-DRIVER-OUTPUT"}});
 fields.append(QJsonObject{{"field","brightness"},{"output","PRIVATE-MONITOR"}});
 fields.append(QJsonObject{{"field","brightness"}});
 if(QString::fromUtf8(argv[1])=="limit" || QString::fromUtf8(argv[1])=="events") {
  for(const auto &field:QStringList{"framebuffer geometry","output disappeared","output added","output enumeration changed","connection status changed","current mode mismatch","CRTC assignment","advertised mode timings/flags","NVIDIA OpenGL VSync","connection/geometry/rotation","mode timings/flags","gamma","transform","border","screen index","color transform","color matrix","other protected properties","protected layout fingerprint","screen geometry"})
   fields.append(QJsonObject{{"field",field}});
 }
 QJsonArray events;
 if(QString::fromUtf8(argv[1])=="events") {
  events.append(QJsonObject{{"phase","PRIVATE"},{"reason","SECRET"},{"fields",QJsonArray{"PRIVATE"}}});
  for(int i=0;i<100;++i) events.append(QJsonObject{{"phase",i==0?"apply_verification":"recovery"},
   {"reason",i==0?"state_mismatch":"command_timeout"},
   {"fields",QJsonArray{"PRIVATE","BorderDimensions","link-status","Colorspace","Dithering","DitheringMode","DitheringDepth","gamma","brightness"}},
   {"raw","PRIVATE DRIVER OUTPUT"},{"output","PRIVATE-MONITOR"}});
 }
 bool ok=DoroDisplayFailure::record(QString::fromUtf8(argv[1]),fields,events);
 return ok?0:3;
}''')
        cls.binary=root/'record'
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','--libs','Qt6Widgets'],text=True))
        subprocess.run(['c++','-std=c++17','-fPIC',str(source),'-I'+str(ROOT/'display'),*flags,'-o',str(cls.binary)],check=True)
    @classmethod
    def tearDownClass(cls): cls.build.cleanup()
    def call(self, state, reason='guard_error'):
        return subprocess.run([str(self.binary),reason],env=dict(os.environ,XDG_STATE_HOME=str(state)),capture_output=True).returncode
    def test_bounded_redacted_replacement(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);record=root/'doroshell-display-errors/last-failure.json'
            for reason in ('guard_error','abnormal_exit','guard_start_failed','PRIVATE RAW ERROR'):
                self.assertEqual(self.call(root,reason),0)
                data=record.read_bytes();self.assertLessEqual(len(data),2048)
                self.assertNotIn(b'PRIVATE',data)
                self.assertEqual(json.loads(data),dict(schema=2,diagnostics=[],reason=reason if reason!='PRIVATE RAW ERROR' else 'guard_error',recovery='unverified',fields=['brightness']))
                self.assertEqual(record.stat().st_mode&0o777,0o600)
                self.assertEqual(record.parent.stat().st_mode&0o777,0o700)
            self.assertEqual([p.name for p in record.parent.iterdir()],['last-failure.json'])
    def test_unavailable_storage_fails_safely(self):
        with tempfile.TemporaryDirectory() as tmp:
            state=Path(tmp)/'file';state.write_text('untouched')
            self.assertEqual(self.call(state),3)
            self.assertEqual(state.read_text(),'untouched')
    def test_symlink_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);real=root/'real';real.mkdir();link=root/'link';link.symlink_to(real,target_is_directory=True)
            self.assertEqual(self.call(link),3);self.assertEqual(list(real.iterdir()),[])
    def test_nonprivate_directory_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)/'doroshell-display-errors';folder.mkdir();folder.chmod(0o755)
            self.assertEqual(self.call(Path(tmp)),3);self.assertEqual(list(folder.iterdir()),[])

    def test_field_count_capped(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.call(Path(tmp),'limit'),0)
            record=Path(tmp)/'doroshell-display-errors/last-failure.json'
            self.assertEqual(len(json.loads(record.read_text())['fields']),16)
            self.assertLessEqual(record.stat().st_size,2048)

    def test_target_symlink_refused(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);folder=root/'doroshell-display-errors';folder.mkdir(mode=0o700)
            target=root/'untouched';target.write_text('personal fixture')
            (folder/'last-failure.json').symlink_to(target)
            self.assertEqual(self.call(root),3)
            self.assertEqual(target.read_text(),'personal fixture')

    def test_phase_records_are_allowlisted_and_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.call(Path(tmp),'events'),0)
            data=(Path(tmp)/'doroshell-display-errors/last-failure.json').read_bytes()
            self.assertLessEqual(len(data),2048);self.assertNotIn(b'PRIVATE',data);self.assertNotIn(b'SECRET',data)
            record=json.loads(data);events=record['diagnostics']
            self.assertEqual(len(events),3)
            self.assertEqual([(e['phase'],e['reason']) for e in events[:2]],[('apply_verification','state_mismatch'),('recovery','command_timeout')])
            for event in events:
                self.assertEqual(set(event),{'phase','reason','fields'})
                self.assertEqual(event['fields'],['BorderDimensions','link-status','Colorspace','Dithering','DitheringMode','DitheringDepth'])

    def test_header_supports_native_cast_restrictions(self):
        root=Path(self.build.name)
        source=root/'native-casts.cpp'
        source.write_text('#include "dorodisplaycontrols.h"\n')
        flags=shlex.split(subprocess.check_output(['pkg-config','--cflags','Qt6Widgets'],text=True))
        subprocess.run(['c++','-std=c++20','-fPIC','-fsyntax-only',
                        '-DQT_NO_CAST_FROM_ASCII','-DQT_NO_CAST_FROM_BYTEARRAY','-DQT_NO_CAST_TO_ASCII',
                        '-DQT_NO_KEYWORDS','-DQT_USE_QSTRINGBUILDER',
                        str(source),'-I'+str(ROOT/'display'),*flags],check=True)
