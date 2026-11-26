#include "model.hpp"
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QRegularExpression>
#include <QSaveFile>
#include <QStandardPaths>
#include <QTemporaryFile>
#include <QUuid>
#include <algorithm>
#include <fcntl.h>
#include <stdexcept>
#include <sys/file.h>
#include <sys/stat.h>
#include <tuple>
#include <unistd.h>

namespace {
QString str(const char *s) { return QString::fromUtf8(s ? s : ""); }
QString normalized(QString s) {
  static const QRegularExpression accents(QStringLiteral("\\p{M}+"));
  return s.normalized(QString::NormalizationForm_KD)
      .toCaseFolded()
      .remove(accents)
      .simplified();
}
[[noreturn]] void fail(const QString &s) {
  throw std::runtime_error(s.toStdString());
}
struct Fd {
  int fd;
  ~Fd() {
    if (fd != -1)
      ::close(fd);
  }
};
constexpr int maxBytes = 128 * 1024;
QByteArray readBytes(const QString &path, bool &exists) {
  Fd fd{::open(QFile::encodeName(path),
               O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC)};
  exists = fd.fd >= 0;
  if (!exists) {
    if (errno == ENOENT)
      return {};
    fail("Cannot read " + path);
  }
  struct stat st{};
  if (fstat(fd.fd, &st) || !S_ISREG(st.st_mode) || st.st_size > maxBytes)
    fail("Invalid preference file: " + path);
  QFile file;
  if (!file.open(fd.fd, QIODevice::ReadOnly))
    fail(file.errorString());
  auto data = file.read(maxBytes + 1);
  if (file.error() != QFile::NoError || data.size() > maxBytes)
    fail("Unable to read " + path);
  return data;
}
bool bounded(const QJsonValue &v, qint64 lo, qint64 hi) {
  return v.isDouble() && v.toInteger(-1) >= lo && v.toInteger(-1) <= hi;
}
bool strings(const QJsonValue &v) {
  if (!v.isArray())
    return false;
  for (const auto x : v.toArray())
    if (!x.isString() || x.toString().isEmpty() || x.toString().size() > 4096)
      return false;
  return true;
}
// Qt normalizes repeated object keys. Refuse them before editing existing user
// settings.
bool uniqueObjectKeys(const QByteArray &json) {
  QList<QSet<QString>> keys;
  for (qsizetype i = 0; i < json.size(); ++i) {
    char c = json[i];
    if (c == '{')
      keys.append(QSet<QString>{});
    else if (c == '}')
      keys.removeLast();
    else if (c == '"') {
      auto start = i++;
      while (i < json.size() && json[i] != '"') {
        if (json[i] == '\\')
          ++i;
        ++i;
      }
      auto next = i + 1;
      while (next < json.size() &&
             QByteArrayView(" \r\n\t").contains(json[next]))
        ++next;
      if (next == json.size() || json[next] != ':' || keys.isEmpty())
        continue;
      auto key =
          QJsonDocument::fromJson("[" + json.mid(start, i - start + 1) + "]")
              .array()
              .first()
              .toString();
      if (keys.last().contains(key))
        return false;
      keys.last().insert(key);
    }
  }
  return true;
}
} // namespace
Catalog loadCatalog() {
  static const QRegularExpression separators(
      QStringLiteral("[^\\p{L}\\p{N}]+"));
  Catalog result;
  auto *list = g_app_info_get_all();
  for (GList *i = list; i; i = i->next) {
    auto *info = G_APP_INFO(i->data);
    if (!G_IS_DESKTOP_APP_INFO(info) || !g_app_info_should_show(info))
      continue;
    auto *app = G_DESKTOP_APP_INFO(info);
    Entry e;
    e.id = str(g_app_info_get_id(info));
    if (e.id.isEmpty() || e.id == "lxqt-comfort.desktop" ||
        g_desktop_app_info_get_is_hidden(app))
      continue;
    e.app = {G_DESKTOP_APP_INFO(g_object_ref(app)), g_object_unref};
    e.name = str(g_app_info_get_display_name(info));
    e.filename = str(g_desktop_app_info_get_filename(app));
    e.executable = str(g_app_info_get_executable(info));
    e.wmClass = str(g_desktop_app_info_get_startup_wm_class(app));
    e.description = str(g_app_info_get_description(info));
    e.categories = str(g_desktop_app_info_get_categories(app))
                       .split(';', Qt::SkipEmptyParts);
    QStringList keywords;
    for (auto p = g_desktop_app_info_get_keywords(app); p && *p; ++p)
      keywords << str(*p);
    for (auto s : {e.name, e.executable, keywords.join(' '), e.description}) {
      e.fields << normalized(s);
      e.tokens << e.fields.last().split(separators, Qt::SkipEmptyParts);
    }
    auto *icon = g_app_info_get_icon(info);
    if (icon && G_IS_THEMED_ICON(icon))
      for (auto p = g_themed_icon_get_names(G_THEMED_ICON(icon));
           *p && e.icon.isNull(); ++p)
        e.icon = QIcon::fromTheme(str(*p));
    if (icon && G_IS_FILE_ICON(icon)) {
      char *path = g_file_get_path(g_file_icon_get_file(G_FILE_ICON(icon)));
      if (path)
        e.icon = QIcon(QFile::decodeName(path));
      g_free(path);
    }
    result << std::move(e);
  }
  g_list_free_full(list, g_object_unref);
  std::sort(result.begin(), result.end(), [](const Entry &a, const Entry &b) {
    return std::tie(a.fields.first(), a.id) < std::tie(b.fields.first(), b.id);
  });
  return result;
}
QStringList searchApps(const Catalog &apps, const QString &text) {
  const QString query = normalized(text);
  if (query.isEmpty())
    return {};
  auto terms = query.split(' ');
  terms.removeDuplicates();
  using Rank = std::tuple<int, int, QString, QString>;
  QList<Rank> hits;
  for (const auto &e : apps) {
    int score = 0;
    bool allName = true;
    bool matched = true;
    for (const auto &term : terms) {
      int best = 100;
      for (int i = 0; i < e.fields.size(); ++i) {
        if (!e.fields[i].contains(term))
          continue;
        const auto &tokens = e.tokens[i];
        bool prefix =
            std::any_of(tokens.begin(), tokens.end(),
                        [&](const auto &t) { return t.startsWith(term); });
        best = i * 3 + (tokens.contains(term) ? 0 : prefix ? 1 : 2);
        break;
      }
      if (best == 100) {
        matched = false;
        break;
      }
      allName &= best < 2;
      score += best;
    }
    if (matched) {
      auto name = e.fields.first();
      int tier = query == name                                ? 0
                 : query == QFileInfo(e.fields[1]).fileName() ? 1
                 : name.startsWith(query)                     ? 2
                 : allName                                    ? 3
                                                              : 4;
      hits.emplaceBack(tier, score, name, e.id);
    }
  }
  std::sort(hits.begin(), hits.end());
  QStringList result;
  for (const auto &hit : hits)
    result << std::get<3>(hit);
  return result;
}
QStringList defaultPins(const Catalog &apps) {
  using Slot = std::pair<QStringList, QStringList>;
  const QList<Slot> defaults = {
      {{"qterminal.desktop", "org.kde.konsole.desktop",
        "org.gnome.Terminal.desktop", "xfce4-terminal.desktop",
        "xterm.desktop"},
       {"x-scheme-handler/terminal"}},
      {{"firefox.desktop", "org.mozilla.firefox.desktop"},
       {"x-scheme-handler/https"}},
      {{"org.kde.dolphin.desktop"}, {"inode/directory"}},
      {{"org.kde.kate.desktop"}, {"text/plain"}},
      {{"vlc.desktop", "org.videolan.VLC.desktop"},
       {"video/mp4", "audio/mpeg"}},
      {{"lxqt-config.desktop"}, {}}};
  QStringList result;
  for (auto [ids, types] : defaults) {
    for (const auto &type : types) {
      auto *info = g_app_info_get_default_for_type(type.toUtf8(), false);
      if (info) {
        ids << str(g_app_info_get_id(info));
        g_object_unref(info);
      }
    }
    for (const auto &id : ids) {
      auto i = std::find_if(apps.begin(), apps.end(), [&](const Entry &e) {
        return e.id == id &&
               (g_desktop_app_info_get_boolean(e.app.get(),
                                               "DBusActivatable") ||
                !QStandardPaths::findExecutable(e.executable).isEmpty());
      });
      if (i != apps.end()) {
        if (!result.contains(id))
          result << id;
        break;
      }
    }
  }
  return result;
}
QString identifyApp(const Catalog &apps, const QStringList &names,
                    const QStringList &classes) {
  auto bare = [](QString id) {
    if (id.endsWith(".desktop"))
      id.chop(8);
    return id;
  };
  for (const auto &name : names) {
    QStringList matches;
    for (const auto &e : apps)
      if (name == e.id || name == bare(e.id) || name == e.filename)
        matches << e.id;
    if (!matches.isEmpty())
      return matches.size() == 1 ? matches.first() : QString{};
  }
  for (int level = 0; level < 3; ++level) {
    QStringList matches;
    for (const auto &e : apps) {
      auto id = bare(e.id);
      QStringList candidates =
          level == 0   ? QStringList{e.wmClass}
          : level == 1 ? QStringList{id}
                       : QStringList{QFileInfo(e.executable).fileName(),
                                     id.section('.', -1)};
      for (const auto &c : classes) {
        if (!c.isEmpty() && candidates.contains(c, Qt::CaseInsensitive)) {
          matches << e.id;
          break;
        }
      }
    }
    if (!matches.isEmpty())
      return matches.size() == 1 ? matches.first() : QString{};
  }
  return {};
}
QString configPath(const QString &name) {
  return QStandardPaths::writableLocation(
             QStandardPaths::GenericConfigLocation) +
         "/lxqt-comfort/" + name;
}
Preference readPreference(const QString &name, QJsonDocument initial) {
  Preference pref{configPath(name), {}, initial, false, {}};
  try {
    pref.original = readBytes(pref.path, pref.exists);
    if (pref.exists) {
      QJsonParseError err;
      pref.value = QJsonDocument::fromJson(pref.original, &err);
      if (err.error != QJsonParseError::NoError)
        fail(err.errorString());
      if (!uniqueObjectKeys(pref.original))
        fail("Duplicate preference key");
    }
  } catch (const std::exception &e) {
    pref.error = QString::fromUtf8(e.what());
  }
  return pref;
}
void Preference::save(const QJsonDocument &next, bool backup) {
  if (!error.isEmpty())
    fail(error);
  QString dir = QFileInfo(path).absolutePath();
  if (!QDir().mkpath(dir))
    fail("Cannot create preference directory");
  Fd lock{::open(QFile::encodeName(dir + "/.portable-settings.lock"),
                 O_CREAT | O_RDWR | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC, 0600)};
  if (lock.fd < 0 || flock(lock.fd, LOCK_EX | LOCK_NB))
    fail("Preferences are busy");
  bool present;
  auto current = readBytes(path, present);
  if (present != exists || current != original)
    fail("Preferences changed elsewhere. Reopen Start.");
  auto bytes = next.toJson();
  if (bytes.size() > maxBytes)
    fail("Preferences exceed size limit");
  if (present && next == value)
    return;
  if (backup && present) {
    QFile b(path + ".backup-" +
            QUuid::createUuid().toString(QUuid::WithoutBraces));
    if (!b.open(QIODevice::NewOnly | QIODevice::WriteOnly,
                QFile::ReadOwner | QFile::WriteOwner) ||
        b.write(current) != current.size() || !b.flush())
      fail("Could not save preference backup");
  }
  if (!present) {
    QTemporaryFile tmp(dir + "/.menu-XXXXXX");
    if (!tmp.open() || tmp.write(bytes) != bytes.size() || !tmp.flush() ||
        fsync(tmp.handle()) ||
        ::link(QFile::encodeName(tmp.fileName()), QFile::encodeName(path)))
      fail("Could not create " + path +
           ". Reopen Start if preferences changed.");
  } else {
    QSaveFile f(path);
    if (!f.open(QIODevice::WriteOnly) ||
        !f.setPermissions(QFile::ReadOwner | QFile::WriteOwner) ||
        f.write(bytes) != bytes.size() || !f.commit())
      fail("Could not save " + path);
  }
  original = bytes;
  exists = true;
  value = next;
}
Preference readPins(const Catalog &apps) {
  auto saved = readPreference(
      "favorites.json",
      QJsonDocument(QJsonArray::fromStringList(defaultPins(apps))));
  if (!strings(saved.value.array()) || !saved.value.isArray())
    saved.error = "Invalid favorites list";
  return saved;
}
Preference readRecent() {
  auto saved = readPreference(
      "recent.json",
      QJsonDocument(QJsonObject{{"enabled", true}, {"items", QJsonArray{}}}));
  auto o = saved.value.object();
  auto limit = o.value("limit").toInt(20);
  if (!o["enabled"].isBool() || !strings(o["items"]) ||
      o["items"].toArray().size() > limit ||
      (o.contains("limit") && !bounded(o["limit"], 1, 50)) ||
      (o.contains("version") && !bounded(o["version"], 1, 1)) ||
      (o.contains("retention_days") && !bounded(o["retention_days"], 0, 365)) ||
      (o.contains("launched_at") && !o["launched_at"].isObject()))
    saved.error = "Invalid recent-program settings";
  const auto times = o.value("launched_at").toObject();
  if (times.size() > 50)
    saved.error = "Invalid timestamps";
  for (auto i = times.begin(); i != times.end(); ++i)
    if (i.key().isEmpty() || i.key().size() > 4096 ||
        !bounded(i.value(), 0, 253402300799))
      saved.error = "Invalid timestamps";
  return saved;
}
QStringList recentItems(const QJsonObject &o, qint64 now) {
  QStringList list;
  if (!o["enabled"].toBool())
    return list;
  int days = o.value("retention_days").toInt();
  for (const auto id : o["items"].toArray()) {
    auto time =
        o.value("launched_at").toObject().value(id.toString()).toInteger(-1);
    if (!days || (time >= 0 && now >= time && now - time < days * 86400LL))
      list << id.toString();
  }
  return list;
}
void updateHistory(const QString &id, std::optional<bool> enabled, bool clear,
                   std::optional<int> limit, std::optional<int> days) {
  auto pref = readRecent();
  if (!pref.error.isEmpty())
    fail(pref.error);
  auto o = pref.value.object();
  auto now = QDateTime::currentSecsSinceEpoch();
  auto items = recentItems(o, now);
  auto stamps = o.value("launched_at").toObject();
  if (enabled)
    o.insert("enabled", *enabled);
  if (days)
    o.insert("retention_days", *days);
  if (limit)
    o.insert("limit", *limit);
  if (o.value("retention_days").toInt())
    items.removeIf([&](const QString &key) {
      auto stamp = stamps.value(key).toInteger(-1);
      return stamp < 0 || stamp > now ||
             now - stamp >= 86400LL * o.value("retention_days").toInt();
    });
  if (!id.isEmpty() && o["enabled"].toBool()) {
    items.removeAll(id);
    items.prepend(id);
    stamps[id] = now;
  }
  if (clear || !o["enabled"].toBool())
    items.clear();
  items = items.mid(0, o.value("limit").toInt(20));
  o["items"] = QJsonArray::fromStringList(items);
  o.remove("launched_at");
  if (o.value("retention_days").toInt()) {
    QJsonObject kept;
    for (const auto &key : items)
      kept[key] = stamps[key];
    o["launched_at"] = kept;
  }
  if (o != pref.value.object())
    pref.save(QJsonDocument(o), false);
}
