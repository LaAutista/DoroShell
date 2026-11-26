// SPDX-License-Identifier: GPL-2.0-or-later
// Single package inventory for the native build: doroshell-check and doroshell-setup --packages read this.
#pragma once
#include <string_view>

namespace doro::packages
{
enum class Group { Build, Desktop, WindowManager, Archive, Network };
struct Package {
    std::string_view name;
    Group group;
};
inline constexpr Package all[] = {
    {"base-devel", Group::Build},
    {"git", Group::Build},
    {"cmake", Group::Build},
    {"ninja", Group::Build},
    {"pkgconf", Group::Build},
    {"qt6-tools", Group::Build},
    {"qt6-base", Group::Desktop},
    {"qt6-svg", Group::Desktop},
    {"qt6-multimedia", Group::Desktop},
    {"qt6-multimedia-ffmpeg", Group::Desktop},
    {"liblxqt", Group::Desktop},
    {"libqtxdg", Group::Desktop},
    {"kwindowsystem", Group::Desktop},
    {"layer-shell-qt", Group::Desktop},
    {"libdbusmenu-lxqt", Group::Desktop},
    {"solid", Group::Desktop},
    {"libsysstat", Group::Desktop},
    {"libstatgrab", Group::Desktop},
    {"libxdamage", Group::Desktop},
    {"libxkbcommon-x11", Group::Desktop},
    {"libpulse", Group::Desktop},
    {"alsa-lib", Group::Desktop},
    {"lm_sensors", Group::Desktop},
    {"libxtst", Group::Desktop},
    {"libxi", Group::Desktop},
    {"libxcursor", Group::Desktop},
    {"libxcb", Group::Desktop},
    {"xcb-util-keysyms", Group::Desktop},
    {"libxss", Group::Desktop},
    {"expat", Group::Desktop},
    {"zlib", Group::Desktop},
    {"jansson", Group::Desktop},
    {"lxqt-qtplugin", Group::Desktop},
    {"lxqt-panel", Group::Desktop},
    {"lxqt-session", Group::Desktop},
    {"lxqt-globalkeys", Group::Desktop},
    {"lxqt-config", Group::Desktop},
    {"lxqt-menu-data", Group::Desktop},
    {"lxqt-policykit", Group::Desktop},
    {"xorg-xprop", Group::Desktop},
    {"xorg-xrandr", Group::Desktop},
    {"xf86-input-libinput", Group::Desktop},
    {"pcmanfm-qt", Group::Desktop},
    {"libfm-qt", Group::Desktop},
    {"breeze-cursors", Group::Desktop},
    {"breeze-icons", Group::Desktop},
    {"xdg-user-dirs", Group::Desktop},
    {"openbox", Group::WindowManager},
    {"dolphin", Group::Archive},
    {"ark", Group::Archive},
    {"networkmanager", Group::Network},
    {"libnm", Group::Network},
    {"libnma", Group::Network},
    {"gtk3", Group::Network},
    {"nm-connection-editor", Group::Network},
    {"network-manager-applet", Group::Network},
    {"dnsmasq", Group::Network},
    {"nftables", Group::Network},
};
} // namespace doro::packages
