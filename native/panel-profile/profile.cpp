// SPDX-License-Identifier: GPL-2.0-or-later
#include <gio/gdesktopappinfo.h>
#include "profile.hpp"
#include "../setup/files.hpp"
#include <QMap>
#include <QRegularExpression>
#include <QSet>
#include <QSettings>
#include <QStringDecoder>
#include <QTemporaryDir>

namespace
{
using doro_files::fail;
struct Sections {
    QStringList order;
    QMap<QString, QByteArray> text;
};

// Preserve the original spelling, comments and values of unrelated sections.
// Reject duplicate sections/keys before QSettings merges them.
Sections splitSections(const QByteArray &bytes)
{
    QStringDecoder decoder(QStringDecoder::Utf8);
    const QString decoded = decoder(bytes);
    if (decoded.isEmpty() || decoder.hasError() || bytes.contains('\0'))
        fail("Panel configuration must be UTF-8 INI text");
    Sections result;
    QString section;
    result.order << section;
    QSet<QByteArray> keys;
    for (qsizetype offset = 0; offset < bytes.size();) {
        auto next = bytes.indexOf('\n', offset);
        if (next < 0)
            next = bytes.size() - 1;
        const auto full = bytes.mid(offset, next - offset + 1), line = full.trimmed();
        offset = next + 1;
        if (line.startsWith('[')) {
            if (!line.endsWith(']') || line.size() < 3)
                fail("Unsupported panel section header");
            section = QString::fromUtf8(line.mid(1, line.size() - 2));
            if (result.order.contains(section))
                fail("Panel contains duplicate section " + section);
            result.order << section;
            keys.clear();
        } else if (!line.isEmpty() && !line.startsWith(';') && !line.startsWith('#')) {
            auto pos = line.indexOf('=');
            if (pos < 1)
                fail("Unsupported multiline panel setting");
            auto key = line.first(pos).trimmed();
            if (keys.contains(key))
                fail("Panel contains duplicate key " + QString::fromUtf8(key));
            keys.insert(key);
        }
        result.text[section] += full;
    }
    return result;
}

QStringList list(const QVariant &v)
{
    if (v.metaType().id() == QMetaType::QString)
        return v.toString().isEmpty() ? QStringList{} : QStringList{v.toString()};
    if (v.metaType().id() == QMetaType::QStringList)
        return v.toStringList();
    if (!v.isValid())
        return {};
    fail("Unsupported panel list value");
}

QString launcherIdentity(QString path)
{
    if (!QDir::isAbsolutePath(path) || !QFileInfo(path).isFile() || !path.endsWith(".desktop"))
        return {};
    auto *app = g_desktop_app_info_new_from_filename(QFile::encodeName(path).constData());
    if (!app)
        return {};
    const auto cls = g_desktop_app_info_get_startup_wm_class(app);
    const auto id = cls && *cls ? QString::fromUtf8(cls) : QFileInfo(path).completeBaseName();
    g_object_unref(app);
    return id.toCaseFolded();
}

// Fold simple app-only widgets into the task list. Keep mixed or custom widgets
// intact: their entries may launch URLs, folders or per-entry commands.
void mergeQuicklaunch(QSettings &c, QStringList &plugins, const QString &start, QStringList &pins)
{
    QSet<QString> identities;
    for (const auto &p : pins) {
        const auto id = launcherIdentity(p);
        if (!id.isEmpty())
            identities.insert(id);
    }
    const auto original = plugins;
    for (const auto &name : original) {
        if (name == "doroshellStart" || c.value(name + "/type", name).toString() != "quicklaunch")
            continue;
        c.beginGroup(name);
        const auto keys = c.allKeys();
        bool plain = true;
        for (const auto &key : keys)
            if (key != "type" && key != "alignment" && key != "apps/size" &&
                !QRegularExpression(R"(^apps/[1-9]\d*/desktop$)").match(key).hasMatch())
                plain = false;
        bool ok = false;
        int size = c.value("apps/size").toInt(&ok);
        QStringList proposed = pins;
        auto ids = identities;
        if (plain && ok && size > 0 && size <= keys.size()) {
            for (int i = 1; i <= size; ++i) {
                const auto value = c.value(QString("apps/%1/desktop").arg(i));
                auto p = value.toString();
                if (value.metaType().id() != QMetaType::QString || p == start) {
                    plain = false;
                    break;
                }
                if (proposed.contains(p))
                    continue;
                auto id = launcherIdentity(p);
                if (id.isEmpty() || ids.contains(id)) {
                    plain = false;
                    break;
                }
                proposed << p;
                ids.insert(id);
            }
            if (plain) {
                pins = proposed;
                identities = ids;
                plugins.removeAll(name);
            }
        } else if (name == "quicklaunch" && keys == QStringList{"alignment", "type"} &&
                   c.value("alignment") == "Left" && c.value("type") == "quicklaunch")
            plugins.removeAll(name);
        c.endGroup();
    }
}
} // namespace

