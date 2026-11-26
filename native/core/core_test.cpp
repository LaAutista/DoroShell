// SPDX-License-Identifier: GPL-2.0-or-later
#include "../setup/files.hpp"
#include <QCoreApplication>
#include <QDeadlineTimer>
#include <QJsonArray>
#include <QJsonDocument>
#include <QProcess>
#include <QTemporaryDir>
#include <QTextStream>
#include <QThread>

using namespace doro_files;
namespace {
void expect(bool ok, const QString &message) {
  if (!ok)
    fail(message);
}
void command(const QString &program, const QStringList &args,
             const QString &home, bool success = true) {
  QProcess p;
  auto env = QProcessEnvironment::systemEnvironment();
  for (auto key : {"DISPLAY", "WAYLAND_DISPLAY", "DBUS_SESSION_BUS_ADDRESS",
                   "XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME"})
    env.remove(key);
  env.insert("HOME", home);
  env.insert("XDG_CONFIG_DIRS", "/etc/xdg");
  p.setProcessEnvironment(env);
  p.start(program, args);
  expect(p.waitForStarted() && p.waitForFinished(60000) &&
             p.exitStatus() == QProcess::NormalExit,
         "Subprocess failed: " + program);
  if ((p.exitCode() == 0) != success)
    fail(program + " " + args.join(' ') + "\n" + p.readAllStandardError() +
         p.readAllStandardOutput());
}
} // namespace

