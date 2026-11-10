import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import sys
from pathlib import Path
import tempfile
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QMimeData
from PySide6.QtGui import QImage,QColor
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from clipboard.clipboard import snapshot,History,Entry,ClipboardWindow,MAX_ITEMS,encode_entry,decode_entry
import modules

app=QApplication.instance() or QApplication([])
assert app.platformName() == 'offscreen', 'Refusing test access to a real clipboard'
class ClipboardTests(unittest.TestCase):
    def test_snapshot_sensitive_and_limits(self):
        mime=QMimeData();mime.setText('hello');mime.setHtml('<b>hello</b>')
        entry=snapshot(mime);self.assertEqual(entry.mime().html(),'<b>hello</b>')
        mime.setData('DELETE',b'danger'); self.assertNotIn('DELETE',snapshot(mime).formats)
        mime.setData('x-kde-passwordManagerHint',b'secret');self.assertIsNone(snapshot(mime))
        mime=QMimeData();mime.setText('x'*262145);self.assertIsNone(snapshot(mime))
        image=QImage(20,10,QImage.Format.Format_ARGB32);image.fill(QColor('pink'))
        mime=QMimeData();mime.setImageData(image)
        self.assertEqual(snapshot(mime).image,image)
        mime.setImageData(QImage(4000,3000,QImage.Format.Format_ARGB32));self.assertIsNone(snapshot(mime))

    def test_historical_file_cut_becomes_copy(self):
        entry=Entry({'text/uri-list':b'file:///fixture', 'application/x-kde-cutselection':b'1', 'x-special/gnome-copied-files':b'cut\nfile:///fixture'},'file:///fixture')
        self.assertEqual(bytes(entry.mime().data('application/x-kde-cutselection')),b'1')
        self.assertEqual(bytes(entry.mime(replay=True).data('application/x-kde-cutselection')),b'0')
        self.assertTrue(bytes(entry.mime(replay=True).data('x-special/gnome-copied-files')).startswith(b'copy\n'))

    def test_capture_wire_roundtrip_and_invalid(self):
        mime=QMimeData();mime.setText('fixture');mime.setHtml('<i>fixture</i>')
        entry=snapshot(mime);self.assertEqual(decode_entry(encode_entry(entry)).identity,entry.identity)
        self.assertIsNone(decode_entry(b'broken'));self.assertIsNone(decode_entry(b'null'))

    def test_history_bound_dedup_and_clear_does_not_copy(self):
        history=History()
        for i in range(60): history.add(Entry({'text/plain':str(i).encode()},str(i)))
        self.assertEqual(len(history.entries),MAX_ITEMS)
        history.add(history.entries[20]);self.assertEqual(len(history.entries),MAX_ITEMS)
        window=ClipboardWindow(app)
        window.history=history;window.refresh();window.search.setText('59')
        self.assertEqual(window.items.count(),1)
        # Only offscreen test clipboard, never personal clipboard.
        window.writing=True;app.clipboard().setText('unchanged');window.writing=False
        window.clear_history();self.assertEqual(app.clipboard().text(),'unchanged')
        window.deleteLater();app.processEvents()

    def test_installer_repeat_exact_rollback_and_fixed_button(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);p=home/'.config/doroshell/panel.conf';p.parent.mkdir(parents=True)
            before='[panel1]\nplugins=start, tasks, notifier, clock\n[notifier]\ntype=statusnotifier\n'
            p.write_text(before)
            modules.run(home,'clipboard',apply=True)
            self.assertIn('tasks, doroClipboard, notifier',p.read_text())
            self.assertTrue((home/'.local/bin/doroshell-clipboard').exists())
            modules.run(home,'clipboard',apply=True)
            modules.run(home,'clipboard',rollback=True)
            self.assertEqual(p.read_text(),before)
            self.assertFalse((home/'.local/bin/doroshell-clipboard').exists())

    def test_installer_conflict_refusal(self):
        with tempfile.TemporaryDirectory() as tmp:
            home=Path(tmp);p=home/'.config/doroshell/panel.conf';p.parent.mkdir(parents=True)
            p.write_text('[panel1]\nplugins=tasks, notifier\n[notifier]\ntype=statusnotifier\n')
            modules.run(home,'clipboard',apply=True)
            p.write_text(p.read_text().replace('alignment=Right','alignment=Left'))
            with self.assertRaises(RuntimeError): modules.run(home,'clipboard',rollback=True)
