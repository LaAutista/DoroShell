#include "xinput.hpp"
#include <xcb/xcbext.h>
#include <poll.h>
#include <sys/stat.h>
#include <cstdlib>

namespace input {
template <class T> static auto owned(T* p) {
    return std::unique_ptr<T, decltype(&std::free)>(p, std::free);
}
template <class T> static auto reply(T* p) {
    if (!p)
        fail("XInput device changed or the X server disconnected.");
    return owned(p);
}
static void checked(xcb_connection_t* x, xcb_void_cookie_t cookie) {
    auto error = owned(xcb_request_check(x, cookie));
    if (error || xcb_connection_has_error(x))
        fail("X server rejected an input property request.");
}
XInput::XInput() {
    if (qgetenv("XDG_SESSION_TYPE") != "x11" || qEnvironmentVariableIsEmpty("DISPLAY"))
        fail("Requires an X11 session; Wayland is unsupported.");
    int screen = 0;
    connection.reset(xcb_connect(nullptr, &screen));
    auto x = connection.get();
    if (!x || xcb_connection_has_error(x))
        fail("Cannot open the X11 display.");
    auto ext = xcb_get_extension_data(x, &xcb_input_id);
    if (!ext || !ext->present)
        fail("XInput is unavailable.");
    opcode = ext->major_opcode;
    auto v = reply(xcb_input_xi_query_version_reply(x, xcb_input_xi_query_version(x, 2, 0), nullptr));
    if (v->major_version < 2)
        fail("XInput 2 is required.");
    auto it = xcb_setup_roots_iterator(xcb_get_setup(x));
    for (int i = 0; i < screen && it.rem; ++i)
        xcb_screen_next(&it);
    if (!it.rem)
        fail("Missing X11 root window.");
    root = it.data->root;
    udevContext.reset(udev_new());
    if (!udevContext)
        fail("Could not initialize device identification.");
}
xcb_atom_t XInput::atom(const QString& s) {
    if (atoms.contains(s))
        return atoms[s];
    auto b = s.toLatin1();
    auto x = connection.get();
    auto r = reply(xcb_intern_atom_reply(x, xcb_intern_atom(x, 0, b.size(), b.constData()), nullptr));
    names[r->atom] = s;
    return atoms[s] = r->atom;
}
QString XInput::atomName(xcb_atom_t a) {
    if (names.contains(a))
        return names[a];
    auto x = connection.get();
    auto r = reply(xcb_get_atom_name_reply(x, xcb_get_atom_name(x, a), nullptr));
    auto s = QString::fromLatin1(xcb_get_atom_name_name(r.get()), xcb_get_atom_name_name_length(r.get()));
    atoms[s] = a;
    return names[a] = s;
}
QJsonObject XInput::get(int id, const QString& prop) {
    auto x = connection.get();
    auto r = reply(xcb_input_xi_get_property_reply(
        x, xcb_input_xi_get_property(x, id, 0, atom(prop), XCB_ATOM_ANY, 0, 1024), nullptr));
    if (!r->type || r->bytes_after)
        return {};
    auto items = xcb_input_xi_get_property_items(r.get());
    QJsonArray values;
    for (quint32 i = 0; i < r->num_items; ++i) {
        if (r->format == 8)
            values.append(static_cast<quint8*>(items)[i]);
        else if (r->format == 16)
            values.append(static_cast<quint16*>(items)[i]);
        else if (r->format == 32)
            values.append(qint64(static_cast<quint32*>(items)[i]));
        else
            return {};
    }
    return value(r->type, r->format, values);
}
QList<Device> XInput::devices() {
    auto x = connection.get();
    auto devices = reply(
        xcb_input_xi_query_device_reply(x, xcb_input_xi_query_device(x, XCB_INPUT_DEVICE_ALL), nullptr));
    QList<Device> output;
    for (auto i = xcb_input_xi_query_device_infos_iterator(devices.get()); i.rem;
         xcb_input_xi_device_info_next(&i)) {
        auto info = i.data;
        if (info->type != XCB_INPUT_DEVICE_TYPE_SLAVE_POINTER)
            continue;
        Device d{};
        d.id = info->deviceid;
        d.enabled = info->enabled;
        d.name = QString::fromLatin1(xcb_input_xi_device_info_name(info), info->name_len);
        auto list =
            owned(xcb_input_xi_list_properties_reply(x, xcb_input_xi_list_properties(x, d.id), nullptr));
        if (!list)
            continue;
        bool evdev = false, libinput = false, synaptics = false, absolute = false;
        auto properties = xcb_input_xi_list_properties_properties(list.get());
        for (int j = 0; j < xcb_input_xi_list_properties_properties_length(list.get()); ++j) {
            auto name = atomName(properties[j]);
            evdev |= name.startsWith("Evdev ");
            libinput |= name.startsWith("libinput ");
            synaptics |= name.startsWith("Synaptics ");
            absolute |= name == "libinput Calibration Matrix";
            if (name == "Device Node" || name == markerProp || name == enabledProp || name == evdevProp ||
                name == libinputProp || name == availableProp)
                d.props[name] = get(d.id, name);
        }
        d.driver = evdev ? "evdev" : libinput ? "libinput" : synaptics ? "synaptics" : "unknown";
        QByteArray node;
        for (auto item : d.get("Device Node")["values"].toArray())
            node.append(char(item.toInt()));
        while (node.endsWith('\0'))
            node.chop(1);
        d.node = QString::fromLatin1(node);
        static const QRegularExpression nodePattern("^/dev/input/event[0-9]+$");
        if (!nodePattern.match(d.node).hasMatch())
            continue;
        struct stat st{};
        if (stat(node.constData(), &st) || !S_ISCHR(st.st_mode))
            continue;
        std::unique_ptr<udev_device, decltype(&udev_device_unref)> device(
            udev_device_new_from_devnum(udevContext.get(), 'c', st.st_rdev), udev_device_unref);
        if (!device)
            continue;
        auto field = [&](const char* key) {
            return QString::fromUtf8(udev_device_get_property_value(device.get(), key));
        };
        bool touch = field("ID_INPUT_TOUCHPAD") == "1";
        bool mouse = field("ID_INPUT_MOUSE") == "1" && field("ID_INPUT_KEYBOARD") != "1" &&
                     field("ID_INPUT_TOUCHSCREEN") != "1";
        d.kind = touch ? "touchpad" : mouse ? "mouse" : "other";
        auto serial = field("ID_SERIAL"), path = field("ID_PATH");
        if (serial.isEmpty() && path.isEmpty())
            d.kind = "other";
        d.key = identity({d.name, serial, path, field("ID_VENDOR_ID"), field("ID_MODEL_ID")});
        auto bus = field("ID_BUS");
        d.usableMouse = d.kind == "mouse" && (bus == "usb" || bus == "bluetooth") &&
                        !field("DEVPATH").contains("/virtual/") && !absolute;
        output << d;
    }
    return output;
}
QString XInput::token() {
    auto x = connection.get();
    auto property = atom("_DOROSHELL_INPUT_SESSION");
    auto read = [&] {
        return reply(xcb_get_property_reply(x, xcb_get_property(x, 0, root, property, XCB_ATOM_ANY, 0, 64),
                                            nullptr));
    };
    auto current = read();
    if (!current->type) {
        auto data = QUuid::createUuid().toString(QUuid::Id128).toLatin1();
        checked(x, xcb_change_property_checked(x, XCB_PROP_MODE_REPLACE, root, property, XCB_ATOM_STRING, 8,
                                               data.size(), data.constData()));
        current = read();
    }
    if (current->format != 8 || current->type != XCB_ATOM_STRING ||
        xcb_get_property_value_length(current.get()) != 32)
        fail("The X11 input session marker is invalid.");
    return QString::fromLatin1(static_cast<char*>(xcb_get_property_value(current.get())), 32);
}
void XInput::change(int id, const QString& prop, const QJsonObject& v) {
    auto x = connection.get();
    int format = v["format"].toInt();
    auto a = v["values"].toArray();
    QByteArray b;
    QList<quint32> words;
    for (auto n : a)
        if (format == 8)
            b.append(char(n.toInt()));
        else if (format == 32)
            words.append(quint32(n.toInteger()));
        else
            fail("Unsupported property format.");
    auto data =
        format == 8 ? static_cast<const void*>(b.constData()) : static_cast<const void*>(words.constData());
    checked(x, xcb_input_xi_change_property_checked(x, id, XCB_PROP_MODE_REPLACE, format, atom(prop),
                                                    v["type"].toInteger(), a.size(), data));
    if (get(id, prop) != v)
        fail("Driver did not accept the requested property.");
}
void XInput::mark(const Device& dev, const QString& marker) {
    QJsonArray bytes;
    for (char c : marker.toLatin1())
        bytes.append(int(c));
    change(dev.id, markerProp, value(XCB_ATOM_STRING, 8, bytes));
}
void XInput::write(const Device& device, const QString& prop, const QJsonObject& desired) {
    // Hold the server for the final compare and write, never across disk I/O or UI.
    const auto all = devices();
    QList<Device> matches;
    for (const auto& d : all)
        if (d.key == device.key)
            matches << d;
    if (matches.size() != 1 || matches[0].id != device.id || matches[0].node != device.node)
        fail("Device changed before apply.");
    auto fresh = matches[0];
    if (prop == enabledProp && desired["values"].toArray() == QJsonArray{0} && !otherMouse(all))
        fail("The other mouse disappeared; touchpad disable refused.");
    auto x = connection.get();
    checked(x, xcb_grab_server_checked(x));
    auto ungrab = qScopeGuard([x] {
        xcb_ungrab_server(x);
        xcb_flush(x);
    });
    fresh.props[markerProp] = get(device.id, markerProp);
    if (fresh.marker() != device.marker())
        fail("Device instance was replaced before apply.");
    if (get(device.id, prop) != device.get(prop))
        fail("Property changed elsewhere before apply.");
    if (prop == enabledProp && desired["values"].toArray() == QJsonArray{0}) {
        bool live = false;
        for (const auto& mouse : all)
            if (mouse.usableMouse && mouse.enabled &&
                get(mouse.id, enabledProp)["values"].toArray() == QJsonArray{1} &&
                get(mouse.id, "Device Node") == mouse.get("Device Node")) {
                live = true;
                break;
            }
        if (!live)
            fail("The other mouse disappeared; touchpad disable refused.");
    }
    if (prop == libinputProp) {
        auto offered = get(device.id, availableProp)["values"].toArray(), req = desired["values"].toArray();
        if (req.size() != offered.size())
            fail("Requested profile is no longer offered.");
        for (qsizetype i = 0; i < req.size(); ++i)
            if (req[i] == 1 && offered[i] != 1)
                fail("Requested profile is no longer offered.");
    }
    change(device.id, prop, desired);
}
bool XInput::collect() {
    bool changed = false;
    auto x = connection.get();
    while (auto raw = xcb_poll_for_event(x)) {
        auto event = owned(raw);
        if ((event->response_type & 0x7f) != XCB_GE_GENERIC)
            continue;
        auto h = reinterpret_cast<xcb_input_hierarchy_event_t*>(event.get());
        if (h->extension == opcode && h->event_type == XCB_INPUT_HIERARCHY)
            changed |= (h->flags & (XCB_INPUT_HIERARCHY_MASK_SLAVE_ADDED |
                                    XCB_INPUT_HIERARCHY_MASK_DEVICE_ENABLED)) != 0;
    }
    if (xcb_connection_has_error(x))
        fail("X server disconnected.");
    return changed;
}
void XInput::watch(Preferences& store) {
    std::unique_ptr<Lock> guard;
    try {
        guard = std::make_unique<Lock>(store.watchLock(), false);
    } catch (const Busy&) {
        return;
    }
    auto x = connection.get();
    struct {
        xcb_input_event_mask_t header;
        quint32 bits;
    } mask{{XCB_INPUT_DEVICE_ALL, 1}, XCB_INPUT_XI_EVENT_MASK_HIERARCHY};
    checked(x, xcb_input_xi_select_events_checked(x, root, 1, &mask.header));
    bool pending = true;
    while (true) {
        if (pending) {
            try {
                auto messages = store.run(*this);
                QTextStream(stdout) << messages.join('\n') << Qt::endl;
                pending = false;
            } catch (const Busy&) {
            }
        }
        if (!pending && !Preferences::needed(store.read().data))
            return;
        if (collect()) {
            QThread::msleep(500);
            collect();
            pending = true;
            continue;
        }
        pollfd fd{xcb_get_file_descriptor(x), POLLIN, 0};
        if (poll(&fd, 1, 5000) < 0 && errno != EINTR)
            fail("Input watcher could not wait for devices.");
    }
}
} // namespace input
