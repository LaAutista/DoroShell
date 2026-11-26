#include "entry.hpp"
#include <QBuffer>
#include <QCryptographicHash>
#include <QImageWriter>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPixmap>
#include <QSet>

namespace clip {
qsizetype Entry::size() const {
  qsizetype bytes = image.sizeInBytes();
  for (const auto &v : formats)
    bytes += v.size();
  return bytes;
}
QByteArray Entry::identity() const {
  QCryptographicHash hash(QCryptographicHash::Sha256);
  for (auto it = formats.cbegin(); it != formats.cend(); ++it) {
    hash.addData(it.key().toUtf8());
    hash.addData(QByteArrayView("\0", 1));
    hash.addData(it.value());
  }
  if (!image.isNull()) {
    hash.addData(
        QByteArrayView(reinterpret_cast<const char *>(image.constBits()),
                       image.sizeInBytes()));
    hash.addData(QByteArray::number(image.width()) + 'x' +
                 QByteArray::number(image.height()));
  }
  return hash.result();
}
std::unique_ptr<QMimeData> Entry::mime(bool replay) const {
  auto out = std::make_unique<QMimeData>();
  for (auto it = formats.cbegin(); it != formats.cend(); ++it) {
    auto value = it.value();
    if (replay && it.key() == "application/x-kde-cutselection")
      value = "0";
    if (replay && it.key() == "x-special/gnome-copied-files" &&
        value.startsWith("cut\n"))
      value.replace(0, 3, "copy");
    out->setData(it.key(), value);
  }
  if (!image.isNull())
    out->setImageData(image);
  return out;
}
std::optional<Entry> snapshot(const QMimeData *source) {
  if (!source)
    return {};
  const auto names = source->formats();
  if (names.size() > 32)
    return {};
  for (const auto &name : names)
    for (auto secret : {"x-kde-passwordmanagerhint", "application/x-keepass",
                        "excludeclipboardcontentfrommonitorprocessing"})
      if (name.contains(QLatin1StringView(secret), Qt::CaseInsensitive))
        return {};
  static const QSet<QString> passive = {"text/plain",
                                        "text/html",
                                        "text/uri-list",
                                        "text/rtf",
                                        "application/rtf",
                                        "x-special/gnome-copied-files",
                                        "application/x-kde-cutselection",
                                        "UTF8_STRING",
                                        "STRING",
                                        "TEXT",
                                        "COMPOUND_TEXT"};
  QSet<QString> represented = {"TARGETS", "MULTIPLE", "TIMESTAMP",
                               "SAVE_TARGETS"};
  Entry entry;
  for (const auto &name : names) {
    if (!passive.contains(name) && !name.startsWith("text/plain;charset="))
      continue;
    entry.formats.insert(name, source->data(name));
    if (entry.size() > maxEntry)
      return {};
    represented.insert(name);
  }
  if (source->hasText())
    entry.text = source->text();
  if (entry.text.size() > 262144)
    return {};
  if (source->hasImage()) {
    auto data = source->imageData();
    entry.image = qvariant_cast<QImage>(data);
    if (entry.image.isNull() && data.canConvert<QPixmap>())
      entry.image = data.value<QPixmap>().toImage();
    if (entry.image.isNull() || entry.size() > maxEntry)
      return {};
    entry.image = entry.image.convertToFormat(QImage::Format_ARGB32);
    if (entry.size() > maxEntry)
      return {};
    if (names.contains("application/x-qt-image")) {
      represented.unite({"application/x-qt-image", "BITMAP", "PIXMAP"});
      for (const auto &fmt : QImageWriter::supportedImageFormats())
        represented.insert("image/" + QString::fromLatin1(fmt));
    }
  }
  if (entry.text.isEmpty() && entry.image.isNull())
    return {};
  entry.complete =
      std::all_of(names.begin(), names.end(),
                  [&](const auto &name) { return represented.contains(name); });
  return entry;
}
QByteArray encode(const Entry &entry) {
  QJsonObject formats;
  for (auto it = entry.formats.cbegin(); it != entry.formats.cend(); ++it)
    formats.insert(it.key(), QString::fromLatin1(it.value().toBase64()));
  QByteArray png;
  if (!entry.image.isNull()) {
    QBuffer buffer(&png);
    if (!buffer.open(QIODevice::WriteOnly) || !entry.image.save(&buffer, "PNG"))
      return "null";
  }
  return QJsonDocument(
             QJsonObject{{"formats", formats},
                         {"image", QString::fromLatin1(png.toBase64())},
                         {"text", entry.text},
                         {"complete", entry.complete}})
      .toJson(QJsonDocument::Compact);
}
std::optional<Entry> decode(const QByteArray &bytes) {
  if (bytes.size() > 8 * 1024 * 1024)
    return {};
  auto obj = QJsonDocument::fromJson(bytes).object();
  if (!obj.value("text").isString() || !obj.value("formats").isObject())
    return {};
  Entry entry;
  entry.text = obj.value("text").toString();
  if (entry.text.size() > 262144)
    return {};
  entry.complete = obj.value("complete").toBool();
  auto formats = obj.value("formats").toObject();
  for (auto it = formats.begin(); it != formats.end(); ++it) {
    auto data =
        QByteArray::fromBase64Encoding(it.value().toString().toLatin1(),
                                       QByteArray::AbortOnBase64DecodingErrors);
    if (!it.value().isString() || !data)
      return {};
    entry.formats[it.key()] = *data;
  }
  auto png = obj.value("image").toString().toLatin1();
  if (!png.isEmpty()) {
    if (!entry.image.loadFromData(QByteArray::fromBase64(png), "PNG"))
      return {};
    entry.image = entry.image.convertToFormat(QImage::Format_ARGB32);
  }
  if ((entry.image.isNull() && entry.text.isEmpty()) || entry.size() > maxEntry)
    return {};
  return entry;
}
} // namespace clip
