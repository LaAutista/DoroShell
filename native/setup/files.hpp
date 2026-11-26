// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QDir>
#include <QFileInfo>
#include <QJsonObject>
#include <QRegularExpression>
#include <QFile>
#include <fcntl.h>
#include <stdexcept>
#include <sys/stat.h>
#include <unistd.h>

namespace doro_files {
[[noreturn]] inline void fail(const QString &text) { throw std::runtime_error(text.toStdString()); }
inline QString path(const QString &home, const QString &rel) {
  QString out = home;
  for (const auto &piece : rel.split('/')) {
    if (piece.isEmpty() || piece == "." || piece == "..")
      fail("Invalid path");
    out += '/' + piece;
    if (QFileInfo(out).isSymLink())
      fail("Refusing symbolic link: " + out);
  }
  return out;
}
inline void makeParents(const QString &filename) {
  if (!QDir().mkpath(QFileInfo(filename).absolutePath()))
    fail("Cannot create directory for " + filename);
}
inline QJsonObject absent() { return {{"exists", false}}; }
inline QJsonObject read(const QString &filename, qint64 maxSize = 1024 * 1024) {
  struct stat st{};
  if (::lstat(QFile::encodeName(filename).constData(), &st)) {
    if (errno == ENOENT)
      return absent();
    fail("Cannot inspect " + filename);
  }
  if (!S_ISREG(st.st_mode) || st.st_uid != getuid() ||
      st.st_size > maxSize || (st.st_mode & 07000))
    fail("Unsupported existing file: " + filename);
  QFile f(filename);
  if (!f.open(QIODevice::ReadOnly))
    fail("Cannot read " + filename);
  auto data = f.readAll();
  if (f.error() != QFileDevice::NoError)
    fail(f.errorString());
  return {{"exists", true},
          {"mode", int(st.st_mode & 0777)},
          {"data", QString::fromLatin1(data.toBase64())}};
}
inline QByteArray bytes(const QJsonObject &state) {
  auto result =
      QByteArray::fromBase64Encoding(state["data"].toString().toLatin1(),
                                     QByteArray::AbortOnBase64DecodingErrors);
  if (!result)
    fail("Invalid backup bytes");
  return *result;
}
inline void validate(const QJsonObject &state) {
  if (state == absent())
    return;
  if (state.size() != 3 || state["exists"] != QJsonValue(true) ||
      !state["data"].isString() || state["mode"].toInt(-1) < 0 ||
      state["mode"].toInt() > 0777)
    fail("Invalid backup state");
  bytes(state);
}
inline void syncParent(const QString &filename) {
  auto dir = QFile::encodeName(QFileInfo(filename).absolutePath());
  int fd = ::open(dir.constData(), O_RDONLY | O_DIRECTORY | O_CLOEXEC);
  if (fd < 0)
    fail("Cannot open directory for " + filename);
  bool ok = ::fsync(fd) == 0;
  ::close(fd);
  if (!ok)
    fail("Cannot sync directory for " + filename);
}
inline void atomic(const QString &filename, const QByteArray &content, int mode) {
  makeParents(filename);
  // Set the mode on the named inode that will actually be renamed. A
  // QSaveFile engine may materialize an unnamed temporary inode during commit.
  auto temporary = QFile::encodeName(QFileInfo(filename).absolutePath() + "/.doroshell-XXXXXX");
  const int fd = ::mkostemp(temporary.data(), O_CLOEXEC);
  if (fd < 0)
    fail("Cannot create temporary file for " + filename);
  QFile file;
  if (!file.open(fd, QIODevice::WriteOnly, QFileDevice::DontCloseHandle) ||
      file.write(content) != content.size() || !file.flush() ||
      ::fchmod(fd, mode) || ::fsync(fd)) {
    file.close();
    ::close(fd);
    ::unlink(temporary.constData());
    fail("Could not atomically write " + filename);
  }
  file.close();
  if (::close(fd) || ::rename(temporary.constData(), QFile::encodeName(filename).constData())) {
    ::unlink(temporary.constData());
    fail("Cannot replace " + filename);
  }
  syncParent(filename);
}
inline void write(const QString &filename, const QJsonObject &state) {
  if (state == absent()) {
    if (QFileInfo::exists(filename)) {
      if (!QFile::remove(filename)) fail("Cannot remove " + filename);
      syncParent(filename);
    }
  } else
    atomic(filename, bytes(state), state["mode"].toInt());
}
inline QString desktopQuote(QString token) {
  if (token.contains(QRegularExpression("[\\x00-\\x1f\\x7f]")))
    fail("Unsupported control character in path");
  token.replace("%", "%%");
  for (auto ch : {'\\', '"', '`', '$'})
    token.replace(QChar(ch), QString("\\") + QChar(ch));
  return '"' + token.replace("\\", "\\\\") + '"';
}
} // namespace doro_files
