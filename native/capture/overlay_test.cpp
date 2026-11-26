// SPDX-License-Identifier: GPL-2.0-or-later
#include "overlay.hpp"
#include <QApplication>
#include <QComboBox>
#include <QTest>

int main(int argc, char **argv) {
    QApplication app(argc, argv);
    QImage frame(640, 480, QImage::Format_RGB32);
    frame.fill(Qt::white);
    Overlay overlay(frame, frame.rect(), {});
    auto *tool = overlay.findChild<QComboBox *>();
    if (!tool) return 1;
    tool->setCurrentText("Redact");
    auto before = overlay.resultImage();
    QTest::mousePress(&overlay, Qt::LeftButton, {}, QPoint(100, 150));
    QTest::mouseMove(&overlay, QPoint(190, 200));
    QTest::mouseRelease(&overlay, Qt::LeftButton, {}, QPoint(190, 200));
    auto after = overlay.resultImage();
    if (after.pixelColor(150, 175) != Qt::black || before.pixelColor(150, 175) != Qt::white) return 2;
    if (overlay.resultImage().cacheKey() != after.cacheKey()) return 3;
    QTest::keyClick(&overlay, Qt::Key_Z, Qt::ControlModifier);
    if (overlay.resultImage() != before) return 4;
    QTest::keyClick(&overlay, Qt::Key_Z, Qt::ControlModifier | Qt::ShiftModifier);
    if (overlay.resultImage() != after) return 5;
    return 0;
}
