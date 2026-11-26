// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QStringList>

namespace input_launcher {
// The stock directory is injectable for isolated tests. Production uses
// /usr/bin.
int launch(const QString &bundle, const QStringList &arguments,
           const QString &stockDirectory);
} // namespace input_launcher
