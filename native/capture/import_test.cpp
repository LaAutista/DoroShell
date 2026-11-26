// SPDX-License-Identifier: GPL-2.0-or-later
#include "import.hpp"
#include "../testing/private_x11.hpp"
#include <QCoreApplication>
#include <QFile>
#include <QThread>
#include <cstdio>

QImage pattern() {
    QImage image(11, 8, QImage::Format_ARGB32);
    for (int y = 0; y < image.height(); ++y)
        for (int x = 0; x < image.width(); ++x)
            image.setPixel(x, y, qRgba(x * 17, y * 29, x + y, 128));
    return image;
}

int main(int argc, char **argv) {
    QCoreApplication app(argc, argv);
    const auto args = app.arguments();
    if (args.size() == 3 && args[1] == "--worker") {
        if (qgetenv("DISPLAY").isEmpty() || qgetenv("DISPLAY") != qgetenv("DOROSHELL_TEST_DISPLAY")) return 1;
        return importScreenshot(pattern(), args[2]) ? 0 : 1;
    }
    if (args.size() == 3) {
        doro_test::isolated(args[1], {args[2]}, "800x600x24");
        return 0;
    }
    if (app.arguments().contains("--import-png")) {
        QFile input;
        if (!input.open(stdin, QIODevice::ReadOnly) ||
            QImage::fromData(input.readAll(), "PNG").convertToFormat(QImage::Format_ARGB32) != pattern())
            return 1;
        if (qEnvironmentVariable("DORO_IMPORT_TEST") == "silent")
            QThread::sleep(10);
        std::puts(qEnvironmentVariable("DORO_IMPORT_TEST") == "reject" ? "REJECT" : "IMPORTED");
        return 0;
    }
    auto editor = app.applicationFilePath();
    qputenv("DORO_IMPORT_TEST", "accept");
    if (!importScreenshot(pattern(), editor)) return 1;
    qputenv("DORO_IMPORT_TEST", "reject");
    if (importScreenshot(pattern(), editor)) return 1;
    qputenv("DORO_IMPORT_TEST", "silent");
    if (importScreenshot(pattern(), editor, 100)) return 1;
    return importScreenshot(pattern(), editor + ".absent") ? 1 : 0;
}
