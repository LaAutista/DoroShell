// SPDX-License-Identifier: GPL-2.0-or-later
#include "../setup/files.hpp"
#include "selection.hpp"
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QJsonArray>
#include <QJsonDocument>
#include <QMap>
#include <QProcess>
#include <QTemporaryDir>
#include <QTextStream>
#include <QThread>
using namespace doro_files;
namespace {
void check(bool value, const QString &msg) {
  if (!value)
    fail(msg);
}
QString hash(QByteArray value) {
  return QCryptographicHash::hash(value, QCryptographicHash::Sha256).toHex();
}
int run(const QString &program, const QStringList &args,
        QByteArray *output = nullptr) {
  QProcess p;
  p.setProcessChannelMode(QProcess::MergedChannels);
  p.start(program, args);
  check(p.waitForFinished(10000) && p.exitStatus() == QProcess::NormalExit,
        "Process did not finish");
  auto data = p.readAll();
  if (output)
    *output = data;
  else if (p.exitCode())
    QTextStream(stderr) << data;
  return p.exitCode();
}
void testFallback(const QString &self) {
  QTemporaryDir dir;
  auto bin = dir.filePath("lxqt-panel"),
       helper = dir.filePath("doroshell-maintenance");
  check(QFile::copy(self, helper), "Cannot stage repair fixture");
  atomic(bin, "broken ELF fixture", 0755);
  auto stock = dir.filePath("stock");
  check(migration::select({bin, "--config", "private"}, stock) ==
            QStringList{stock + "/lxqt-panel"},
        "Failed dependency check did not select stock without private args");
  auto report = dir.filePath("repair-args");
  for (int i = 0; i < 100 && !QFileInfo::exists(report); ++i)
    QThread::msleep(10);
  check(bytes(read(report)) ==
            "repair\n--kind\npanel\n--current\n" + bin.toUtf8(),
        "Failed dependency check did not request repair");
}
void testWallpaper(const QString &program) {
  QTemporaryDir dir;
  auto config = dir.filePath("doroshell/wallpaper.json");
  qputenv("XDG_CONFIG_HOME", dir.path().toUtf8());
  atomic(config, "{\"personal\":\"kept\",\"enabled\":false}", 0600);
  for (auto action : {"pause", "resume", "off"}) {
    check(run(program, {action}) == 0, "Wallpaper CLI refused action");
    auto value = QJsonDocument::fromJson(bytes(read(config))).object();
    check(value["personal"] == "kept" &&
              value["paused"] == (QString(action) == "pause") &&
              value["enabled"] == false,
          "Wallpaper command damaged settings");
  }
  atomic(config, "broken", 0600);
  check(run(program, {"off"}) != 0 && bytes(read(config)) == "broken",
        "Wallpaper CLI overwrote damaged settings");
}
void test(QString migrate, QString route) {
  QTemporaryDir dir;
  check(dir.isValid(), "Temporary directory");
  QString home = dir.filePath("home with spaces"),
          bundle = dir.filePath("bundle"),
          receipt = home + "/.local/state/doroshell-native/migration.json";
  check(QDir().mkpath(home) && QDir().mkpath(bundle),
        "Cannot prepare test paths");
  check(QFile::copy(migrate, bundle + "/doroshell-migrate") &&
            QFile::copy(route, bundle + "/doroshell-route"),
        "Cannot stage migration");
  QStringList args{"--home", home};
  auto call = [&](QString action) {
    return run(bundle + "/doroshell-migrate", args + QStringList{action});
  };
  auto installExe = [&](QString name) {
    check(QFile::copy("/usr/bin/printf", bundle + '/' + name),
          "Cannot stage " + name);
  };
  QString stateDir = ".local/state/doroshell/",
          menu = ".local/state/lxqt-comfort/menu-install.json";
  QString start = ".local/bin/lxqt-comfort-menu",
          settings = ".local/bin/doroshell-settings",
          network = ".local/share/applications/doroshell-network.desktop",
          panel = ".local/bin/doroshell-native-panel",
          snap = ".local/bin/doroshell-snap";
  QMap<QString, QJsonObject> originals;
  auto put = [&](QString name, QByteArray data, int mode) {
    atomic(home + '/' + name, data, mode);
    originals[name] = read(home + '/' + name);
  };
  auto manifest = [&](QString name, QJsonObject obj) {
    put(name, QJsonDocument(obj).toJson(), 0600);
  };
  put(start, "old menu", 0755);
  put(settings, "old settings", 0755);
  put(network,
      "[Desktop Entry]\nName=Wi-Fi & Network\nExec=/usr/bin/python3 "
      "chooser.py\n",
      0644);
  QJsonObject menuRecord;
  for (auto name : {start, settings, network}) {
    menuRecord[name] = QJsonObject{{"mode", QJsonValue::Null},
                                   {"original", QJsonValue::Null},
                                   {"installed_mode", originals[name]["mode"]},
                                   {"installed", hash(bytes(originals[name]))}};
  }
  manifest(menu, menuRecord);
  put(panel, "old panel", 0755);
  QString panelConf = ".config/doroshell/panel.conf",
          panelEntry = ".config/autostart/lxqt-panel.desktop";
  put(panelConf, "[quicklaunch]\napps=favorites;edited after setup\n", 0600);
  put(panelEntry, "[Desktop Entry]\nExec=existing panel launcher\n", 0600);
  auto panelRec = [&](QString digest) {
    return QJsonObject{
        {"mode", 0600}, {"before", QJsonValue::Null}, {"after", digest}};
  };
  manifest(stateDir + "native-panel.json",
           {{panel, panelRec(hash("old panel"))},
            {panelConf, panelRec(hash("pre edits"))},
            {panelEntry, panelRec(hash(bytes(originals[panelEntry])))}});
  put(snap, "original snap", 0755);
  manifest(
      stateDir + "snapping.json",
      {{"edits", QJsonArray{QJsonObject{{"file", snap},
                                        {"kind", "file"},
                                        {"before", QJsonValue::Null},
                                        {"mode", 0755},
                                        {"after", originals[snap]["data"]}}}},
       {"backup",
        QJsonObject{
            {snap, QJsonObject{{"mode", 0755}, {"data", QJsonValue::Null}}}}}});
  put(".config/lxqt-comfort/favorites.json", "[\"firefox.desktop\"]", 0600);
  auto module = [&](QString key, const QStringList &entries) {
    QJsonArray edits;
    QJsonObject backup;
    for (const auto &name : entries) {
      bool app = name.endsWith(".desktop");
      auto data = app ? "[Desktop Entry]\nExec=/usr/bin/python helper.py\n"
                      : ("RC2 " + name).toUtf8();
      if (name.endsWith("/lxqt-desktop.desktop"))
        data = ("[Desktop Entry]\nExec=\"" + home +
                "/.local/bin/doroshell-wallpaper-desktop\"\nTryExec=/usr/bin/"
                "python\n")
                   .toUtf8();
      put(name, data, app ? 0600 : 0755);
      auto snap = originals.value(name);
      edits.append(QJsonObject{{"file", name},
                               {"kind", "file"},
                               {"before", QJsonValue::Null},
                               {"mode", snap["mode"]},
                               {"after", snap["data"]}});
      backup[name] =
          QJsonObject{{"mode", snap["mode"]}, {"data", QJsonValue::Null}};
    }
    manifest(stateDir + key + ".json", {{"edits", edits}, {"backup", backup}});
  };
  module("maintenance",
         {".local/bin/doroshell-update", ".local/bin/doroshell-remove"});
  module("input-settings",
         {".local/bin/doroshell-config-input",
          ".local/share/applications/lxqt-config-input.desktop",
          ".config/autostart/doroshell-input-defaults.desktop"});
  module("wallpaper", {".local/bin/doroshell-wallpaper-desktop",
                       ".local/bin/doroshell-wallpaper",
                       ".config/autostart/lxqt-desktop.desktop"});
  module("screenshots", {".local/bin/doroshell-screenshot"});
  module("clipboard", {".local/bin/doroshell-clipboard"});
  put(".config/doroshell/input-preferences.json",
      "{\"all_mice\":false,\"startup\":\"installed\"}", 0600);
  const QString watch = ".config/autostart/doroshell-input.desktop";
  put(watch,
      ("[Desktop Entry]\nType=Application\nName=DoroShell input "
       "preferences\nExec=\"/usr/bin/python\" \"" +
       home +
       "/.local/share/doroshell/toolkit/input_preferences.py\" "
       "--login\nOnlyShowIn=LXQt;\n")
          .toUtf8(),
      0600);
  for (auto name :
       {"doroshell-start", "doroshell-settings", "doroshell-network",
        "doroshell-snap", "lxqt-panel", "doroshell-maintenance",
        "doroshell-screenshot", "doroshell-clipboard",
        "doroshell-input-preferences", "lxqt-config-input", "doroshell-desktop",
        "doroshell-wallpaper", "pcmanfm-qt", "doroshell-video-worker",
        "doroshell-display"})
    installExe(name);
  check(call("--refresh") != 0, "Refresh re-enabled RC2");
  check(call("--plan") == 0 && !QFile::exists(receipt), "Plan wrote or failed");
  atomic(home + '/' + settings, "personal edit", 0755);
  check(call("--apply") == 1 && !QFile::exists(receipt) &&
            read(home + '/' + start) == originals[start],
        "Conflict partially applied");
  write(home + '/' + settings, originals[settings]);
  check(call("--apply") == 0 && QFile::exists(receipt), "Migration refused");
  check(!bytes(read(home + "/.config/autostart/lxqt-desktop.desktop"))
             .contains("python"),
        "Desktop still gated by Python");
  check(
      bytes(read(home + "/.local/share/applications/lxqt-config-input.desktop"))
          .contains("Exec=" +
                    desktopQuote(home + "/.local/bin/doroshell-config-input")
                        .toUtf8()),
      "Input desktop entry interprets ELF as Python");
  check(bytes(read(home + '/' + watch))
            .contains((bundle + "/doroshell-input-preferences").toUtf8()),
        "RC2 watcher still points to old helper");
  auto migrated = read(receipt, 32 * 1024 * 1024);
  check(call("--apply") == 0 && read(receipt, 32 * 1024 * 1024) == migrated,
        "Repeat changed receipt");
  QByteArray out;
  check(run(home + '/' + start, {"%s", "quote; spaces $"}, &out) == 0 &&
            out == "quote; spaces $",
        "Native route changed argv");
  check(bytes(read(home + '/' + network))
            .contains(desktopQuote(bundle + "/doroshell-network").toUtf8()),
        "Missing native network");
  for (auto name : {panelConf, panelEntry, menu,
                    QString(".config/lxqt-comfort/favorites.json"),
                    QString(".config/doroshell/input-preferences.json")})
    check(read(home + '/' + name) == originals[name],
          "Changed retained state " + name);
  auto j = QJsonDocument::fromJson(bytes(migrated)).object();
  j["phase"] = "applying";
  atomic(receipt, QJsonDocument(j).toJson(), 0600);
  write(home + '/' + start, originals[start]);
  check(call("--apply") == 1 && call("--recover") == 0 &&
            bytes(read(home + '/' + start))
                .startsWith("\x7f"
                            "ELF"),
        "Incomplete apply recovery");
  atomic(home + '/' + snap, "personal edit after apply", 0755);
  check(call("--undo") == 1 && bytes(read(home + '/' + start))
                                   .startsWith("\x7f"
                                               "ELF"),
        "Undo ignored edit");
  write(home + '/' + snap,
        j["files"].toObject()[snap].toObject()["to"].toObject());
  check(call("--undo") == 0 && !QFile::exists(receipt), "Undo failed");
  for (auto it = originals.cbegin(); it != originals.cend(); ++it)
    check(read(home + '/' + it.key()) == it.value(),
          "Original differs: " + it.key());
  check(call("--apply") == 0, "Reinstallation failed");
  const auto oldBundle = bundle;
  bundle = dir.filePath("next bundle");
  check(QDir().mkpath(bundle), "Cannot create update bundle");
  for (const auto &f : QDir(oldBundle).entryList(QDir::Files))
    check(QFile::copy(oldBundle + '/' + f, bundle + '/' + f),
          "Cannot stage second release");
  check(call("--refresh") == 0 &&
            bytes(read(home + '/' + watch))
                .contains((bundle + "/doroshell-input-preferences").toUtf8()),
        "Refresh lost input selection");
  check(bytes(read(home + '/' + network))
            .contains((bundle + "/doroshell-network").toUtf8()),
        "Did not select new release");
  // A user opting out through the new helper owns the current preference.
  check(QFile::remove(home + '/' + watch), "Cannot simulate opt out");
  atomic(home + "/.config/doroshell/input-preferences.json",
         "{\"all_mice\":false,\"startup\":null}", 0600);
  check(call("--undo") == 0 && !QFile::exists(home + '/' + watch),
        "Undo resurrected disabled watcher");
  check(read(home + '/' + start) == originals[start],
        "Release update lost the RC2 original");
}
} // namespace
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  try {
    auto args = app.arguments();
    if (QFileInfo(args[0]).fileName() == "doroshell-maintenance") {
      atomic(QFileInfo(args[0]).absolutePath() + "/repair-args",
             args.mid(1).join('\n').toUtf8(), 0600);
      return 0;
    }
    test(args.at(1), args.at(2));
    testFallback(app.applicationFilePath());
    testWallpaper(args.at(3));
  } catch (const std::exception &e) {
    QTextStream(stderr) << e.what() << '\n';
    return 1;
  }
  return 0;
}
