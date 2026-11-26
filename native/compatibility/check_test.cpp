// SPDX-License-Identifier: GPL-2.0-or-later
// Runs doroshell-check against simulated machines in temporary directories. Symlinked as pacman, xprop
// or nmcli, this same binary answers as that tool from fixture files, so no real system tool is queried.
#include "packages.hpp"
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QDir>
#include <QDirIterator>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcess>
#include <QTemporaryDir>
#include <cstdio>
#include <stdexcept>

namespace
{
void require(bool pass, const QString &message)
{
    if (!pass)
        throw std::runtime_error(message.toStdString());
}

QByteArray fixture(const char *name)
{
    QFile file(qEnvironmentVariable("DORO_FAKE") + '/' + name);
    return file.open(QIODevice::ReadOnly) ? file.readAll() : QByteArray("\x01"); // \x01: fixture absent
}

int fakeTool(const QString &tool, const QStringList &arguments)
{
    if (tool == "pacman") { // pacman -T: print unsatisfied names, exit 127 if any
        const auto installed = fixture("installed").split('\n');
        int code = 0;
        for (const auto &name : arguments.mid(1))
            if (!installed.contains(name.toUtf8())) {
                std::puts(qPrintable(name));
                code = 127;
            }
        return code;
    }
    const auto text = fixture(tool == "xprop" ? "wm" : "nm");
    if (text == "\x01")
        return 1;
    if (tool == "nmcli")
        std::puts(text.constData());
    else if (arguments.contains("-root"))
        std::puts("_NET_SUPPORTING_WM_CHECK(WINDOW): window id # 0x200001");
    else
        std::printf("_NET_WM_NAME = \"%s\"\n", text.constData());
    return 0;
}

void write(const QString &path, const QByteArray &content)
{
    require(QDir().mkpath(QFileInfo(path).absolutePath()), "mkpath " + path);
    QFile file(path);
    require(file.open(QIODevice::WriteOnly) && file.write(content) == content.size(), "write " + path);
}

struct Machine {
    QTemporaryDir dir;
    QStringList tools{"pacman", "xprop", "nmcli"};
    QStringList missing;
    QProcessEnvironment env;
    Machine()
    {
        require(dir.isValid(), "temporary directory");
        write(path("root/etc/os-release"), "NAME=\"CachyOS Linux\"\nID=cachyos\nID_LIKE=arch\n");
        write(path("root/etc/xdg/openbox/rc.xml"), "<openbox_config/>\n");
        write(path("root/etc/xdg/lxqt/panel.conf"), "[General]\npanels=panel1\n\n[panel1]\nposition=Bottom\n");
        write(path("root/sys/class/net/lo/type"), "772\n");
        write(path("root/sys/class/net/enp3s0/device/vendor"), "0x8086\n");
        write(path("home/.config/lxqt/panel.conf"), "[taskbar]\nbuttonWidth=200\n"); // plugin overrides only, as LXQt leaves it
        write(path("home/.local/state/doroshell/menu.json"), "{\"receipt\": true}\n");
        write(path("fake/wm"), "Openbox");
        write(path("fake/nm"), "running");
        env.insert("PATH", path("bin"));
        env.insert("HOME", path("home"));
        env.insert("DORO_FAKE", path("fake"));
        env.insert("XDG_CURRENT_DESKTOP", "LXQt");
        env.insert("XDG_SESSION_TYPE", "x11");
        env.insert("DISPLAY", ":99");
    }
    QString path(const QString &relative) const { return dir.filePath(relative); }
    QByteArray digest() const
    {
        QCryptographicHash hash(QCryptographicHash::Sha256);
        QStringList files;
        for (QDirIterator it(path("home"), QDir::Files | QDir::Hidden, QDirIterator::Subdirectories); it.hasNext();)
            files << it.next();
        files.sort();
        for (const auto &name : files) {
            QFile file(name);
            require(file.open(QIODevice::ReadOnly), "read " + name);
            hash.addData(name.toUtf8() + '\0' + file.readAll() + QFileInfo(name).lastModified().toString(Qt::ISODateWithMs).toUtf8());
        }
        return hash.result();
    }
    struct Result {
        int code;
        QByteArray text;
        QJsonObject json;
        QString status(const QString &id) const
        {
            for (const auto &value : json["checks"].toArray())
                if (value.toObject()["id"].toString() == id)
                    return value.toObject()["status"].toString();
            return "absent";
        }
    };
    Result run(const QString &check, bool json = true, QStringList options = {})
    {
        QByteArray installed;
        for (const auto &package : doro::packages::all)
            if (!missing.contains(QString::fromUtf8(package.name)))
                installed += QByteArray(package.name.data(), qsizetype(package.name.size())) + '\n';
        write(path("fake/installed"), installed);
        QDir().mkpath(path("bin"));
        for (const auto &tool : tools)
            if (!QFileInfo::exists(path("bin/" + tool)))
                require(QFile::link(QCoreApplication::applicationFilePath(), path("bin/" + tool)), "link " + tool);
        const auto before = digest();
        QProcess process;
        process.setProcessEnvironment(env);
        process.start(check, QStringList{"--home", path("home"), "--sysroot", path("root")} + options + (json ? QStringList{"--json"} : QStringList{}));
        require(process.waitForFinished(30000) && process.exitStatus() == QProcess::NormalExit, "doroshell-check did not finish");
        require(digest() == before, "the check changed files in the home directory");
        Result result{process.exitCode(), process.readAllStandardOutput(), {}};
        if (json) {
            result.json = QJsonDocument::fromJson(result.text).object();
            require(!result.json.isEmpty(), "invalid JSON: " + QString::fromUtf8(result.text));
        }
        return result;
    }
};

void tests(const QString &check, bool show)
{
    { // Healthy Ethernet-only desktop: passes, and the absent Wi-Fi adapter is not a problem.
        Machine m;
        const auto r = m.run(check);
        require(r.code == 0 && r.json["ok"].toBool(), "healthy desktop must pass: " + QString::fromUtf8(r.text));
        require(r.status("wifi-hardware") == "ok" && r.json["wifi_adapters"].toInt(-1) == 0 && r.json["wired_adapters"].toInt(-1) == 1, "ethernet-only desktop");
        require(r.status("network-service") == "ok" && r.status("panel-layout") == "ok" && r.status("openbox-config") == "ok", "healthy checks");
        require(r.json["missing_packages"].toArray().isEmpty(), "nothing to install");
    }
    { // Laptop: Openbox not installed while another window manager runs; network tools missing; Wi-Fi present.
        Machine m;
        m.missing = {"openbox", "networkmanager", "nm-connection-editor", "ark"};
        m.tools = {"pacman", "xprop"};
        QFile::remove(m.path("root/etc/xdg/openbox/rc.xml"));
        write(m.path("fake/wm"), "Xfwm4");
        write(m.path("root/sys/class/net/wlan0/wireless/x"), "");
        const auto r = m.run(check);
        require(r.code == 1 && !r.json["ok"].toBool(), "laptop must fail");
        require(r.status("openbox-installed") == "missing-package", "openbox is reported as a missing package");
        require(r.status("window-manager") == "warning" && r.json["active_window_manager"].toString() == "Xfwm4", "running window manager is reported separately");
        require(r.status("openbox-config") == "missing-package", "missing rc.xml is traced to the openbox package");
        require(r.status("archive-actions") == "missing-package" && r.status("network-packages") == "missing-package", "archive and network packages");
        require(r.status("network-service") == "unavailable", "nmcli absent is an unavailable probe, not a second failure");
        require(r.json["wifi_adapters"].toInt(-1) == 1 && r.status("build-tools") == "ok", "wifi counted, build tools fine");
        require(r.json["missing_packages"].toArray() == QJsonArray({"openbox", "ark", "networkmanager", "nm-connection-editor"}), "install list, each package once");
        if (show)
            std::fputs(m.run(check, false).text.constData(), stdout);
    }
    { // No package manager and no xprop: unknown, not "missing".
        Machine m;
        m.tools = {"nmcli"};
        const auto r = m.run(check);
        require(r.status("package-manager") == "unavailable" && r.status("openbox-installed") == "unavailable", "package probes unavailable");
        require(r.status("window-manager") == "unavailable", "window manager probe unavailable");
        require(r.code == 0 && r.json["missing_packages"].toArray().isEmpty(), "unknown is not a failure and invents no packages");
    }
    { // Wayland, non-LXQt, non-Arch, relocated config: each is unsupported.
        Machine m;
        m.env.insert("XDG_SESSION_TYPE", "wayland");
        m.env.insert("XDG_CURRENT_DESKTOP", "KDE");
        m.env.insert("XDG_CONFIG_HOME", m.path("elsewhere"));
        write(m.path("root/etc/os-release"), "ID=fedora\n");
        const auto r = m.run(check);
        for (auto id : {"display-server", "desktop", "distribution", "home-layout"})
            require(r.status(id) == "unsupported", QString(id) + " must be unsupported");
        require(r.code == 1 && r.status("window-manager") == "unavailable", "unsupported session fails");
    }
    { // The installer's panel adapter refuses anything but a single panel1, so two panels block.
        Machine m;
        write(m.path("home/.config/lxqt/panel.conf"), "[General]\npanels=panel1, panel2\n\n[panel1]\n\n[panel2]\n");
        const auto r = m.run(check);
        require(r.status("panel-layout") == "unsupported" && r.code == 1 && !r.json["ok"].toBool(), "two panels block");
        require(m.run(check, true, {"--panel", "panel2"}).code == 0, "explicit second panel selected");
        require(m.run(check, true, {"--panel", "panel3"}).code == 1, "unknown panel refused");
    }
    { // Openbox installed but no rc.xml anywhere: core setup has nothing to seed from, so it blocks.
        Machine m;
        QFile::remove(m.path("root/etc/xdg/openbox/rc.xml"));
        const auto r = m.run(check);
        require(r.status("openbox-installed") == "ok" && r.status("openbox-config") == "unsupported", "missing Openbox defaults block");
        require(r.code == 1 && !r.json["ok"].toBool() && r.json["missing_packages"].toArray().isEmpty(), "blocked without a package to install");
    }
    { // A stopped NetworkManager is a note, not a blocker.
        Machine m;
        write(m.path("fake/nm"), "not running");
        const auto r = m.run(check);
        require(r.status("network-service") == "warning" && r.code == 0, "notes do not block");
    }
}
} // namespace

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    const auto self = QFileInfo(QString::fromLocal8Bit(argv[0])).fileName();
    if (self == "pacman" || self == "xprop" || self == "nmcli")
        return fakeTool(self, app.arguments().mid(1));
    if (argc < 2) {
        std::fputs("usage: native-compatibility-test <doroshell-check> [--show]\n", stderr);
        return 2;
    }
    try {
        tests(app.arguments().at(1), app.arguments().contains("--show"));
    } catch (const std::exception &error) {
        std::fprintf(stderr, "FAIL: %s\n", error.what());
        return 1;
    }
    return 0;
}
