#include "browse.hpp"
#include <QCoreApplication>
#include <QDateTime>
#include <QDirIterator>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QProcess>
#include <QSet>
#include <QStandardPaths>
#include <QTimer>
#include <QUrl>
#include <QXmlStreamReader>
#include <fcntl.h>
#include <stdexcept>
#include <sys/stat.h>
#include <unistd.h>

namespace {
[[noreturn]] void invalid() {
  throw std::runtime_error("Unsupported desktop history");
}
bool clean(const QString &s) {
  for (auto c : s)
    if (!c.isPrint() || c.category() == QChar::Separator_Line ||
        c.category() == QChar::Separator_Paragraph)
      return false;
  return true;
}
QString localPath(const QString &raw) {
  if (raw.size() > 4096 || !raw.startsWith("file:", Qt::CaseInsensitive) ||
      raw.contains('?') || raw.contains('#') || !clean(raw))
    return {};
  QUrl uri(raw, QUrl::StrictMode);
  if (!uri.isValid() || uri.hasQuery() || uri.hasFragment() ||
      (!uri.authority().isEmpty() && uri.authority().toLower() != "localhost"))
    return {};
  QStringDecoder decode(QStringDecoder::Utf8);
  QString path = decode(
      QByteArray::fromPercentEncoding(uri.path(QUrl::FullyEncoded).toUtf8()));
  if (decode.hasError() || !path.startsWith('/') || !clean(path))
    return {};
  for (const auto &part : path.mid(1).split('/'))
    if (part.isEmpty() || part == "." || part == "..")
      return {};
  return QUrl::fromLocalFile(path).toEncoded().size() <= 4096 ? path
                                                              : QString{};
}
} // namespace
QJsonArray parseDocuments(const QByteArray &xml) {
  if (xml.size() > 1024 * 1024)
    invalid();
  QXmlStreamReader r(xml);
  QHash<QString, qint64> records;
  QSet<QString> privatePaths;
  int depth = 0, count = 0;
  QString current;
  bool privateItem = false;
  qint64 stamp = std::numeric_limits<qint64>::min();
  while (!r.atEnd()) {
    auto t = r.readNext();
    if (t == QXmlStreamReader::DTD || t == QXmlStreamReader::EntityReference)
      invalid();
    if (t == QXmlStreamReader::StartElement) {
      ++depth;
      if (depth > 16 || r.attributes().size() > 32 ||
          (depth == 1 && (r.name() != u"xbel" || !r.namespaceUri().isEmpty())))
        invalid();
      if (r.name() == u"bookmark" && r.namespaceUri().isEmpty()) {
        if (depth != 2 || ++count > 2048)
          invalid();
        current = localPath(r.attributes().value("href").toString());
        privateItem = false;
        stamp = std::numeric_limits<qint64>::min();
        for (auto key : {"visited", "modified", "added"}) {
          auto date = QDateTime::fromString(
              r.attributes().value(key).toString(), Qt::ISODateWithMs);
          if (date.isValid() && date.timeSpec() != Qt::LocalTime)
            stamp = std::max(stamp, date.toMSecsSinceEpoch());
        }
      } else if (r.name() == u"private" &&
                 r.namespaceUri() ==
                     u"http://www.freedesktop.org/standards/desktop-bookmarks")
        privateItem = true;
    } else if (t == QXmlStreamReader::EndElement) {
      if (depth == 2 && !current.isEmpty()) {
        if (privateItem)
          privatePaths.insert(current);
        if (!records.contains(current) || records[current] < stamp)
          records[current] = stamp;
        current.clear();
      }
      --depth;
    }
  }
  if (r.hasError())
    invalid();
  auto keys = records.keys();
  keys.removeIf([&](auto &key) { return privatePaths.contains(key); });
  std::sort(keys.begin(), keys.end(), [&](auto &a, auto &b) {
    return records[a] != records[b] ? records[a] > records[b] : a < b;
  });
  QJsonArray result;
  for (const auto &key : keys.mid(0, 20))
    result.append(
        QJsonObject{{"path", key}, {"name", key.section('/', -1).left(128)}});
  return result;
}
QJsonArray readDocuments() {
  auto base =
      QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation);
  auto path = QFile::encodeName(base + "/recently-used.xbel");
  int fd = ::open(path, O_RDONLY | O_NONBLOCK | O_NOFOLLOW | O_CLOEXEC);
  if (fd < 0) {
    if (errno == ENOENT)
      return {};
    invalid();
  }
  QFile f;
  if (!f.open(fd, QIODevice::ReadOnly, QFileDevice::AutoCloseHandle)) {
    close(fd);
    invalid();
  }
  struct stat st{};
  if (fstat(fd, &st) || !S_ISREG(st.st_mode) || st.st_size > 1024 * 1024)
    invalid();
  auto bytes = f.read(1024 * 1024 + 1);
  if (f.error() != QFile::NoError)
    invalid();
  return parseDocuments(bytes);
}
QJsonArray listFolder(const QString &path) {
  if (!QDir::isAbsolutePath(path))
    throw std::runtime_error("Invalid folder path");
  QDir dir(path);
  if (!dir.exists() || !dir.isReadable())
    throw std::runtime_error("Cannot read folder");
  QDirIterator iter(path, QDir::AllEntries | QDir::NoDotAndDotDot |
                              QDir::Hidden | QDir::System);
  QFileInfoList entries;
  int scanned = 0;
  while (scanned < 2000 && iter.hasNext()) {
    iter.next();
    ++scanned;
    auto f = iter.fileInfo();
    if (f.isHidden() || f.isSymLink() || (!f.isDir() && !f.isFile()))
      continue;
    entries << f;
  }
  std::sort(entries.begin(), entries.end(), [](auto &a, auto &b) {
    if (a.isDir() != b.isDir())
      return a.isDir();
    auto diff =
        QString::compare(a.fileName(), b.fileName(), Qt::CaseInsensitive);
    return diff == 0 ? a.fileName() < b.fileName() : diff < 0;
  });
  QJsonArray result;
  for (auto &f : entries.mid(0, 200))
    result.append(
        QJsonObject{{"name", f.fileName()}, {"directory", f.isDir()}});
  if (entries.size() > 200 || iter.hasNext())
    result.append(QJsonObject{{"limited", true}});
  return result;
}
void browseWorker(QMenu *menu, QStringList arguments,
                  std::function<void(QJsonArray)> finished) {
  auto *p = new QProcess(menu);
  p->setStandardErrorFile(QProcess::nullDevice());
  auto *timer = new QTimer(p);
  timer->setSingleShot(true);
  auto fail = [p, menu] {
    if (!menu->isVisible() || p->property("stopped").toBool())
      return;
    p->setProperty("stopped", true);
    menu->addAction("Unavailable. Reopen to try again.")->setEnabled(false);
    if (p->state() != QProcess::NotRunning)
      p->kill();
  };
  QObject::connect(timer, &QTimer::timeout, p, fail);
  QObject::connect(menu, &QMenu::aboutToHide, p, [p] {
    p->setProperty("stopped", true);
    if (p->state() != QProcess::NotRunning)
      p->kill();
  });
  QObject::connect(p, &QProcess::errorOccurred, p,
                   [p, fail](QProcess::ProcessError e) {
                     fail();
                     if (e == QProcess::FailedToStart)
                       p->deleteLater();
                   });
  QObject::connect(
      p, &QProcess::finished, p,
      [p, menu, timer, finished, fail](int code, QProcess::ExitStatus status) {
        timer->stop();
        if (!p->property("stopped").toBool() && menu->isVisible()) {
          auto bytes = p->readAllStandardOutput();
          auto json = QJsonDocument::fromJson(bytes);
          if (code || status != QProcess::NormalExit ||
              bytes.size() > 1024 * 1024 || !json.isArray())
            fail();
          else
            finished(json.array());
        }
        p->deleteLater();
      });
  p->start(QCoreApplication::applicationFilePath(), arguments);
  timer->start(1500);
}
