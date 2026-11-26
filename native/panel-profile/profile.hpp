// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QByteArray>
#include <QString>
bool panelDefinesLayout(const QByteArray &data);
QByteArray applyPluginOverrides(const QByteArray &defaults, const QByteArray &overrides);
QByteArray buildPanelProfile(const QByteArray &stock, const QString &home, const QString &selection);
