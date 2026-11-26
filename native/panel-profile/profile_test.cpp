// SPDX-License-Identifier: GPL-2.0-or-later
#include "../setup/files.hpp"
#include <QCoreApplication>
#include <QJsonDocument>
#include <QProcess>
#include <QSettings>
#include <QTemporaryDir>
#include <cstdio>

namespace
{
using namespace doro_files;
void require(bool truth, const char *msg)
{
    if (!truth)
        fail(msg);
}
QByteArray loadFile(const QString &path)
{
    QFile f(path);
    require(f.open(QIODevice::ReadOnly), "Fixture file missing");
    return f.readAll();
}
void test(const QString &helper)
{
    QTemporaryDir tmp;
    require(tmp.isValid(), "Cannot create temp directory");
    const QString home = tmp.filePath("test café % home"), defaults = tmp.filePath("xdg");
    const QString binary = tmp.filePath("private-runtime/bin/lxqt-panel");
    require(QDir().mkdir(home), "Cannot create fixture home");
    const QString original = home + "/.config/lxqt/panel.conf", config = home + "/.config/doroshell/panel.conf",
                  desktop = home + "/.config/autostart/lxqt-panel.desktop",
                  journal = home + "/.local/state/doroshell-native/panel.json",
                  legacy = home + "/.local/state/doroshell/native-panel.json",
                  apps = home + "/.local/share/applications";
    const QByteArray example =
        "[Desktop Entry]\nType=Application\nName=Fixture\nExec=/usr/bin/true\nStartupWMClass=Fixture\n";
    const QByteArray ext =
        "[extra]\n; Preserve this spelling and comment.\ntype=spacing\nexample = individual choice\n";
    QByteArray stock =
        "panels=panel1\n\n[panel1]\nplugins=fancymenu,quicklaunch,taskbar,extra,statusnotifier,clock,edge\n"
        "position=Bottom\niconSize=32\n[fancymenu]\ntype=fancymenu\n[taskbar]\ntype=taskbar\n"
        "closeOnMiddleClick=true\n[statusnotifier]\ntype=statusnotifier\nhideList=Bell\n"
        "[clock]\ntype=worldclock\ncustomFormat=HH:mm\n[edge]\ntype=showdesktop\n"
        "[quicklaunch]\ntype=quicklaunch\napps\\size=1\napps\\1\\desktop=" +
        (apps + "/fixture.desktop").toUtf8() + "\n" + ext;
    atomic(defaults + "/lxqt/panel.conf", stock, 0644);
    for (const auto &desktopId : {"fixture.desktop", "doroshell-network.desktop", "lxqt-comfort.desktop"})
        atomic(apps + "/" + desktopId, example, 0644);
    makeParents(binary);
    require(QFile::copy(QCoreApplication::applicationFilePath(), binary), "Cannot create fixture ELF");
    atomic(tmp.filePath("private-runtime/share/doroshell-panel/patches/0016-network-chooser.patch"), "fixture",
           0644);
    QByteArray prior = "[Desktop Entry]\nType=Application\nName=Personal "
                       "panel\nExec=lxqt-panel\nOnlyShowIn=LXQt;\nX-Personal=preserve\n";
    atomic(desktop, prior, 0640);
    auto env = QProcessEnvironment::systemEnvironment();
    env.insert("HOME", home);
    env.insert("XDG_CONFIG_DIRS", defaults);
    for (auto var : {"XDG_CONFIG_HOME", "XDG_STATE_HOME", "XDG_DATA_HOME", "DBUS_SESSION_BUS_ADDRESS",
                     "WAYLAND_DISPLAY", "DISPLAY"})
        env.remove(var);
    env.insert("QT_QPA_PLATFORM", "xcb");
    auto run = [&](QStringList args, int expected = 0) {
        QProcess p;
        p.setProcessEnvironment(env);
        p.setProcessChannelMode(QProcess::MergedChannels);
        p.start(helper, args);
        require(p.waitForFinished(7000), "Native panel profile CLI timed out");
        auto response = p.readAllStandardOutput();
        if (p.exitCode() != expected || p.exitStatus() != QProcess::NormalExit) {
            std::fprintf(stderr, "Unexpected result for %s: %s\n", qPrintable(args.join(" ")),
                         response.constData());
            fail("Unexpected panel CLI status");
        }
        return response;
    };
    auto args = QStringList{"--apply", "--binary", binary};
    run({"--plan", "--binary", binary});
    require(!QFile::exists(journal) && !QFile::exists(config) && !QFile::exists(original) &&
                !QFile::exists(home + "/.local/state/doroshell/native-panel.lock"),
            "Plan wrote files");
    run(args);
    require(!QFile::exists(original), "System-default case materialized a user stock config");
    auto first = loadFile(config), firstJournal = loadFile(journal), afterDesktop = loadFile(desktop);
    require(first.contains(ext) && afterDesktop.contains("X-Personal=preserve") &&
                afterDesktop.contains(" --launch"),
            "Personal settings or autostart fields lost");
    QSettings p(config, QSettings::IniFormat);
    const auto plugins = p.value("panel1/plugins").toStringList();
    require(plugins.first() == "doroshellStart" && plugins.last() == "edge" &&
                plugins.at(plugins.size() - 2) == "clock" && !plugins.contains("fancymenu") &&
                plugins.count("extra") == 1 && plugins.count("doroshellTasks") == 1 &&
                plugins.count("doroshellLegacyTray") == 1 &&
                plugins.indexOf("doroshellLegacyTray") == plugins.indexOf("statusnotifier") + 1 &&
                !plugins.contains("quicklaunch"),
            "Unexpected panel widget list");
    require(p.value("doroshellTasks/type") == "taskbar" && p.value("doroshellTasks/groupingEnabled").toBool() &&
                p.value("doroshellTasks/closeOnMiddleClick").toBool() &&
                p.value("doroshellTasks/doroshellPinned").toStringList() ==
                    QStringList{apps + "/fixture.desktop"} &&
                p.value("statusnotifier/doroshellNetworkButton").toBool() &&
                p.value("statusnotifier/doroshellPopup").toBool() &&
                !p.value("statusnotifier/doroshellCollapseNew").toBool() &&
                p.value("statusnotifier/hideList") == "Bell" && p.value("clock/showDate").toBool() &&
                p.value("clock/doroshellTwoLine").toBool() && p.value("clock/customFormat") == "HH:mm" &&
                p.value("edge/doroshellEdge").toBool() && p.value("panel1/iconSize").toInt() == 32,
            "Lost selected widget behavior, custom format or pinned apps");
    run(args);
    require(loadFile(config) == first && loadFile(journal) == firstJournal && loadFile(desktop) == afterDesktop,
            "Repeated stage rewrote state");
    // Exercise the executable selected by the staged autostart using a harmless ELF fixture.
    require(run({"--launch"}).trimmed() == config.toUtf8(),
            "Staged panel did not receive its isolated --config");

    auto installed = QJsonDocument::fromJson(firstJournal).object();
    auto rec = installed.value("files").toObject();
    auto interrupt = [&](QString phase) {
        auto j = installed;
        j["phase"] = phase;
        atomic(journal, QJsonDocument(j).toJson(), 0600);
    };
    for (int mask = 0; mask < 4; ++mask) {
        interrupt("applying");
        write(config,
              rec[".config/doroshell/panel.conf"].toObject()[(mask & 1) ? "after" : "original"].toObject());
        write(desktop, rec[".config/autostart/lxqt-panel.desktop"]
                           .toObject()[(mask & 2) ? "after" : "original"]
                           .toObject());
        run({"--apply"}, 1);
        run({"--recover"});
        require(loadFile(config) == first && loadFile(desktop) == afterDesktop,
                "Interrupted staging did not recover");
    }
    auto edited = first + "\n# pin was moved\n";
    atomic(config, edited, 0600);
    run(args);
    require(loadFile(config) == edited, "Repeat staging discarded personalized pins");
    run({"--undo"}, 1);
    require(loadFile(desktop) == afterDesktop && loadFile(config) == edited, "Failed undo mutated files");
    run({"--undo", "--keep-panel-edits"});
    auto archives =
        QDir(home + "/.local/state/doroshell-native").entryList({"panel-edited-*.conf"}, QDir::Files);
    require(archives.size() == 1 &&
                loadFile(home + "/.local/state/doroshell-native/" + archives.first()) == edited &&
                loadFile(desktop) == prior && read(desktop)["mode"].toInt() == 0640 && !QFile::exists(config) &&
                !QFile::exists(journal),
            "Undo lost edited profile, original autostart or mode");

    for (int mask = 0; mask < 4; ++mask) {
        run(args);
        interrupt("undoing");
        write(config,
              rec[".config/doroshell/panel.conf"].toObject()[(mask & 1) ? "after" : "original"].toObject());
        write(desktop, rec[".config/autostart/lxqt-panel.desktop"]
                           .toObject()[(mask & 2) ? "after" : "original"]
                           .toObject());
        run({"--recover"});
        require(!QFile::exists(journal) && !QFile::exists(config) && loadFile(desktop) == prior,
                "Interrupted undo did not recover");
    }
    // A custom Quick Launch command stays in its widget; an existing tray is reused.
    auto custom =
        QByteArray(stock).replace("extra,statusnotifier", "extra,tray,statusnotifier") + "[tray]\ntype=tray\n";
    custom.replace("apps\\size=1", "apps\\size=1\napps\\1\\command=personal command");
    atomic(original, custom, 0640);
    run(args);
    {
        QSettings c(config, QSettings::IniFormat);
        const auto active = c.value("panel1/plugins").toStringList();
        require(active.contains("quicklaunch") && active.contains("tray") &&
                    !active.contains("doroshellLegacyTray") &&
                    c.value("quicklaunch/apps/1/command") == "personal command",
                "Changed custom launcher or duplicated existing bridge");
    }
    auto active = loadFile(desktop);
    atomic(desktop, active + "X-Changed=true\n", 0600);
    run({"--undo", "--keep-panel-edits"}, 1);
    require(QFile::exists(config), "Changed autostart allowed partial undo");
    atomic(desktop, active, 0600);
    run({"--undo"});
    require(loadFile(original) == custom && read(original)["mode"].toInt() == 0640, "Edited the stock profile");
    const QByteArray overrides = "[taskbar]\ncloseOnMiddleClick=false\n[personal]\nchoice=retained\n";
    atomic(original, overrides, 0640);
    run(args);
    {
        QSettings effective(config, QSettings::IniFormat);
        require(effective.contains("doroshellTasks/closeOnMiddleClick") &&
                !effective.value("doroshellTasks/closeOnMiddleClick").toBool() &&
                effective.value("personal/choice") == "retained", "Lost a personal plugin override");
    }
    run({"--undo"});
    require(loadFile(original) == overrides, "Materialised defaults into the user's stock layout");
    const QByteArray other = "[panel1]\n; Personal panel stays intact\nplugins=systemtray\nposition=Top\n"
                             "[systemtray]\ntype=tray\n";
    auto multi = QByteArray(stock).replace("[panel1]", "[panel2]").replace("panels=panel1", "panels=panel2,panel1") + other;
    atomic(original, multi, 0640);
    run(args, 1);
    run(args + QStringList{"--panel", "panel3"}, 1);
    run(args + QStringList{"--panel", "panel2"});
    auto prepared = loadFile(config);
    require(prepared.contains(other) && !prepared.contains("doroshellLegacyTray"),
            "Changed the other panel or duplicated its legacy tray");
    QSettings selected(config, QSettings::IniFormat);
    require(selected.value("panel2/doroshellTheme").toBool() && !selected.contains("panel1/doroshellTheme"),
            "Styled the wrong panel");
    run(args + QStringList{"--panel", "panel1"}, 1);
    run({"--undo"});
    require(loadFile(original) == multi, "Multi-panel rollback changed the stock profile");
    for (const auto &bad : {QByteArray(stock).replace("panels=panel1", "panels=panel1,panel2"),
                            QByteArray(stock).replace("taskbar,extra", "taskbar,extra,extra"),
                            QByteArray(stock).replace("type=taskbar", "type=dockbarx"),
                            stock + "[doroshellTasks]\ntype=spacing\n", stock + "[extra]\nfoo=bar\n"}) {
        atomic(original, bad, 0640);
        run(args, 1);
        require(!QFile::exists(journal) && !QFile::exists(config) && loadFile(desktop) == prior,
                "Unsupported layout staged");
    }
    atomic(original, stock, 0640);
    atomic(legacy, "legacy receipt", 0600);
    run(args, 1);
    run({"--undo"}, 1);
    require(loadFile(legacy) == "legacy receipt" && !QFile::exists(config) && loadFile(original) == stock,
            "Changed RC2 ownership");
    QFile::remove(legacy);
    require(QFile::link(original, config), "Could not create protected symlink fixture");
    run(args, 1);
    require(loadFile(original) == stock && QFileInfo(config).isSymLink(), "Followed a personal symlink");
}
} // namespace

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    if (QFileInfo(QString::fromLocal8Bit(argv[0])).fileName() == "lxqt-panel") {
        if (argc != 3 || QByteArray(argv[1]) != "--config")
            return 2;
        std::puts(argv[2]);
        return 0;
    }
    try {
        require(argc == 2, "Need panel-profile executable path");
        test(app.arguments().at(1));
        return 0;
    } catch (const std::exception &e) {
        std::fprintf(stderr, "%s\n", e.what());
        return 1;
    }
}
