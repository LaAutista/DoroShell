#include "cursor.hpp"
#include <QBuffer>
#include <QFile>
#include <QFileInfo>
#include <QImageReader>
#include <QPainter>
#include <QtEndian>
#include <zlib.h>

namespace cursor {
namespace {
constexpr qint64 imageLimit = 64LL * 1024 * 1024,
                 pixelLimit = 64LL * 1024 * 1024;
const QByteArray pngSignature = QByteArray::fromHex("89504e470d0a1a0a");
quint32 word(QByteArrayView data, int offset = 0) {
  return qFromBigEndian<quint32>(data.data() + offset);
}
QByteArray packed(quint32 n) {
  n = qToBigEndian(n);
  return QByteArray(reinterpret_cast<const char *>(&n), 4);
}
void chunk(QByteArray &out, QByteArrayView name, QByteArrayView data) {
  out += packed(data.size());
  out.append(name);
  out.append(data);
  uLong crc = crc32(0, reinterpret_cast<const Bytef *>(name.data()), 4);
  out += packed(
      crc32(crc, reinterpret_cast<const Bytef *>(data.data()), data.size()));
}
void checkSize(QSize size, int frames) {
  if (!size.isValid() || size.isEmpty() || size.width() > 8192 ||
      size.height() > 8192 || frames < 1 || frames > 300 ||
      qint64(size.width()) * size.height() * frames > pixelLimit)
    fail("Cursor animation exceeds the size or frame limit.");
}
Animation apng(const QByteArray &bytes) {
  // Qt decodes PNG pixels. Assemble each APNG frame as a small ordinary PNG;
  // composition/disposal happens on its authored canvas. A separate poster is
  // skipped.
  QByteArray header, palette, payload;
  QImage canvas;
  QRect rect;
  int delay = 0, dispose = 0, blend = 0, declared = 0;
  bool seenData = false, ended = false;
  quint32 sequence = 0;
  Animation animation;
  auto finish = [&] {
    if (rect.isEmpty())
      return;
    if (payload.isEmpty())
      fail("APNG frame has no pixels.");
    QByteArray png = pngSignature;
    chunk(png, "IHDR",
          packed(rect.width()) + packed(rect.height()) + header.mid(8));
    png += palette;
    chunk(png, "IDAT", payload);
    chunk(png, "IEND", {});
    auto image = QImage::fromData(png, "PNG");
    if (image.isNull() || image.size() != rect.size())
      fail("Invalid APNG image data.");
    auto previous = canvas;
    QPainter p(&canvas);
    if (!blend)
      p.setCompositionMode(QPainter::CompositionMode_Source);
    p.drawImage(rect.topLeft(), image);
    p.end();
    animation.frames.append({canvas, delay});
    if (dispose == 1) {
      QPainter clear(&canvas);
      clear.setCompositionMode(QPainter::CompositionMode_Source);
      clear.fillRect(rect, Qt::transparent);
    } else if (dispose == 2)
      canvas = previous;
    payload.clear();
    rect = {};
  };
  for (qsizetype pos = 8; pos + 12 <= bytes.size();) {
    auto count = word(bytes, pos);
    if (count > quint64(bytes.size() - pos - 12))
      fail("Truncated APNG chunk.");
    auto name = QByteArrayView(bytes).sliced(pos + 4, 4);
    auto data = QByteArrayView(bytes).sliced(pos + 8, count);
    auto crc =
        crc32(0, reinterpret_cast<const Bytef *>(name.data()), count + 4);
    if (crc != word(bytes, pos + 8 + count))
      fail("Invalid APNG checksum.");
    pos += 12 + count;
    if (name == "IHDR") {
      if (count != 13 || !header.isEmpty() || pos != 33)
        fail("Invalid APNG header.");
      header = data.toByteArray();
      checkSize({int(word(data)), int(word(data, 4))}, 1);
    } else if (name == "acTL") {
      if (header.isEmpty() || declared || seenData || count != 8)
        fail("Invalid APNG animation control.");
      declared = int(word(data));
      QSize size(int(word(header)), int(word(header, 4)));
      checkSize(size, declared);
      canvas = QImage(size, QImage::Format_ARGB32_Premultiplied);
      if (canvas.isNull())
        fail("Could not allocate animation canvas.");
      canvas.fill(Qt::transparent);
      animation.crop = canvas.rect();
    } else if (name == "fcTL") {
      if (!declared || count != 26 || word(data) != sequence++)
        fail("Invalid APNG frame control.");
      finish();
      quint32 w = word(data, 4), h = word(data, 8), x = word(data, 12),
              y = word(data, 16);
      if (!w || !h || quint64(x) + w > quint64(canvas.width()) ||
          quint64(y) + h > quint64(canvas.height()) ||
          animation.frames.size() >= declared)
        fail("Invalid APNG frame bounds.");
      rect = {int(x), int(y), int(w), int(h)};
      auto num = qFromBigEndian<quint16>(data.data() + 20),
           den = qFromBigEndian<quint16>(data.data() + 22);
      delay = qMax(10, qRound(1000. * num / (den ? den : 100)));
      dispose = uchar(data[24]);
      blend = uchar(data[25]);
      if (dispose > 2 || blend > 1)
        fail("Invalid APNG frame operation.");
    } else if (name == "IDAT") {
      seenData = true;
      if (!rect.isEmpty())
        payload.append(data);
    } else if (name == "fdAT") {
      if (!seenData || rect.isEmpty() || count < 4 || word(data) != sequence++)
        fail("Invalid APNG frame sequence.");
      payload.append(data.sliced(4));
    } else if (name == "IEND") {
      if (count || pos != bytes.size())
        fail("Invalid end of APNG.");
      finish();
      ended = true;
      break;
    } else if (!seenData &&
               (name == "PLTE" || name == "tRNS" || name == "sRGB" ||
                name == "gAMA" || name == "cHRM"))
      chunk(palette, name, data);
  }
  if (!ended || declared < 2 || animation.frames.size() != declared)
    fail("An animated PNG with at least two complete frames is required.");
  return animation;
}
QRect visible(const QImage &image) {
  int x1 = image.width(), y1 = image.height(), x2 = -1, y2 = -1;
  for (int y = 0; y < image.height(); ++y) {
    auto *p = reinterpret_cast<const QRgb *>(image.constScanLine(y));
    for (int x = 0; x < image.width(); ++x)
      if (qAlpha(p[x])) {
        x1 = qMin(x, x1);
        x2 = qMax(x, x2);
        y1 = qMin(y, y1);
        y2 = y;
      }
  }
  return {QPoint(x1, y1), QPoint(x2, y2)};
}
} // namespace
Animation decode(const QString &path) {
  if (path.isEmpty()) {
    Animation spinner;
    spinner.crop = QRect(0, 0, 32, 32);
    for (int i = 0; i < 12; ++i) {
      QImage frame(32, 32, QImage::Format_ARGB32_Premultiplied);
      frame.fill(Qt::transparent);
      QPainter painter(&frame);
      painter.setRenderHint(QPainter::Antialiasing);
      painter.translate(16, 16);
      painter.rotate(i * 30);
      for (int spoke = 0; spoke < 12; ++spoke) {
        painter.setPen(QPen(QColor(195, 53, 116, 40 + spoke * 19), 3, Qt::SolidLine, Qt::RoundCap));
        painter.drawLine(0, -8, 0, -13);
        painter.rotate(30);
      }
      painter.end();
      spinner.frames.append({frame, 70});
    }
    return spinner;
  }
  if (!QFileInfo(path).isFile() || QFileInfo(path).size() > imageLimit)
    fail("Choose a local animation smaller than 64 MiB.");
  QFile f(path);
  if (!f.open(QIODevice::ReadOnly))
    fail(f.errorString());
  auto bytes = f.read(imageLimit + 1);
  if (bytes.size() > imageLimit || f.error() != QFile::NoError)
    fail("Cannot read the animation.");
  if (bytes.startsWith(pngSignature)) {
    auto animation = apng(bytes);
    bool shown = false;
    for (const auto &frame : animation.frames)
      if (!visible(frame.pixels).isEmpty()) {
        shown = true;
        break;
      }
    if (!shown)
      fail("Animation is empty.");
    return animation;
  }
  QBuffer buffer(&bytes);
  buffer.open(QIODevice::ReadOnly);
  QImageReader reader(&buffer);
  if (!reader.supportsAnimation())
    fail("Select an animated GIF, WebP or APNG.");
  Animation result;
  while (reader.canRead()) {
    checkSize(reader.size(), result.frames.size() + 1);
    auto img =
        reader.read().convertToFormat(QImage::Format_ARGB32_Premultiplied);
    if (img.isNull())
      fail(reader.errorString());
    result.crop |= visible(img);
    result.frames.append({img, qMax(10, reader.nextImageDelay())});
  }
  if (result.frames.size() < 2 || result.crop.isEmpty())
    fail("The animation must contain at least two frames with visible pixels.");
  return result;
}
} // namespace cursor
