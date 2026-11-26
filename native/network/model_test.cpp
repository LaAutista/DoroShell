#include "model.hpp"
#include <cstdio>

int main() {
    using namespace net;
    int failures = 0;
    auto check = [&](bool ok, const char* what) {
        if (!ok) {
            std::fprintf(stderr, "%s\n", what);
            ++failures;
        }
    };
    check(security(NM_802_11_AP_SEC_NONE, NM_802_11_AP_FLAGS_NONE) == "open", "open");
    check(security(NM_802_11_AP_SEC_NONE, NM_802_11_AP_FLAGS_PRIVACY) == "none", "WEP");
    check(security(NM_802_11_AP_SEC_KEY_MGMT_OWE, NM_802_11_AP_FLAGS_PRIVACY) == "owe", "OWE");
    check(security(static_cast<NM80211ApSecurityFlags>(NM_802_11_AP_SEC_KEY_MGMT_PSK |
                                                       NM_802_11_AP_SEC_KEY_MGMT_SAE),
                   NM_802_11_AP_FLAGS_PRIVACY) == "sae",
          "prefer SAE");
    check(validHotspot("Home", "password"), "valid hotspot");
    check(!validHotspot(QString(17, QChar(0x00e9)), "password"), "SSID byte limit");
    check(!validHotspot("Home", "passwörd"), "hotspot password character limit");
    auto ssid = g_bytes_new_static("phone", 5);
    auto ap = wifiProfile(ssid, "wpa-psk", true);
    auto wifi = nm_connection_get_setting_wireless(ap.get());
    auto con = nm_connection_get_setting_connection(ap.get());
    auto sec = nm_connection_get_setting_wireless_security(ap.get());
    check(nm_setting_connection_get_num_permissions(con) == 1, "profiles belong to the user");
    check(!nm_setting_connection_get_autoconnect(con), "hotspot not automatically activated");
    check(QString(nm_setting_wireless_get_mode(wifi)) == "ap", "AP mode");
    check(QString(nm_setting_wireless_security_get_proto(sec, 0)) == "rsn", "WPA2");
    check(QString(nm_setting_wireless_security_get_pairwise(sec, 0)) == "ccmp", "CCMP");
    check(QString(nm_setting_ip_config_get_method(nm_connection_get_setting_ip4_config(ap.get()))) ==
              "shared",
          "shared IPv4");
    auto open = wifiProfile(ssid, "open");
    check(!nm_connection_get_setting_wireless_security(open.get()), "open security");
    auto enterprise = wifiProfile(ssid, "wpa-eap-suite-b-192");
    check(QString(nm_setting_802_1x_get_eap_method(nm_connection_get_setting_802_1x(enterprise.get()),
                                                   0)) == "tls",
          "enterprise TLS");
    g_bytes_unref(ssid);
    return failures ? 1 : 0;
}
