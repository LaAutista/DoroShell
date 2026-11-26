// SPDX-License-Identifier: GPL-2.0-or-later
#include "../setup/files.hpp"
#include <QCoreApplication>
#include <QDateTime>
#include <QJsonArray>
#include <QJsonDocument>
#include <QLockFile>
#include <QStandardPaths>
#include <QTextStream>
using namespace doro_files;
namespace {
QString status() {
  QStringList active;
  auto runtime = qEnvironmentVariable("XDG_RUNTIME_DIR");
  if (runtime.startsWith('/')) {
    for (const auto &fi : QDir(runtime).entryInfoList(
             {"doroshell-wallpaper-*.json"}, QDir::Files | QDir::NoSymLinks)) {
      auto age = fi.lastModified().msecsTo(QDateTime::currentDateTime());
      if (age < 0 || age > 5000)
        continue;
      QFile f(fi.absoluteFilePath());
      if (!f.open(QIODevice::ReadOnly) || f.size() > 65536)
        continue;
      auto record = QJsonDocument::fromJson(f.readAll()).object();
      auto pid = record["pid"].toInteger(-1);
      auto binary = QFileInfo(record["binary"].toString()).canonicalFilePath();
      if (pid <= 0 || binary.isEmpty() ||
          QFileInfo(QString("/proc/%1/exe").arg(pid)).canonicalFilePath() !=
              binary ||
          record["display"] != qEnvironmentVariable("DISPLAY"))
        continue;
      QString activity =
          record["playing"].toBool()
              ? QStringLiteral("playing")
              : record["reasons"].toVariant().toStringList().join(", ");
      if (!record["error"].toString().isEmpty())
        activity += " — " + record["error"].toString();
      active << fi.completeBaseName() + ": " + activity;
    }
  }
  if (!active.isEmpty())
    return "Native wallpaper renderer active\n" + active.join('\n');
  auto base = QDir::homePath() + "/.local/state/";
  if (QFile::exists(base + "doroshell/wallpaper.json") ||
      QFile::exists(base + "doroshell-native/desktop.json"))
    return "Staged for next desktop startup. Current desktop animation is not "
           "active.";
  return "No staged wallpaper desktop or active renderer was found.";
}
void change(const QString &action) {
  auto root =
      QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation);
  if (!root.startsWith('/') || QDir::cleanPath(root) != root)
    fail("Invalid config directory");
  auto name = path(root, "doroshell/wallpaper.json");
  makeParents(name);
  QLockFile lock(name + ".lock");
  if (!lock.tryLock(0))
    fail("Wallpaper settings are busy");
  auto current = read(name);
  QJsonObject values;
  if (current != absent()) {
    auto doc = QJsonDocument::fromJson(bytes(current));
    if (!doc.isObject())
      fail("Cannot read wallpaper settings");
    values = doc.object();
  }
  QJsonObject defaults{
      {"enabled", false}, {"file", ""},      {"fit", "crop"},
      {"monitor", "all"}, {"fps", 30},       {"muted", true},
      {"volume", 100},    {"paused", false}, {"pause_fullscreen", true},
      {"generation", 0}};
  for (auto it = defaults.begin(); it != defaults.end(); ++it) {
    if (!values.contains(it.key()))
      values[it.key()] = it.value();
    else if (values[it.key()].type() != it.value().type())
      fail("Invalid wallpaper setting: " + it.key());
  }
  if (action == "off")
    values["enabled"] = false;
  else
    values["paused"] = action == "pause";
  const auto media = values["file"].toString();
  auto fps = values["fps"].toInt(-1), volume = values["volume"].toInt(-1);
  if (!QStringList{"fit", "crop", "stretch"}.contains(
          values["fit"].toString()) ||
      !QList<int>{15, 30, 60}.contains(fps) || volume < 0 || volume > 100 ||
      values["generation"].toInteger(-1) < 0 ||
      (values["enabled"].toBool() &&
       (!QFileInfo(media).isAbsolute() || !QFileInfo(media).isFile())))
    fail("Invalid wallpaper settings");
  if (read(name) != current)
    fail("Wallpaper settings changed elsewhere");
  atomic(name, QJsonDocument(values).toJson(), 0600);
}
} // namespace
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  try {
    auto args = app.arguments().mid(1);
    if (args.size() > 1)
      fail("Expected gui, off, pause, resume or status");
    auto action = args.value(0, "gui");
    if (action == "--help" || action == "-h") {
      QTextStream(stdout)
          << "doroshell-wallpaper [gui|off|pause|resume|status]\n";
      return 0;
    }
    if (action == "gui") {
      auto exe = QFile::encodeName(app.applicationDirPath() + "/pcmanfm-qt");
      execl(exe.constData(), exe.constData(), "--profile", "lxqt",
            "--desktop-pref=general", nullptr);
      fail("Cannot launch the native desktop preferences");
    } else if (action == "status")
      QTextStream(stdout) << status() << '\n';
    else if (QStringList{"pause", "resume", "off"}.contains(action))
      change(action);
    else
      fail("Expected gui, off, pause, resume or status");
  } catch (const std::exception &e) {
    QTextStream(stderr) << e.what() << '\n';
    return 1;
  }
  return 0;
}
