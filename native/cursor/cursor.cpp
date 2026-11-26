#include "cursor.hpp"
#include <QDataStream>
#include <QFile>
#include <QFileInfo>
#include <QPainter>
#include <X11/Xcursor/Xcursor.h>
#include <memory>

namespace cursor {
const QMap<QString, QStringList> &aliases() {
  static const QMap<QString, QStringList> all = {
      {"wait", {"watch"}},
      {"progress",
       {"left_ptr_watch", "half-busy", "00000000000000020006000e7e9ffc3f",
        "08e8e1c95fe2fc01f976f1e063a24ccd",
        "3ecb610c1bf2410f44200f48c40d3599"}},
      {"default", {"left_ptr", "arrow", "top_left_arrow"}}};
  return all;
}
namespace {
struct Image {
  int size;
  QImage pixels;
  QPoint hot;
  int delay;
};
Image pointer(const QString &file, int size, bool pink) {
  if (!QFileInfo(file).isFile() || QFileInfo(file).size() > 32 * 1024 * 1024)
    fail("Base theme has no readable default cursor.");
  std::unique_ptr<XcursorImage, decltype(&XcursorImageDestroy)> im(
      XcursorFilenameLoadImage(QFile::encodeName(file), size),
      XcursorImageDestroy);
  if (!im || !im->size || im->width > 1024 || im->height > 1024 ||
      im->xhot >= im->width || im->yhot >= im->height)
    fail("Invalid default pointer in base cursor theme.");
  QImage img(reinterpret_cast<uchar *>(im->pixels), im->width, im->height,
             im->width * 4, QImage::Format_ARGB32_Premultiplied);
  double scale = double(size) / im->size;
  QSize bounds(qMax(1, qRound(im->width * scale)),
               qMax(1, qRound(im->height * scale)));
  if (bounds.width() > 512 || bounds.height() > 512)
    fail("Unsupported base pointer dimensions.");
  auto arrow =
      img.scaled(bounds, Qt::IgnoreAspectRatio, Qt::SmoothTransformation)
          .convertToFormat(QImage::Format_ARGB32);
  if (pink)
    for (int y = 0; y < arrow.height(); ++y) {
      auto *p = reinterpret_cast<QRgb *>(arrow.scanLine(y));
      for (int x = 0; x < arrow.width(); ++x) {
        auto v = p[x];
        int r = qRed(v), g = qGreen(v), b = qBlue(v);
        if (std::max({r, g, b}) > 100)
          p[x] = qRgba(r + int((255 - r) * .65), int(g * .55),
                       qBound(0, b + int((220 - b) * .45), 255), qAlpha(v));
      }
    }
  return {size,
          arrow.convertToFormat(QImage::Format_ARGB32_Premultiplied),
          {qMin(bounds.width() - 1, qRound(im->xhot * scale)),
           qMin(bounds.height() - 1, qRound(im->yhot * scale))},
          0};
}
QByteArray encode(const QList<Image> &frames) {
  QByteArray bytes;
  QDataStream out(&bytes, QIODevice::WriteOnly);
  out.setByteOrder(QDataStream::LittleEndian);
  constexpr quint32 type = 0xfffd0002;
  quint32 offset = 16 + frames.size() * 12;
  out << quint32(0x72756358) << quint32(16) << quint32(0x10000)
      << quint32(frames.size());
  for (const auto &f : frames) {
    out << type << quint32(f.size) << offset;
    offset += 36 + f.pixels.width() * f.pixels.height() * 4;
    if (offset > 64 * 1024 * 1024)
      fail("Generated cursor exceeds file limit.");
  }
  for (const auto &f : frames) {
    out << quint32(36) << type << quint32(f.size) << quint32(1)
        << quint32(f.pixels.width()) << quint32(f.pixels.height())
        << quint32(f.hot.x()) << quint32(f.hot.y()) << quint32(f.delay);
    for (int y = 0; y < f.pixels.height(); ++y) {
      auto *p = reinterpret_cast<const QRgb *>(f.pixels.constScanLine(y));
      for (int x = 0; x < f.pixels.width(); ++x)
        out << quint32(p[x]);
    }
  }
  return bytes;
}
} // namespace
QMap<QString, QByteArray> generate(const QString &image, const QString &base,
                                   bool pink) {
  auto animation = decode(image);
  QList<Image> wait, progress, pointers;
  for (int size : {24, 30, 32, 48, 64}) {
    auto arrow = pointer(base + "/cursors/default", size, pink);
    if (pink)
      pointers << arrow;
    for (const auto &f : animation.frames) {
      auto art = f.pixels.copy(animation.crop);
      if (art.width() > size || art.height() > size)
        art = art.scaled(size, size, Qt::KeepAspectRatio,
                         Qt::SmoothTransformation);
      QImage busy(size, size, QImage::Format_ARGB32_Premultiplied);
      busy.fill(Qt::transparent);
      QPainter p(&busy);
      p.drawImage((size - art.width()) / 2, (size - art.height()) / 2, art);
      p.end();
      wait.append({size, busy, {size / 2, size / 2}, f.delay});
      auto badge = art.scaled(qMax(1, qRound(art.width() * .75)),
                              qMax(1, qRound(art.height() * .75)),
                              Qt::IgnoreAspectRatio, Qt::SmoothTransformation);
      QPoint origin(qRound(size * .5), qRound(size * .4));
      auto extent =
          QSize(origin.x() + badge.width(), origin.y() + badge.height())
              .expandedTo(arrow.pixels.size());
      QImage combined(extent, QImage::Format_ARGB32_Premultiplied);
      combined.fill(Qt::transparent);
      QPainter combine(&combined);
      combine.drawImage(origin, badge);
      combine.drawImage(0, 0, arrow.pixels);
      combine.end();
      progress.append({size, combined, arrow.hot, f.delay});
    }
  }
  QMap<QString, QByteArray> result = {{"wait", encode(wait)},
                                      {"progress", encode(progress)}};
  if (pink)
    result.insert("default", encode(pointers));
  return result;
}
} // namespace cursor
