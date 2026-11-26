// SPDX-License-Identifier: GPL-2.0-or-later
#include "session.hpp"
#include <QtCore>
#include <stdexcept>

int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  if (argc != 2)
    return 1;
  QTemporaryDir tmp;
  if (!tmp.isValid())
    return 1;
  auto home = tmp.filePath("home"), bin = tmp.filePath("café, 東京; native");
  QDir().mkpath(home + "/.config/openbox");
  QDir().mkpath(home + "/.config/lxqt");
  QDir().mkdir(bin);
  for (auto name : {"doroshell-setup", "doroshell-start",
                    "doroshell-screenshot", "doroshell-snap"})
    if (!QFile::copy(argv[1], bin + "/" + name))
      return 1;
  auto xml = home + "/.config/openbox/rc.xml";
  auto ini = home + "/.config/lxqt/globalkeyshortcuts.conf";
  QByteArray initialXml = "<openbox_config>\n<keyboard>\n<!-- my setting "
                          "-->\n</keyboard>\n</openbox_config>\n";
  QByteArray initialIni = "[Control%2BAlt%2BT.1]\nExec=qterminal\n\n[Print.8]"
                          "\nEnabled=true\nExec=screengrab, -f\n";
  auto write = [](QString name, QByteArray data) {
    QFile f(name);
    return f.open(QIODevice::WriteOnly) && f.write(data) == data.size();
  };
  auto read = [](QString name) {
    QFile f(name);
    if (!f.open(QIODevice::ReadOnly))
      return QByteArray();
    return f.readAll();
  };
  auto run = [&](const QString &op) {
    return QProcess::execute(bin + "/doroshell-setup",
                             {"--session", op, "--home", home});
  };
  if (!write(xml, initialXml) || !write(ini, initialIni) || run("--plan") ||
      read(xml) != initialXml)
    return 2;
  if (run("--apply") || run("--apply"))
    return 3;
  auto changed = read(xml), shortcuts = read(ini);
  QSettings parsed(ini, QSettings::IniFormat);
  if (parsed.value("Print.8/Exec").toStringList() != QStringList{bin + "/doroshell-screenshot"} ||
      parsed.value("Alt+F1.1/Exec").toStringList() != QStringList{bin + "/doroshell-start"})
    return 9;
  if (changed.count("W-Left") != 1 || !changed.contains("my setting") ||
      !shortcuts.startsWith("[Control%2BAlt%2BT.1]\nExec=qterminal\n") ||
      shortcuts.count("[Print.8]") != 1 ||
      !shortcuts.contains("doroshell-start"))
    return 4;
  if (!write(xml, changed + "\n") || run("--undo") == 0 || !write(xml, changed))
    return 5;
  if (run("--undo") || read(xml) != initialXml || read(ini) != initialIni)
    return 6;
  QByteArray custom = "[Print.8]\nEnabled=true\nExec=my-own-capture\n";
  if (!write(ini, custom) || run("--apply") == 0 || read(xml) != initialXml ||
      read(ini) != custom)
    return 7;
  auto rc2 = initialXml;
  rc2.replace("</keyboard>", "<keybind key=\"W-Left\"></keybind></keyboard>");
  try {
    openboxBindings(rc2, "/dummy");
    return 8;
  } catch (const std::runtime_error &) {
  }
  return 0;
}
