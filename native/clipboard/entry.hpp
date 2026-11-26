#pragma once
#include <QImage>
#include <QMap>
#include <QMimeData>
#include <memory>
#include <optional>

namespace clip {
constexpr qsizetype maxEntry = 4 * 1024 * 1024;
struct Entry {
  QMap<QString, QByteArray> formats;
  QString text;
  QImage image;
  bool complete = true;
  qsizetype size() const;
  QByteArray identity() const;
  std::unique_ptr<QMimeData> mime(bool replay) const;
};
std::optional<Entry> snapshot(const QMimeData *source);
QByteArray encode(const Entry &entry);
std::optional<Entry> decode(const QByteArray &bytes);
} // namespace clip
