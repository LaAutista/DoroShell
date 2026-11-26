#include "model.hpp"
#include <QMap>
#include <algorithm>
#include <pwd.h>
#include <unistd.h>

namespace net {
QString security(NM80211ApSecurityFlags flags, NM80211ApFlags apFlags) {
    if (flags & NM_802_11_AP_SEC_KEY_MGMT_EAP_SUITE_B_192)
        return "wpa-eap-suite-b-192";
    if (flags & NM_802_11_AP_SEC_KEY_MGMT_802_1X)
        return "wpa-eap";
    if (flags & NM_802_11_AP_SEC_KEY_MGMT_SAE)
        return "sae";
    if (flags & NM_802_11_AP_SEC_KEY_MGMT_PSK)
        return "wpa-psk";
    if (flags & (NM_802_11_AP_SEC_KEY_MGMT_OWE | NM_802_11_AP_SEC_KEY_MGMT_OWE_TM))
        return "owe";
    if (flags)
        return "unsupported";
    return apFlags & NM_802_11_AP_FLAGS_PRIVACY ? "none" : "open";
}
QString security(NMAccessPoint* ap) {
    return security(static_cast<NM80211ApSecurityFlags>(nm_access_point_get_wpa_flags(ap) |
                                                        nm_access_point_get_rsn_flags(ap)),
                    nm_access_point_get_flags(ap));
}
static QByteArray bytes(GBytes* ssid) {
    gsize size = 0;
    auto data = static_cast<const char*>(g_bytes_get_data(ssid, &size));
    return QByteArray(data, qsizetype(size));
}
QString ssidName(GBytes* ssid) {
    auto raw = bytes(ssid);
    auto utf8 = nm_utils_ssid_to_utf8(reinterpret_cast<const guint8*>(raw.constData()), raw.size());
    QString result = QString::fromUtf8(utf8);
    g_free(utf8);
    return result;
}
QVector<NMAccessPoint*> nearby(NMDeviceWifi* device) {
    auto active = nm_device_wifi_get_active_access_point(device);
    QMap<std::pair<QByteArray, QString>, NMAccessPoint*> best;
    for (auto ap : objects<NMAccessPoint>(nm_device_wifi_get_access_points(device))) {
        auto ssid = nm_access_point_get_ssid(ap);
        if (!ssid || !g_bytes_get_size(ssid))
            continue;
        auto& previous = best[{bytes(ssid), security(ap)}];
        if (!previous || ap == active ||
            (previous != active &&
             nm_access_point_get_strength(ap) > nm_access_point_get_strength(previous)))
            previous = ap;
    }
    auto values = best.values();
    std::stable_sort(values.begin(), values.end(), [active](auto a, auto b) {
        if ((a == active) != (b == active))
            return a == active;
        return nm_access_point_get_strength(a) > nm_access_point_get_strength(b);
    });
    return values;
}
QVector<NMRemoteConnection*> profiles(NMDevice* device, NMAccessPoint* ap) {
    auto candidates = objects<NMRemoteConnection>(nm_device_get_available_connections(device));
    if (!ap) {
        auto active = nm_device_get_active_connection(device);
        auto saved = active ? nm_active_connection_get_connection(active) : nullptr;
        if (saved && !candidates.contains(saved))
            candidates.push_back(saved);
    }
    candidates.removeIf([ap](auto profile) {
        return ap ? !nm_access_point_connection_valid(ap, NM_CONNECTION(profile))
                  : !nm_connection_is_type(NM_CONNECTION(profile), NM_SETTING_WIRED_SETTING_NAME);
    });
    return candidates;
}
QString stateLabel(NMDevice* device) {
    auto state = nm_device_get_state(device);
    if (state == NM_DEVICE_STATE_ACTIVATED)
        return "Connected";
    if (state == NM_DEVICE_STATE_FAILED)
        return "Connection failed";
    if (state == NM_DEVICE_STATE_DEACTIVATING)
        return "Disconnecting…";
    if (state >= NM_DEVICE_STATE_PREPARE && state < NM_DEVICE_STATE_ACTIVATED)
        return "Connecting…";
    if (!nm_device_get_managed(device))
        return "Unmanaged";
    if (NM_IS_DEVICE_ETHERNET(device) && !nm_device_ethernet_get_carrier(NM_DEVICE_ETHERNET(device)))
        return "Cable unplugged";
    return "Disconnected";
}
bool supportsHotspot(NMDeviceWifi* device) {
    constexpr auto required =
        NM_WIFI_DEVICE_CAP_AP | NM_WIFI_DEVICE_CAP_RSN | NM_WIFI_DEVICE_CAP_CIPHER_CCMP;
    return (nm_device_wifi_get_capabilities(device) & required) == required;
}
bool validHotspot(const QString& name, const QString& password) {
    return !name.isEmpty() && name.toUtf8().size() <= 32 && password.size() >= 8 && password.size() <= 63 &&
           std::all_of(password.cbegin(), password.cend(), [](QChar c) { return c >= u' ' && c <= u'~'; });
}
bool editableSecret(NMRemoteConnection* profile) {
    if (!nm_remote_connection_get_version_id(profile))
        return false;
    static const QStringList allowed{
        "connection", "802-11-wireless", "802-11-wireless-security", "ipv4", "ipv6", "proxy", "match",
        "link"};
    guint length;
    auto settings = nm_connection_get_settings(NM_CONNECTION(profile), &length);
    bool valid = true;
    for (guint i = 0; i < length; ++i)
        if (!allowed.contains(QString::fromUtf8(nm_setting_get_name(settings[i]))))
            valid = false;
    g_free(settings);
    return valid;
}
std::shared_ptr<NMConnection> wifiProfile(GBytes* ssid, const QString& key, bool hotspot) {
    auto user = getpwuid(getuid());
    if (!user || !user->pw_name || !*user->pw_name)
        return {};
    auto profile = own(nm_simple_connection_new());
    auto settings = nm_setting_connection_new();
    auto uuid = nm_utils_uuid_generate();
    g_object_set(settings, "id", ssidName(ssid).toUtf8().constData(), "uuid", uuid, "type",
                 NM_SETTING_WIRELESS_SETTING_NAME, "autoconnect", !hotspot, nullptr);
    g_free(uuid);
    if (!nm_setting_connection_add_permission(NM_SETTING_CONNECTION(settings), "user", user->pw_name,
                                              nullptr)) {
        g_object_unref(settings);
        return {};
    }
    nm_connection_add_setting(profile.get(), settings);
    auto wifi = nm_setting_wireless_new();
    g_object_set(wifi, "ssid", ssid, "mode", hotspot ? "ap" : "infrastructure", nullptr);
    nm_connection_add_setting(profile.get(), wifi);
    if (key != "open") {
        auto sec = nm_setting_wireless_security_new();
        g_object_set(sec, "key-mgmt", key.toLatin1().constData(), nullptr);
        if (hotspot) {
            nm_setting_wireless_security_add_proto(NM_SETTING_WIRELESS_SECURITY(sec), "rsn");
            nm_setting_wireless_security_add_pairwise(NM_SETTING_WIRELESS_SECURITY(sec), "ccmp");
        }
        nm_connection_add_setting(profile.get(), sec);
    }
    if (key.startsWith("wpa-eap")) {
        auto enterprise = nm_setting_802_1x_new();
        auto suiteB = key == "wpa-eap-suite-b-192";
        nm_setting_802_1x_add_eap_method(NM_SETTING_802_1X(enterprise), suiteB ? "tls" : "peap");
        if (!suiteB)
            g_object_set(enterprise, "phase2-auth", "mschapv2", nullptr);
        nm_connection_add_setting(profile.get(), enterprise);
    }
    if (hotspot) {
        auto ipv4 = nm_setting_ip4_config_new();
        g_object_set(ipv4, "method", "shared", nullptr);
        nm_connection_add_setting(profile.get(), ipv4);
    }
    return profile;
}
} // namespace net