bool panelDefinesLayout(const QByteArray &data)
{
    static const QRegularExpression entry(R"(^\s*(?:\[panel[1-9][0-9]*\]|panels\s*=))",
                                          QRegularExpression::MultilineOption);
    return entry.match(QString::fromUtf8(data)).hasMatch();
}

QByteArray applyPluginOverrides(const QByteArray &defaults, const QByteArray &overrides)
{
    if (overrides.isEmpty()) return defaults;
    const auto base = splitSections(defaults), personal = splitSections(overrides);
    QByteArray result;
    for (const auto &section : base.order) {
        const auto original = base.text.value(section);
        if (!personal.text.contains(section)) {
            result += original;
        } else {
            QSet<QByteArray> keys;
            auto keyOf = [](QByteArray line) -> QByteArray {
                line = line.trimmed();
                const auto equals = line.indexOf('=');
                if (line.startsWith(';') || line.startsWith('#') || line.startsWith('[') || equals < 1) return {};
                return line.first(equals).trimmed();
            };
            const auto user = personal.text.value(section);
            for (const auto &line : user.split('\n')) keys.insert(keyOf(line));
            result += user;
            if (!result.endsWith('\n')) result += '\n';
            for (const auto &line : original.split('\n')) {
                const auto key = keyOf(line);
                if (!key.isEmpty() && !keys.contains(key)) result += line + '\n';
            }
        }
        if (!result.endsWith('\n')) result += '\n';
    }
    for (const auto &section : personal.order) {
        if (!base.text.contains(section)) result += personal.text.value(section) + '\n';
    }
    return result;
}

