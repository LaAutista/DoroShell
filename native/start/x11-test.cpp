#include <QApplication>
#include <QCoreApplication>
#include <QDir>
#include <QDropEvent>
#include <QElapsedTimer>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QMimeData>
#include <QProcess>
#include <QTemporaryDir>
#include <QThread>
#include <QWidget>
#include <cstring>
#include <functional>
#include <iostream>
#include <stdexcept>
#include <xcb/xcb.h>
#include <xcb/xcb_keysyms.h>
#include <xcb/xtest.h>

namespace {
void require(bool ok, const char *msg) {
  if (!ok)
    throw std::runtime_error(msg);
}
void writeFile(QString path, QByteArray bytes) {
  QFile f(path);
  require(f.open(QIODevice::WriteOnly) && f.write(bytes) == bytes.size(),
          "create fixture");
}
void await(const std::function<bool()> &condition, const char *msg) {
  QElapsedTimer t;
  t.start();
  while (t.elapsed() < 5000) {
    if (condition())
      return;
    QThread::msleep(25);
  }
  throw std::runtime_error(msg);
}
xcb_atom_t atom(xcb_connection_t *x, const char *name) {
  auto *r = xcb_intern_atom_reply(
      x, xcb_intern_atom(x, false, std::strlen(name), name), nullptr);
  require(r, "X atom");
  auto a = r->atom;
  free(r);
  return a;
}
struct Child : QProcess {
  ~Child() override {
    if (state() != NotRunning) {
      kill();
      waitForFinished(4000);
    }
  }
};
} // namespace
int main(int argc, char **argv) {
  if (argc == 3 && QByteArray(argv[1]) == "--drop-target") {
    QApplication app(argc, argv);
    class Target : public QWidget {
    public:
      QString result;

    protected:
      void dragEnterEvent(QDragEnterEvent *event) override {
        if (event->mimeData()->hasUrls() &&
            event->possibleActions() == Qt::CopyAction)
          event->acceptProposedAction();
      }
      void dropEvent(QDropEvent *event) override {
        auto urls = event->mimeData()->urls();
        if (urls.size() == 1 && event->proposedAction() == Qt::CopyAction) {
          writeFile(result, urls.first().toLocalFile().toUtf8());
          event->acceptProposedAction();
        }
      }
    } target;
    target.result = QFile::decodeName(argv[2]);
    target.setAcceptDrops(true);
    target.setGeometry(660, 250, 300, 230);
    target.show();
    writeFile(target.result + ".ready", "ok");
    return app.exec();
  }
  QCoreApplication core(argc, argv);
  if (argc != 3) {
    std::cerr << "usage: doro-start-x11-test /path/to/Xvfb "
                 "/path/to/doroshell-start\n";
    return 2;
  }
  QTemporaryDir t;
  try {
    require(t.isValid(), "temp home");
    auto env = QProcessEnvironment::systemEnvironment();
    env.remove("XAUTHORITY");
    env.remove("SESSION_MANAGER");
    env.remove("WAYLAND_DISPLAY");
    env.remove("QT_SCALE_FACTOR");
    for (auto key : {"HOME", "XDG_CONFIG_HOME", "XDG_DATA_HOME",
                     "XDG_RUNTIME_DIR", "XDG_DATA_DIRS", "XDG_CONFIG_DIRS"})
      env.insert(key,
                 t.path() +
                     (QByteArray(key) == "HOME" ? "" : "/" + QString(key)));
    for (auto key :
         {"HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_RUNTIME_DIR"})
      require(QDir().mkpath(env.value(key)), "mkdir");
    QFile::setPermissions(env.value("XDG_RUNTIME_DIR"), QFile::ReadOwner |
                                                            QFile::WriteOwner |
                                                            QFile::ExeOwner);
    for (auto key : {"DBUS_SYSTEM_BUS_ADDRESS", "DBUS_SESSION_BUS_ADDRESS"})
      env.insert(key, "unix:path=" + t.path() + "/absent");
    env.insert("QT_QPA_PLATFORM", "xcb");
    auto apps = env.value("XDG_DATA_HOME") + "/applications";
    require(QDir().mkpath(apps), "applications directory");
    writeFile(
        apps + "/testing.desktop",
        "[Desktop "
        "Entry]\nType=Application\nName=Regression\nExec=/usr/bin/touch \"" +
            QFile::encodeName(t.path() + "/launched") +
            "\"\nStartupWMClass=DoroFixture\n");
    Child server;
    server.setProcessEnvironment(env);
    server.start(argv[1], {"-displayfd", "1", "-screen", "0", "1000x740x24",
                           "-nolisten", "tcp"});
    require(server.waitForReadyRead(5000), "private Xvfb startup");
    auto num = server.readLine().trimmed();
    bool parsed = false;
    num.toUInt(&parsed);
    require(parsed, "private display number");
    QByteArray display = ":" + num;
    env.insert("DISPLAY", display);
    std::unique_ptr<xcb_connection_t, decltype(&xcb_disconnect)> x(
        xcb_connect(display.constData(), nullptr), xcb_disconnect);
    require(!xcb_connection_has_error(x.get()), "private X connection");
    auto screen = xcb_setup_roots_iterator(xcb_get_setup(x.get())).data;
    auto root = screen->root;
    Child service;
    service.setProcessEnvironment(env);
    service.start(argv[2], {"--background"});
    require(service.waitForStarted(), "service startup");
    auto toggle = [&](QStringList args) {
      QProcess p;
      p.setProcessEnvironment(env);
      p.start(argv[2], args);
      require(p.waitForFinished(5000) && !p.exitCode(), "IPC client");
    };
    await(
        [&] {
          return !QDir(env.value("XDG_RUNTIME_DIR"))
                      .entryList({"doroshell-native-start-*.lock"})
                      .isEmpty();
        },
        "resident lock");
    toggle({"--background"});
    auto active = atom(x.get(), "_NET_ACTIVE_WINDOW");
    auto w = xcb_generate_id(x.get());
    xcb_create_window(x.get(), XCB_COPY_FROM_PARENT, w, root, 0, 0, 60, 50, 0,
                      XCB_WINDOW_CLASS_INPUT_OUTPUT, screen->root_visual, 0,
                      nullptr);
    const char klass[] = "regression\0DoroFixture";
    xcb_change_property(x.get(), XCB_PROP_MODE_REPLACE, w, XCB_ATOM_WM_CLASS,
                        XCB_ATOM_STRING, 8, sizeof(klass), klass);
    xcb_change_property(x.get(), XCB_PROP_MODE_REPLACE, root, active,
                        XCB_ATOM_WINDOW, 32, 1, &w);
    xcb_flush(x.get());
    auto cfg = env.value("XDG_CONFIG_HOME") + "/lxqt-comfort";
    await(
        [&] {
          QFile f(cfg + "/recent.json");
          return f.open(QIODevice::ReadOnly) &&
                 QJsonDocument::fromJson(f.readAll())
                     .object()["items"]
                     .toArray()
                     .contains("testing.desktop");
        },
        "record external focused desktop ID");
    auto mapped = [&] {
      bool shown = false;
      auto *tree =
          xcb_query_tree_reply(x.get(), xcb_query_tree(x.get(), root), nullptr);
      if (!tree)
        return false;
      auto *children = xcb_query_tree_children(tree);
      for (int i = 0; i < xcb_query_tree_children_length(tree); ++i) {
        auto *a = xcb_get_window_attributes_reply(
            x.get(), xcb_get_window_attributes(x.get(), children[i]), nullptr);
        auto *g = xcb_get_geometry_reply(
            x.get(), xcb_get_geometry(x.get(), children[i]), nullptr);
        shown |= a && g && a->map_state == XCB_MAP_STATE_VIEWABLE &&
                 g->width == 508 && g->height == 634;
        free(a);
        free(g);
      }
      free(tree);
      return shown;
    };
    require(!mapped(), "background is hidden");
    toggle({});
    await(mapped, "toggle opens");
    toggle({});
    await([&] { return !mapped(); }, "toggle hides");
    toggle({});
    await(mapped, "reopen");
    auto *keys = xcb_key_symbols_alloc(x.get());
    require(keys, "keyboard map");
    for (auto sym : {unsigned('r'), unsigned('e'), unsigned('g'), 0xff0du}) {
      auto *codes = xcb_key_symbols_get_keycode(keys, sym);
      require(codes && codes[0], "keycode");
      for (auto type : {XCB_KEY_PRESS, XCB_KEY_RELEASE})
        xcb_test_fake_input(x.get(), type, codes[0], 0, root, 0, 0, 0);
      free(codes);
    }
    xcb_key_symbols_free(keys);
    xcb_flush(x.get());
    await([&] { return QFileInfo::exists(t.path() + "/launched"); },
          "search and Return launch GIO desktop entry");
    await([&] { return !mapped(); }, "successful launch closes Start");
    Child receiver;
    receiver.setProcessEnvironment(env);
    auto drop = t.path() + "/dropped";
    receiver.start(core.applicationFilePath(), {"--drop-target", drop});
    await([&] { return QFileInfo::exists(drop + ".ready"); },
          "native drop receiver");
    require(QFile::remove(t.path() + "/launched"), "clear launch marker");
    writeFile(cfg + "/favorites.json", "[\"testing.desktop\"]");
    toggle({});
    await(mapped, "show pinned source");
    auto pointer = [&](uint8_t type, int xPos, int yPos) {
      xcb_test_fake_input(x.get(), type, type == XCB_MOTION_NOTIFY ? 0 : 1, 0,
                          root, xPos, yPos, 0);
      xcb_flush(x.get());
      QThread::msleep(60);
    };
    pointer(XCB_MOTION_NOTIFY, 75, 215);
    pointer(XCB_BUTTON_PRESS, 0, 0);
    pointer(XCB_MOTION_NOTIFY, 91, 215);
    pointer(XCB_MOTION_NOTIFY, 130, 215);
    pointer(XCB_MOTION_NOTIFY, 360, 300);
    pointer(XCB_MOTION_NOTIFY, 770, 350);
    pointer(XCB_MOTION_NOTIFY, 795, 350);
    pointer(XCB_BUTTON_RELEASE, 0, 0);
    await(
        [&] {
          QFile f(drop);
          return f.open(QIODevice::ReadOnly) &&
                 f.readAll() == QFile::encodeName(apps + "/testing.desktop");
        },
        "native file URI accepted as Copy");
    require(!QFileInfo::exists(t.path() + "/launched") &&
                QFileInfo::exists(apps + "/testing.desktop"),
            "drag neither launches nor moves source");
    return 0;
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
