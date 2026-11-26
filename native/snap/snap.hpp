// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <QByteArray>
#include <QHash>
#include <QRect>

#include <xcb/xcb.h>
#include <array>
#include <memory>
#include <optional>
#include <utility>
#include <vector>

enum class Action { Left, Right, Restore };

class Snap
{
  public:
    Snap();
    void apply(Action action);
    void poll();

  private:
    using Window = xcb_window_t;
    struct Drag {
        Window window;
        QRect frame;
    };
    std::unique_ptr<xcb_connection_t, decltype(&xcb_disconnect)> connection;
    Window root;
    QHash<QByteArray, xcb_atom_t> atoms;
    QHash<Window, QRect> saved;
    std::optional<Drag> drag;
    bool wasDown = false;

    xcb_atom_t atom(const QByteArray &name);
    std::vector<uint32_t> numbers(Window window, const QByteArray &name);
    Window active();
    bool eligible(Window window);
    std::array<int, 4> extents(Window window);
    QRect frame(Window window);
    std::pair<QRect, QRect> areas(QPoint point);
    void message(Window window, const QByteArray &name, std::array<uint32_t, 5> data);
    void resize(Window window, QRect target);
    bool watch(Window window);
    void unwatch(Window window);
    void drain();
    void finishDrag(const xcb_query_pointer_reply_t &pointer);
    void snapTo(Window window, QRect before, QRect workArea, Action side);
};
