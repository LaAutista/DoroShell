// SPDX-License-Identifier: GPL-2.0-or-later
#include "../testing/private_x11.hpp"
#include <QCoreApplication>
#include <QXmlStreamWriter>
#include <QDir>
#include <QElapsedTimer>
#include <QFile>
#include <QLocalSocket>
#include <QProcess>
#include <QRect>
#include <QTemporaryDir>
#include <QThread>
#include <QUuid>
#include <xcb/xcb.h>
#include <xcb/xtest.h>
#include <cstdio>
#include <cstdlib>
#include <memory>
#include <stdexcept>
#include <unistd.h>

namespace
{
using namespace doro_test;
template <class T> auto owned(T *reply) { return std::unique_ptr<T, decltype(&std::free)>(reply, std::free); }
template <class F> void waitFor(F condition, const char *failure)
{
    QElapsedTimer t;
    t.start();
    while (!condition()) {
        require(t.elapsed() < 3000, failure);
        QThread::msleep(20);
    }
}

void exercise(const QString &binary)
{
    require(QDir::home().dirName().startsWith("doroshell-private-native-") &&
                qgetenv("DISPLAY") == qgetenv("DOROSHELL_TEST_DISPLAY") && !qgetenv("DISPLAY").isEmpty(),
            "Private display required");
    std::unique_ptr<xcb_connection_t, decltype(&xcb_disconnect)> connection(xcb_connect(nullptr, nullptr),
                                                                            xcb_disconnect);
    auto *c = connection.get();
    require(!xcb_connection_has_error(c), "Cannot connect to test display");
    const auto *screen = xcb_setup_roots_iterator(xcb_get_setup(c)).data;
    const auto root = screen->root;
    auto atom = [&](const QByteArray &name) {
        auto reply =
            owned(xcb_intern_atom_reply(c, xcb_intern_atom(c, false, name.size(), name.data()), nullptr));
        require(bool(reply), "Cannot get test atom");
        return reply->atom;
    };
    auto firstValue = [&](xcb_window_t target, xcb_atom_t key) -> uint32_t {
        auto reply = owned(
            xcb_get_property_reply(c, xcb_get_property(c, false, target, key, XCB_ATOM_ANY, 0, 1), nullptr));
        return reply && reply->format == 32 && reply->value_len
                   ? *static_cast<uint32_t *>(xcb_get_property_value(reply.get()))
                   : 0;
    };
    auto command = [&](const QString &action) {
        require(QProcess::execute(binary, {action}) == 0, "Sending snap command failed");
    };
    command("stop");
    require(QProcess::execute(binary, {"left"}) != 0, "Unsupported window manager accepted");
    // Openbox parses Execute arguments with GLib's shell-argument parser.
    const auto quotedPath = "'" + QString(binary).replace("'", "'\\''") + "'";
    QFile config(QDir::home().filePath("rc.xml"));
    require(config.open(QIODevice::WriteOnly), "Cannot create test WM configuration");
    QXmlStreamWriter xml(&config);
    xml.writeStartElement("openbox_config");
    xml.writeDefaultNamespace("http://openbox.org/3.4/rc");
    xml.writeStartElement("keyboard");
    for (const auto &[key, action] : {std::pair{"Left", "left"}, {"Right", "right"}, {"Down", "restore"}}) {
        xml.writeStartElement("keybind");
        xml.writeAttribute("key", QStringLiteral("W-") + key);
        xml.writeStartElement("action");
        xml.writeAttribute("name", "Execute");
        xml.writeTextElement("command", quotedPath + " " + action);
        xml.writeEndElement();
        xml.writeEndElement();
    }
    xml.writeEndDocument();
    config.close();
    Child wm;
    wm.start("openbox", {"--sm-disable", "--config-file", config.fileName()});
    auto wmCheck = atom("_NET_SUPPORTING_WM_CHECK");
    waitFor([&] { return firstValue(root, wmCheck) != 0; }, "Openbox failed to start");
    Child daemon;
    daemon.start(binary, {});
    waitFor(
        [&] {
            QLocalSocket probe;
            probe.connectToServer("doroshell-snap-" + QString::number(getuid()));
            return probe.waitForConnected(100);
        },
        "Snapping service failed to start");
    const auto w = xcb_generate_id(c);
    auto active = atom("_NET_ACTIVE_WINDOW");
    auto create = [&](int width, int height) {
        auto cookie =
            xcb_create_window_checked(c, XCB_COPY_FROM_PARENT, w, root, 50, 90, width, height, 0,
                                      XCB_WINDOW_CLASS_INPUT_OUTPUT, XCB_COPY_FROM_PARENT, 0, nullptr);
        require(!owned(xcb_request_check(c, cookie)), "Cannot create or reuse window ID");
        xcb_map_window(c, w);
        xcb_flush(c);
        waitFor([&] { return firstValue(root, active) == w; }, "Test window not focused");
        QThread::msleep(100);
    };
    auto destroy = [&] {
        xcb_destroy_window(c, w);
        xcb_flush(c);
        auto clientList = atom("_NET_CLIENT_LIST");
        waitFor([&] { return firstValue(root, clientList) != w; }, "Destroyed window is still managed");
    };
    auto frame = [&] {
        auto tree = owned(xcb_query_tree_reply(c, xcb_query_tree(c, w), nullptr));
        require(bool(tree), "Missing frame window");
        auto g = owned(xcb_get_geometry_reply(c, xcb_get_geometry(c, tree->parent), nullptr));
        require(bool(g), "Missing frame geometry");
        return QRect(g->x, g->y, g->width, g->height);
    };
    auto expect = [&](QRect rect, const char *message) { waitFor([&] { return frame() == rect; }, message); };
    const int half = screen->width_in_pixels / 2;
    const QRect left(0, 0, half, screen->height_in_pixels);
    const QRect right(half, 0, screen->width_in_pixels - half, screen->height_in_pixels);
    auto chord = [&](xcb_keysym_t arrow) {
        auto *setup = xcb_get_setup(c);
        const int count = setup->max_keycode - setup->min_keycode + 1;
        auto keys = owned(
            xcb_get_keyboard_mapping_reply(c, xcb_get_keyboard_mapping(c, setup->min_keycode, count), nullptr));
        require(bool(keys), "Missing keyboard map");
        auto code = [&](xcb_keysym_t sym) -> uint8_t {
            const auto *syms = xcb_get_keyboard_mapping_keysyms(keys.get());
            for (int i = 0; i < count; ++i)
                if (syms[i * keys->keysyms_per_keycode] == sym)
                    return setup->min_keycode + i;
            throw std::runtime_error("Missing test key");
        };
        const auto super = code(0xffeb); // Super_L
        const auto key = code(arrow);
        for (const auto &[kind, detail] : {std::pair{XCB_KEY_PRESS, super},
                                           {XCB_KEY_PRESS, key},
                                           {XCB_KEY_RELEASE, key},
                                           {XCB_KEY_RELEASE, super}})
            xcb_test_fake_input(c, kind, detail, 0, root, 0, 0, 0);
        xcb_flush(c);
    };
    create(260, 240);
    chord(0xff51);
    expect(left, "Super+Left failed to snap");
    destroy();
    create(400, 320); // Same XID, different size.
    const auto original = frame();
    chord(0xff53);
    expect(right, "Super+Right failed on the replacement window");
    command("left");
    expect(left, "Repeated snap failed");
    chord(0xff54);
    expect(original, "Super+Down used another window's geometry");
    command("restore");
    QThread::msleep(120);
    expect(original, "Repeated restore moved the window");
    auto strut = atom("_NET_WM_STRUT_PARTIAL");
    uint32_t reserved[12]{};
    reserved[3] = 30;
    reserved[11] = screen->width_in_pixels - 1;
    xcb_change_property(c, XCB_PROP_MODE_REPLACE, w, strut, XCB_ATOM_CARDINAL, 32, 12, reserved);
    xcb_flush(c);
    require(firstValue(w, strut) == 0, "Unexpected strut");
    command("left");
    expect(left.adjusted(0, 0, 0, -30), "Panel strut ignored");
    command("restore");
    expect(original, "Restore after partial-strut snap failed");
    xcb_delete_property(c, w, strut);
    xcb_flush(c);

    command("left");
    expect(left, "Cannot snap before unmapping");
    xcb_unmap_window(c, w);
    xcb_flush(c);
    const auto list = atom("_NET_CLIENT_LIST");
    waitFor([&] { return firstValue(root, list) != w; }, "Openbox did not unmanage hidden window");
    xcb_map_window(c, w);
    xcb_flush(c);
    waitFor([&] { return firstValue(root, active) == w && firstValue(root, list) == w; },
            "Cannot remap window");
    command("restore");
    expect(original, "Unmapping discarded saved geometry");

    auto input = [&](uint8_t kind, uint8_t detail, QPoint pos = {}) {
        xcb_test_fake_input(c, kind, detail, 0, root, pos.x(), pos.y(), 0);
        xcb_flush(c);
        QThread::msleep(70);
    };
    auto title = [&] {
        auto r = frame();
        return QPoint(r.center().x(), r.y() + 8);
    };
    auto start = title();
    input(XCB_MOTION_NOTIFY, 0, start);
    input(XCB_BUTTON_PRESS, 1);
    for (int i = 1; i <= 10; ++i)
        input(XCB_MOTION_NOTIFY, 0, {start.x() - (start.x() - 2) * i / 10, start.y() + i * 2});
    input(XCB_BUTTON_RELEASE, 1);
    expect(left, "Drag to left edge failed");
    command("restore");
    expect(original, "Drag restore lost initial geometry");

    input(XCB_MOTION_NOTIFY, 0, title());
    input(XCB_BUTTON_PRESS, 1);
    destroy();
    create(320, 260);
    const auto untouched = frame();
    input(XCB_MOTION_NOTIFY, 0, {1, 240});
    input(XCB_BUTTON_RELEASE, 1);
    QThread::msleep(130);
    expect(untouched, "Destroyed drag snapped replacement");
    command("restore");
    QThread::msleep(120);
    expect(untouched, "Destroyed drag kept restore geometry");
    command("stop");
    require(daemon.waitForFinished(2000) && daemon.exitCode() == 0, "Service stop failed");
    command("stop");
}

} // namespace

int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    try {
        require(argc == 3, "Specify Xvfb and snapping executable paths");
        if (QString::fromLocal8Bit(argv[1]) == "--worker")
            exercise(QString::fromLocal8Bit(argv[2]));
        else
            doro_test::isolated(QString::fromLocal8Bit(argv[1]), {QString::fromLocal8Bit(argv[2])},
                                "1025x768x24");
        return 0;
    } catch (const std::exception &e) {
        std::fprintf(stderr, "%s\n", e.what());
        return 1;
    }
}
