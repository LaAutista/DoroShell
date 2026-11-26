// SPDX-License-Identifier: GPL-2.0-or-later
#include "snap.hpp"

#include <QCoreApplication>
#include <xcb/randr.h>
#include <algorithm>
#include <cstdlib>
#include <stdexcept>

namespace
{
template <class T> auto owned(T *response)
{
    return std::unique_ptr<T, decltype(&std::free)>(response, std::free);
}
struct WindowGone : std::runtime_error {
    WindowGone() : std::runtime_error("X window unavailable") {}
};
bool overlaps(int first, int last, uint32_t start, uint32_t end)
{
    return int64_t(first) <= end && int64_t(last) >= start;
}
} // namespace

Snap::Snap() : connection(nullptr, xcb_disconnect)
{
    int screen = 0;
    connection.reset(xcb_connect(nullptr, &screen));
    if (xcb_connection_has_error(connection.get()))
        throw std::runtime_error("Cannot connect to the X11 display");
    auto screens = xcb_setup_roots_iterator(xcb_get_setup(connection.get()));
    while (screen-- > 0 && screens.rem)
        xcb_screen_next(&screens);
    if (!screens.rem)
        throw std::runtime_error("X11 screen unavailable");
    root = screens.data->root;
    const auto wm = numbers(root, "_NET_SUPPORTING_WM_CHECK");
    if (wm.empty())
        throw std::runtime_error("No EWMH window manager detected");
    auto *c = connection.get();
    auto cookie = xcb_get_property(c, false, wm.front(), atom("_NET_WM_NAME"), XCB_ATOM_ANY, 0, 1024);
    auto name = owned(xcb_get_property_reply(c, cookie, nullptr));
    if (!name || name->format != 8 ||
        !QByteArray(static_cast<const char *>(xcb_get_property_value(name.get())),
                    xcb_get_property_value_length(name.get()))
             .toLower()
             .contains("openbox"))
        throw std::runtime_error("Edge snapping currently supports Openbox only");
}

xcb_atom_t Snap::atom(const QByteArray &name)
{
    auto found = atoms.constFind(name);
    if (found != atoms.cend())
        return found.value();
    auto *c = connection.get();
    auto reply = owned(xcb_intern_atom_reply(c, xcb_intern_atom(c, false, name.size(), name.data()), nullptr));
    if (!reply)
        throw std::runtime_error("Cannot resolve X11 atom");
    return atoms.insert(name, reply->atom).value();
}

std::vector<uint32_t> Snap::numbers(Window window, const QByteArray &name)
{
    auto *c = connection.get();
    auto cookie = xcb_get_property(c, false, window, atom(name), XCB_ATOM_ANY, 0, 1024 * 1024);
    auto reply = owned(xcb_get_property_reply(c, cookie, nullptr));
    if (!reply)
        throw WindowGone();
    if (reply->format != 32 || !reply->value_len)
        return {};
    const auto *data = static_cast<uint32_t *>(xcb_get_property_value(reply.get()));
    return {data, data + reply->value_len};
}

Snap::Window Snap::active()
{
    const auto windows = numbers(root, "_NET_ACTIVE_WINDOW");
    return windows.empty() ? XCB_NONE : windows.front();
}

bool Snap::eligible(Window window)
{
    auto contains = [this](const auto &items, const char *name) {
        return std::find(items.begin(), items.end(), atom(name)) != items.end();
    };
    const auto kinds = numbers(window, "_NET_WM_WINDOW_TYPE");
    if (!kinds.empty() && !contains(kinds, "_NET_WM_WINDOW_TYPE_NORMAL"))
        return false;
    const auto states = numbers(window, "_NET_WM_STATE");
    return !contains(states, "_NET_WM_STATE_FULLSCREEN") && !contains(states, "_NET_WM_STATE_HIDDEN");
}

std::array<int, 4> Snap::extents(Window window)
{
    const auto values = numbers(window, "_NET_FRAME_EXTENTS");
    std::array<int, 4> result{};
    if (values.size() == result.size() &&
        std::all_of(values.begin(), values.end(), [](auto v) { return v <= UINT16_MAX; }))
        std::copy(values.begin(), values.end(), result.begin());
    return result;
}

QRect Snap::frame(Window window)
{
    auto *c = connection.get();
    auto geometry = xcb_get_geometry(c, window);
    auto position = xcb_translate_coordinates(c, window, root, 0, 0);
    auto g = owned(xcb_get_geometry_reply(c, geometry, nullptr));
    auto p = owned(xcb_translate_coordinates_reply(c, position, nullptr));
    if (!g || !p)
        throw WindowGone();
    const auto [left, right, top, bottom] = extents(window);
    return {p->dst_x - left, p->dst_y - top, g->width + left + right, g->height + top + bottom};
}

