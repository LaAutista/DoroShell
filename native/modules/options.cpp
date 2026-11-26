// SPDX-License-Identifier: GPL-2.0-or-later
#include "options.hpp"
#include "../setup/files.hpp"
#include <expat.h>
namespace modules {
using doro_files::fail;
using theme::Edit;
QStringList names() {
  return {"single-desktop", "wallpaper-glass", "taskbar",  "taskbar-size",
          "taskbar-drag",   "dolphin",         "kate",     "dolphin-dark",
          "kate-dark",      "start-shortcut",  "clipboard"};
}
QStringList paths(const QString &name) {
  if (name == "single-desktop")
    return {openbox};
  if (name == "clipboard")
    return {privatePanel, ".config/autostart/doroshell-clipboard.desktop"};
  if (name == "wallpaper-glass")
    return {glass};
  if (name == "taskbar-size" || name == "taskbar-drag")
    return {privatePanel};
  if (name == "taskbar")
    return {stockPanel};
  if (name == "start-shortcut")
    return {shortcuts};
  if (name.endsWith("-dark"))
    return {".config/" + name.section('-', 0, 0) + "rc"};
  if (name == "kate" || name == "dolphin")
    return {".config/mimeapps.list", ".config/lxqt-mimeapps.list"};
  fail("Unknown module " + name);
}
namespace {
#if XML_MAJOR_VERSION > 2 || (XML_MAJOR_VERSION == 2 && XML_MINOR_VERSION >= 9)
constexpr auto indexOfXml = XML_GetCurrentByteIndex64;
constexpr auto sizeOfXml = XML_GetCurrentByteCount64;
#else
constexpr auto indexOfXml = XML_GetCurrentByteIndex;
constexpr auto sizeOfXml = XML_GetCurrentByteCount;
#endif
struct DesktopXml {
  XML_Parser parser;
  QStringList stack;
  QByteArray source;
  QString key, ruleText;
  QByteArray prefix;
  qsizetype start = -1, inside = -1, close = -1, end = -1, container = -1;
  bool rule = false, bad = false, seenContainer = false;
  bool child() const {
    return stack == QStringList{"openbox_config", "desktops", key};
  }
  bool parent() const {
    return stack == QStringList{"openbox_config", "desktops"};
  }
  DesktopXml(QByteArray b, QString k)
      : parser(XML_ParserCreateNS(nullptr, '|')), source(std::move(b)),
        key(std::move(k)) {
    if (!parser)
      fail("Cannot initialize Openbox parser");
    auto done = qScopeGuard([&] { XML_ParserFree(parser); });
    XML_SetUserData(parser, this);
    XML_SetStartDoctypeDeclHandler(
        parser, [](void *p, const char *, const char *, const char *, int) {
          static_cast<DesktopXml *>(p)->bad = true;
        });
    XML_SetElementHandler(
        parser,
        [](void *p, const char *name, const char **) {
          auto &x = *static_cast<DesktopXml *>(p);
          if (x.child())
            x.bad = true;
          x.stack << QString::fromUtf8(name).section('|', -1);
          if (x.parent()) {
            if (x.seenContainer)
              x.bad = true;
            x.seenContainer = true;
            auto offset = indexOfXml(x.parser);
            auto tag = x.source.mid(offset + 1, sizeOfXml(x.parser) - 1)
                           .split('>')
                           .first()
                           .split(' ')
                           .first();
            auto colon = tag.indexOf(':');
            if (colon >= 0)
              x.prefix = tag.left(colon + 1);
          }
          if (x.child()) {
            if (x.start >= 0)
              x.bad = true;
            x.start = indexOfXml(x.parser);
            x.inside = x.start + sizeOfXml(x.parser);
          }
          if (x.stack.endsWith("desktop") &&
              x.stack.value(x.stack.size() - 2) == "application") {
            x.rule = true;
            x.ruleText.clear();
          }
        },
        [](void *p, const char *) {
          auto &x = *static_cast<DesktopXml *>(p);
          if (x.rule && x.stack.endsWith("desktop")) {
            if (x.ruleText.trimmed().toInt() > 1)
              x.bad = true;
            x.rule = false;
          }
          if (x.child()) {
            x.close = indexOfXml(x.parser);
            x.end = x.close + sizeOfXml(x.parser);
          }
          if (x.parent())
            x.container = indexOfXml(x.parser);
          x.stack.removeLast();
        });
    XML_SetCharacterDataHandler(parser, [](void *p, const char *data, int len) {
      auto &x = *static_cast<DesktopXml *>(p);
      if (x.rule)
        x.ruleText += QString::fromUtf8(data, len);
    });
    if (!XML_Parse(parser, source.constData(), source.size(), XML_TRUE) ||
        bad || container < 0 || (key == "number" && start < 0) ||
        (start >= 0 &&
         !QRegularExpression("^\\s*[0-9]+\\s*$")
              .match(QString::fromUtf8(source.mid(inside, close - inside)))
              .hasMatch()))
      fail("Expected one Openbox desktops section with numeric settings and no "
           "application pinned to another desktop");
  }
};
QJsonObject settingsObject(const QByteArray &bytes) {
  if (bytes.isNull())
    return {};
  auto doc = QJsonDocument::fromJson(bytes);
  if (!doc.isObject() ||
      (doc.object().contains("version") && doc.object()["version"] != 1))
    fail("Unsupported wallpaper glass settings");
  return doc.object();
}
QJsonValue ini(const QByteArray &data, const QString &section,
               const QString &key) {
  return theme::readValue(Edit{"settings", "ini", section, key, {}}, data);
}
QStringList plugins(const QByteArray &data, const QString &group) {
  QStringList list;
  for (auto entry :
       ini(data, group, "plugins").toString().split(',', Qt::SkipEmptyParts)) {
    entry = entry.trimmed();
    if (!QRegularExpression("^[A-Za-z0-9_.-]+$").match(entry).hasMatch() ||
        list.contains(entry))
      fail("Invalid or duplicate panel plugin");
    list << entry;
  }
  return list;
}
QStringList groups(const QByteArray &data) {
  if (!data.isValidUtf8() || data.contains('\0'))
    fail("Malformed configuration");
  QStringList result;
  for (auto line : data.split('\n')) {
    line = line.trimmed();
    if (!line.startsWith('['))
      continue;
    if (!line.endsWith(']') || line.count(']') != 1)
      fail("Malformed configuration section");
    auto group = QString::fromUtf8(line.mid(1, line.size() - 2));
    if (result.contains(group))
      fail("Duplicate configuration section " + group);
    result << group;
  }
  return result;
}
} // namespace
QString taskPanel(const QByteArray &data) {
  QString result;
  for (auto g : groups(data)) {
    if (!QRegularExpression("^panel[1-9][0-9]*$").match(g).hasMatch())
      continue;
    for (auto p : plugins(data, g)) {
      if (p.startsWith("doroshellTasks") && ini(data, p, "type") == "taskbar") {
        if (!result.isEmpty())
          fail("Multiple DoroShell task widgets");
        result = g;
      }
    }
  }
  if (result.isEmpty())
    fail("Stage the DoroShell panel before changing taskbar settings");
  return result;
}
QList<Edit> edits(const QString &home, const QString &module,
                  const QJsonObject &options,
                  const QMap<QString, QByteArray> &files) {
  QList<Edit> result;
  auto add = [&](QString path, QString group, QString field,
                 QJsonValue desired) {
    result.append({path, "ini", group, field, desired});
  };
  if (module == "wallpaper-glass") {
    for (auto key : {"version", "enabled"})
      result.append(
          {glass,
           "json",
           {},
           key,
           QString(key) == "version" ? QJsonValue(1) : QJsonValue(true)});
  } else if (module == "clipboard") {
    auto data = files.value(privatePanel);
    auto panel = taskPanel(data);
    auto list = plugins(data, panel);
    QString notifier;
    for (const auto &p : list)
      if (p == "statusnotifier" || ini(data, p, "type") == "statusnotifier") {
        if (!notifier.isEmpty())
          fail("Ambiguous tray widgets");
        notifier = p;
      }
    QString widget = "doroClipboard",
            app =
                home + "/.local/share/applications/doroshell-clipboard.desktop";
    if (notifier.isEmpty())
      fail("Cannot find the notification area in the selected panel");
    if (groups(data).contains(widget) || list.contains(widget))
      fail("Preserving an existing personal clipboard panel widget");
    list.insert(list.indexOf(notifier), widget);
    add(privatePanel, panel, "plugins", list.join(", "));
    add(privatePanel, widget, "type", "quicklaunch");
    add(privatePanel, widget, "alignment", "Right");
    add(privatePanel, widget, "apps\\1\\desktop", app);
    add(privatePanel, widget, "apps\\size", "1");
    auto autoPath = paths(module).last();
    if (!files.value(autoPath).isNull())
      fail("Preserving an existing clipboard autostart entry");
    auto command = doro_files::desktopQuote(options["clipboard"].toString());
    auto payload =
        ("[Desktop Entry]\nType=Application\nName=DoroClipboard\nExec=" +
         command + "\nOnlyShowIn=LXQt;\n")
            .toUtf8();
    result.append(
        {autoPath, "file", {}, {}, QString::fromLatin1(payload.toBase64())});
  } else if (module == "single-desktop") {
    for (auto key : {"number", "firstdesk"})
      result.append({openbox, "xml", {}, key, "1"});
  } else if (module == "kate" || module == "dolphin") {
    for (const auto &path : paths(module))
      add(path, "Default Applications",
          module == "kate" ? "text/plain" : "inode/directory",
          "org.kde." + module + ".desktop;");
  } else if (module.endsWith("-dark")) {
    add(paths(module).first(), "UiSettings", "ColorScheme", "BreezeDark");
  } else if (module == "taskbar-size") {
    const QMap<QString, QPair<int, int>> sizes{
        {"small", {20, 36}}, {"medium", {28, 48}}, {"large", {36, 56}}};
    QString size = options["size"].toString();
    if (!sizes.contains(size))
      fail("Unknown taskbar size");
    auto data = files.value(privatePanel);
    auto panel = taskPanel(data);
    add(privatePanel, panel, "iconSize", QString::number(sizes[size].first));
    for (auto p : plugins(data, panel))
      if (p.startsWith("doroshellTasks") && ini(data, p, "type") == "taskbar")
        add(privatePanel, p, "buttonWidth",
            QString::number(sizes[size].second));
  } else if (module == "taskbar") {
    auto data = files.value(stockPanel);
    auto list = plugins(data, "panel1"), previous = list;
    if (list.isEmpty())
      fail("An initialized stock LXQt panel1 layout is required");
    list.removeIf([&](const QString &g) {
      return g == "dockbarx" || ini(data, g, "type") == "dockbarx";
    });
    QString task;
    for (const auto &g : list)
      if (g == "taskbar" || ini(data, g, "type") == "taskbar") {
        if (!task.isEmpty())
          fail("Ambiguous stock taskbar");
        task = g;
      }
    if (task.isEmpty()) {
      task = "doroshelltaskbar";
      if (groups(data).contains(task) || list.contains(task))
        fail("Conflicting taskbar section");
      list << task;
      add(stockPanel, task, "type", "taskbar");
    }
    if (list != previous)
      add(stockPanel, "panel1", "plugins", list.join(", "));
    auto style = options["style"].toString();
    if (style != "icons" && style != "standard")
      fail("Unknown taskbar style");
    add(stockPanel, task, "buttonStyle",
        style == "icons" ? "Icon" : "IconText");
    add(stockPanel, task, "groupingEnabled", "true");
    add(stockPanel, task, "iconByClass", "true");
    add(stockPanel, task, "showOnlyOneDesktopTasks", "false");
  } else if (module == "start-shortcut") {
    auto data = files.value(shortcuts);
    QString group;
    for (auto g : groups(data)) {
      auto decoded = QUrl::fromPercentEncoding(g.toUtf8());
      if (decoded.compare("Alt+F1", Qt::CaseInsensitive) != 0 &&
          !decoded.startsWith("Alt+F1.", Qt::CaseInsensitive))
        continue;
      if (!group.isEmpty() ||
          !QRegularExpression("^Alt(\\+|%2[Bb])F1\\.[1-9][0-9]*$")
               .match(g)
               .hasMatch())
        fail("Ambiguous Alt+F1 binding");
      group = g;
    }
    QString exe = options["start"].toString();
    if (!QRegularExpression("^/[A-Za-z0-9_./-]+$").match(exe).hasMatch())
      fail("Unsupported shortcut executable path");
    if (!group.isEmpty()) {
      bool standard =
          ini(data, group, "path") == "/panel/fancymenu/show_hide" &&
          ini(data, group, "Exec").isNull();
      bool owned =
          ini(data, group, "Exec") == exe && ini(data, group, "path").isNull();
      auto enabled = ini(data, group, "Enabled");
      if (((!standard && !owned) || (!enabled.isNull() && enabled != "true")) &&
          !options["replace"].toBool())
        fail("Personal Alt+F1 binding; choose --replace-start-shortcut "
             "explicitly");
      bool active = false;
      for (auto line : data.split('\n')) {
        line = line.trimmed();
        if (line.startsWith('[')) {
          active = line == ("[" + group + "]").toUtf8();
          continue;
        }
        if (!active || line.isEmpty() || line.startsWith('#') ||
            line.startsWith(';'))
          continue;
        if (!QStringList{"Enabled", "Comment", "Exec", "path"}.contains(
                QString::fromUtf8(line.left(line.indexOf('='))).trimmed()))
          fail("Unsupported Alt+F1 setting");
      }
    } else
      group = "Alt%2BF1.1";
    add(shortcuts, group, "path", QJsonValue::Null);
    add(shortcuts, group, "Exec", exe);
    add(shortcuts, group, "Comment", "DoroShell Start");
    add(shortcuts, group, "Enabled", "true");
  }
  return result;
}
QJsonValue value(const Edit &e, const QByteArray &source) {
  if (e.kind == "json") {
    auto obj = settingsObject(source);
    auto v = obj.value(e.key);
    if (!v.isUndefined() && v.type() != e.desired.type())
      fail("Malformed wallpaper-glass setting");
    return v.isUndefined() ? QJsonValue(QJsonValue::Null) : v;
  }
  if (e.kind == "xml") {
    DesktopXml xml(source, e.key);
    return xml.start < 0
               ? QJsonValue(QJsonValue::Null)
               : QJsonValue(QString::fromUtf8(
                                source.mid(xml.inside, xml.close - xml.inside))
                                .trimmed());
  }
  return theme::readValue(e, source);
}
QByteArray set(const Edit &e, const QByteArray &source, const QJsonValue &v) {
  if (value(e, source) == v)
    return source;
  if (e.kind == "json") {
    auto obj = settingsObject(source);
    if (v.isNull())
      obj.remove(e.key);
    else
      obj[e.key] = v;
    return QJsonDocument(obj).toJson();
  }
  if (e.kind == "xml") {
    DesktopXml xml(source, e.key);
    auto b = source;
    if (xml.start < 0) {
      auto tag = xml.prefix + e.key.toUtf8();
      return b.insert(xml.container, "<" + tag + ">" + v.toString().toUtf8() +
                                         "</" + tag + ">");
    }
    return v.isNull() ? b.remove(xml.start, xml.end - xml.start)
                      : b.replace(xml.inside, xml.close - xml.inside,
                                  v.toString().toUtf8());
  }
  return theme::setValue(e, source, v);
}
} // namespace modules
