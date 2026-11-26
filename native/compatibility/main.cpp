// SPDX-License-Identifier: GPL-2.0-or-later
// doroshell-check: read-only preflight. It reads files and runs bounded queries; it never writes.
#include "packages.hpp"
#include <QCommandLineParser>
#include <QCoreApplication>
#include <QDir>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcess>
#include <QRegularExpression>
#include <QStandardPaths>
#include <QTextStream>
#include <optional>

namespace
{
using doro::packages::Group;
// ok: verified. missing-package: install something. unsupported: this session/system cannot run the build.
// unavailable: the probe itself could not run, so nothing is known. warning: works, with a caveat.
struct Check {
    QString id, status, summary, fix;
    QStringList packages;
};
struct Output {
    int code;
    QString text;
};

std::optional<Output> run(const QString &tool, const QStringList &arguments, int timeoutMs)
{
    const auto path = QStandardPaths::findExecutable(tool);
    if (path.isEmpty())
        return std::nullopt;
    QProcess process;
    auto env = QProcessEnvironment::systemEnvironment();
    env.insert("LC_ALL", "C");
    process.setProcessEnvironment(env);
    process.start(path, arguments, QIODevice::ReadOnly);
    if (!process.waitForFinished(timeoutMs)) {
        process.kill();
        process.waitForFinished(1000);
        return std::nullopt;
    }
    if (process.exitStatus() != QProcess::NormalExit)
        return std::nullopt;
    return Output{process.exitCode(), QString::fromUtf8(process.readAllStandardOutput())};
}

std::optional<QString> readText(const QString &path)
{
    QFile file(path);
    if (!QFileInfo(path).isFile() || !file.open(QIODevice::ReadOnly))
        return std::nullopt;
    return QString::fromUtf8(file.read(1024 * 1024));
}

QMap<QString, QString> osRelease(const QString &sysroot)
{
    QMap<QString, QString> result;
    for (const auto &line : readText(sysroot + "/etc/os-release").value_or(QString()).split('\n')) {
        const auto equals = line.indexOf('=');
        if (equals <= 0 || line.startsWith('#'))
            continue;
        auto value = line.mid(equals + 1).trimmed();
        if (value.size() >= 2 && (value.startsWith('"') || value.startsWith('\'')) && value.endsWith(value.front()))
            value = value.mid(1, value.size() - 2);
        result[line.left(equals)] = value;
    }
    return result;
}

QStringList systemConfigDirs(const QString &sysroot)
{
    QStringList result;
    auto dirs = qEnvironmentVariable("XDG_CONFIG_DIRS");
    for (const auto &dir : (dirs.isEmpty() ? QString("/etc/xdg") : dirs).split(':'))
        if (dir.startsWith('/'))
            result << sysroot + dir;
    return result;
}

std::optional<QString> systemDefault(const QString &sysroot, const QString &relative)
{
    for (const auto &dir : systemConfigDirs(sysroot))
        if (auto text = readText(dir + '/' + relative))
            return text;
    return std::nullopt;
}

QStringList panelGroups(const QString &text)
{
    QStringList result;
    auto matches = QRegularExpression("^\\[(panel[1-9][0-9]*)\\]$", QRegularExpression::MultilineOption).globalMatch(text);
    while (matches.hasNext())
        result << matches.next().captured(1);
    return result;
}

std::optional<QString> panelsKey(const QString &text)
{
    const auto match = QRegularExpression("^\\s*panels\\s*=(.*)$", QRegularExpression::MultilineOption).match(text);
    return match.hasMatch() ? std::optional(match.captured(1).trimmed()) : std::nullopt;
}

// LXQt omits `panels=` for its default single-panel layout, so a missing key means panel1.
bool selectedLayout(const QString &text, const QString &selection)
{
    auto declared = panelsKey(text).value_or("panel1").split(',');
    for (auto &id : declared) id = id.trimmed();
    auto groups = panelGroups(text);
    declared.sort();
    groups.sort();
    return declared == groups && (selection.isEmpty() ? groups == QStringList{"panel1"}
                                                      : groups.count(selection) == 1);
}

// Name the running X11 window manager advertises through EWMH; nullopt when it cannot be read.
std::optional<QString> activeWindowManager()
{
    if (qEnvironmentVariableIsEmpty("DISPLAY"))
        return std::nullopt;
    const auto root = run("xprop", {"-root", "_NET_SUPPORTING_WM_CHECK"}, 2000);
    if (!root || root->code)
        return std::nullopt;
    const auto window = QRegularExpression("window id # (0x[0-9a-fA-F]+)\\s*$").match(root->text);
    if (!window.hasMatch() || window.captured(1).toULongLong(nullptr, 16) == 0)
        return std::nullopt;
    const auto name = run("xprop", {"-id", window.captured(1), "-notype", "_NET_WM_NAME"}, 2000);
    if (!name || name->code)
        return std::nullopt;
    const auto match = QRegularExpression("^_NET_WM_NAME = \"([^\"\\n]+)\"\\s*$").match(name->text);
    return match.hasMatch() ? std::optional(match.captured(1)) : std::nullopt;
}

QString quoted(const QStringList &names) { return names.join(", "); }

QList<Check> inspect(const QString &home, const QString &sysroot, const QString &panel, QJsonObject &facts)
{
    QList<Check> checks;
    const auto release = osRelease(sysroot);
    const auto distro = release.value("ID", "unknown");
    const bool arch = distro == "arch" || release.value("ID_LIKE").split(' ').contains("arch");
    checks << (arch ? Check{"distribution", "ok", "Distribution: " + distro + " (Arch-based).", {}, {}}
                    : Check{"distribution", "unsupported", "Distribution: " + distro + ". DoroShell needs Arch or an Arch derivative.", {}, {}});

    const auto desktop = qEnvironmentVariable("XDG_CURRENT_DESKTOP");
    const bool lxqt = desktop.toCaseFolded().split(':').contains("lxqt");
    checks << (lxqt ? Check{"desktop", "ok", "Desktop: LXQt.", {}, {}}
                    : Check{"desktop", "unsupported",
                            "Desktop: " + (desktop.isEmpty() ? QString("not reported") : desktop) + ". DoroShell extends LXQt.",
                            "Log in to an LXQt session and run this again.", {}});

    auto session = qEnvironmentVariable("XDG_SESSION_TYPE");
    if (session.isEmpty())
        session = !qEnvironmentVariableIsEmpty("WAYLAND_DISPLAY") ? "wayland" : !qEnvironmentVariableIsEmpty("DISPLAY") ? "x11" : "unknown";
    checks << (session == "x11" ? Check{"display-server", "ok", "Display server: X11.", {}, {}}
                                : Check{"display-server", "unsupported", "Display server: " + session + ". Only X11 is supported.",
                                        "Choose the LXQt (X11) session at the login screen.", {}});

    QStringList moved;
    for (const auto &[variable, standard] : {std::pair{"XDG_CONFIG_HOME", ".config"}, {"XDG_DATA_HOME", ".local/share"}, {"XDG_STATE_HOME", ".local/state"}}) {
        const auto value = qEnvironmentVariable(variable);
        if (!value.isEmpty() && QDir::cleanPath(value) != QDir::cleanPath(home + '/' + standard))
            moved << variable;
    }
    checks << (moved.isEmpty() ? Check{"home-layout", "ok", "Settings folders use the standard home layout.", {}, {}}
                               : Check{"home-layout", "unsupported", quoted(moved) + " point outside the standard home layout.",
                                       "Unset them for the desktop session, then run this again.", {}});

    // One bounded dependency test; pacman -T also honours packages that provide another name.
    QStringList names;
    for (const auto &package : doro::packages::all)
        names << QString::fromUtf8(package.name);
    std::optional<QStringList> missing;
    const bool pacman = !QStandardPaths::findExecutable("pacman").isEmpty();
    if (pacman)
        if (const auto test = run("pacman", QStringList{"-T"} + names, 10000); test && (test->code == 0 || test->code == 127))
            missing = test->text.split('\n', Qt::SkipEmptyParts);
    checks << (missing ? Check{"package-manager", "ok", "pacman answered the package query.", {}, {}}
                       : Check{"package-manager", "unavailable",
                               pacman ? "pacman did not answer, so installed packages could not be checked."
                                      : "pacman was not found, so installed packages could not be checked.",
                               {}, {}});

    auto group = [&](Group wanted, const QString &id, const QString &present, const QString &absent) {
        if (!missing) {
            checks << Check{id, "unavailable", "Not checked: " + present.left(present.size() - 1) + " (no package query).", {}, {}};
            return true;
        }
        QStringList lacking;
        for (const auto &package : doro::packages::all)
            if (package.group == wanted && missing->contains(QString::fromUtf8(package.name)))
                lacking << QString::fromUtf8(package.name);
        checks << (lacking.isEmpty() ? Check{id, "ok", present, {}, {}}
                                     : Check{id, "missing-package", absent + " Missing: " + quoted(lacking) + '.', {}, lacking});
        return lacking.isEmpty();
    };
    group(Group::Build, "build-tools", "Build tools are installed.", "Build tools are incomplete.");
    group(Group::Desktop, "desktop-packages", "LXQt and Qt packages are installed.", "LXQt or Qt packages are incomplete.");
    const bool openboxInstalled = group(Group::WindowManager, "openbox-installed", "Openbox is installed.", "Openbox is not installed.");
    group(Group::Archive, "archive-actions", "Dolphin and Ark are installed for archive actions.", "Archive actions need Dolphin and Ark.");
    const bool networkInstalled = group(Group::Network, "network-packages", "NetworkManager packages are installed.", "Wi-Fi & Network needs NetworkManager packages.");

    // Which window manager is running is a separate fact from whether Openbox is installed.
    const auto wm = session == "x11" ? activeWindowManager() : std::nullopt;
    facts["active_window_manager"] = wm ? QJsonValue(*wm) : QJsonValue();
    if (session != "x11")
        checks << Check{"window-manager", "unavailable", "Running window manager not checked outside an X11 session.", {}, {}};
    else if (!wm)
        checks << Check{"window-manager", "unavailable", "The running window manager could not be read (xprop missing or no answer).", {}, {}};
    else if (wm->toCaseFolded() == "openbox")
        checks << Check{"window-manager", "ok", "Running window manager: Openbox.", {}, {}};
    else
        checks << Check{"window-manager", "warning", "Running window manager: " + *wm + ". Snapping, themes and shortcuts take effect only under Openbox.",
                        "In LXQt Session Settings choose openbox as the window manager, then log in again.", {}};

    const auto rc = home + "/.config/openbox/rc.xml";
    if (QFileInfo(rc).isFile())
        checks << Check{"openbox-config", "ok", "Openbox settings found in ~/.config/openbox/rc.xml.", {}, {}};
    else if (systemDefault(sysroot, "openbox/rc.xml"))
        checks << Check{"openbox-config", "ok", "Openbox system defaults found; setup starts from them.", {}, {}};
    else if (!missing || !openboxInstalled) // installing openbox supplies the default, so one fix covers both
        checks << Check{"openbox-config", missing ? "missing-package" : "unavailable", "No Openbox settings file exists yet; installing openbox provides one.", {},
                        missing ? QStringList{"openbox"} : QStringList{}};
    else
        checks << Check{"openbox-config", "unsupported", "Openbox is installed but neither ~/.config/openbox/rc.xml nor a system default exists.",
                        "Reinstall openbox, or copy your own rc.xml to ~/.config/openbox/rc.xml.", {}};

    auto layout = readText(home + "/.config/lxqt/panel.conf");
    if (!layout || (panelGroups(*layout).isEmpty() && !panelsKey(*layout)))
        layout = systemDefault(sysroot, "lxqt/panel.conf");
    if (layout && selectedLayout(*layout, panel))
        checks << Check{"panel-layout", "ok", "Selected taskbar panel: " + (panel.isEmpty() ? QString("panel1") : panel), {}, {}};
    else if (!layout)
        checks << Check{"panel-layout", missing ? "missing-package" : "unavailable", "No LXQt panel layout exists yet; installing lxqt-panel provides the default.", {},
                        missing ? QStringList{"lxqt-panel"} : QStringList{}};
    else
        checks << Check{"panel-layout", "unsupported", "Cannot select a panel from this layout.",
                        "Check the panel names in panel.conf and pass --panel panelN to the check and installer.", {}};

    // NetworkManager availability and Wi-Fi hardware are separate: an Ethernet-only desktop passes.
    const auto nm = run("nmcli", {"-t", "-f", "RUNNING", "general"}, 3000);
    if (!nm)
        checks << Check{"network-service", "unavailable",
                        networkInstalled && missing ? "NetworkManager did not answer (nmcli missing or timed out)."
                                                    : "NetworkManager not checked: nmcli is not installed.", {}, {}};
    else if (nm->code == 0 && nm->text.trimmed() == "running")
        checks << Check{"network-service", "ok", "NetworkManager is running.", {}, {}};
    else
        checks << Check{"network-service", "warning", "NetworkManager is installed but not running, so Wi-Fi & Network cannot list connections.",
                        "sudo systemctl enable --now NetworkManager", {}};

    int wifi = 0, wired = 0;
    const QDir net(sysroot + "/sys/class/net");
    for (const auto &name : net.entryList(QDir::Dirs | QDir::NoDotAndDotDot)) {
        const auto base = net.filePath(name);
        if (QFileInfo::exists(base + "/wireless") || QFileInfo::exists(base + "/phy80211"))
            ++wifi;
        else if (QFileInfo::exists(base + "/device")) // virtual interfaces (lo, bridges) have no device
            ++wired;
    }
    facts["wifi_adapters"] = wifi;
    facts["wired_adapters"] = wired;
    checks << Check{"wifi-hardware", "ok",
                    wifi ? QString("Wi-Fi adapter found.") : wired ? QString("No Wi-Fi adapter; wired network only, which is supported.")
                                                                   : QString("No network adapter found; Wi-Fi & Network will show none."), {}, {}};

    facts["distribution"] = distro;
    facts["arch_based"] = arch;
    facts["desktop"] = desktop;
    facts["session"] = session;
    return checks;
}
} // namespace

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    QCommandLineParser parser;
    parser.setApplicationDescription("Check whether this computer can run the native DoroShell build. Changes nothing.");
    parser.addHelpOption();
    parser.addOption({"panel", "Panel to customise.", "panelN"});
    parser.addOption({"json", "Print the report as JSON for the installer."});
    parser.addOption({"home", "User home to inspect.", "path", QDir::homePath()});
    parser.addOption({"sysroot", "Read /etc and /sys below this directory (for tests).", "path", QString()});
    parser.process(app);
    if (!parser.positionalArguments().isEmpty())
        parser.showHelp(2);

    QJsonObject report;
    const auto checks = inspect(QDir::cleanPath(parser.value("home")), parser.value("sysroot"), parser.value("panel"), report);
    QStringList install;
    QJsonArray list;
    int blocking = 0, unverified = 0;
    for (const auto &check : checks) {
        blocking += check.status == "missing-package" || check.status == "unsupported";
        unverified += check.status == "unavailable";
        for (const auto &package : check.packages)
            if (!install.contains(package))
                install << package;
        list << QJsonObject{{"id", check.id}, {"status", check.status}, {"summary", check.summary}, {"fix", check.fix},
                            {"packages", QJsonArray::fromStringList(check.packages)}};
    }
    report["ok"] = blocking == 0;
    report["checks"] = list;
    report["missing_packages"] = QJsonArray::fromStringList(install);

    QTextStream out(stdout);
    if (parser.isSet("json")) {
        out << QJsonDocument(report).toJson();
        return blocking ? 1 : 0;
    }
    const QMap<QString, QString> labels{{"ok", "[ok]      "}, {"missing-package", "[missing] "}, {"unsupported", "[blocked] "},
                                        {"unavailable", "[unknown] "}, {"warning", "[note]    "}};
    out << "DoroShell compatibility check (nothing is changed)\n\n";
    for (const auto &check : checks) {
        out << labels[check.status] << check.summary << '\n';
        if (!check.fix.isEmpty())
            out << "          Fix: " << check.fix << '\n';
    }
    out << '\n';
    if (!install.isEmpty())
        out << "Install what is missing:\n  sudo pacman -S --needed " << install.join(' ') << "\n\n";
    if (blocking)
        out << "Result: not ready. " << blocking << " item(s) above must be fixed first.\n";
    else if (unverified)
        out << "Result: no problem found, but " << unverified << " item(s) could not be checked.\n";
    else
        out << "Result: ready for the native DoroShell build.\n";
    return blocking ? 1 : 0;
}