std::pair<QRect, QRect> Snap::areas(QPoint point)
{
    auto *c = connection.get();
    auto g = owned(xcb_get_geometry_reply(c, xcb_get_geometry(c, root), nullptr));
    if (!g)
        throw WindowGone();
    QRect monitor(0, 0, g->width, g->height);
    auto reply = owned(xcb_randr_get_monitors_reply(c, xcb_randr_get_monitors(c, root, true), nullptr));
    if (reply) {
        bool first = true;
        for (auto i = xcb_randr_get_monitors_monitors_iterator(reply.get()); i.rem;
             xcb_randr_monitor_info_next(&i)) {
            const QRect candidate(i.data->x, i.data->y, i.data->width, i.data->height);
            if (first || candidate.contains(point))
                monitor = candidate;
            if (candidate.contains(point))
                break;
            first = false;
        }
    }
    int left = monitor.left(), top = monitor.top();
    int right = monitor.right() + 1, bottom = monitor.bottom() + 1;
    for (auto w : numbers(root, "_NET_CLIENT_LIST")) {
        std::vector<uint32_t> s;
        try {
            s = numbers(w, "_NET_WM_STRUT_PARTIAL");
        } catch (const WindowGone &) {
            continue;
        }
        if (s.size() != 12)
            continue;
        if (s[0] && s[0] <= g->width && overlaps(top, bottom - 1, s[4], s[5]))
            left = std::max(left, int(s[0]));
        if (s[1] && s[1] <= g->width && overlaps(top, bottom - 1, s[6], s[7]))
            right = std::min(right, g->width - int(s[1]));
        if (s[2] && s[2] <= g->height && overlaps(left, right - 1, s[8], s[9]))
            top = std::max(top, int(s[2]));
        if (s[3] && s[3] <= g->height && overlaps(left, right - 1, s[10], s[11]))
            bottom = std::min(bottom, g->height - int(s[3]));
    }
    return {monitor, {left, top, std::max(1, right - left), std::max(1, bottom - top)}};
}

void Snap::message(Window window, const QByteArray &name, std::array<uint32_t, 5> data)
{
    xcb_client_message_event_t event{};
    event.response_type = XCB_CLIENT_MESSAGE;
    event.window = window;
    event.type = atom(name);
    event.format = 32;
    std::copy(data.begin(), data.end(), event.data.data32);
    xcb_send_event(connection.get(), false, root,
                   XCB_EVENT_MASK_SUBSTRUCTURE_REDIRECT | XCB_EVENT_MASK_SUBSTRUCTURE_NOTIFY,
                   reinterpret_cast<const char *>(&event));
}

void Snap::resize(Window window, QRect target)
{
    const auto [left, right, top, bottom] = extents(window);
    message(window, "_NET_WM_STATE",
            {0, atom("_NET_WM_STATE_MAXIMIZED_VERT"), atom("_NET_WM_STATE_MAXIMIZED_HORZ"), 2, 0});
    message(window, "_NET_MOVERESIZE_WINDOW",
            {1 | (15 << 8) | (2 << 12), uint32_t(target.x()), uint32_t(target.y()),
             uint32_t(std::max(1, target.width() - left - right)),
             uint32_t(std::max(1, target.height() - top - bottom))});
    xcb_flush(connection.get());
}

bool Snap::watch(Window window)
{
    const uint32_t mask = XCB_EVENT_MASK_STRUCTURE_NOTIFY;
    auto request = xcb_change_window_attributes_checked(connection.get(), window, XCB_CW_EVENT_MASK, &mask);
    return !owned(xcb_request_check(connection.get(), request));
}

void Snap::unwatch(Window window)
{
    if (saved.contains(window) || (drag && drag->window == window))
        return;
    const uint32_t mask = 0;
    xcb_change_window_attributes(connection.get(), window, XCB_CW_EVENT_MASK, &mask);
}

void Snap::drain()
{
    while (auto event = owned(xcb_poll_for_queued_event(connection.get()))) {
        if ((event->response_type & 0x7f) != XCB_DESTROY_NOTIFY)
            continue;
        const auto w = reinterpret_cast<const xcb_destroy_notify_event_t *>(event.get())->window;
        saved.remove(w);
        if (drag && drag->window == w)
            drag.reset();
    }
}

void Snap::snapTo(Window w, QRect before, QRect workArea, Action side)
{
    if (!saved.contains(w)) {
        if (!watch(w))
            return;
        saved.insert(w, before);
    }
    const int half = workArea.width() / 2;
    if (side == Action::Left)
        workArea.setWidth(half);
    else
        workArea.setLeft(workArea.left() + half);
    resize(w, workArea);
}

void Snap::apply(Action action)
{
    try {
        Window w = active();
        drain();
        if (!w || !eligible(w))
            return;
        if (action == Action::Restore) {
            if (saved.contains(w)) {
                auto original = saved.take(w);
                unwatch(w);
                resize(w, original);
            }
        } else {
            auto rect = frame(w);
            auto middle = rect.topLeft() + QPoint(rect.width() / 2, rect.height() / 2);
            snapTo(w, rect, areas(middle).second, action);
        }
    } catch (const WindowGone &) {
    }
}

void Snap::finishDrag(const xcb_query_pointer_reply_t &pointer)
{
    const auto [w, before] = *drag;
    const auto now = frame(w);
    if (before.topLeft() != now.topLeft() && before.size() == now.size()) {
        const auto [monitor, workArea] = areas({pointer.root_x, pointer.root_y});
        drain();
        if (drag && pointer.root_x <= monitor.left() + 8)
            snapTo(w, before, workArea, Action::Left);
        else if (drag && pointer.root_x >= monitor.right() - 8)
            snapTo(w, before, workArea, Action::Right);
    }
    drag.reset();
    unwatch(w);
}

void Snap::poll()
{
    auto *c = connection.get();
    auto p = owned(xcb_query_pointer_reply(c, xcb_query_pointer(c, root), nullptr));
    if (!p) {
        QCoreApplication::exit(1);
        return;
    }
    drain();
    const bool down = p->mask & XCB_KEY_BUT_MASK_BUTTON_1;
    try {
        if (down && !wasDown) {
            const auto w = active();
            if (w && eligible(w) && watch(w)) {
                drag = Drag{w, {}};
                drag->frame = frame(w);
            }
        } else if (wasDown && !down && drag) {
            finishDrag(*p);
        }
    } catch (const WindowGone &) {
        if (drag) {
            const auto w = drag->window;
            drag.reset();
            unwatch(w);
        }
    }
    wasDown = down;
}
