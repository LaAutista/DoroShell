// SPDX-License-Identifier: GPL-2.0-or-later
#include "launch.hpp"
#include "../migration/selection.hpp"
#include <QTextStream>

namespace input_launcher {
int launch(const QString &bundle, const QStringList &arguments,
           const QString &stockDirectory) {
  auto env = QProcessEnvironment::systemEnvironment();
  if (env.value("DISPLAY").isEmpty() &&
      env.value("WAYLAND_DISPLAY").isEmpty() &&
      env.value("QT_QPA_PLATFORM").isEmpty() &&
      !arguments.contains("-platform")) {
    const QStringList info{"-h", "--help", "--help-all", "-v", "--version"};
    if (arguments.size() == 1 && info.contains(arguments.first()))
      env.insert("QT_QPA_PLATFORM", "offscreen");
    else {
      QTextStream(stderr) << "Open Keyboard and Mouse Settings from your "
                             "graphical desktop session.\n";
      return 1;
    }
  }

  const auto target = bundle + "/lxqt-config-input";
  const auto executable = migration::select({target}, stockDirectory).first();
  if (executable != target)
    QTextStream(stderr) << "The DoroShell input dialog is unavailable. Opening "
                           "LXQt Keyboard and Mouse Settings.\n";
  QProcess dialog;
  dialog.setProcessEnvironment(env);
  dialog.setProcessChannelMode(QProcess::ForwardedChannels);
  dialog.setUnixProcessParameters(QProcess::UnixProcessFlag::DisableCoreDumps);
  dialog.start(executable, arguments);
  if (!dialog.waitForStarted() || !dialog.waitForFinished(-1)) {
    QTextStream(stderr) << "Cannot start Keyboard and Mouse Settings: "
                        << dialog.errorString() << '\n';
    return 1;
  }
  if (dialog.exitStatus() != QProcess::NormalExit) {
    QTextStream(stderr)
        << "Keyboard and Mouse Settings exited unexpectedly. Check your "
           "graphical session and Qt platform plugin.\n";
    return 1;
  }
  return dialog.exitCode();
}
} // namespace input_launcher
