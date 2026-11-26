#pragma once
#include <NetworkManager.h>
#include <QString>
#include <QVector>
#include <memory>

namespace net {
template <class T> std::shared_ptr<T> own(T* value) {
    return {value, [](T* ptr) {
                if (ptr)
                    g_object_unref(ptr);
            }};
}
template <class T> std::shared_ptr<T> retain(T* value) {
    if (value)
        g_object_ref(value);
    return own(value);
}

template <class T> QVector<T*> objects(const GPtrArray* list) {
    QVector<T*> out;
    if (list)
        for (guint i = 0; i < list->len; ++i)
            out.push_back(static_cast<T*>(list->pdata[i]));
    return out;
}

QString security(NM80211ApSecurityFlags flags, NM80211ApFlags apFlags);
QString security(NMAccessPoint* ap);
QString ssidName(GBytes* ssid);
QString stateLabel(NMDevice* device);
QVector<NMAccessPoint*> nearby(NMDeviceWifi* device);
QVector<NMRemoteConnection*> profiles(NMDevice* device, NMAccessPoint* ap);
bool supportsHotspot(NMDeviceWifi* device);
bool validHotspot(const QString& name, const QString& password);
bool editableSecret(NMRemoteConnection* profile);
std::shared_ptr<NMConnection> wifiProfile(GBytes* ssid, const QString& key, bool hotspot = false);
} // namespace net
