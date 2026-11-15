"""No personal bus or power actions: Qt messages, fake service and synthetic widgets."""
import contextlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
import shiboken6
from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtTest import QTest
from test_menu import menu, installer
import power_capabilities as caps


class FakeBus:
    def __init__(self, values=None, connected=True):
        self.values = dict.fromkeys(caps.METHODS.values(), 'yes')
        self.values.update(values or {}); self.connected = connected; self.calls = []
    def isConnected(self): return self.connected
    def asyncCall(self, message, timeout):
        assert message.service() == 'org.freedesktop.login1'
        assert message.path() == '/org/freedesktop/login1'
        assert message.interface() == 'org.freedesktop.login1.Manager'
        assert message.member() in caps.METHODS.values()
        assert message.arguments() == [] and not message.autoStartService()
        assert not message.isInteractiveAuthorizationAllowed()
        assert timeout == caps.CALL_TIMEOUT_MS
        self.calls.append(message.member())
        value = self.values[message.member()]
        if isinstance(value, tuple): reply = message.createErrorReply(value[0], value[1])
        else:
            reply = message.createReply()
            reply.setArguments(value if isinstance(value, list) else [value])
        return caps.dbus.QDBusPendingCall.fromCompletedCall(reply)


class StalledWatcher(QObject):
    finished = Signal(object)
    def __init__(self, call, parent): super().__init__(parent)
    def isFinished(self): return False
    def reply(self): raise AssertionError('Late/cancelled reply must not be consumed')


class CapabilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = menu.QApplication.instance() or menu.QApplication([])
    def setUp(self):
        self.bus = FakeBus()
        self.factory = self.enterContext(patch.object(caps.dbus.QDBusConnection, 'systemBus', return_value=self.bus))
        self.provider = caps.PowerCapabilities(); self.addCleanup(lambda: shiboken6.delete(self.provider))
    def finish(self):
        for _ in range(3): self.app.processEvents()
        self.assertFalse(self.provider.pending); self.assertFalse(self.provider.deadline.isActive())
    def test_construction_does_not_connect_and_queries_have_no_auth_activation_or_actions(self):
        self.factory.assert_not_called(); self.assertFalse(self.provider.status('shutdown')[0])
        self.provider.refresh(); self.assertFalse(self.provider.status('shutdown')[0]); self.finish()
        self.assertEqual(self.bus.calls, list(caps.METHODS.values())); self.assertTrue(self.provider.status('shutdown')[0])
        QTest.qWait(30); self.assertEqual(len(self.bus.calls), 4)
    def test_yes_no_na_challenge_are_distinct(self):
        self.bus.values.update(dict(zip(caps.METHODS.values(), ['yes','no','na','challenge'])))
        self.provider.refresh(); self.finish()
        for action, allowed, suffix in [('shutdown',True,''),('reboot',False,'not permitted'),('suspend',False,'not supported'),('hibernate',True,'authorization required')]:
            self.assertEqual(self.provider.status(action)[:2], (allowed,suffix))
    def test_inhibitor_states_never_offer_override(self):
        for value in ('inhibited','inhibitor-blocked','challenge-inhibitor-blocked'):
            self.bus.values['CanPowerOff']=value;self.provider.refresh();self.finish()
            self.assertEqual(self.provider.status('shutdown')[:2], (False,'inhibited'))
    def test_absent_bus_or_qt_is_unknown_and_no_service_is_started(self):
        self.bus.connected=False;self.provider.refresh()
        self.assertFalse(self.bus.calls);self.assertEqual(self.provider.states['shutdown'],'unavailable')
        with patch.object(caps,'dbus',None):self.provider.refresh()
        self.assertEqual(self.provider.status('shutdown')[:2],(False,'availability unknown'))
    def test_service_error_timeout_denial_and_unknown_method_are_not_hardware_claims(self):
        errors={'ServiceUnknown':'service-unavailable','NameHasNoOwner':'service-unavailable','NoReply':'timeout','Timeout':'timeout',
                'AccessDenied':'query-denied','AuthFailed':'query-denied','UnknownMethod':'unsupported-query','UnknownInterface':'unsupported-query','UnknownError':'query-error'}
        for name,state in errors.items():
            self.bus.values['CanPowerOff']=('org.freedesktop.DBus.Error.'+name,'private raw error not to show')
            self.provider.refresh();self.finish();self.assertEqual(self.provider.states['shutdown'],state)
            allowed,label,detail=self.provider.status('shutdown');self.assertFalse(allowed);self.assertEqual(label,'availability unknown')
            self.assertNotIn('private',detail);self.assertNotIn('unsupported by the current hardware',detail)
    def test_unrecognized_or_malformed_replies_remain_unknown(self):
        for value in ('YES','unexpected private reply',[],['yes','yes'],[None],[True],[{'yes':True}]):
            self.bus.values['CanPowerOff']=value;self.provider.refresh();self.finish()
            self.assertEqual(self.provider.states['shutdown'],'invalid-reply')
            self.assertFalse(self.provider.status('shutdown')[0]);self.assertNotIn('private',self.provider.status('shutdown')[2])
    def test_pending_refresh_coalesces_timeout_then_late_reply_cannot_override(self):
        with patch.object(caps.dbus,'QDBusPendingCallWatcher',StalledWatcher):
            self.provider.deadline.setInterval(10);self.provider.refresh();old=dict(self.provider.pending)
            self.provider.refresh();self.assertEqual(len(self.bus.calls),4)
            QTest.qWait(30);self.assertFalse(self.provider.pending);self.assertEqual(set(self.provider.states.values()),{'timeout'})
        self.provider.refresh();self.finish();self.assertTrue(self.provider.status('shutdown')[0])
        self.provider.complete('shutdown',old['shutdown']);self.assertTrue(self.provider.status('shutdown')[0])
    def test_deleted_provider_drops_queued_completed_callbacks(self):
        provider=caps.PowerCapabilities();provider.refresh()
        self.assertTrue(provider.pending);shiboken6.delete(provider)
        self.app.processEvents();self.app.processEvents()
        self.assertFalse(shiboken6.isValid(provider))
    def test_cancel_and_changed_capability_require_explicit_refresh_without_retry(self):
        with patch.object(caps.dbus,'QDBusPendingCallWatcher',StalledWatcher):
            self.provider.refresh();self.provider.cancel();self.assertEqual(set(self.provider.states.values()),{'unknown'})
        QTest.qWait(30);self.assertEqual(len(self.bus.calls),4)
        self.provider.refresh();self.finish();self.assertTrue(self.provider.status('shutdown')[0])
        self.bus.values['CanPowerOff']='no';self.provider.refresh();self.assertFalse(self.provider.status('shutdown')[0]);self.finish()
        self.assertEqual(self.provider.status('shutdown')[1],'not permitted')


class PowerWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app = menu.QApplication.instance() or menu.QApplication([])
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.home=Path(tmp.name)
        self.enterContext(patch.dict(os.environ,{'HOME':str(self.home),'XDG_CONFIG_HOME':str(self.home/'config'),'XDG_DATA_HOME':str(self.home/'data')},clear=True))
        self.bus=FakeBus();self.enterContext(patch.object(caps.dbus.QDBusConnection,'systemBus',return_value=self.bus))
        self.enterContext(patch.object(menu,'PowerCapabilities',caps.PowerCapabilities))
        self.enterContext(patch.object(menu,'applications',return_value=[]))
        self.entry=Mock();self.entry.launch.return_value=True
        self.entries=self.enterContext(patch.object(menu,'desktop_entry',return_value=self.entry))
        self.enterContext(patch.object(menu.Gio.AppInfo,'launch_default_for_uri',side_effect=AssertionError('No real URI dispatch')))
        self.enterContext(patch.object(menu.Gio.AppInfo,'create_from_commandline',side_effect=AssertionError('No commands')))
        self.error=self.enterContext(patch.object(menu.StartMenu,'error'))
        self.windows=[];self.addCleanup(self.cleanup)
    def cleanup(self):
        for w in self.windows:
            if shiboken6.isValid(w):w.close();shiboken6.delete(w)
    def window(self,show=True):
        w=menu.StartMenu();self.windows.append(w)
        if show:w.show();self.finish()
        return w
    def finish(self):
        for _ in range(3):self.app.processEvents()
    def actions(self,w):return {a.data():a for a in w.power_menu.actions() if a.data()}
    def refresh(self,w):w.power_capabilities.refresh();self.finish()
    def test_initial_unknown_then_update_does_not_write_or_dispatch(self):
        w=self.window(False);self.assertFalse(w.session_button.isEnabled());self.assertIn('unknown',w.session_button.toolTip())
        self.assertTrue(self.actions(w)['lockscreen'].isEnabled());self.assertTrue(self.actions(w)['logout'].isEnabled())
        self.assertFalse(w.primary_path.exists());w.show();self.finish();self.assertTrue(w.session_button.isEnabled())
        self.entry.launch.assert_not_called();self.assertFalse(w.primary_path.exists())
    def test_states_consistent_across_primary_choices_menu_and_direct_guard(self):
        self.bus.values.update({'CanReboot':'no','CanSuspend':'na','CanHibernate':'challenge'});w=self.window();actions=self.actions(w)
        self.assertFalse(actions['reboot'].isEnabled());self.assertIn('not permitted',actions['reboot'].text())
        self.assertFalse(actions['suspend'].isEnabled());self.assertIn('not supported',actions['suspend'].text())
        self.assertTrue(actions['hibernate'].isEnabled());self.assertIn('authorization required',actions['hibernate'].text())
        with patch.object(menu.QMessageBox,'question') as question:
            w.session_action('reboot');w.session_action('suspend');question.assert_not_called()
        w.set_primary_action('reboot');self.assertFalse(w.primary_path.exists());self.assertEqual(w.primary_action,'shutdown')
        w.set_primary_action('hibernate');self.assertEqual(w.primary_action,'hibernate');self.assertTrue(w.session_button.isEnabled())
        self.assertIn('requires authorization',w.session_button.toolTip());self.entry.launch.assert_not_called()
    def test_saved_unavailable_primary_is_preserved_across_reopen_and_changes(self):
        w=self.window();w.set_primary_action('hibernate');before=w.primary_path.read_bytes()
        self.bus.values['CanHibernate']='na';self.refresh(w)
        self.assertEqual(w.primary_action,'hibernate');self.assertFalse(w.session_button.isEnabled())
        choice=next(a for a in w.primary_choices.actions() if a.data()=='hibernate')
        self.assertTrue(choice.isChecked());self.assertFalse(choice.isEnabled());self.assertFalse(self.actions(w)['hibernate'].isVisible())
        w.hide();w.show();self.finish();other=self.window();self.assertEqual(other.primary_action,'hibernate')
        self.assertFalse(other.session_button.isEnabled());self.assertEqual(w.primary_path.read_bytes(),before)
        self.bus.values['CanHibernate']='yes';self.refresh(other);self.assertTrue(other.session_button.isEnabled());self.assertEqual(w.primary_path.read_bytes(),before)
    def test_unknown_service_keeps_native_options_logout_lock_and_refresh_available(self):
        self.bus.values=dict.fromkeys(caps.METHODS.values(),('org.freedesktop.DBus.Error.ServiceUnknown','private'))
        w=self.window();self.assertFalse(w.session_button.isEnabled());self.assertIn('unknown',w.session_button.toolTip())
        actions=self.actions(w);self.assertTrue(actions['logout'].isEnabled());self.assertTrue(actions['lockscreen'].isEnabled())
        self.assertTrue(w.power_menu.actions()[-1].isEnabled());self.assertEqual(w.power_menu.actions()[-1].text(),'All session options…')
        with patch.object(menu.QMessageBox,'question') as question:w.session_action('shutdown');question.assert_not_called()
        self.entry.launch.assert_not_called();self.assertIn('All session options',self.error.call_args.args[0])
    def test_challenge_cancel_then_fake_confirm_preserves_native_route_and_history(self):
        self.bus.values['CanHibernate']='challenge';w=self.window()
        with patch.object(menu.QMessageBox,'question',return_value=menu.QMessageBox.StandardButton.Cancel) as question,patch.object(w.recent,'save') as recent:
            w.session_action('hibernate');self.assertIn('requires authorization',question.call_args.args[2])
            self.assertEqual(question.call_args.args[-1],menu.QMessageBox.StandardButton.Cancel);self.entry.launch.assert_not_called();self.finish()
            question.return_value=menu.QMessageBox.StandardButton.Yes;w.session_action('hibernate')
            self.entry.launch.assert_called_once_with([],None);recent.assert_not_called()
            self.entries.assert_called_with('lxqt-hibernate.desktop');w.session_action('hibernate');self.entry.launch.assert_called_once()
    def test_changed_capability_during_confirmation_refuses_and_never_queues_retry(self):
        w=self.window()
        def answer(*args):
            w.power_capabilities.states['shutdown']='no';w.power_capabilities.changed.emit()
            return menu.QMessageBox.StandardButton.Yes
        with patch.object(menu.QMessageBox,'question',side_effect=answer):w.session_action('shutdown')
        self.entry.launch.assert_not_called();self.assertFalse(w.launching);self.assertFalse(w.session_button.isEnabled())
        self.assertIn('changed during confirmation',self.error.call_args.args[0])
        self.refresh(w);self.assertTrue(w.session_button.isEnabled());self.entry.launch.assert_not_called()
    def test_actual_offscreen_confirmation_cancel_default_and_yes_with_fake_dispatch(self):
        w=self.window();failures=[]
        def respond(button):
            try:
                dialog=self.app.activeModalWidget();self.assertIsInstance(dialog,menu.QMessageBox)
                self.assertEqual(dialog.defaultButton(),dialog.button(menu.QMessageBox.StandardButton.Cancel))
                dialog.button(button).click()
            except Exception as exc:
                failures.append(exc)
                if self.app.activeModalWidget():self.app.activeModalWidget().reject()
        QTimer.singleShot(0,lambda:respond(menu.QMessageBox.StandardButton.Cancel));w.session_action('shutdown');self.finish()
        self.assertFalse(failures,failures);self.entry.launch.assert_not_called()
        QTimer.singleShot(0,lambda:respond(menu.QMessageBox.StandardButton.Yes));w.session_action('shutdown')
        self.assertFalse(failures,failures);self.entry.launch.assert_called_once_with([],None)
    def test_no_polling_refresh_and_close_cancel_owned_queries(self):
        with patch.object(caps.dbus,'QDBusPendingCallWatcher',StalledWatcher):
            w=self.window();self.assertTrue(w.power_capabilities.pending);w.hide();self.assertFalse(w.power_capabilities.pending)
        QTest.qWait(20);self.assertEqual(len(self.bus.calls),4);w.show();self.finish();self.assertEqual(len(self.bus.calls),8)
        QTest.qWait(20);self.assertEqual(len(self.bus.calls),8)
        next(a for a in w.power_menu.actions() if a.text()=='Refresh power availability').trigger();self.finish()
        self.assertEqual(len(self.bus.calls),12);self.entry.launch.assert_not_called()
    def test_missing_launcher_remains_disabled_and_lock_dispatch_unchanged(self):
        w=self.window();self.entries.return_value=None;w.refresh_primary_action()
        self.assertFalse(w.session_button.isEnabled());self.assertIn('not installed',w.session_button.toolTip())
        w.set_primary_action('shutdown');self.assertFalse(w.primary_path.exists())
        self.entries.return_value=self.entry;w.refresh_primary_action();calls=len(self.bus.calls)
        with patch.object(menu.QMessageBox,'question') as question:w.session_action('lockscreen');question.assert_not_called()
        self.entry.launch.assert_called_once_with([],None);self.assertEqual(len(self.bus.calls),calls)
    def test_installer_packages_both_helpers_repeat_conflict_and_exact_restore(self):
        target=self.home/'.local/share/lxqt-comfort/power_capabilities.py';target.parent.mkdir(parents=True)
        target.write_bytes(b'# fixture previous helper\n');target.chmod(0o640)
        with contextlib.redirect_stdout(io.StringIO()):
            for _ in range(2):installer.install(self.home,apply=True)
            expected=(Path(__file__).resolve().parents[1]/'menu/power_capabilities.py').read_bytes()
            self.assertEqual(target.read_bytes(),expected)
            self.assertEqual((self.home/'.local/share/doroshell/toolkit/menu/power_capabilities.py').read_bytes(),expected)
            target.write_bytes(b'# fixture later edit\n')
            with self.assertRaises(RuntimeError):installer.rollback(self.home)
            self.assertEqual(target.read_bytes(),b'# fixture later edit\n');target.write_bytes(expected)
            installer.rollback(self.home)
        self.assertEqual(target.read_bytes(),b'# fixture previous helper\n');self.assertEqual(target.stat().st_mode&0o777,0o640)

if __name__=='__main__':unittest.main()
