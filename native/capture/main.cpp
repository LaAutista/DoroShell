#include "overlay.hpp"
#include <QtWidgets>
#include <cstdio>
#include <fcntl.h>
#include <unistd.h>
#include <xcb/xfixes.h>

namespace {
bool paintPointer(QImage &image, QPoint origin) {
  std::unique_ptr<xcb_connection_t, decltype(&xcb_disconnect)> conn(
      xcb_connect(nullptr, nullptr), &xcb_disconnect);
  if (xcb_connection_has_error(conn.get()))
    return false;
  using Version = xcb_xfixes_query_version_reply_t;
  std::unique_ptr<Version, decltype(&std::free)> ver(
      xcb_xfixes_query_version_reply(
          conn.get(), xcb_xfixes_query_version(conn.get(), 2, 0), nullptr),
      &std::free);
  if (!ver || ver->major_version < 2)
    return false;
  using Cursor = xcb_xfixes_get_cursor_image_reply_t;
  std::unique_ptr<Cursor, decltype(&std::free)> cursor(
      xcb_xfixes_get_cursor_image_reply(
          conn.get(), xcb_xfixes_get_cursor_image(conn.get()), nullptr),
      &std::free);
  if (!cursor ||
      qint64(cursor->width) * cursor->height !=
          xcb_xfixes_get_cursor_image_cursor_image_length(cursor.get()))
    return false;
  QImage shape(reinterpret_cast<const uchar *>(
                   xcb_xfixes_get_cursor_image_cursor_image(cursor.get())),
               cursor->width, cursor->height, cursor->width * 4,
               QImage::Format_ARGB32_Premultiplied);
  QPainter painter(&image);
  painter.drawImage(QPoint(cursor->x - cursor->xhot, cursor->y - cursor->yhot) -
                        origin,
                    shape);
  return true;
}
} // namespace

int main(int argc, char **argv) {
  if (qEnvironmentVariable("XDG_SESSION_TYPE", "x11") != "x11") {
    fputs("DoroShell capture requires X11.\n", stderr);
    return 1;
  }
  // XCB root-window geometry, cursor positions, monitor rectangles and output
  // PNGs must share native coordinates even when Qt scales each monitor
  // differently.
  qputenv("QT_ENABLE_HIGHDPI_SCALING", "0");
  qputenv("QT_SCALE_FACTOR", "1");
  qunsetenv("QT_SCREEN_SCALE_FACTORS");
  QApplication app(argc, argv);
  app.setQuitOnLastWindowClosed(false);
  QCommandLineParser parser;
  parser.addHelpOption();
  QCommandLineOption output("output", "Write a new PNG.", "file");
  QCommandLineOption notify("notify",
                            "Report when the desktop has been frozen.");
  parser.addOptions({output, notify});
  parser.process(app);
  if (app.platformName() != "xcb")
    return 1;
  QLockFile lock(
      QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation) +
      "/doroshell-capture-overlay.lock");
  if (!lock.tryLock(0)) {
    if (parser.isSet(notify))
      puts("BUSY");
    return 0;
  }
  QImage result;
  Overlay::Request request;
  bool first = true;
  for (;;) {
    if (!first) {
      QGuiApplication::sync();
      if (request.delay) {
        QProgressDialog countdown("Starting capture…", "Cancel", 0,
                                  request.delay);
        countdown.setWindowTitle("New capture");
        countdown.setMinimumDuration(0);
        QElapsedTimer clock;
        clock.start();
        while (clock.elapsed() < 1000 * request.delay) {
          countdown.setValue(clock.elapsed() / 1000);
          app.processEvents();
          if (countdown.wasCanceled())
            return 0;
          QThread::msleep(30);
        }
        countdown.hide();
      }
      QGuiApplication::sync();
    }
    auto *screen = QGuiApplication::screenAt(QCursor::pos());
    if (!screen)
      screen = app.primaryScreen();
    if (!screen)
      return 1;
    auto screens =
        request.monitor ? QList<QScreen *>{screen} : screen->virtualSiblings();
    QRect bounds;
    for (auto *s : screens)
      bounds = bounds.united(s->geometry());
    if (bounds.isEmpty() ||
        qint64(bounds.width()) * bounds.height() > 100000000)
      return 1;
    QImage image(bounds.size(), QImage::Format_RGB32);
    if (image.isNull())
      return 1;
    image.fill(Qt::black);
    {
      QPainter p(&image);
      for (auto *s : screens) {
        auto frame = s->grabWindow(0).toImage();
        if (frame.isNull() || frame.size() != s->geometry().size())
          return 1;
        p.drawImage(s->geometry().topLeft() - bounds.topLeft(), frame);
      }
    }
    auto windows = windowsAtCapture();
    for (auto &w : windows) {
      w.frame.translate(-bounds.topLeft());
      w.client.translate(-bounds.topLeft());
    }
    if (request.pointer && !paintPointer(image, bounds.topLeft())) {
      QMessageBox::warning(nullptr, "Screenshot",
                           "Could not capture the X11 pointer.");
      return 1;
    }
    if (first && parser.isSet(notify)) {
      puts("FROZEN");
      fflush(stdout);
    }
    first = false;
    Overlay overlay(std::move(image), bounds, windows);
    auto code = overlay.exec();
    if (overlay.nextCapture) {
      request = *overlay.nextCapture;
      continue;
    }
    if (code != QDialog::Accepted)
      return 0;
    result = overlay.resultImage();
    break;
  }
  if (parser.isSet(output)) {
    auto filename = QFile::encodeName(parser.value(output));
    int fd = ::open(filename.constData(),
                    O_WRONLY | O_CREAT | O_EXCL | O_CLOEXEC, 0600);
    if (fd < 0) {
      perror("Save screenshot");
      return 1;
    }
    QFile file;
    if (!file.open(fd, QIODevice::WriteOnly, QFileDevice::AutoCloseHandle)) {
      ::close(fd);
      ::unlink(filename.constData());
      return 1;
    }
    if (!result.save(&file, "PNG") || !file.flush()) {
      file.close();
      ::unlink(filename.constData());
      return 1;
    }
    return 0;
  }
  auto *clipboard = app.clipboard();
  clipboard->setImage(result);
  if (!clipboard->ownsClipboard())
    return 1;
  lock.unlock();
  QObject::connect(clipboard, &QClipboard::dataChanged, &app, [&] {
    if (!clipboard->ownsClipboard())
      app.quit();
  });
  return app.exec();
}
