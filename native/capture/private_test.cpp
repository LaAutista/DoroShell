#include "../testing/private_x11.hpp"
#include <QtWidgets>
#include <X11/keysym.h>
#include <sys/stat.h>
#include <xcb/xcb.h>
#include <xcb/xcb_keysyms.h>
#include <xcb/xtest.h>

struct Pattern : QWidget {
  QImage pixels;
  Pattern()
      : QWidget(nullptr,
                Qt::FramelessWindowHint | Qt::X11BypassWindowManagerHint),
        pixels(800, 600, QImage::Format_RGB32) {
    for (int y = 0; y < pixels.height(); ++y)
      for (int x = 0; x < pixels.width(); ++x)
        pixels.setPixel(x, y, qRgb(x % 256, y % 256, (x >> 8) * 8 + (y >> 8)));
    setGeometry(pixels.rect());
  }
  void paintEvent(QPaintEvent *) override {
    QPainter(this).drawImage(0, 0, pixels);
  }
};
int test(const QString &exe) {
  using doro_test::require;
  require(qgetenv("DOROSHELL_TEST_DISPLAY") == qgetenv("DISPLAY") &&
              !qgetenv("DISPLAY").isEmpty(),
          "private display required");
  Pattern source;
  source.show();
  QApplication::processEvents();
  QGuiApplication::sync();
  auto *x = xcb_connect(nullptr, nullptr);
  auto root = xcb_setup_roots_iterator(xcb_get_setup(x)).data->root;
  auto event = [&](uint8_t type, uint8_t detail, int px = 0, int py = 0) {
    xcb_test_fake_input(x, type, detail, XCB_CURRENT_TIME, root, px, py, 0);
    xcb_flush(x);
    QThread::msleep(35);
  };
  auto key = [&](const QString &key) {
    auto *symbols = xcb_key_symbols_alloc(x);
    auto *codes = xcb_key_symbols_get_keycode(
        symbols, key == "Escape" ? XK_Escape : XK_Return);
    require(codes && codes[0], "missing X11 keycode");
    event(XCB_KEY_PRESS, codes[0]);
    event(XCB_KEY_RELEASE, codes[0]);
    std::free(codes);
    xcb_key_symbols_free(symbols);
  };
  QTemporaryDir files;
  for (auto action : {"full", "crop", "cancel", "exists"}) {
    auto path = files.filePath(action);
    if (QByteArray(action) == "exists") {
      QFile f(path);
      require(f.open(QIODevice::WriteOnly), "fixture");
      f.write("preserve");
    }
    doro_test::Child child;
    child.start(exe, {"--notify", "--output", path});
    require(child.waitForReadyRead(4000) && child.readLine() == "FROZEN\n",
            "capture not frozen");
    QThread::msleep(300);
    if (QByteArray(action) == "crop") {
      event(XCB_MOTION_NOTIFY, 0, 125, 200);
      event(XCB_BUTTON_PRESS, 1);
      event(XCB_MOTION_NOTIFY, 0, 299, 355);
      event(XCB_BUTTON_RELEASE, 1);
    }
    key(QByteArray(action) == "cancel" ? "Escape" : "Return");
    require(child.waitForFinished(3000), "capture did not finish");
    if (QByteArray(action) == "cancel") {
      require(!QFileInfo::exists(path), "cancel wrote a file");
      continue;
    }
    if (QByteArray(action) == "exists") {
      QFile f(path);
      require(child.exitCode() != 0 && f.open(QIODevice::ReadOnly) &&
                  f.readAll() == "preserve",
              "overwrote existing file");
      continue;
    }
    struct stat st{};
    require(!stat(QFile::encodeName(path).constData(), &st) &&
                (st.st_mode & 0777) == 0600,
            "capture output permissions");
    auto expected =
        QByteArray(action) == "crop"
            ? source.pixels.copy(QRect(QPoint(125, 200), QPoint(299, 355)))
            : source.pixels;
    require(QImage(path).convertToFormat(QImage::Format_RGB32) == expected,
            "saved pixels differ");
  }
  xcb_disconnect(x);
  return 0;
}
int main(int argc, char **argv) {
  try {
    if (argc != 3)
      return 1;
    if (QByteArray(argv[1]) == "--worker") {
      QApplication app(argc, argv);
      return test(argv[2]);
    }
    QCoreApplication app(argc, argv);
    doro_test::isolated(argv[1], {argv[2]}, "800x600x24");
  } catch (const std::exception &e) {
    qCritical() << e.what();
    return 1;
  }
}
