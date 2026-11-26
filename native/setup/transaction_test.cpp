#include <QtCore>
#include <cstdio>
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  if (argc != 2)
    return 1;
  QTemporaryDir work;
  if (!work.isValid())
    return 1;
  auto bin = work.filePath("tools $special % ü");
  auto home = work.filePath("home");
  QDir().mkdir(bin);
  QDir().mkdir(home);
  for (auto name :
       {"doroshell-start", "doroshell-settings", "doroshell-network",
        "doroshell-screenshot", "doroshell-clipboard", "doroshell-setup"})
    if (!QFile::copy(argv[1], bin + "/" + name))
      return 2;
  auto run = [&](QString cmd) {
    return QProcess::execute(bin + "/doroshell-setup", {"--home", home, cmd});
  };
  auto entry = home + "/.local/share/applications/doroshell-network.desktop";
  auto receipt = home + "/.local/state/doroshell-native/launchers.json";
  if (run("--plan") || QFileInfo::exists(receipt) || QFileInfo::exists(entry))
    return 3;
  if (run("--apply") || run("--apply"))
    return 4;
  QFile f(entry);
  if (!f.open(QIODevice::ReadOnly))
    return 5;
  auto original = f.readAll();
  f.close();
  if (!original.contains("%%") || !original.contains("\\\\$special"))
    return 6;
  auto write = [&](QByteArray content) {
    if (!f.open(QIODevice::WriteOnly))
      return false;
    bool ok = f.write(content) == content.size();
    f.close();
    return ok;
  };
  if (!write(original + "# personal\n") || run("--undo") == 0 ||
      run("--apply") == 0)
    return 7;
  if (!write(original) || run("--undo") || QFileInfo::exists(entry))
    return 8;
  // An interrupted install has every allowed path's previous and target bytes
  // persisted before any desktop file changes.
  if (run("--apply"))
    return 9;
  QFile journal(receipt);
  if (!journal.open(QIODevice::ReadOnly))
    return 10;
  auto j = QJsonDocument::fromJson(journal.readAll()).object();
  journal.close();
  j["phase"] = "applying";
  if (!journal.open(QIODevice::WriteOnly))
    return 11;
  journal.write(QJsonDocument(j).toJson());
  journal.close();
  if (!f.remove() || run("--recover") || !QFileInfo::exists(entry))
    return 12;
  if (run("--undo") || QFileInfo::exists(receipt))
    return 13;
  if (!write("unmanaged") || run("--apply") == 0 || QFileInfo::exists(receipt))
    return 14;
  return 0;
}
