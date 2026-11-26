// SPDX-License-Identifier: GPL-2.0-or-later
#include "../compatibility/packages.hpp"
#include "files.hpp"
#include "session.hpp"
#include <QCommandLineParser>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDir>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLockFile>
#include <QRegularExpression>
#include <QSaveFile>
#include <QTextStream>
#include <memory>
#include <stdexcept>
#include <sys/stat.h>
#include <unistd.h>

namespace {
using Error = std::runtime_error;
using namespace doro_files;
const QString stateDir = ".local/state/doroshell-native";
const QString receipt = stateDir + "/launchers.json";
struct Launcher {
  QString id, executable, name, icon, category, option;
};
const QList<Launcher> launchers = {{"lxqt-comfort",
                                    "doroshell-start",
                                    "DoroShell Start",
                                    "start-here",
                                    "Utility",
                                    {}},
                                   {"doroshell-network",
                                    "doroshell-network",
                                    "Wi-Fi & Network",
                                    "network-wireless",
                                    "Network",
                                    {}},
                                   {"doroshell-settings",
                                    "doroshell-settings",
                                    "DoroShell Settings",
                                    "preferences-desktop",
                                    "Settings",
                                    {}},
                                   {"doroshell-clipboard",
                                    "doroshell-clipboard", "DoroClipboard",
                                    "edit-paste", "Utility", " --show"},
                                   {"doroshell-screenshot",
                                    "doroshell-screenshot",
                                    "DoroShell Screenshot",
                                    "camera-photo",
                                    "Utility",
                                    {}}};
struct Scope {
  QList<Launcher> entries;
  QString record;
};
const QList<Launcher> session = {
    {".config/openbox/rc.xml", "doroshell-snap", {}, {}, {}, {}},
    {".config/lxqt/globalkeyshortcuts.conf", "doroshell-start", {}, {}, {}, {}},
    {".config/autostart/doroshell-snap.desktop",
     "doroshell-snap",
     "DoroShell edge snapping",
     {},
     {},
     {}},
    {".config/autostart/doroshell-recent-programs.desktop",
     "doroshell-start",
     "DoroShell recent programs",
     {},
     {},
     " --background"}};
const QList<Launcher> desktop = {{".config/autostart/lxqt-desktop.desktop",
                                  "doroshell-desktop",
                                  {},
                                  {},
                                  {},
                                  {}}};
const QList<Launcher> inputPage = {
    {"lxqt-config-input",
     "doroshell-config-input",
     "Keyboard and Mouse Settings",
     "preferences-desktop-peripherals",
     "Settings",
     {}},
    {".config/autostart/doroshell-input-defaults.desktop",
     "doroshell-input-preferences",
     "DoroShell mouse defaults",
     {},
     {},
     " --first-login"}};
QString key(const Launcher &l) {
  if (l.id.startsWith(".config/"))
    return l.id;
  return ".local/share/applications/" + l.id + ".desktop";
}
QJsonObject desired(const Launcher &l, const QJsonObject &original) {
  auto exe = QCoreApplication::applicationDirPath() + "/" + l.executable;
  if (!QFileInfo(exe).isFile() || !QFileInfo(exe).isExecutable())
    fail("Missing installed executable: " + exe);
  if (l.id.startsWith(".config/")) {
    QByteArray content;
    int mode = original["mode"].toInt(0644);
    if (l.executable == "doroshell-desktop") {
      content =
          original == absent()
              ? QByteArray("[Desktop Entry]\nType=Application\nName=DoroShell "
                           "desktop\nOnlyShowIn=LXQt;\nX-LXQt-Module="
                           "true\nExec=pcmanfm-qt --desktop --profile=lxqt\n")
              : bytes(original);
      QStringList digests;
      for (const auto &leaf :
           {"pcmanfm-qt", "doroshell-video-worker", "doroshell-display"}) {
        QFile f(QCoreApplication::applicationDirPath() + "/" + leaf);
        QCryptographicHash hash(QCryptographicHash::Sha256);
        if (!QFileInfo(f).isExecutable() || !f.open(QIODevice::ReadOnly) ||
            !hash.addData(&f))
          fail("Missing native desktop component: " + f.fileName());
        digests << QString::fromLatin1(hash.result().toHex());
      }
      auto lines = content.split('\n');
      bool main = false, found = false;
      for (auto &line : lines) {
        auto text = line.trimmed();
        if (text.startsWith('['))
          main = text == "[Desktop Entry]";
        if (!main || !text.startsWith("Exec="))
          continue;
        bool hook =
            text ==
            "Exec=sh -c \"systemctl --user start plasma-dolphin.service; exec "
            "pcmanfm-qt --desktop --profile=lxqt\"";
        if (found ||
            (!hook && text != "Exec=pcmanfm-qt --desktop --profile=lxqt" &&
             text != "Exec=/usr/bin/pcmanfm-qt --desktop --profile=lxqt"))
          fail("Existing desktop startup command is customized");
        found = true;
        line = ("Exec=" + desktopQuote(exe) +
                (hook ? " --dolphin-service " : " ") + digests.join(' '))
                   .toUtf8();
      }
      if (!found)
        fail("Existing desktop has no recognized startup command");
      content = lines.join('\n');
    } else if (l.id.endsWith(".desktop")) {
      content = QString("[Desktop "
                        "Entry]\nType=Application\nName=%1\nExec=%2%"
                        "3\nOnlyShowIn=LXQt;\n")
                    .arg(l.name, desktopQuote(exe), l.option)
                    .toUtf8();
    } else {
      bool openbox = l.id.endsWith("rc.xml");
      QByteArray base;
      if (original != absent())
        base = bytes(original);
      else {
        QStringList defaults =
            openbox ? QStringList{"/etc/xdg/openbox/rc.xml"}
                    : QStringList{"/etc/xdg/lxqt/globalkeyshortcuts.conf",
                                  "/usr/share/lxqt/globalkeyshortcuts.conf"};
        for (const auto &candidate : defaults) {
          QFile f(candidate);
          if (f.open(QIODevice::ReadOnly)) {
            base = f.readAll();
            break;
          }
        }
        if (base.isEmpty())
          fail("Cannot locate distribution defaults for " + l.id);
      }
      auto screenshot =
          QCoreApplication::applicationDirPath() + "/doroshell-screenshot";
      if (!openbox && l.option != "start-only" && !QFileInfo(screenshot).isExecutable())
        fail("Missing native screenshot binary");
      content = openbox ? openboxBindings(base, exe)
                        : lxqtBindings(base, l.option == "print-only" ? QString{} : exe,
                                       l.option == "start-only" ? QString{} : screenshot);
    }
    return {{"exists", true},
            {"data", QString::fromLatin1(content.toBase64())},
            {"mode", mode}};
  }
  auto icon = l.icon;
  if (l.id == "lxqt-comfort") {
    const QDir artwork(QCoreApplication::applicationDirPath() + "/../share/doroshell");
    for (const auto &name : {"start.png", "start.svg"}) {
      auto file = QFileInfo(artwork.filePath(name)).canonicalFilePath();
      if (!file.isEmpty()) {
        icon = file.replace('\\', "\\\\");
        break;
      }
    }
  }
  QByteArray content =
      QString("[Desktop "
              "Entry]\nType=Application\nName=%1\nExec=%2%3\nIcon=%4\nTerminal="
              "false\nCategories=%5;\n")
          .arg(l.name, desktopQuote(exe), l.option, icon, l.category)
          .toUtf8();
  return {{"exists", true},
          {"data", QString::fromLatin1(content.toBase64())},
          {"mode", 0644}};
}
void save(const Scope &scope, const QString &home, const QJsonObject &j) {
  atomic(path(home, scope.record), QJsonDocument(j).toJson(), 0600);
}
void validateJournal(const Scope &scope, const QJsonObject &j) {
  if (j["version"].toInt() != 1 ||
      !QStringList{"applying", "installed", "undoing"}.contains(
          j["phase"].toString()))
    fail("Invalid launcher journal");
  auto files = j.value("files").toObject();
  if (files.size() != scope.entries.size())
    fail("Invalid launcher journal inventory");
  for (const auto &l : scope.entries) {
    auto rec = files[key(l)].toObject();
    for (const auto &field : {"original", "previous", "after"})
      validate(rec[field].toObject());
    if (rec["after"].toObject() == absent())
      fail("Missing target launcher");
  }
}
void check(const Scope &scope, const QString &home, const QJsonObject &files,
           const QString &source, const QString &dest) {
  for (const auto &l : scope.entries) {
    auto k = key(l);
    auto rec = files[k].toObject(), current = read(path(home, k));
    if (current != rec[source].toObject() && current != rec[dest].toObject())
      fail("Launcher edited elsewhere: " + k);
  }
}
void finish(const Scope &scope, const QString &home, QJsonObject j) {
  auto files = j.value("files").toObject();
  bool undo = j["phase"] == "undoing";
  QString from = undo ? "after" : "previous", to = undo ? "original" : "after";
  check(scope, home, files, from, to);
  for (const auto &l : scope.entries) {
    auto k = key(l), filename = path(home, k);
    auto rec = files[k].toObject(), current = read(filename);
    if (current == rec[to].toObject())
      continue;
    if (current != rec[from].toObject())
      fail("Launcher edited elsewhere: " + k);
    write(filename, rec[to].toObject());
  }
  check(scope, home, files, to, to);
  if (undo)
    write(path(home, scope.record), absent());
  else {
    j["phase"] = "installed";
    save(scope, home, j);
  }
}
int run(const Scope &scope, const QString &home, const QString &op) {
  if (!QFileInfo(home).isDir() || QFileInfo(home).canonicalFilePath() != home ||
      QFileInfo(home).ownerId() != getuid())
    fail("Use an existing, user-owned home directory with a canonical absolute "
         "path");
  auto filename = path(home, scope.record);
  std::unique_ptr<QLockFile> lock;
  if (op != "plan") {
    auto lockPath = path(home, stateDir + "/setup.lock");
    makeParents(lockPath);
    lock = std::make_unique<QLockFile>(lockPath);
    if (!lock->tryLock())
      fail("Another native setup is active");
  }
  auto journalState = read(filename);
  QJsonObject j;
  if (journalState != absent()) {
    j = QJsonDocument::fromJson(bytes(journalState)).object();
    validateJournal(scope, j);
    if (j["phase"] != "installed") {
      if (op != "recover")
        fail("Native launcher transaction interrupted. Run --recover.");
      finish(scope, home, j);
      return 0;
    }
  }
  if (op == "recover")
    return 0;
  if (op == "undo") {
    if (j.isEmpty())
      return 0;
    check(scope, home, j["files"].toObject(), "after", "after");
    j["phase"] = "undoing";
    save(scope, home, j);
    finish(scope, home, j);
    return 0;
  }
  auto files = j.value("files").toObject();
  if (!files.isEmpty())
    check(scope, home, files, "after", "after");
  bool changed = false;
  for (const auto &l : scope.entries) {
    auto k = key(l);
    auto current = read(path(home, k));
    auto original = files.contains(k)
                        ? files[k].toObject()["original"].toObject()
                        : current;
    auto after = desired(l, original);
    if (j.isEmpty() && current != absent() && current != after &&
        !l.id.endsWith("rc.xml") && !l.id.endsWith("globalkeyshortcuts.conf") &&
        l.executable != "doroshell-desktop")
      fail("Existing launcher is owned outside native setup: " + k);
    QTextStream(stdout) << (current == after ? "Keep " : "Register ") << k
                        << Qt::endl;
    files[k] = QJsonObject{
        {"original", original}, {"previous", current}, {"after", after}};
    changed |= current != after;
  }
  if (op == "plan" || (!changed && !j.isEmpty()))
    return 0;
  j = {{"version", 1}, {"phase", "applying"}, {"files", files}};
  save(scope, home, j);
  finish(scope, home, j);
  return 0;
}
} // namespace
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  QCommandLineParser p;
  p.setApplicationDescription(
      "Register the native DoroShell application launchers. Default: preview.");
  p.addHelpOption();
  p.addOption(
      {"input", "Register the combined pointer page and initialize existing "
                "choices or the flat-profile default at login."});
  p.addOption(
      {"packages",
       "Show the Arch/CachyOS prerequisites for the complete native build."});
  p.addOption(
      {"desktop", "Stage the native wallpaper desktop for next login."});
  p.addOption(
      {"session",
       "Set up Openbox snapping, Print, Alt+F1, and next-login services."});
  p.addOption({"scope","Stage one group of launchers or bindings.","name"});
  p.addOption({"home", "Target user home.", "path", QDir::homePath()});
  for (auto v : {"plan", "apply", "undo", "recover"})
    p.addOption(
        {v, QString("Perform %1 on the native launcher registration.").arg(v)});
  p.process(app);
  if (p.isSet("packages")) {
    if (app.arguments().size() != 2)
      p.showHelp(2);
    QTextStream out(stdout);
    out << "Build and desktop prerequisites on Arch-based LXQt systems:\nsudo pacman -Syu --needed";
    for (const auto &package : doro::packages::all)
      out << " " << QString::fromUtf8(package.name);
    out << Qt::endl;
    return 0;
  }
  QStringList selected;
  for (auto v : {"plan", "apply", "undo", "recover"})
    if (p.isSet(v))
      selected << v;
  if (selected.size() > 1 || !p.positionalArguments().isEmpty() ||
      (int(p.isSet("desktop")) + int(p.isSet("session")) +
           int(p.isSet("input")) + int(p.isSet("scope")) >
       1))
    p.showHelp(2);
  try {
    std::initializer_list<std::pair<QString,Scope>> scopes{
        {"session", {session, stateDir + "/session.json"}},
        {"desktop", {desktop, stateDir + "/desktop.json"}},
        {"input", {inputPage, stateDir + "/input.json"}}};
    if (p.isSet("scope")) {
      auto print = session.at(1), start = print;
      print.executable = "doroshell-screenshot";
      print.option = "print-only";
      start.option = "start-only";
      const QMap<QString,QList<Launcher>> groups{
        {"menu-entries",launchers.mid(0,3)},{"clipboard-entry",{launchers.at(3)}},
        {"screenshot-entry",{launchers.at(4)}},{"recent",{session.at(3)}},
        {"snap",{session.at(0),session.at(2)}},{"print-key",{print}},{"start-key",{start}}};
      auto name=p.value("scope");
      if (!groups.contains(name)) fail("Unknown setup group: "+name);
      return run({groups.value(name),stateDir+"/"+name+".json"}, QDir::cleanPath(p.value("home")),selected.value(0,"plan"));
    }
    Scope scope{launchers, receipt};
    for (const auto &[name, item] : scopes) {
      if (p.isSet(name))
        return run(item, QDir::cleanPath(p.value("home")),
                   selected.value(0, "plan"));
    }
    return run(scope, QDir::cleanPath(p.value("home")),
               selected.value(0, "plan"));
  } catch (const std::exception &e) {
    QTextStream(stderr) << e.what() << Qt::endl;
    return 1;
  }
}
