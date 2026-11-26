#pragma once
#include <QtCore>
#include <optional>

namespace input {
inline constexpr auto enabledProp = "Device Enabled";
inline constexpr auto evdevProp = "Device Accel Profile";
inline constexpr auto libinputProp = "libinput Accel Profile Enabled";
inline constexpr auto availableProp = "libinput Accel Profiles Available";
inline constexpr auto markerProp = "_DOROSHELL_INPUT_INSTANCE";

[[noreturn]] void fail(const QString& reason);
QString digest(const QByteArray& raw);
QString identity(const QStringList& fields);
QJsonObject value(int type, int format, const QJsonArray& values);
QJsonArray target(const QString& name, const QJsonObject& current);
struct Device {
    QString key, name, node, kind, driver;
    int id;
    bool enabled, usableMouse;
    QJsonObject props;
    QJsonObject get(const QString& prop) const { return props.value(prop).toObject(); }
    QString marker() const;
};
struct Capability {
    QString action, property;
    QJsonArray values;
    bool operator==(const Capability&) const = default;
};
std::optional<Capability> capability(const Device& dev);
bool otherMouse(const QList<Device>& devices);
class Backend {
  public:
    virtual ~Backend() = default;
    virtual QList<Device> devices() = 0;
    virtual QString token() = 0;
    virtual void mark(const Device& device, const QString& marker) = 0;
    virtual void write(const Device& device, const QString& prop, const QJsonObject& target) = 0;
};
class Lock {
  public:
    Lock(const QString& path, bool wait);
    ~Lock();
    Lock(const Lock&) = delete;
    void operator=(const Lock&) = delete;

  private:
    int fd = -1;
};
struct Busy : std::runtime_error {
    Busy() : std::runtime_error("Input preferences are busy.") {}
};
struct Saved {
    QByteArray raw;
    QJsonObject data;
};
struct Edit {
    QString key;
    QJsonObject rule;
    bool stop = false;
    bool undoFirstLogin = false;
    std::optional<bool> global;
    QString revision;
    bool requested() const { return !key.isEmpty() || stop || global.has_value(); }
};
class Preferences {
  public:
    Preferences(QString home, QString helper);
    Saved read() const;
    static bool needed(const QJsonObject& data);
    bool firstLogin();
    void removeFirstLogin(const std::function<Backend&()>& backend);
    QStringList run(Backend& backend, const Edit& edit = {}, bool* incomplete = nullptr);
    QString watchLock() const;
    void startWatcher() const;

  private:
    QString home, helper, path, startup, lock;
    void safe(const QString& name) const;
    void write(const QString& name, const QByteArray& bytes) const;
    void store(const QJsonObject& data) const;
    QByteArray payload(bool legacy = false) const;
    QByteArray checkStartup(const QJsonObject& data) const;
    void autostart(QJsonObject& data, bool required) const;
    void archive(const QString& key, const QJsonObject& rule, const QJsonObject& receipt,
                 const QString& reason) const;
};
} // namespace input
