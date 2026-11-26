// SPDX-License-Identifier: GPL-2.0-or-later
#include <QtCore>
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  if (argc != 2)
    return 1;
  QTemporaryDir temp;
  auto home = temp.filePath("home"), bin = temp.filePath("bin");
  if (!temp.isValid() || !QDir().mkpath(home + "/.config/autostart") ||
      !QDir().mkdir(bin))
    return 1;
  for (auto name : {"doroshell-setup", "doroshell-desktop", "pcmanfm-qt",
                    "doroshell-video-worker", "doroshell-display"})
    if (!QFile::copy(argv[1], bin + "/" + name))
      return 1;
  auto run = [&](const QString &op) {
    return QProcess::execute(bin + "/doroshell-setup",
                             {"--home", home, "--desktop", op});
  };
  QFile file(home + "/.config/autostart/lxqt-desktop.desktop");
  if (run("--plan") || file.exists() || run("--apply") || !file.exists() ||
      run("--undo") || file.exists())
    return 2;
  QByteArray original =
      "[Desktop Entry]\nType=Application\nName=My desktop\nExec=sh -c "
      "\"systemctl --user start plasma-dolphin.service; exec pcmanfm-qt "
      "--desktop --profile=lxqt\"\nOnlyShowIn=LXQt;\n";
  auto write = [&](const QByteArray &v) {
    if (!file.open(QIODevice::WriteOnly))
      return false;
    bool ok = file.write(v) == v.size();
    file.close();
    return ok;
  };
  auto read = [&] {
    if (!file.open(QIODevice::ReadOnly))
      return QByteArray();
    auto v = file.readAll();
    file.close();
    return v;
  };
  if (!write(original) || run("--apply") || run("--apply"))
    return 3;
  auto applied = read();
  if (!applied.contains(" --dolphin-service ") ||
      !applied.contains("Name=My desktop") || run("--undo") ||
      read() != original)
    return 4;
  QByteArray custom = "[Desktop Entry]\nExec=my-desktop\n";
  if (!write(custom) || run("--apply") == 0 || read() != custom)
    return 5;
}
