"""Offscreen lifecycle tests with real QProcess and a controlled capture child.

The child emulates ScreenGrab output, not its UI or X11 capture. These tests
never connect to the user's display, singleton socket, or real clipboard.
"""
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

os.environ['QT_QPA_PLATFORM'] = 'offscreen'
from PySide6.QtCore import QMimeData, QProcess, QSettings
from PySide6.QtTest import QSignalSpy
from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QApplication

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('screenshot_runtime', ROOT / 'runtime/screenshot.py')
shot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(shot)

CHILD = r"""
import os
from pathlib import Path
import sys
import time
from PySide6.QtGui import QColor, QImage
root = Path(os.environ['XDG_CONFIG_HOME']) / 'captures'
mode = sys.argv[1]
if mode == 'slow':
    time.sleep(0.15)
if mode == 'partial':
    (root / 'capture.png').write_bytes(b'incomplete image')
elif mode not in ('cancel', 'error'):
    im = QImage(37, 23, QImage.Format.Format_ARGB32)
    im.fill(QColor('blue' if mode == 'blue' else 'red'))
    assert im.save(str(root / 'capture.png'))
    if mode == 'multiple':
        assert im.save(str(root / 'other.png'))
if mode == 'error':
    sys.exit(2)
if mode == 'crash':
    import signal
    os.kill(os.getpid(), signal.SIGKILL)
"""


class ScreenshotLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        if cls.app.platformName() != 'offscreen':
            raise unittest.SkipTest('Refusing to touch a real display clipboard')

    def setUp(self):
        self.capture = shot.Capture(self.app)
        self.app.clipboard().setText('clipboard before capture')
        self.directory = tempfile.TemporaryDirectory(prefix='doroshell-test-child-')
        self.child = Path(self.directory.name) / 'capture.py'
        self.child.write_text(CHILD)
        self.started = []

    def tearDown(self):
        if self.capture.process is not None:
            self.capture.process.kill()
            self.capture.process.waitForFinished(2000)
            self.capture.cleanup()
        self.directory.cleanup()

    def start(self, mode):
        child = self.child
        started = self.started
        class ChildProcess(QProcess):
            def start(self, program, arguments):
                started.append((program, arguments))
                super().start(sys.executable, [str(child), mode])
        with patch.object(shot, 'QProcess', ChildProcess):
            self.capture.start()
        return Path(self.capture.temp.name)

    def finish(self):
        deadline = time.monotonic() + 5
        while self.capture.process is not None and time.monotonic() < deadline:
            self.app.processEvents()
            time.sleep(0.005)
        self.assertIsNone(self.capture.process, 'Capture child did not finish')
        self.assertIsNone(self.capture.temp)

    def test_success_cancel_success_keeps_last_complete_image(self):
        first = self.start('red')
        self.finish()
        self.assertFalse(first.exists())
        self.assertEqual(self.app.clipboard().image().size(), QImage(37, 23, QImage.Format.Format_ARGB32).size())
        self.assertEqual(self.app.clipboard().image().pixelColor(0, 0), QColor('red'))
        cancelled = self.start('cancel')
        self.assertNotEqual(first, cancelled)
        self.finish()
        self.assertFalse(cancelled.exists())
        self.assertEqual(self.app.clipboard().image().pixelColor(0, 0), QColor('red'))
        self.start('blue')
        self.finish()
        self.assertEqual(self.app.clipboard().image().pixelColor(0, 0), QColor('blue'))

    def test_cancel_partial_failure_crash_and_ambiguous_output_preserve_text(self):
        for mode in ('cancel', 'partial', 'error', 'crash', 'multiple'):
            with self.subTest(mode=mode):
                temporary = self.start(mode)
                self.finish()
                self.assertFalse(temporary.exists())
                self.assertEqual(self.app.clipboard().text(), 'clipboard before capture')

    def test_repeated_start_does_not_stack_capture(self):
        temporary = self.start('slow')
        active = self.capture.process
        self.capture.start()
        self.assertIs(self.capture.process, active)
        self.assertEqual(len(self.started), 1)
        self.assertEqual(self.started[0], ('screengrab', ['--region', '--no-win']))
        self.finish()
        self.assertFalse(temporary.exists())

    def test_failed_start_preserves_clipboard_and_cleans_up(self):
        class MissingProcess(QProcess):
            def start(self, program, arguments):
                super().start('/definitely-not-an-installed-doroshell-capture', arguments)
        with patch.object(shot, 'QProcess', MissingProcess), patch.object(shot.QMessageBox, 'warning') as warning:
            self.capture.start()
            temporary = Path(self.capture.temp.name)
            self.finish()
            warning.assert_called_once()
        self.assertFalse(temporary.exists())
        self.assertEqual(self.app.clipboard().text(), 'clipboard before capture')

    def test_cancel_and_invalid_output_do_not_republish_rich_clipboard(self):
        mime = QMimeData()
        mime.setText('keep this text')
        mime.setHtml('<b>keep this text</b>')
        self.app.clipboard().setMimeData(mime)
        changed = QSignalSpy(self.app.clipboard().dataChanged)
        for mode in ('cancel', 'partial', 'multiple', 'error'):
            with self.subTest(mode=mode):
                self.start(mode)
                self.finish()
                self.assertEqual(changed.count(), 0)
                self.assertEqual(self.app.clipboard().text(), 'keep this text')
                self.assertEqual(self.app.clipboard().mimeData().html(), '<b>keep this text</b>')

    def test_crash_reports_failure_and_next_capture_succeeds(self):
        with patch.object(sys, 'stderr', new_callable=io.StringIO) as stderr:
            temporary = self.start('crash')
            self.finish()
        self.assertIn('ScreenGrab crashed; clipboard unchanged', stderr.getvalue())
        self.assertFalse(temporary.exists())
        self.assertEqual(self.app.clipboard().text(), 'clipboard before capture')
        self.start('blue')
        self.finish()
        self.assertEqual(self.app.clipboard().image().pixelColor(0, 0), QColor('blue'))

    def test_capture_configuration_is_private_and_disables_filename_copy(self):
        temporary = self.start('slow')
        env = self.capture.process.processEnvironment()
        self.assertEqual(env.value('XDG_CONFIG_HOME'), str(temporary))
        settings = QSettings(str(temporary / 'screengrab/screengrab.conf'), QSettings.Format.IniFormat)
        self.assertEqual(settings.value('Base/defDir'), str(temporary / 'captures'))
        self.assertEqual(settings.value('Base/defImgFormat'), 'png')
        self.assertEqual(settings.value('Base/CopyFilenameToClipboard', type=int), 0)
        self.assertTrue(settings.value('System/AllowCopies', type=bool))
        self.assertFalse(settings.value('System/closeInTray', type=bool))
        self.finish()
        self.assertFalse(temporary.exists())
