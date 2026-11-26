// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include "../theme/theme.hpp"
namespace modules {
const QString dir = ".local/state/doroshell-native/modules/";
const QString privatePanel = ".config/doroshell/panel.conf",
              stockPanel = ".config/lxqt/panel.conf",
              shortcuts = ".config/lxqt/globalkeyshortcuts.conf",
              openbox = ".config/openbox/rc.xml",
              glass = ".config/doroshell/wallpaper-glass.json";
QStringList names();
QStringList paths(const QString &module);
QList<theme::Edit> edits(const QString &home, const QString &module,
                         const QJsonObject &options,
                         const QMap<QString, QByteArray> &files);
QJsonValue value(const theme::Edit &e, const QByteArray &source);
QByteArray set(const theme::Edit &e, const QByteArray &source,
               const QJsonValue &v);
QString taskPanel(const QByteArray &data);
} // namespace modules
