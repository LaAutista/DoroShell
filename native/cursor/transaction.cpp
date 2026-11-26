#include "cursor.hpp"
#include <QtCore>
#include <fcntl.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

namespace cursor {
namespace {
const QString root = ".icons/DoroShell-Loading/",
              session = ".config/lxqt/session.conf",
              parentTheme = ".icons/default/index.theme",
              xresources = ".Xresources",
              receipt = ".local/state/lxqt-comfort/cursor-install.json";
const QString themeName = "DoroShell-Loading";
struct State {
  QByteArray data;
  int mode = 0644;
};
bool operator==(const State &a, const State &b) {
  return a.data.isNull() == b.data.isNull() && a.data == b.data &&
         (a.data.isNull() || a.mode == b.mode);
}
QJsonValue hash(const State &s) {
  return s.data.isNull()
             ? QJsonValue(QJsonValue::Null)
             : QJsonValue(QString::fromLatin1(
                   QCryptographicHash::hash(s.data, QCryptographicHash::Sha256)
                       .toHex()));
}
QString path(const QString &home, const QString &rel) {
  if (!QDir::isAbsolutePath(home) ||
      QFileInfo(home).canonicalFilePath() != home ||
      QFileInfo(home).ownerId() != getuid())
    fail("Use an existing, canonical home owned by your account.");
  auto p = home;
  for (const auto &part : rel.split('/')) {
    if (part.isEmpty() || part == "." || part == "..")
      fail("Invalid cursor file path.");
    p += "/" + part;
    QFileInfo f(p);
    if (f.isSymLink())
      fail("Refusing a symlink: " + p);
  }
  return p;
}
State read(const QString &home, const QString &rel) {
  const auto p = path(home, rel);
  auto name = QFile::encodeName(p);
  int fd = open(name, O_NOFOLLOW | O_NONBLOCK | O_RDONLY | O_CLOEXEC);
  if (fd < 0) {
    if (errno == ENOENT)
      return {};
    fail("Cannot read " + p);
  }
  QFile f;
  if (!f.open(fd, QIODevice::ReadOnly, QFileDevice::AutoCloseHandle)) {
    close(fd);
    fail("Cannot read " + p);
  }
  int cap = rel == receipt ? 240 * 1024 * 1024 : 64 * 1024 * 1024;
  struct stat st{};
  if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_uid != getuid() ||
      (st.st_mode & 07000) || st.st_size > cap)
    fail("Unsupported cursor file: " + p);
  auto bytes = f.read(cap + 1);
  struct stat after{};
  if (fstat(fd, &after) || bytes.size() != st.st_size ||
      f.error() != QFile::NoError ||
      st.st_mtim.tv_sec != after.st_mtim.tv_sec ||
      st.st_mtim.tv_nsec != after.st_mtim.tv_nsec)
    fail("Cursor file changed while reading: " + p);
  return {bytes.isNull() ? QByteArray("") : bytes, int(st.st_mode & 0777)};
}
void write(const QString &home, const QString &rel, const State &expected,
           const State &wanted) {
  if (!(read(home, rel) == expected))
    fail("Cursor file changed during apply: " + rel);
  if (expected == wanted)
    return;
  const auto p = path(home, rel);
  if (wanted.data.isNull()) {
    if (!QFile::remove(p))
      fail("Cannot remove " + p);
    return;
  }
  if (!QDir().mkpath(QFileInfo(p).absolutePath()))
    fail("Cannot create cursor directory.");
  QSaveFile f(p);
  QFile::Permissions permissions;
  constexpr QFile::Permission bits[] = {
      QFile::ExeOther, QFile::WriteOther, QFile::ReadOther,
      QFile::ExeGroup, QFile::WriteGroup, QFile::ReadGroup,
      QFile::ExeOwner, QFile::WriteOwner, QFile::ReadOwner};
  for (int i = 0; i < 9; ++i)
    if (wanted.mode & (1 << i))
      permissions |= bits[i];
  if (!f.open(QIODevice::WriteOnly) || !f.setPermissions(permissions) ||
      f.write(wanted.data) != wanted.data.size() || !f.flush() ||
      fsync(f.handle()) || !(read(home, rel) == expected) || !f.commit())
    fail("Could not save " + p);
}
struct Lock {
  int fd = -1;
  explicit Lock(const QString &home) {
    auto p = path(home, ".local/state/doroshell/cursor.lock");
    if (!QDir().mkpath(QFileInfo(p).absolutePath()))
      fail("Cannot create cursor state directory.");
    fd = open(QFile::encodeName(p),
              O_CLOEXEC | O_CREAT | O_RDWR | O_NOFOLLOW | O_NONBLOCK, 0600);
    struct stat st{};
    if (fd < 0 || fstat(fd, &st) || !S_ISREG(st.st_mode) ||
        st.st_uid != getuid() || flock(fd, LOCK_EX | LOCK_NB)) {
      if (fd >= 0)
        close(fd);
      fail("Cursor operation is busy or lock is invalid.");
    }
  }
  ~Lock() { close(fd); }
};
QSet<QString> names() {
  QSet<QString> paths{root + "index.theme", session, parentTheme, xresources};
  for (auto it = aliases().begin(); it != aliases().end(); ++it) {
    paths.insert(root + "cursors/" + it.key());
    for (const auto &s : it.value())
      paths.insert(root + "cursors/" + s);
  }
  return paths;
}
struct Backup {
  State before;
  QJsonValue installed, pending;
  int pendingMode = -1;
};
bool digestOrNull(QJsonValue v) {
  static const QRegularExpression sha("^[0-9a-f]{64}$");
  return v.isNull() || (v.isString() && sha.match(v.toString()).hasMatch());
}
Backup validate(const QJsonObject &o) {
  auto mode = o.value("mode"), bytes = o.value("before"),
       installed = o.value("installed"), pending = o.value("pending_from"),
       prior = o.value("pending_mode");
  if (mode.toInt(-1) < 0 || mode.toInt() > 0777 ||
      (!bytes.isNull() && !bytes.isString()) || !digestOrNull(installed) ||
      pending.isUndefined() != prior.isUndefined() ||
      (!pending.isUndefined() &&
       (!digestOrNull(pending) ||
        (pending.isNull() ? !prior.isNull()
                          : (prior.toInt(-1) < 0 || prior.toInt() > 0777)))))
    fail("Invalid cursor receipt.");
  State before{{}, mode.toInt()};
  if (bytes.isString()) {
    auto decoded = QByteArray::fromBase64Encoding(
        bytes.toString().toLatin1(), QByteArray::AbortOnBase64DecodingErrors);
    if (!decoded || decoded.decoded.size() > 64 * 1024 * 1024)
      fail("Invalid cursor backup data.");
    before.data = decoded.decoded.isNull() ? QByteArray("") : decoded.decoded;
  }
  return {before, installed, pending, prior.toInt(-1)};
}
QByteArray setIni(QByteArray data, QString section, QString key,
                  QString value) {
  if (!data.isValidUtf8())
    fail("Invalid UTF-8 settings.");
  QStringList lines = QString::fromUtf8(data).split('\n');
  bool in = false, seen = false, written = false;
  QString output;
  const QString item = key + "=" + value + "\n";
  for (qsizetype i = 0; i < lines.size(); ++i) {
    QString raw = lines[i], stripped = raw.trimmed();
    if (stripped.startsWith('[') && stripped.endsWith(']')) {
      if (in && !written) {
        output += item;
        written = true;
      }
      in = stripped == "[" + section + "]";
      if (in && seen)
        fail("Duplicate cursor settings section.");
      seen |= in;
    } else if (in && stripped.section('=', 0, 0).trimmed() == key &&
               stripped.contains('=')) {
      if (written)
        fail("Duplicate cursor setting.");
      output += item;
      written = true;
      continue;
    }
    if (i < lines.size() - 1 || !raw.isEmpty())
      output += raw + "\n";
  }
  if (!seen) {
    if (!output.isEmpty() && !output.endsWith("\n\n"))
      output += "\n";
    output += "[" + section + "]\n";
  }
  if (!written)
    output += item;
  return output.toUtf8();
}
QByteArray setXresources(QByteArray bytes) {
  if (!bytes.isValidUtf8())
    fail("Invalid UTF-8 Xresources.");
  QString text = QString::fromUtf8(bytes);
  QRegularExpression line("(?m)^Xcursor\\.theme[ \\t]*:[^\\r\\n]*");
  auto desired = "Xcursor.theme: " + themeName;
  if (text.contains(line))
    text.replace(line, desired);
  else {
    if (!text.isEmpty() && !text.endsWith('\n'))
      text += '\n';
    text += desired + "\n";
  }
  return text.toUtf8();
}
} // namespace
QStringList change(const QString &home, const QString &image,
                   const QString &base, bool pink, bool apply, bool restore) {
  auto allowed = names();
  std::unique_ptr<Lock> lock;
  if (apply || restore)
    lock = std::make_unique<Lock>(home);
  auto original = read(home, receipt);
  QJsonObject manifest;
  if (!original.data.isNull()) {
    auto doc = QJsonDocument::fromJson(original.data);
    if (!doc.isObject() || doc.object().isEmpty())
      fail("Invalid cursor receipt.");
    manifest = doc.object();
    for (auto it = manifest.begin(); it != manifest.end(); ++it) {
      if (!allowed.contains(it.key()) || !it.value().isObject())
        fail("Unexpected cursor receipt path.");
      validate(it.value().toObject());
    }
    auto required = allowed;
    required.remove(root + "cursors/default");
    for (const auto &n : aliases().value("default"))
      required.remove(root + "cursors/" + n);
    for (const auto &n : required)
      if (!manifest.contains(n))
        fail("Incomplete cursor receipt.");
  }
  if (restore && manifest.isEmpty())
    return {"No managed cursor theme."};
  auto baseName = QFileInfo(QDir::cleanPath(base)).fileName();
  if (!restore &&
      (baseName == themeName ||
       !QRegularExpression("^[\\p{L}\\p{N}_+ -][\\p{L}\\p{N}._+ -]{0,127}$")
            .match(baseName)
            .hasMatch()))
    fail("Invalid inherited cursor theme name.");
  QMap<QString, State> current, target;
  for (const auto &n : allowed)
    if (!restore || manifest.contains(n))
      current[n] = read(home, n);
  if (!restore) {
    auto art = generate(image, base, pink);
    for (auto it = art.begin(); it != art.end(); ++it)
      for (auto n : QStringList{it.key()} + aliases().value(it.key()))
        target[root + "cursors/" + n] = {it.value()};
    target[root + "index.theme"] = {
        ("[Icon Theme]\nName=DoroShell Loading\nComment=Personal animated "
         "loading cursors\nInherits=" +
         baseName + "\n")
            .toUtf8()};
    target[session] = {
        setIni(current[session].data, "Mouse", "cursor_theme", themeName)};
    target[parentTheme] = {
        setIni(current[parentTheme].data, "Icon Theme", "Inherits", themeName)};
    target[xresources] = {setXresources(current[xresources].data)};
  }
  QJsonObject pending = manifest, final;
  for (auto it = manifest.begin(); it != manifest.end(); ++it) {
    auto n = it.key();
    const auto rec = validate(it.value().toObject());
    auto now = current[n];
    auto digest = hash(now);
    bool installed = rec.installed == digest &&
                     (digest.isNull() || now.mode == rec.before.mode);
    bool pendingBefore = !rec.pending.isUndefined() && rec.pending == digest &&
                         (digest.isNull() || now.mode == rec.pendingMode);
    if (!installed && !pendingBefore && !(restore && now == rec.before))
      fail("Edited managed cursor file: " + n);
    if (!target.contains(n))
      target[n] = rec.before;
  }
  QStringList touched;
  for (auto it = target.begin(); it != target.end(); ++it) {
    const auto n = it.key();
    auto now = current[n];
    auto rec = manifest.value(n).toObject();
    if (rec.isEmpty()) {
      rec["before"] = now.data.isNull()
                          ? QJsonValue(QJsonValue::Null)
                          : QString::fromLatin1(now.data.toBase64());
      rec["mode"] = now.mode;
    }
    it.value().mode = rec.value("mode").toInt();
    if (!(now == it.value()))
      touched << n;
    rec["installed"] = hash(it.value());
    rec.remove("pending_from");
    rec.remove("pending_mode");
    final[n] = rec;
    rec["pending_from"] = hash(now);
    rec["pending_mode"] =
        now.data.isNull() ? QJsonValue(QJsonValue::Null) : QJsonValue(now.mode);
    pending[n] = rec;
  }
  if (!restore && !apply)
    return touched.isEmpty() ? QStringList{"Cursor already matches."} : touched;
  if (!restore && touched.isEmpty() && final == manifest)
    return {"Cursor already matches."};
  State journal = original;
  if (!restore) {
    journal = {QJsonDocument(pending).toJson(QJsonDocument::Compact), 0600};
    if (journal.data.size() > 240 * 1024 * 1024)
      fail("Cursor receipt exceeds size limit.");
    write(home, receipt, original, journal);
  }
  for (auto it = target.begin(); it != target.end(); ++it)
    write(home, it.key(), current[it.key()], it.value());
  for (auto it = target.begin(); it != target.end(); ++it)
    if (!(read(home, it.key()) == it.value()))
      fail("Cursor changed during finalization: " + it.key());
  write(home, receipt, journal,
        restore
            ? State{}
            : State{QJsonDocument(final).toJson(QJsonDocument::Compact), 0600});
  return touched.isEmpty() ? QStringList{"Cursor settings saved."} : touched;
}
} // namespace cursor
