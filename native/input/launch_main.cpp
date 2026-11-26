// SPDX-License-Identifier: GPL-2.0-or-later
#include "launch.hpp"
#include <QCoreApplication>
#include <QFileInfo>

int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  auto bin = app.applicationDirPath();
  if (QFileInfo(bin).fileName() == "input" &&
      QFileInfo::exists(bin + "/../../CMakeCache.txt"))
    bin = QFileInfo(bin + "/../upstream/runtime/bin").absoluteFilePath();
  return input_launcher::launch(bin, app.arguments().mid(1), "/usr/bin");
}
