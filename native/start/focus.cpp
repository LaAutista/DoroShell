#include "focus.hpp"
#include <QCoreApplication>
#include <QFile>
#include <cstdlib>
#include <cstring>
#include <sys/stat.h>

namespace {
uint32_t firstWord(const QByteArray &bytes) {
  uint32_t value = 0;
  if (bytes.size() >= 4)
    std::memcpy(&value, bytes.constData(), 4);
  return value;
}
} // namespace
FocusTracker::FocusTracker(const Catalog &apps) : catalog(apps) {
  int screen = 0;
  connection = xcb_connect(nullptr, &screen);
  if (xcb_connection_has_error(connection))
    return;
  auto iter = xcb_setup_roots_iterator(xcb_get_setup(connection));
  while (screen-- > 0 && iter.rem)
    xcb_screen_next(&iter);
  if (!iter.rem)
    return;
  root = iter.data->root;
  active = atom("_NET_ACTIVE_WINDOW");
  file = atom("_KDE_NET_WM_DESKTOP_FILE");
  gtkId = atom("_GTK_APPLICATION_ID");
  type = atom("_NET_WM_WINDOW_TYPE");
  normal = atom("_NET_WM_WINDOW_TYPE_NORMAL");
  dialog = atom("_NET_WM_WINDOW_TYPE_DIALOG");
  uint32_t mask = XCB_EVENT_MASK_PROPERTY_CHANGE;
  xcb_change_window_attributes(connection, root, XCB_CW_EVENT_MASK, &mask);
  auto *notifier = new QSocketNotifier(xcb_get_file_descriptor(connection),
                                       QSocketNotifier::Read, this);
  connect(notifier, &QSocketNotifier::activated, this, [this, notifier] {
    drain();
    if (xcb_connection_has_error(connection))
      notifier->setEnabled(false);
  });
  selectActive();
  drain();
}
FocusTracker::~FocusTracker() {
  if (connection)
    xcb_disconnect(connection);
}
xcb_atom_t FocusTracker::atom(const char *name) {
  auto *r = xcb_intern_atom_reply(
      connection, xcb_intern_atom(connection, 0, std::strlen(name), name),
      nullptr);
  auto a = r ? r->atom : 0;
  free(r);
  return a;
}
QByteArray FocusTracker::property(xcb_window_t w, xcb_atom_t prop,
                                  xcb_atom_t expected, int format) {
  auto *r = xcb_get_property_reply(
      connection, xcb_get_property(connection, 0, w, prop, expected, 0, 1024),
      nullptr);
  QByteArray result;
  if (r && r->format == format && !r->bytes_after)
    result = QByteArray(static_cast<char *>(xcb_get_property_value(r)),
                        xcb_get_property_value_length(r));
  free(r);
  return result;
}
void FocusTracker::selectActive() {
  auto id = firstWord(property(root, active, XCB_ATOM_WINDOW, 32));
  if (id == window)
    return;
  uint32_t mask = 0;
  if (window)
    xcb_change_window_attributes(connection, window, XCB_CW_EVENT_MASK, &mask);
  window = id;
  last.clear();
  if (id) {
    mask = XCB_EVENT_MASK_PROPERTY_CHANGE;
    xcb_change_window_attributes(connection, window, XCB_CW_EVENT_MASK, &mask);
    examine();
  }
  xcb_flush(connection);
}
void FocusTracker::examine() {
  // When the installed helper is removed or replaced it relinquishes recording.
  struct stat installed{}, running{};
  if (::stat(QFile::encodeName(QCoreApplication::applicationFilePath()),
             &installed) ||
      ::stat("/proc/self/exe", &running) ||
      installed.st_ino != running.st_ino || installed.st_dev != running.st_dev)
    return;
  auto history = readRecent();
  if (!history.error.isEmpty() || !history.value.object()["enabled"].toBool())
    return;
  auto kind = firstWord(property(window, type, XCB_ATOM_ATOM, 32));
  if (kind && kind != normal && kind != dialog)
    return;
  QStringList names, classes;
  for (auto a : {file, gtkId}) {
    auto s = property(window, a, XCB_ATOM_ANY, 8);
    if (!s.isEmpty())
      names << QString::fromUtf8(s.constData());
  }
  for (const auto &s :
       property(window, XCB_ATOM_WM_CLASS, XCB_ATOM_STRING, 8).split('\0'))
    if (!s.isEmpty())
      classes << QString::fromLatin1(s);
  auto key = identifyApp(catalog, names, classes);
  static const QStringList excluded = {
      "lxqt-leave.desktop",    "lxqt-lockscreen.desktop",
      "lxqt-logout.desktop",   "lxqt-shutdown.desktop",
      "lxqt-reboot.desktop",   "lxqt-suspend.desktop",
      "lxqt-hibernate.desktop"};
  if (!key.isEmpty() && key != last && !excluded.contains(key)) {
    try {
      updateHistory(key);
      last = key;
    } catch (const std::exception &) {
    }
  }
}
void FocusTracker::drain() {
  while (auto *event = xcb_poll_for_event(connection)) {
    if ((event->response_type & 0x7f) == XCB_PROPERTY_NOTIFY) {
      auto *p = reinterpret_cast<xcb_property_notify_event_t *>(event);
      if (p->window == root && p->atom == active)
        selectActive();
      else if (p->window == window &&
               (p->atom == type || p->atom == file || p->atom == gtkId ||
                p->atom == XCB_ATOM_WM_CLASS))
        examine();
    }
    free(event);
  }
}
