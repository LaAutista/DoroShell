#pragma once
#include "model.hpp"
#include <QSocketNotifier>
#include <xcb/xcb.h>

class FocusTracker : public QObject {
public:
  explicit FocusTracker(const Catalog &apps);
  ~FocusTracker() override;

private:
  void selectActive();
  void examine();
  void drain();
  xcb_atom_t atom(const char *name);
  QByteArray property(xcb_window_t window, xcb_atom_t property, xcb_atom_t type,
                      int format);
  const Catalog &catalog;
  xcb_connection_t *connection = nullptr;
  xcb_window_t root = 0, window = 0;
  xcb_atom_t active = 0, file = 0, gtkId = 0, type = 0, normal = 0, dialog = 0;
  QString last;
};
