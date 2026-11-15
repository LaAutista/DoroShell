"""Bounded read-only logind capability snapshots; never execute a session action."""
from PySide6.QtCore import QObject, QTimer, Signal
try:
    from PySide6 import QtDBus as dbus
except ImportError:
    dbus = None

METHODS = {'shutdown': 'CanPowerOff', 'reboot': 'CanReboot',
           'suspend': 'CanSuspend', 'hibernate': 'CanHibernate'}
CALL_TIMEOUT_MS = 1500
RESULTS = {
    'yes': (True, '', 'logind reports this action is available without further authentication.'),
    'challenge': (True, 'authorization required', 'logind reports this action requires authorization. LXQt may request it after confirmation.'),
    'no': (False, 'not permitted', 'logind reports this action is not permitted for this user.'),
    'na': (False, 'not supported', 'logind reports this action is unsupported by the current hardware, kernel or drivers.'),
    'inhibited': (False, 'inhibited', 'logind reports an inhibitor. DoroShell does not override inhibitors.'),
    'inhibitor-blocked': (False, 'inhibited', 'logind reports this action is blocked by an inhibitor.'),
    'challenge-inhibitor-blocked': (False, 'inhibited', 'logind reports authorization would be required, but an inhibitor blocks this action.'),
}
UNKNOWN = {
    'unknown': 'Not checked.', 'checking': 'Checking power availability…',
    'unavailable': 'The system bus or Qt D-Bus interface is unavailable.',
    'service-unavailable': 'The logind service is unavailable; it was not started.',
    'timeout': 'The capability check timed out.',
    'query-denied': 'Permission to read this capability was denied.',
    'unsupported-query': 'This capability query is not supported by the service.',
    'invalid-reply': 'The service returned an unrecognized capability reply.',
    'query-error': 'The capability check failed.',
}


def classify(reply):
    if reply.type() == dbus.QDBusMessage.MessageType.ErrorMessage:
        return {'org.freedesktop.DBus.Error.ServiceUnknown': 'service-unavailable',
                'org.freedesktop.DBus.Error.NameHasNoOwner': 'service-unavailable',
                'org.freedesktop.DBus.Error.NoReply': 'timeout',
                'org.freedesktop.DBus.Error.Timeout': 'timeout',
                'org.freedesktop.DBus.Error.AccessDenied': 'query-denied',
                'org.freedesktop.DBus.Error.AuthFailed': 'query-denied',
                'org.freedesktop.DBus.Error.UnknownMethod': 'unsupported-query',
                'org.freedesktop.DBus.Error.UnknownInterface': 'unsupported-query'}.get(reply.errorName(), 'query-error')
    values = reply.arguments()
    if (reply.type() == dbus.QDBusMessage.MessageType.ReplyMessage and len(values) == 1
            and type(values[0]) is str and values[0] in RESULTS):
        return values[0]
    return 'invalid-reply'


class PowerCapabilities(QObject):
    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.states = dict.fromkeys(METHODS, 'unknown')
        self.pending = {}
        self.deadline = QTimer(self)
        self.deadline.setSingleShot(True)
        self.deadline.setInterval(CALL_TIMEOUT_MS + 100)
        self.deadline.timeout.connect(lambda: self.cancel('timeout'))

    def status(self, action):
        state = self.states.get(action, 'unknown')
        return RESULTS.get(state, (False, 'availability unknown',
            'Availability unknown. ' + UNKNOWN.get(state, UNKNOWN['invalid-reply'])))

    def refresh(self):
        if self.pending:
            return
        self.states = dict.fromkeys(METHODS, 'checking')
        self.changed.emit()
        if dbus is None:
            self.states = dict.fromkeys(METHODS, 'unavailable'); self.changed.emit(); return
        connection = dbus.QDBusConnection.systemBus()
        if not connection.isConnected():
            self.states = dict.fromkeys(METHODS, 'unavailable'); self.changed.emit(); return
        for action, method in METHODS.items():
            message = dbus.QDBusMessage.createMethodCall('org.freedesktop.login1', '/org/freedesktop/login1',
                                                       'org.freedesktop.login1.Manager', method)
            message.setAutoStartService(False)
            message.setInteractiveAuthorizationAllowed(False)
            watcher = dbus.QDBusPendingCallWatcher(connection.asyncCall(message, CALL_TIMEOUT_MS), self)
            self.pending[action] = watcher
            watcher.finished.connect(lambda _, action=action, watcher=watcher: self.complete(action, watcher))
            if watcher.isFinished():
                QTimer.singleShot(0, self, lambda action=action, watcher=watcher: self.complete(action, watcher))
        self.deadline.start()

    def complete(self, action, watcher):
        if self.pending.get(action) is not watcher:
            return
        self.pending.pop(action)
        self.states[action] = classify(watcher.reply())
        watcher.deleteLater()
        if not self.pending:
            self.deadline.stop()
        self.changed.emit()

    def cancel(self, reason='unknown'):
        self.deadline.stop()
        pending, self.pending = self.pending, {}
        for action, watcher in pending.items():
            self.states[action] = reason
            watcher.deleteLater()
        if pending:
            self.changed.emit()
