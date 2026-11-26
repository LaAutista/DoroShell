#include "session.hpp"
#include <QDir>
#include <QMap>
#include <QRegularExpression>
#include <QSet>
#include <QUrl>
#include <QXmlStreamReader>
#include <stdexcept>

namespace {
[[noreturn]] void refuse(const QString &msg) {
  throw std::runtime_error(msg.toStdString());
}
QString text(const QByteArray &raw) {
  auto s = QString::fromUtf8(raw);
  if (s.contains(QChar::Null) || raw != s.toUtf8())
    refuse("Unsupported configuration encoding");
  return s;
}
} // namespace
QByteArray openboxBindings(const QByteArray &original, const QString &binary) {
  auto source = text(original);
  QXmlStreamReader xml(source);
  int keyboards = 0;
  bool standard = false;
  while (!xml.atEnd()) {
    xml.readNext();
    if (!xml.isStartElement())
      continue;
    if (xml.name() == u"openbox_config")
      standard = true;
    if (xml.name() == u"keyboard")
      ++keyboards;
    if (xml.name() == u"keybind") {
      auto keys = xml.attributes().value("key").toString().split(
          QRegularExpression("\\s+"), Qt::SkipEmptyParts);
      for (const auto &key : keys)
        if (QStringList{"W-Left", "W-Right", "W-Down"}.contains(
                key, Qt::CaseInsensitive))
          refuse("Openbox already uses " + key +
                 ". Existing binding preserved.");
    }
  }
  if (xml.hasError() || !standard || keyboards != 1 ||
      source.count("</keyboard>") != 1)
    refuse("Unsupported Openbox keyboard configuration");
  auto quoted = binary;
  quoted.replace("'", "'\\''");
  quoted = ("'" + quoted + "'").toHtmlEscaped();
  QString block = "\n<!-- DoroShell native snapping -->\n";
  for (auto key : {"Left", "Right", "Down"}) {
    auto action = QString(key) == "Down" ? "restore" : QString(key).toLower();
    block +=
        QString("<keybind key=\"W-%1\"><action name=\"Execute\"><command>%2 "
                "%3</command></action></keybind>\n")
            .arg(QString(key), quoted, action);
  }
  source.insert(source.indexOf("</keyboard>"), block);
  return source.toUtf8();
}
QByteArray lxqtBindings(const QByteArray &original, const QString &start,
                        const QString &capture) {
  auto src = text(original);
  const QString newline = src.contains("\r\n") ? "\r\n" : "\n";
  auto lines = src.split(newline);
  struct Section {
    int first, last;
    QString name;
  };
  QList<Section> sections;
  for (int i = 0; i < lines.size(); ++i) {
    QString line = lines[i].trimmed();
    if (!line.startsWith('['))
      continue;
    if (!line.endsWith(']'))
      refuse("Malformed LXQt shortcut section");
    if (!sections.isEmpty())
      sections.last().last = i;
    sections.append({i, int(lines.size()), line.sliced(1, line.size() - 2)});
  }
  // Qt INI group names encode '+'. Preserve the spelling of existing groups.
  for (const QString &key : QStringList{"Alt+F1", "Print"}) {
    QString name, exec = key == "Print" ? capture : start;
    if (exec.isEmpty()) continue;
    if (!QDir::isAbsolutePath(exec) || exec.contains(QRegularExpression("[\\x00-\\x1f]")))
      refuse("Invalid executable path for an LXQt shortcut");
    // LXQt reads Exec as a QSettings string list. Encode one complete argv
    // element so punctuation in the home directory cannot split the command.
    exec.replace('\\', "\\\\");
    exec.replace('"', "\\\"");
    exec = '"' + exec + '"';
    const QRegularExpression group("^" + QRegularExpression::escape(key) +
                                       "\\.[1-9][0-9]*$",
                                   QRegularExpression::CaseInsensitiveOption);
    int index = -1;
    for (int i = 0; i < sections.size(); ++i) {
      auto decoded = QUrl::fromPercentEncoding(sections[i].name.toUtf8());
      if (decoded.compare(key, Qt::CaseInsensitive) != 0 &&
          !decoded.startsWith(key + ".", Qt::CaseInsensitive))
        continue;
      if (!group.match(decoded).hasMatch() || index != -1)
        refuse("Ambiguous LXQt shortcut " + key);
      index = i;
    }
    if (index >= 0) {
      auto &s = sections[index];
      name = s.name;
      QMap<QString, QString> settings;
      for (int i = s.first + 1; i < s.last; ++i) {
        auto l = lines[i].trimmed();
        if (l.isEmpty() || l.startsWith('#') || l.startsWith(';')) {
          continue;
        }
        int at = l.indexOf('=');
        if (at < 1)
          refuse("Invalid shortcut setting");
        auto k = l.left(at);
        if (settings.contains(k) ||
            !QStringList{"path", "Comment", "Enabled", "Exec"}.contains(k))
          refuse("Unrecognized shortcut setting for " + key);
        settings.insert(k, l.mid(at + 1));
      }
      bool standard =
          key == "Print"
              ? (settings.value("Exec") == "screengrab, -f" &&
                 !settings.contains("path"))
              : (settings.value("path") == "/panel/fancymenu/show_hide" &&
                 !settings.contains("Exec"));
      if (!standard || settings.value("Enabled", "true") != "true")
        refuse("Personal " + key + " shortcut preserved");
      // Make this change without shifting the index of any other section.
      lines[s.first] =
          QString("[%1]%2Comment=DoroShell %3%2Enabled=true%2Exec=%4")
              .arg(name, newline, key == "Print" ? "screenshot" : "Start",
                   exec);
      for (int i = s.first + 1; i < s.last; ++i) {
        auto l = lines[i].trimmed();
        if (!l.isEmpty() && !l.startsWith('#') && !l.startsWith(';'))
          lines[i] = QString();
      }
    } else {
      name = key == "Print" ? "Print.1" : "Alt%2BF1.1";
      lines << QString("[%1]%2Comment=DoroShell %3%2Enabled=true%2Exec=%4%2")
                   .arg(name, newline, key == "Print" ? "screenshot" : "Start",
                        exec);
    }
  }
  QStringList retained;
  for (const auto &l : lines)
    if (!l.isNull())
      retained << l;
  return retained.join(newline).toUtf8();
}
