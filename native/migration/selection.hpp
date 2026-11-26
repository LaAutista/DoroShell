// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QFileInfo>
#include <QProcess>
namespace migration {
inline QStringList
select(QStringList args, const QString &stockDir = QStringLiteral("/usr/bin")) {
  auto target = QFileInfo(args.first());
  auto leaf = target.fileName();
  if (leaf != "lxqt-panel" && leaf != "lxqt-config-input")
    return args;
  QProcess loader;
  auto env = QProcessEnvironment::systemEnvironment();
  env.insert("LC_ALL", "C");
  loader.setProcessEnvironment(env);
  loader.setProcessChannelMode(QProcess::MergedChannels);
  loader.start("/usr/bin/ldd", {"-r", target.absoluteFilePath()});
  bool healthy = loader.waitForFinished(7000) && target.isExecutable() &&
                 loader.exitStatus() == QProcess::NormalExit &&
                 !loader.exitCode();
  auto report = loader.readAllStandardOutput();
  if (healthy && !report.contains("not found") &&
      !report.contains("undefined symbol"))
    return args;
  QProcess::startDetached(target.absolutePath() + "/doroshell-maintenance",
                          {"repair", "--kind",
                           leaf == "lxqt-panel" ? "panel" : "input",
                           "--current", target.absoluteFilePath()});
  return {stockDir + '/' + leaf};
}
} // namespace migration
