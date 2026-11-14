"""Private rendered installed-toolkit input check; never changes physical input."""
import argparse
import os
from pathlib import Path
import sys

from x11_isolation import isolated


def worker(output):
    assert os.environ.get('DISPLAY')==os.environ.get('DOROSHELL_TEST_DISPLAY') and os.environ['DISPLAY']!=':0'
    from unittest.mock import patch
    root=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(root))
    import install
    home=Path.home(); install.install(home,True)
    toolkit=home/'.local/share/doroshell/toolkit'; sys.path.insert(0,str(toolkit))
    import input_preferences as ip
    import input_diagnostics as diagnostics
    import settings
    assert Path(ip.__file__).parent==toolkit and Path(diagnostics.__file__).parent==toolkit and settings.ROOT==toolkit
    from test_input_preferences import device,Backend
    from PySide6.QtWidgets import QApplication,QPushButton,QCheckBox,QLabel,QComboBox
    from PySide6.QtCore import Qt
    from PySide6.QtGui import QFont
    from PySide6.QtTest import QTest
    app=QApplication([]); mouse=device(); pad=device('touchpad','libinput','b'*64)
    backend=Backend([mouse,pad]); store=ip.Preferences(home)
    configuration=diagnostics.parse_configuration('Section "InputClass"\nIdentifier "fixture"\nMatchProduct "Synthetic mouse"\nOption "AccelerationScheme" "none"\nEndSection\n')
    with patch.object(ip,'XInput',return_value=backend),patch.object(diagnostics,'read_configuration',return_value=configuration):
        window=settings.Settings(home); window.show()
        window.categories.setCurrentRow(window.categories.count()-1); app.processEvents()
        page=window.pages.currentWidget().widget()
        buttons=page.findChildren(QPushButton)
        refresh=next(b for b in buttons if b.text()=='Refresh devices')
        apply=next(b for b in buttons if b.text()=='Save and apply')
        stop=next(b for b in buttons if b.text()=='Stop managing and restore')
        QTest.mouseClick(refresh,Qt.MouseButton.LeftButton); app.processEvents()
        evidence=next(l for l in page.findChildren(QLabel) if l.accessibleName()=='Read-only input capability evidence')
        assert 'control: available' in evidence.text() and 'requests none (intent only)' in evidence.text()
        assert 'initialization: unverified' in evidence.text()
        assert not backend.writes and not store.path.exists()
        check=page.findChild(QCheckBox); check.setFocus(); QTest.keyClick(check,Qt.Key.Key_Space)
        QTest.mouseClick(apply,Qt.MouseButton.LeftButton); app.processEvents()
        assert mouse['props'][ip.PROFILE]['values']==[0xffffffff]
        assert str(toolkit/'input_preferences.py').encode() in store.startup.read_bytes()
        assert str(root).encode() not in store.startup.read_bytes()
        assert any('applied and read back' in l.text() for l in page.findChildren(QLabel))
        output.mkdir(parents=True,exist_ok=True); window.grab().save(str(output/'installed-input-default.png'))
        QTest.mouseClick(stop,Qt.MouseButton.LeftButton); app.processEvents()
        assert mouse['props'][ip.PROFILE]['values']==[0] and not store.startup.exists()
        mouse['props'].pop(ip.PROFILE); QTest.mouseClick(refresh,Qt.MouseButton.LeftButton); app.processEvents()
        assert not apply.isEnabled() and 'control: unavailable' in evidence.text()
        assert 'initialization: unverified' in evidence.text() and 'requests none (intent only)' in evidence.text()
        window.grab().save(str(output/'installed-input-unavailable.png'))
        original_font=QFont(window.font()); large_font=QFont(original_font); large_font.setPointSize(16)
        window.setFont(large_font); window.resize(600,480); app.processEvents()
        area=window.pages.currentWidget(); area.ensureWidgetVisible(evidence); app.processEvents()
        assert area.horizontalScrollBar().maximum()==0
        assert evidence.height()>=evidence.heightForWidth(evidence.width())
        window.grab().save(str(output/'installed-input-evidence-large-font.png'))
        window.setFont(original_font); window.resize(880,650); app.processEvents()
        combo=page.findChild(QComboBox); combo.setCurrentIndex(1)
        backend.items=[pad]; check.setChecked(True)
        QTest.mouseClick(apply,Qt.MouseButton.LeftButton); app.processEvents()
        assert pad['props'][ip.ENABLED]['values']==[1]
        assert any('another enabled' in l.text() for l in page.findChildren(QLabel))
        QTest.mouseClick(stop,Qt.MouseButton.LeftButton); app.processEvents(); store.require_inactive()
        font=QFont(app.font()); font.setPointSize(16); app.setFont(font)
        window.resize(600,480); app.processEvents()
        area=window.pages.currentWidget(); area.ensureWidgetVisible(stop); app.processEvents()
        assert area.horizontalScrollBar().maximum()==0
        window.grab().save(str(output/'installed-input-large-font.png'))
        window.close()
    install.rollback(home)
    assert not store.helper.exists() and not store.startup.exists() and store.path.exists()
    print('PASS installed toolkit imports, rendered read-only capability/intent/unverified status without writes, keyboard opt-in, persistence/restoration, last-mouse refusal, large-font scroll and safe removal; mock devices only')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--xvfb',type=Path); parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--worker',action='store_true'); args=parser.parse_args()
    if args.worker: worker(args.output)
    else:
        if not args.xvfb: parser.error('--xvfb is required')
        isolated(args.xvfb,[sys.executable,str(Path(__file__).resolve()),'--worker','--output',str(args.output.absolute())])
