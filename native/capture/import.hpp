// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QImage>

// Success means ScreenGrab decoded the image and created its editor.
bool importScreenshot(const QImage &image, const QString &editor, int timeoutMs = 8000);