int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  try {
    auto args = app.arguments();
    if (args.size() != 4)
      fail("Expected core binary and runtime path");
    QTemporaryDir temp;
    if (!temp.isValid())
      fail("Cannot create isolated test home");
    auto home = temp.filePath("home"), bin = temp.filePath("bin");
    QDir().mkpath(home);
    QDir().mkpath(bin);
    for (const auto &exe : QDir(args[2] + "/bin").entryInfoList(QDir::Files)) {
      if (QStringList{"doroshell-core", "doroshell-maintenance"}.contains(
              exe.fileName()))
        continue;
      // Hardlinks keep the executable's own canonical location inside the test
      // bundle.
      auto dest = bin + "/" + exe.fileName();
      if (::link(QFile::encodeName(exe.absoluteFilePath()),
                 QFile::encodeName(dest))) {
        expect(QFile::copy(exe.absoluteFilePath(), dest),
               "Cannot copy " + dest);
      }
    }
    expect(QFile::link(args[2] + "/share", temp.filePath("share")),
           "Cannot link resources");
    auto core = bin + "/doroshell-core";
    expect(QFile::copy(args[1], core), "Cannot copy core");
    auto call = [&](QString op, bool success = true) {
      command(core, {"--home", home, op}, home, success);
    };
    auto record = home + "/.local/state/doroshell-native/core.json";
    auto rc = home + "/.config/openbox/rc.xml";
    auto pref = home + "/.config/doroshell/input-preferences.json";
    atomic(pref, R"({"version":1,"rules":{},"receipts":{},"all_mice":false})",
           0600);
    auto original = read(pref);
    command(core, {"--plan", "--panel", "not-a-panel"}, home, false);
    command(core, {"--remove", "--panel", "panel2"}, home, false);
    command(core, {"--apply", "--panel", "panel999"}, home, false);
    expect(!QFileInfo::exists(record), "Unknown panel claimed installation");
    call("--refresh", false);
    call("--plan");
    expect(!QFileInfo::exists(record) && !QFileInfo::exists(rc),
           "Plan wrote files");
    // The alias target is never run. Withhold the input GUI until recovery.
    expect(QFile::link(core, bin + "/doroshell-maintenance"),
           "Cannot create alias target fixture");
    expect(
        QFile::rename(bin + "/doroshell-config-input", bin + "/input-on-hold"),
        "Cannot withhold input GUI");
    command(core, {"--apply", "--panel", "panel1"}, home, false);
    command(core, {"--apply", "--panel", "panel2"}, home, false);
    expect(QJsonDocument::fromJson(bytes(read(record))).object()["panel"] ==
               "panel1",
           "Pending installation lost its panel selection");
    expect(
        QFileInfo::exists(rc) &&
            QFileInfo::exists(home + "/.config/autostart/lxqt-desktop.desktop"),
        "Did not reach final stage");
    // Exercise recovery using the real component helpers. Alias target is never
    // run in this test.
    expect(
        QFile::rename(bin + "/input-on-hold", bin + "/doroshell-config-input"),
        "Cannot restore input GUI");
    call("--recover");
    auto installed = read(record);
    call("--apply");
    expect(read(record) == installed && read(pref) == original,
           "Repeat changed core receipt or input choices");
    expect(QFileInfo(home + "/.local/bin/doroshell-update").isSymLink(),
           "Missing update alias");
    // Simulate an updater swapping one desktop component at the same absolute
    // path. Replace our hardlink atomically to leave the bundle untouched.
    auto desktopEntry = home + "/.config/autostart/lxqt-desktop.desktop";
    // An already installed native build pointed this file directly at the
    // patched LXQt program. Its managed receipt must upgrade to the launcher.
    auto inputKey =
        QString(".local/share/applications/lxqt-config-input.desktop");
    auto inputEntry = home + '/' + inputKey;
    auto selectedInput = read(inputEntry);
    auto nativeInput = bytes(selectedInput);
    expect(nativeInput.contains("/doroshell-config-input"),
           "Fresh input entry omitted the checked launcher");
    auto oldInput = nativeInput;
    oldInput.replace("/doroshell-config-input", "/lxqt-config-input");
    atomic(inputEntry, oldInput, selectedInput["mode"].toInt());
    auto inputReceipt = home + "/.local/state/doroshell-native/input.json";
    auto inputJournal =
        QJsonDocument::fromJson(bytes(read(inputReceipt))).object();
    auto managed = inputJournal["files"].toObject();
    auto entryRecord = managed[inputKey].toObject();
    entryRecord["after"] = read(inputEntry);
    managed[inputKey] = entryRecord;
    inputJournal["files"] = managed;
    atomic(inputReceipt, QJsonDocument(inputJournal).toJson(), 0600);
    auto previousDesktop = read(desktopEntry);
    atomic(bin + "/doroshell-display", "new build digest fixture", 0700);
    call("--refresh");
    expect(read(inputEntry) == selectedInput,
           "Owned older input entry did not upgrade");
    expect(read(desktopEntry) != previousDesktop,
           "Update kept obsolete desktop executable digests");
    auto underTest =
        home + "/.local/share/applications/doroshell-network.desktop";
    auto beforeEdit = read(underTest);
    atomic(underTest, bytes(beforeEdit) + "# personal\n", 0600);
    call("--remove", false);
    expect(bytes(read(underTest)).endsWith("# personal\n"),
           "Removal overwrote personal edit");
    write(underTest, beforeEdit);
    call("--recover");
    expect(!QFileInfo::exists(rc) && !QFileInfo::exists(record) &&
               read(pref) == original,
           "Removal failed to restore fresh home");
    expect(!QFileInfo(home + "/.local/bin/doroshell-update").isSymLink(),
           "Update alias retained after removal");

    // A palette managed outside the core keeps its own lifecycle and original
    // file mode.
    QFile stock("/etc/xdg/openbox/rc.xml");
    expect(stock.open(QIODevice::ReadOnly), "Missing Openbox prerequisite");
    atomic(rc, stock.readAll(), 0640);
    command(bin + "/doroshell-theme", {"--apply", "heretic"}, home);
    auto theme = home + "/.local/state/doroshell/theme.json";
    auto existingTheme = read(theme), existingRc = read(rc);
    call("--apply");
    call("--remove");
    expect(read(theme) == existingTheme && read(rc) == existingRc,
           "Independent theme or Openbox config changed");
    // An explicit screenshot-only install must not claim the menu, snapping,
    // another keyboard shortcut, a display, or the update alias.
    {
      QTemporaryDir profile;
      const auto h = profile.path();
      auto shortcuts = h + "/.config/lxqt/globalkeyshortcuts.conf";
      auto openbox = h + "/.config/openbox/rc.xml";
      auto shortBefore =
          QByteArray("[Alt%2BF1.1]\nExec=personal-menu\nEnabled=true\n");
      atomic(shortcuts, shortBefore, 0640);
      const auto originalShortcuts = read(shortcuts);
      command(core, {"--apply", "--modules", "screenshots"}, h);
      expect(bytes(read(shortcuts)).contains("personal-menu") &&
                 bytes(read(shortcuts)).contains("DoroShell screenshot") &&
                 !QFileInfo::exists(openbox) &&
                 !QFileInfo::exists(h + "/.local/bin/doroshell-update") &&
                 !QFileInfo::exists(
                     h + "/.local/share/applications/lxqt-comfort.desktop") &&
                 QFileInfo::exists(
                     h +
                     "/.local/share/applications/doroshell-screenshot.desktop"),
             "Screenshot-only install leaked an unrelated stage");
      auto rec = h + "/.local/state/doroshell-native/core.json";
      auto saved = read(rec);
      command(core, {"--apply"}, h);
      expect(read(rec) == saved,
             "Implicit update expanded a partial selection");
      command(core, {"--refresh", "--modules", "menu"}, h);
      expect(QFileInfo::exists(
                 h + "/.config/autostart/doroshell-recent-programs.desktop") &&
                 bytes(read(shortcuts)).contains("personal-menu") &&
                 !QFileInfo::exists(openbox),
             "Adding the menu installed unrelated bindings");
      expect(QFile::rename(bin + "/doroshell-snap", bin + "/snap-on-hold"),
             "Cannot withhold snap");
      command(core, {"--refresh", "--modules", "snapping"}, h, false);
      expect(QJsonDocument::fromJson(bytes(read(rec))).object()["phase"] ==
                 "extend",
             "Extension lost its pending state");
      command(core, {"--refresh", "--modules", "cursor"}, h, false);
      expect(QFile::rename(bin + "/snap-on-hold", bin + "/doroshell-snap"),
             "Cannot restore snap binary");
      command(core, {"--refresh", "--modules", "snapping"}, h);
      expect(bytes(read(openbox)).contains("DoroShell native snapping"),
             "Recovery forgot pending snapping extension");
      command(core, {"--apply", "--modules", "theme", "maintenance"}, h);
      expect(QFileInfo(h + "/.local/bin/doroshell-update").isSymLink(),
             "Missing selected maintenance");
      command(core, {"--remove"}, h);
      expect(read(shortcuts) == originalShortcuts &&
                 !QFileInfo::exists(openbox) && !QFileInfo::exists(rec),
             "Removing multiple additions lost original contents or mode");
    }
    {
      QTemporaryDir profile;
      auto h = profile.path();
      command(core, {"--apply", "--modules", "none"}, h);
      auto rec = h + "/.local/state/doroshell-native/core.json";
      expect(QJsonDocument::fromJson(bytes(read(rec)))
                 .object()["steps"]
                 .toArray()
                 .isEmpty(),
             "Optional-only core created unrelated settings");
      command(core, {"--apply", "--modules", "clipboard"}, h);
      expect(
          QFileInfo::exists(h + "/.config/doroshell/panel.conf") &&
              QFileInfo::exists(
                  h +
                  "/.local/share/applications/doroshell-clipboard.desktop") &&
              QFileInfo::exists(
                  h + "/.local/share/applications/lxqt-comfort.desktop") &&
              !QFileInfo::exists(
                  h +
                  "/.local/share/applications/doroshell-screenshot.desktop") &&
              !QFileInfo::exists(h + "/.config/openbox/rc.xml"),
          "Clipboard dependency expansion failed");
      command(core, {"--remove"}, h);
    }
    {
      // A v1 receipt from the combined helper must retain exact ownership.
      QTemporaryDir profile;
      auto h = profile.path();
      command(bin + "/doroshell-setup", {"--apply"}, h);
      command(bin + "/doroshell-setup", {"--session", "--apply"}, h);
      auto rec = h + "/.local/state/doroshell-native/core.json";
      QJsonObject old{{"version", 1},
                      {"next", 10},
                      {"active", false},
                      {"panel", ""},
                      {"phase", "installed"},
                      {"owned", QJsonArray{false, false, false, true, false,
                                           false, true, false, false, false}},
                      {"inputPrefsAbsent", true},
                      {"preset", "windows"},
                      {"seed", absent()}};
      atomic(rec, QJsonDocument(old).toJson(), 0600);
      command(core, {"--apply", "--modules", "screenshots"}, h);
      expect(!QFileInfo::exists(
                 h + "/.local/state/doroshell-native/print-key.json"),
             "Old aggregate owned a duplicate new stage");
      command(core, {"--remove"}, h);
      expect(!QFileInfo::exists(h + "/.config/lxqt/globalkeyshortcuts.conf") &&
                 !QFileInfo::exists(
                     h +
                     "/.local/share/applications/doroshell-screenshot.desktop"),
             "Old aggregate failed to unwind");
    }
    {
      QTemporaryDir partial;
      auto h = partial.path();
      const auto rc = h + "/.config/openbox/rc.xml";
      const auto receipt = h + "/.local/state/doroshell-native/core.json";
      command(core, {"--apply"}, h);
      // Snapping was installed over the theme's Openbox XML. Removal must
      // rebase snapping before it can later restore its own baseline.
      expect(QFile::rename(bin + "/doroshell-snap", bin + "/snap-on-hold"),
             "Cannot interrupt shortcut reapplication");
      command(core, {"--remove", "--modules", "theme"}, h, false);
      expect(QFileInfo::exists(receipt) &&
                 !QFileInfo::exists(h + "/.local/state/doroshell/theme.json"),
             "Test did not interrupt the retained snapping reapplication");
      expect(QFile::rename(bin + "/snap-on-hold", bin + "/doroshell-snap"),
             "Cannot restore reapply fixture");
      command(core, {"--recover"}, h);
      expect(!QFileInfo::exists(h + "/.local/state/doroshell/theme.json") &&
                 bytes(read(rc)).contains("DoroShell native snapping"),
             "Removing the theme lost snapping");
      command(core, {"--remove", "--modules", "snapping"}, h);
      expect(!QFileInfo::exists(rc),
             "Last owner retained/reintroduced the theme's Openbox file");
      command(core, {"--remove", "--modules", "core"}, h);
      expect(QJsonDocument::fromJson(bytes(read(receipt)))
                 .object()["steps"]
                 .toArray()
                 .isEmpty(),
             "Removing the remaining core retained component ownership");
      command(core, {"--remove"}, h);
      expect(!QFileInfo::exists(receipt),
             "Complete removal retained partial-install anchor");
    }
    {
      QTemporaryDir partial;
      auto h = partial.path();
      auto menu = h + "/.local/share/applications/lxqt-comfort.desktop";
      auto shot = h + "/.local/share/applications/doroshell-screenshot.desktop";
      auto receipt = h + "/.local/state/doroshell-native/core.json";
      command(core,
              {"--apply", "--modules", "menu", "clipboard", "screenshots"}, h);
      command(core, {"--remove", "--modules", "clipboard"}, h);
      expect(QFileInfo::exists(menu) &&
                 !QFileInfo::exists(h + "/.config/doroshell/panel.conf") &&
                 QFileInfo::exists(shot),
             "Removing clipboard lost explicitly installed dependencies");
      auto owned = read(shot);
      atomic(shot, bytes(owned) + "# personal\n", owned["mode"].toInt());
      command(core, {"--remove", "--modules", "screenshots"}, h, false);
      expect(QJsonDocument::fromJson(bytes(read(receipt))).object()["phase"] ==
                     "subset" &&
                 bytes(read(shot)).contains("# personal"),
             "Edited screenshot entry overwritten or removal intent lost");
      command(core, {"--remove", "--modules", "menu"}, h, false);
      write(shot, owned);
      command(core, {"--recover"}, h);
      expect(QFileInfo::exists(menu) && !QFileInfo::exists(shot),
             "Interrupted removal resumed with wrong scope");
      command(core, {"--remove"}, h);
    }
    {
      // Opposite layering: the user subsequently chose a different palette.
      // Removing the lower snapping stage must keep that palette and mode.
      QTemporaryDir partial;
      auto h = partial.path();
      auto config = h + "/.config/openbox/rc.xml";
      QFile base("/etc/xdg/openbox/rc.xml");
      expect(base.open(QIODevice::ReadOnly), "Openbox baseline missing");
      atomic(config, base.readAll(), 0640);
      auto before = read(config);
      command(core, {"--apply", "--modules", "snapping"}, h);
      command(core, {"--apply", "--modules", "theme"}, h);
      command(bin + "/doroshell-theme", {"--apply", "heretic"}, h);
      command(core, {"--remove", "--modules", "snapping"}, h);
      expect(!bytes(read(config)).contains("DoroShell native snapping") &&
                 bytes(read(h + "/.config/doroshell/theme.conf"))
                     .contains("heretic"),
             "Removing an earlier stage reset a newer personal palette choice");
      command(core, {"--remove"}, h);
      expect(read(config) == before,
             "Theme rebasing lost baseline mode or bytes");
    }
    if (!args[3].isEmpty()) {
      QTemporaryDir fresh;
      expect(fresh.isValid(), "Private input home");
      auto h = fresh.path();
      command(core, {"--apply"}, h);
      QProcess server;
      server.start(args[3], {"-displayfd", "1", "-screen", "0", "800x600x24",
                             "-nolisten", "tcp", "-noreset"});
      expect(server.waitForStarted() && server.waitForReadyRead(),
             "Private X11 server failed");
      bool ok = false;
      int id = server.readLine().trimmed().toInt(&ok);
      expect(ok && id >= 0, "Invalid private display");
      auto env = QProcessEnvironment::systemEnvironment();
      env.insert("HOME", h);
      env.insert("DISPLAY", ":" + QString::number(id));
      env.insert("XDG_SESSION_TYPE", "x11");
      env.remove("XAUTHORITY");
      QProcess watcher;
      watcher.setProcessEnvironment(env);
      watcher.start(bin + "/doroshell-input-preferences", {"--first-login"});
      expect(watcher.waitForStarted(), "Private input first login");
      QDeadlineTimer deadline(5000);
      auto prefs = h + "/.config/doroshell/input-preferences.json";
      while (!deadline.hasExpired()) {
        if (QJsonDocument::fromJson(bytes(read(prefs))).object()["startup"] ==
            "installed")
          break;
        QThread::msleep(10);
      }
      expect(
          QFileInfo::exists(h + "/.config/autostart/doroshell-input.desktop"),
          "Watcher was never installed");
      command(core, {"--remove"}, h);
      expect(watcher.waitForFinished(7500) && watcher.exitCode() == 0 &&
                 !QFileInfo::exists(prefs) &&
                 !QFileInfo::exists(
                     h + "/.config/autostart/doroshell-input.desktop"),
             "Post-login core removal left input active");
      server.terminate();
      server.waitForFinished();
    }
    return 0;
  } catch (const std::exception &e) {
    QTextStream(stderr) << e.what() << Qt::endl;
    return 1;
  }
}
