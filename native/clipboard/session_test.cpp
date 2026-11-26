#include "../testing/private_x11.hpp"
#include <QApplication>
#include <QClipboard>
#include <QElapsedTimer>
#include <QMimeData>
#include <QProcess>
#include <QThread>
#include <QTimer>
#include <cstdio>
#include <cstdlib>
#include <xcb/xcb.h>

template <class Predicate> bool until(Predicate done, int ms = 3000) {
  QElapsedTimer clock;
  clock.start();
  do {
    QApplication::processEvents();
    if (done())
      return true;
    QThread::msleep(10);
  } while (clock.elapsed() < ms);
  return false;
}
int main(int argc, char **argv) {
  if (argc == 3 && QByteArray(argv[1]) != "--worker") {
    QCoreApplication outer(argc, argv);
    doro_test::isolated(argv[1], {argv[2]}, "800x600x24");
    return 0;
  }
  if (qgetenv("DOROSHELL_TEST_DISPLAY").isEmpty() ||
      qgetenv("DOROSHELL_TEST_DISPLAY") != qgetenv("DISPLAY"))
    return 77;
  QApplication app(argc, argv);
  if (argc != 3 || QByteArray(argv[1]) != "--worker")
    return 1;
  auto *clip = app.clipboard();
  auto *x = xcb_connect(nullptr, nullptr);
  auto *atom =
      xcb_intern_atom_reply(x, xcb_intern_atom(x, 0, 9, "CLIPBOARD"), nullptr);
  if (!atom)
    return 1;
  auto owner = [&] {
    auto *r = xcb_get_selection_owner_reply(
        x, xcb_get_selection_owner(x, atom->atom), nullptr);
    auto id = r ? r->owner : 0u;
    std::free(r);
    return id;
  };
  QProcess service;
  service.start(argv[2], {});
  if (!service.waitForStarted())
    return 2;
  QTimer ready;
  ready.setSingleShot(true);
  ready.start(450);
  until([&] { return !ready.isActive(); });
  clip->setText("synthetic copy");
  auto source = owner();
  if (!until([&] { return owner() != source && owner() != 0; }) ||
      clip->text() != "synthetic copy")
    return 3;
  auto *mixed = new QMimeData;
  mixed->setText("rich");
  mixed->setData("application/x-fixture", "original");
  clip->setMimeData(mixed);
  ready.start(400);
  until([&] { return !ready.isActive(); });
  if (owner() != source ||
      clip->mimeData()->data("application/x-fixture") != "original")
    return 4;
  if (QProcess::execute(argv[2], {"--show"}) != 0 ||
      QProcess::execute(argv[2], {"--stop"}) != 0)
    return 5;
  if (!service.waitForFinished(2500) || service.exitCode() != 0)
    return 6;
  std::free(atom);
  xcb_disconnect(x);
}
