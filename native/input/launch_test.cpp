// SPDX-License-Identifier: GPL-2.0-or-later
#include "launch.hpp"
#include <QApplication>
#include <QDeadlineTimer>
#include <QDir>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QProcess>
#include <QTemporaryDir>
#include <QTextStream>
#include <QThread>
#include <stdexcept>

namespace {
void expect(bool value, const char *reason) {
  if (!value)
    throw std::runtime_error(reason);
}
void record(const QString &name, const QStringList &args) {
  QFile f(qEnvironmentVariable("DOROSHELL_LAUNCH_LOG") + '/' + name);
  const auto json = QJsonDocument(QJsonArray::fromStringList(args))
                        .toJson(QJsonDocument::Compact);
  expect(f.open(QIODevice::WriteOnly) && f.write(json) == json.size(),
         "Could not log fixture argv");
}
QStringList readArgs(const QString &name) {
  QFile f(qEnvironmentVariable("DOROSHELL_LAUNCH_LOG") + '/' + name);
  if (!f.open(QIODevice::ReadOnly))
    return {};
  QStringList args;
  for (const auto &arg : QJsonDocument::fromJson(f.readAll()).array())
    args << arg.toString();
  return args;
}
} // namespace
int main(int argc, char **argv) {
  try {
    auto name = QFileInfo(QFile::decodeName(argv[0]));
    if (name.fileName() == "lxqt-config-input" &&
        !qEnvironmentVariableIsEmpty("DOROSHELL_TEST_QT_GUI")) {
      QApplication attempt(argc, argv);
      return 0;
    }
    QCoreApplication app(argc, argv);
    auto args = app.arguments().mid(1);
    if (name.fileName() == "doroshell-maintenance" ||
        name.fileName() == "lxqt-config-input") {
      record(name.fileName() == "doroshell-maintenance" ? "repair"
                                                        : name.dir().dirName(),
             args);
      return 0;
    }
    expect(args.size() == 1, "Expected launcher binary");
    QTemporaryDir root;
    expect(root.isValid(), "Temporary directory failed");
    auto bin = root.filePath("private"), stock = root.filePath("stock");
    expect(QDir().mkpath(bin) && QDir().mkpath(stock),
           "Cannot create test directories");
    auto target = bin + "/lxqt-config-input";
    auto runner = bin + "/doroshell-config-input";
    auto self = app.applicationFilePath();
    expect(QFile::copy(args[0], runner) && QFile::copy(self, target) &&
               QFile::copy(self, stock + "/lxqt-config-input") &&
               QFile::copy(self, bin + "/doroshell-maintenance"),
           "Cannot stage fixtures");
    qputenv("HOME", root.path().toUtf8());
    qputenv("DOROSHELL_LAUNCH_LOG", root.filePath("logs").toUtf8());
    expect(QDir().mkpath(root.filePath("logs")), "Cannot create log directory");
    qunsetenv("DISPLAY");
    qunsetenv("WAYLAND_DISPLAY");
    qunsetenv("QT_QPA_PLATFORM");
    expect(QProcess::execute(runner, {}) == 1 &&
               !QFileInfo::exists(root.filePath("logs/repair")),
           "Headless startup was not refused");
    const QStringList requested{"--demo", "path with spaces", "$(false)"};
    qputenv("QT_QPA_PLATFORM", "offscreen");
    expect(QProcess::execute(runner, requested) == 0 &&
               readArgs("private") == requested,
           "Healthy private dialog lost arguments");
    qputenv("QT_QPA_PLATFORM", "doroshell-unavailable-platform");
    qputenv("DOROSHELL_TEST_QT_GUI", "yes");
    expect(QProcess::execute(runner, {}) == 1 &&
               !QFileInfo::exists(root.filePath("logs/repair")),
           "Unavailable platform plugin caused a rebuild or launcher crash");
    qunsetenv("DOROSHELL_TEST_QT_GUI");
    qputenv("QT_QPA_PLATFORM", "offscreen");
    // Reproduce an upgrade that removed a previously linked Qt soname.
    QFile image(target);
    expect(image.open(QIODevice::ReadWrite), "Cannot open dependency fixture");
    auto elf = image.readAll();
    expect(elf.contains("libQt6Core.so.6"), "Qt soname not found in fixture");
    elf.replace("libQt6Core.so.6", "libBadCore.so.6");
    expect(image.seek(0) && image.write(elf) == elf.size(),
           "Cannot prepare missing dependency");
    image.close();
    expect(input_launcher::launch(bin, requested, stock) == 0 &&
               readArgs("stock") == requested,
           "Stock fallback did not receive the exact arguments");
    QDeadlineTimer deadline(3000);
    while (readArgs("repair").isEmpty() && !deadline.hasExpired())
      QThread::msleep(10);
    expect(readArgs("repair") ==
               QStringList{"repair", "--kind", "input", "--current", target},
           "Wrong native repair target");
    return 0;
  } catch (const std::exception &e) {
    QTextStream(stderr) << e.what() << Qt::endl;
    return 1;
  }
}
