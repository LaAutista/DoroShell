// SPDX-License-Identifier: GPL-2.0-or-later
#include "../setup/files.hpp"
#include <QtCore>
using namespace doro_files;
namespace {
void check(bool x, const QString &m) {
  if (!x)
    fail(m);
}
void exercise(const QString &program) {
  QTemporaryDir tmp;
  QString home = tmp.filePath("home"), bin = tmp.filePath("bin");
  check(QDir().mkpath(home) && QDir().mkpath(bin),
        "Cannot create test directories");
  check(QFile::copy(program, bin + "/doroshell-modules"),
        "Cannot copy module helper");
  for (auto cmd : {"doroshell-start", "doroshell-clipboard"})
    check(QFile::copy("/usr/bin/true", bin + '/' + cmd),
          "Cannot stage fixture");
  auto call = [&](QString op, QString name, QStringList extra = QStringList{},
                  bool ok = true) {
    QProcess p;
    p.setProcessChannelMode(QProcess::MergedChannels);
    p.start(bin + "/doroshell-modules",
            QStringList{name, "--home", home, "--" + op} + extra);
    check(p.waitForFinished(5000) && p.exitStatus() == QProcess::NormalExit,
          "Unexpected process exit");
    auto out = p.readAll();
    if ((p.exitCode() == 0) != ok)
      fail("Unexpected status for " + name + " " + op + ": " +
           QString::fromUtf8(out));
    return out;
  };
  auto file = [&](QString name) { return home + '/' + name; };
  auto put = [&](QString name, QByteArray data, int mode = 0640) {
    atomic(file(name), data, mode);
  };
  auto contents = [&](QString name) { return bytes(read(file(name))); };
  QString xml = ".config/openbox/rc.xml",
          panel = ".config/doroshell/panel.conf",
          stock = ".config/lxqt/panel.conf",
          key = ".config/lxqt/globalkeyshortcuts.conf",
          mime = ".config/mimeapps.list",
          lxqtMime = ".config/lxqt-mimeapps.list",
          glass = ".config/doroshell/wallpaper-glass.json",
          state = ".local/state/doroshell-native/",
          receipt = state + "modules/";
  auto base = QByteArray(
      "<openbox_config><!-- <number>96</number> "
      "--><desktops><number>4</number></desktops></openbox_config>\n");
  put(xml, base);
  auto original = read(file(xml));
  call("plan", "single-desktop");
  check(!QFileInfo::exists(file(receipt)) && read(file(xml)) == original,
        "Plan changed home");
  call("apply", "single-desktop", {"--claim", "build-A"});
  check(contents(xml).contains("<number>1</number><firstdesk>1</firstdesk>"),
        "Wrong Openbox settings");
  call("undo", "single-desktop", {"--claim", "build-B"});
  check(QFile::exists(file(receipt + "single-desktop.json")),
        "Another deployment removed setting");
  call("apply", "single-desktop");
  call("undo", "single-desktop", {"--claim", "build-A"});
  check(read(file(xml)) == original, "Openbox bytes/mode did not restore");
  auto claim = QStringList{"--claim", "build-A"};
  call("resume", "single-desktop", claim);
  check(!QFile::exists(file(receipt + "single-desktop.json")),
        "Resume resurrected an unowned option");
  call("apply", "single-desktop", claim);
  call("suspend", "single-desktop", {"--claim", "other"});
  check(contents(xml).contains("<number>1</number>"),
        "Another claim suspended the option");
  put(xml, contents(xml) + "<!-- Personal -->\n");
  call("suspend", "single-desktop", claim);
  call("suspend", "single-desktop", claim);
  auto suspended =
      QJsonDocument::fromJson(call("status", "single-desktop")).object();
  check(suspended["suspended"] == true && suspended["enabled"] == true &&
            suspended["pending"] == false && suspended["claim"] == "build-A",
        "Suspended ownership lost");
  check(contents(xml).contains("<number>4</number>") &&
            contents(xml).contains("Personal"),
        "Suspension lost personal settings");
  auto baseWithSnap = contents(xml).replace(
      "</openbox_config>",
      "<keyboard><!-- Added snapping --></keyboard></openbox_config>");
  put(xml, baseWithSnap, 0600);
  call("resume", "single-desktop", claim);
  call("resume", "single-desktop", claim);
  check(contents(xml).contains("Added snapping") &&
            contents(xml).contains("<number>1</number>"),
        "Resume damaged new core layer");
  call("undo", "single-desktop", claim);
  check(contents(xml) == baseWithSnap && read(file(xml))["mode"] == 0600,
        "Removing option did not restore exact new core layer");
  put(xml, base);
  call("apply", "single-desktop", claim);
  call("suspend", "single-desktop", claim);
  put(xml, base + "<!-- Core changed while suspended -->\n");
  call("undo", "single-desktop", claim);
  check(!QFile::exists(file(receipt + "single-desktop.json")) &&
            contents(xml).contains("Core changed while suspended"),
        "Undo re-applied a suspended option");
  put(xml, QByteArray(base).replace(
               "</openbox_config>",
               "<applications><application><desktop>3</desktop></application></"
               "applications></openbox_config>"));
  call("apply", "single-desktop", {}, false);
  put(xml, base);
  auto namespaced =
      QByteArray("<ob:openbox_config "
                 "xmlns:ob=\"urn:openbox\"><ob:desktops><ob:number>3</"
                 "ob:number></ob:desktops></ob:openbox_config>");
  put(xml, namespaced);
  call("apply", "single-desktop");
  check(contents(xml).contains("<ob:firstdesk>1</ob:firstdesk>"),
        "Wrong namespace for the inserted Openbox setting");
  call("undo", "single-desktop");
  check(contents(xml) == namespaced, "Namespaced Openbox rollback");
  put(mime, "[Default "
            "Applications]\ntext/plain=old.desktop;\ninode/"
            "directory=files.desktop;\n");
  put(lxqtMime, "[Default Applications]\r\ntext/plain=old.desktop;\r\n");
  auto mimeStart = read(file(mime)), lxStart = read(file(lxqtMime));
  call("apply", "dolphin");
  call("apply", "kate");
  call("undo", "kate");
  call("undo", "dolphin");
  check(read(file(mime)) == mimeStart && read(file(lxqtMime)) == lxStart,
        "Overlapping modules could not undo in reverse");
  call("apply", "kate", claim);
  for (auto operation : {"suspend", "resume"}) {
    call(operation, "kate", claim);
    auto record =
        QJsonDocument::fromJson(contents(receipt + "kate.json")).object();
    record["phase"] =
        QString(operation) == "suspend" ? "suspending" : "resuming";
    put(receipt + "kate.json", QJsonDocument(record).toJson(), 0600);
    auto entry = record["files"].toObject()[mime].toObject();
    write(file(mime), entry["from"].toObject());
    call("recover", "kate", {"--claim", "foreign"});
    check(read(file(mime)) == entry["from"], "Foreign recovery wrote settings");
    call("recover", "kate", claim);
    check(read(file(mime)) == entry["to"] &&
              QJsonDocument::fromJson(call("status", "kate"))
                      .object()["pending"] == false,
          "Layer recovery incomplete");
  }
  call("undo", "kate", claim);
  call("apply", "kate");
  auto own = QJsonDocument::fromJson(contents(receipt + "kate.json")).object();
  own["phase"] = "applying";
  put(receipt + "kate.json", QJsonDocument(own).toJson(), 0600);
  write(file(mime), mimeStart);
  call("apply", "kate", {}, false);
  call("recover", "kate");
  QByteArray expected = contents(mime);
  put(mime, expected + "[Personal]\nfoo=yes\n");
  auto lxInstalled = contents(lxqtMime);
  put(lxqtMime,
      QByteArray(lxInstalled).replace("org.kde.kate", "org.personal"));
  call("undo", "kate", {}, false);
  check(contents(mime).contains("org.kde.kate"),
        "File changed on failed undo preflight");
  put(lxqtMime, lxInstalled);
  call("undo", "kate");
  check(contents(mime).contains("foo=yes") &&
            contents(mime).contains("text/plain=old.desktop;"),
        "Lost personal edits");
  put(glass, "{\"version\":1,\"enabled\":false,\"personal\":\"on\"}");
  auto glassBase = read(file(glass));
  call("apply", "wallpaper-glass");
  check(QJsonDocument::fromJson(contents(glass)).object()["enabled"] == true,
        "Wallpaper glass not enabled");
  call("undo", "wallpaper-glass");
  check(read(file(glass)) == glassBase, "Glass rollback differs");
  if (QFileInfo::exists("/usr/share/color-schemes/BreezeDark.colors"))
    for (auto m : {"kate-dark", "dolphin-dark"}) {
      call("apply", m);
      call("undo", m);
    }
  put(stock, "[panel1]\nplugins=dockbarx,clock\n[clock]\ntype=worldclock\n");
  auto stockBase = read(file(stock));
  call("apply", "taskbar", {"--taskbar-style", "standard"});
  check(contents(stock).contains("buttonStyle=IconText"),
        "No standard taskbar");
  call("undo", "taskbar");
  check(read(file(stock)) == stockBase, "Stock taskbar changed");
  put(panel, "[panel2]\nplugins=doroshellTasks,statusnotifier,clock\niconSize="
             "26\n[doroshellTasks]\ntype=taskbar\nbuttonWidth=38\n");
  auto panelBase = read(file(panel));
  call("apply", "taskbar-size", {}, false);
  put(state + "panel.json", "{\"phase\":\"installed\"}", 0600);
  call("apply", "taskbar-size", claim + QStringList{"--taskbar-size", "large"});
  check(contents(panel).contains("iconSize=36") &&
            contents(panel).contains("buttonWidth=56"),
        "Wrong task button size");
  call("suspend", "taskbar-size", claim);
  call("resume", "taskbar-size", claim);
  check(contents(panel).contains("buttonWidth=56"),
        "Resume lost the selected taskbar size");
  call("apply", "taskbar-size", {"--taskbar-size", "small"});
  call("apply", "taskbar-drag");
  put(".local/share/applications/doroshell-clipboard.desktop",
      "[Desktop Entry]\nExec=doroshell-clipboard --show\n", 0644);
  call("apply", "clipboard");
  check(
      contents(panel).contains("doroshellTasks, doroClipboard, statusnotifier"),
      "Clipboard button position");
  check(contents(".config/autostart/doroshell-clipboard.desktop")
            .contains("OnlyShowIn=LXQt;"),
        "Clipboard autostart missing");
  call("undo", "clipboard");
  call("undo", "taskbar-size");
  check(read(file(panel)) == panelBase, "Panel modules lost profile");
  put(key,
      "[Alt%2BF1.2]\nEnabled=true\nExec=personal\n[Print.1]\nExec=other\n");
  auto keyBase = read(file(key));
  call("apply", "start-shortcut", {}, false);
  call("apply", "start-shortcut", {"--replace-start-shortcut"});
  check(contents(key).contains("Exec=other"), "Changed Print shortcut");
  call("undo", "start-shortcut");
  check(read(file(key)) == keyBase, "Alt+F1 restore differs");
  auto distro = tmp.filePath("distro");
  atomic(distro + "/lxqt/globalkeyshortcuts.conf",
         "[Print.7]\nExec=personal-default\n", 0644);
  qputenv("XDG_CONFIG_DIRS", distro.toUtf8());
  QFile::remove(file(key));
  call("apply", "start-shortcut");
  check(contents(key).contains("Exec=personal-default"),
        "Shadowed inherited shortcuts");
  call("undo", "start-shortcut");
  check(!QFile::exists(file(key)), "Did not restore inherited shortcuts");
  put(".local/state/doroshell/kate.json", "{}", 0600);
  call("apply", "kate", {}, false);
  auto status = QJsonDocument::fromJson(call("status", "kate")).object();
  check(status["owner"] == "rc2", "Missing RC2 ownership");
  call("apply", "kate", {"--claim", "build-C"});
  check(!QFile::exists(file(receipt + "kate.json")),
        "Claimed existing RC2 scope");
}
} // namespace
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  try {
    exercise(app.arguments().at(1));
  } catch (const std::exception &e) {
    QTextStream(stderr) << e.what() << '\n';
    return 1;
  }
  return 0;
}
