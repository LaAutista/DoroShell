#pragma once
#include <QImage>
#include <QMap>
#include <QStringList>
#include <stdexcept>
namespace cursor {
struct Frame {
  QImage pixels;
  int delay;
};
struct Animation {
  QList<Frame> frames;
  QRect crop;
};
Animation decode(const QString &path);
QMap<QString, QByteArray> generate(const QString &image, const QString &base,
                                   bool pink);
QStringList change(const QString &home, const QString &image,
                   const QString &base, bool pink, bool apply, bool restore);
const QMap<QString, QStringList> &aliases();
[[noreturn]] inline void fail(const QString &message) {
  throw std::runtime_error(message.toStdString());
}
} // namespace cursor
