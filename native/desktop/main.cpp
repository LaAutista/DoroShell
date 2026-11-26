// SPDX-License-Identifier: GPL-2.0-or-later
#include <QtCore>
#include <unistd.h>

namespace {
bool healthy(const QString &path, QByteArray expected) {
  QFile file(path);
  if (!QFileInfo(file).isExecutable() || !file.open(QIODevice::ReadOnly))
    return false;
  QCryptographicHash hash(QCryptographicHash::Sha256);
  if (!hash.addData(&file) || hash.result().toHex() != expected)
    return false;
  QProcess loader;
  auto env = QProcessEnvironment::systemEnvironment();
  env.insert("LC_ALL", "C");
  loader.setProcessEnvironment(env);
  loader.setProcessChannelMode(QProcess::MergedChannels);
  loader.start("/usr/bin/ldd", {"-r", path});
  if (!loader.waitForFinished(5000) || loader.exitCode() ||
      loader.exitStatus() != QProcess::NormalExit)
    return false;
  auto output = loader.readAll();
  return !output.contains("not found") && !output.contains("undefined symbol");
}
} // namespace
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  auto args = app.arguments().mid(1);
  bool hook = args.removeOne("--dolphin-service");
  if (args.size() != 3) {
    qCritical() << "Expected the three configured desktop build digests.";
    return 2;
  }
  for (const auto &hash : args)
    if (!QRegularExpression("^[0-9a-f]{64}$").match(hash).hasMatch())
      return 2;
  QString base = app.applicationDirPath() + "/";
  QStringList components = {"pcmanfm-qt", "doroshell-video-worker",
                            "doroshell-display"};
  bool available = true;
  for (int i = 0; i < components.size() && available; ++i)
    available = healthy(base + components[i], args[i].toLatin1());
  if (hook)
    QProcess::execute("/usr/bin/systemctl",
                      {"--user", "start", "plasma-dolphin.service"});
  if (available) {
    int code = QProcess::execute(base + components.first(),
                                 {"--desktop", "--profile=lxqt"});
    if (!code)
      return 0;
  }
  qWarning() << "Loading the distribution desktop after a native component "
                "failed its check or exited with an error.";
  if (!available)
    QProcess::startDetached(base + "doroshell-maintenance",
                            {"repair", "--kind", "desktop", "--current",
                             base + components.first()});
  execl("/usr/bin/pcmanfm-qt", "pcmanfm-qt", "--desktop", "--profile=lxqt",
        static_cast<char *>(nullptr));
  perror("pcmanfm-qt");
  return 1;
}
