#pragma once
#include "preferences.hpp"
#include <xcb/xinput.h>
#include <libudev.h>
namespace input {
class XInput final : public Backend {
  public:
    XInput();
    QList<Device> devices() override;
    QString token() override;
    void mark(const Device& device, const QString& marker) override;
    void write(const Device& device, const QString& name, const QJsonObject& target) override;
    void watch(Preferences& store);

  private:
    std::unique_ptr<xcb_connection_t, decltype(&xcb_disconnect)> connection{nullptr, xcb_disconnect};
    std::unique_ptr<udev, decltype(&udev_unref)> udevContext{nullptr, udev_unref};
    xcb_window_t root = 0;
    quint8 opcode = 0;
    QHash<xcb_atom_t, QString> names;
    QHash<QString, xcb_atom_t> atoms;
    xcb_atom_t atom(const QString& value);
    QString atomName(xcb_atom_t value);
    QJsonObject get(int id, const QString& prop);
    void change(int id, const QString& prop, const QJsonObject& value);
    bool collect();
};
} // namespace input