QByteArray buildPanelProfile(const QByteArray &stock, const QString &home, const QString &selection)
{
    const auto original = splitSections(stock);
    QTemporaryDir tmp;
    if (!tmp.isValid())
        fail("Cannot create private panel scratch directory");
    const QString path = tmp.filePath("panel.conf");
    doro_files::atomic(path, stock, 0600);
    QSettings c(path, QSettings::IniFormat);
    c.setFallbacksEnabled(false);
    const auto groups = c.childGroups();
    QStringList panels;
    static const QRegularExpression panelId(R"(^panel[1-9][0-9]*$)"), widgetId(R"(^[A-Za-z][A-Za-z0-9_-]*$)");
    for (const auto &g : groups)
        if (panelId.match(g).hasMatch())
            panels << g;
    auto declared = list(c.value("panels", "panel1"));
    declared.sort();
    panels.sort();
    if (declared != panels || c.status() != QSettings::NoError)
        fail("Declared panel list differs from the panel sections");
    if (selection.isEmpty() && panels != QStringList{"panel1"})
        fail("Choose the panel to customise using --panel panelN");
    const QString panel = selection.isEmpty() ? "panel1" : selection;
    if (!panels.contains(panel))
        fail("Unknown panel: " + panel);
    QSet<QString> otherWidgets;
    bool otherTray = false;
    for (const auto &other : panels) {
        if (other == panel) continue;
        for (const auto &widget : list(c.value(other + "/plugins"))) {
            otherWidgets.insert(widget);
            if (c.value(widget + "/type", widget).toString() == "tray") otherTray = true;
        }
    }
    auto plugins = list(c.value(panel + "/plugins"));
    QSet<QString> seen;
    QMap<QString, QStringList> byType;
    for (const auto &w : plugins) {
        if (!widgetId.match(w).hasMatch() || seen.contains(w) || otherWidgets.contains(w) || w == "General" || panelId.match(w).hasMatch())
            fail("Ambiguous panel widget name: " + w);
        seen.insert(w);
        auto type = c.value(w + "/type", w).toString();
        if (!widgetId.match(type).hasMatch())
            fail("Unsupported panel plugin type");
        byType[type] << w;
    }
    if (plugins.isEmpty() || byType.contains("dockbarx"))
        fail("Expected a populated LXQt widget list. DockBarX pin import needs a separate migration.");
    for (auto type : {"taskbar", "statusnotifier", "worldclock", "showdesktop", "tray"})
        if (byType[type].size() > 1)
            fail("Multiple " + QString(type) + " widgets need explicit selection");

    QMap<QString, QVariant> previous;
    for (const auto &k : c.allKeys())
        previous[k] = c.value(k);
    auto create = [&](const QString &name, const QString &type) {
        if (groups.contains(name) || plugins.contains(name) || otherWidgets.contains(name))
            fail("Existing widget conflicts with " + name);
        c.setValue(name + "/type", type);
        return name;
    };
    auto ensure = [&](const QString &type, const QString &name) {
        if (!byType[type].isEmpty())
            return byType[type].first();
        auto added = create(name, type);
        plugins << added;
        return added;
    };
    const auto start = home + "/.local/share/applications/lxqt-comfort.desktop";
    bool hasStart = false;
    for (const auto &name : byType["quicklaunch"]) {
        auto size = c.beginReadArray(name + "/apps");
        if (size > 65536)
            fail("Invalid Quick Launch size");
        for (int i = 0; i < size; ++i) {
            c.setArrayIndex(i);
            if (c.value("desktop") == start)
                hasStart = true;
        }
        c.endArray();
    }
    if (!hasStart) {
        const auto startName = create("doroshellStart", "quicklaunch");
        c.setValue(startName + "/alignment", "Left");
        c.setValue(startName + "/apps/1/desktop", start);
        c.setValue(startName + "/apps/size", 1);
        plugins.prepend(startName);
    }
    if (byType["fancymenu"].contains("fancymenu"))
        plugins.removeAll("fancymenu");

    const auto oldTask = byType["taskbar"].value(0);
    const auto task = create("doroshellTasks", "taskbar");
    auto index = plugins.indexOf(oldTask);
    if (index >= 0) {
        plugins[index] = task;
        c.beginGroup(oldTask);
        const auto keys = c.allKeys();
        c.endGroup();
        for (const auto &k : keys)
            c.setValue(task + "/" + k, c.value(oldTask + "/" + k));
    } else
        plugins.insert(qMin(qsizetype(1), plugins.size()), task);
    auto pins = list(c.value(task + "/doroshellPinned"));
    mergeQuicklaunch(c, plugins, start, pins);
    c.setValue(task + "/alignment", "Left");
    c.setValue(task + "/doroshellPinned", pins);
    c.setValue(task + "/groupingEnabled", true);
    c.setValue(task + "/iconByClass", true);
    c.setValue(task + "/showOnlyOneDesktopTasks", false);
    c.setValue(task + "/buttonStyle", "Icon");
    c.setValue(task + "/buttonWidth", 48);

    auto notifier = ensure("statusnotifier", "doroshellNotifier");
    if (byType["tray"].isEmpty() && !otherTray) {
        const auto bridge = ensure("tray", "doroshellLegacyTray");
        plugins.removeAll(bridge);
        plugins.insert(plugins.indexOf(notifier) + 1, bridge);
    }
    c.setValue(notifier + "/alignment", "Right");
    c.setValue(notifier + "/doroshellPopup", true);
    c.setValue(notifier + "/doroshellNetworkButton", true);
    c.setValue(notifier + "/doroshellCollapseNew",
               !c.contains(notifier + "/hideList") && !c.contains(notifier + "/autoHideList"));
    for (const auto &kind : {"mount", "volume", "tray"}) {
        for (const auto &w : plugins)
            if (c.value(w + "/type", w).toString() == kind && !c.contains(w + "/alignment"))
                c.setValue(w + "/alignment", "Right");
    }
    auto clock = ensure("worldclock", "doroshellClock");
    plugins.removeAll(clock);
    plugins << clock;
    c.setValue(clock + "/alignment", "Right");
    c.setValue(clock + "/doroshellTwoLine", true);
    c.setValue(clock + "/formatType", "short-timeonly");
    c.setValue(clock + "/dateFormatType", "short");
    c.setValue(clock + "/showDate", true);
    c.setValue(clock + "/datePosition", "below");
    if (!c.contains(clock + "/customFormat")) {
        c.setValue(clock + "/useAdvancedManualFormat", true);
        c.setValue(clock + "/customFormat", "h:mm AP'<br/>'ddd, MMM d");
    }
    const auto edge = ensure("showdesktop", "doroshellShowDesktop");
    plugins.removeAll(edge);
    plugins << edge;
    c.setValue(edge + "/alignment", "Right");
    c.setValue(edge + "/doroshellEdge", true);
    for (const auto &w : plugins)
        if (!c.contains(w + "/type"))
            c.setValue(w + "/type", w);
    c.setValue(panel + "/plugins", plugins);
    c.setValue(panel + "/doroshellTheme", true);
    for (const auto &[key, value] : QList<QPair<QString, QVariant>>{
             {"position", "Bottom"}, {"panelSize", 40}, {"iconSize", 28}, {"lineCount", 1}})
        if (!c.contains(panel + "/" + key))
            c.setValue(panel + "/" + key, value);
    c.setValue("__userfile__", true);
    QSet<QString> changed;
    for (const auto &key : c.allKeys())
        if (!previous.contains(key) || previous[key] != c.value(key))
            changed.insert(key.contains('/') ? key.section('/', 0, 0) : "General");
    c.sync();
    if (c.status() != QSettings::NoError)
        fail("Cannot serialize panel profile");
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly))
        fail("Cannot read prepared panel profile");
    const auto serialized = splitSections(file.readAll());
    QByteArray out;
    if (changed.contains("General"))
        out += serialized.text.value("General");
    else
        out += original.text.value("") + original.text.value("General");
    for (const auto &g : original.order)
        if (!g.isEmpty() && g != "General") {
            if (!out.isEmpty() && !out.endsWith('\n'))
                out += '\n';
            out += changed.contains(g) ? serialized.text.value(g) : original.text.value(g);
        }
    for (const auto &g : serialized.order)
        if (!g.isEmpty() && g != "General" && !original.text.contains(g)) {
            if (!out.isEmpty() && !out.endsWith('\n'))
                out += '\n';
            out += serialized.text.value(g);
        }
    return out;
}
