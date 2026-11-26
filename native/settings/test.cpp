#include "hub.hpp"
#include <QtWidgets>
#include <cstdio>
#include <iostream>
#include <stdexcept>

namespace {
void check(bool ok, const char *reason) {
  if (!ok)
    throw std::runtime_error(reason);
}
void write(QString path, QByteArray bytes) {
  QFile f(path);
  check(f.open(QIODevice::WriteOnly | QIODevice::Truncate) &&
            f.write(bytes) == bytes.size(),
        "write fixture");
}
QByteArray bytes(QString path) {
  QFile f(path);
  if (!f.open(QIODevice::ReadOnly))
    return {};
  return f.readAll();
}
void await(const std::function<bool()> &done, const char *reason) {
  QElapsedTimer time;
  time.start();
  while (time.elapsed() < 5000) {
    QApplication::processEvents();
    if (done())
      return;
    QThread::msleep(5);
  }
  throw std::runtime_error(reason);
}
QPushButton *button(QWidget *w, const QString &label) {
  for (auto *b : w->findChildren<QPushButton *>())
    if (b->text() == label)
      return b;
  throw std::runtime_error(("Missing control: " + label).toStdString());
}
} // namespace
int main(int argc, char **argv) {
  QString executable = QFileInfo(QFile::decodeName(argv[0])).fileName();
  if (executable.startsWith("doroshell-") ||
      executable == "lxqt-config-input" || executable == "pcmanfm-qt" ||
      executable == "choose-defaults") {
    QCoreApplication app(argc, argv);
    auto dest = qEnvironmentVariable("DOROSHELL_FIXTURE_LOG");
    if (dest.isEmpty())
      return 2;
    auto args = app.arguments().mid(1);
    write(dest + "/" + executable, args.join("|").toUtf8() + "\n");
    if (args == QStringList{"--status"})
      puts("{\"preset\":\"heretic\",\"managed\":true}");
    else
      puts("Fixture finished");
    return 0;
  }
  QTemporaryDir temp;
  if (!temp.isValid())
    return 1;
  qputenv("DOROSHELL_FIXTURE_LOG", temp.path().toUtf8());
  qputenv("HOME", temp.path().toUtf8());
  qputenv("QT_QPA_PLATFORM", "offscreen");
  qputenv("XDG_DATA_HOME", (temp.path() + "/share").toUtf8());
  qputenv("XDG_DATA_DIRS", (temp.path() + "/empty").toUtf8());
  qputenv("DBUS_SESSION_BUS_ADDRESS",
          ("unix:path=" + temp.path() + "/absent").toUtf8());
  qputenv("XDG_CONFIG_HOME", (temp.path() + "/config").toUtf8());
  QApplication app(argc, argv);
  try {
    auto bin = temp.path() + "/bin";
    check(QDir().mkpath(bin), "mkdir bin");
    for (auto name : {"doroshell-start", "doroshell-theme", "doroshell-cursor",
                      "doroshell-portable", "doroshell-input-overrides",
                      "doroshell-config-input", "pcmanfm-qt", "choose-defaults"})
      check(QFile::link(QCoreApplication::applicationFilePath(),
                        bin + "/" + name),
            "fixture binary");
    auto dir = temp.path() + "/share/applications";
    check(QDir().mkpath(dir), "applications directory");
    write(dir + "/lxqt-config-file-associations.desktop",
          "[Desktop Entry]\nType=Application\nName=Choose defaults\nExec=\"" +
              QFile::encodeName(bin + "/choose-defaults") + "\" --defaults\n");
    SettingsHub hub(bin);
    hub.show();
    auto *tabs = hub.findChild<QTabWidget *>();
    button(&hub, "Edit folder links…")->click();
    await(
        [&] {
          return bytes(temp.path() + "/doroshell-start") == "--settings\n";
        },
        "start preferences action");
    button(&hub, "Portable Start preferences…")->click();
    await([&] { return bytes(temp.path() + "/doroshell-portable") == "\n"; },
          "portable settings action");
    tabs->setCurrentIndex(1);
    button(&hub, "Advanced display controls…")->click();
    await(
        [&] {
          return bytes(temp.path() + "/pcmanfm-qt") ==
                 "--profile|lxqt|--desktop-pref=advanced\n";
        },
        "advanced preferences action");
    tabs->setCurrentIndex(2);
    button(&hub, "Mouse and Touchpad settings…")->click();
    await([&] { return bytes(temp.path() + "/doroshell-config-input") == "\n"; },
          "native input action");
    tabs->setCurrentIndex(3);
    check(!button(&hub, "Wi-Fi && Network…")->isEnabled(),
          "missing native component disabled");
    button(&hub, "Choose default applications…")->click();
    await(
        [&] {
          return bytes(temp.path() + "/choose-defaults") == "--defaults\n";
        },
        "GIO default application selector action");
    tabs->setCurrentIndex(4);
    auto *preset = hub.findChild<QComboBox *>("themePreset");
    auto *log = hub.findChild<QPlainTextEdit *>("themeStatus");
    await(
        [&] {
          return preset->isEnabled() && preset->currentData() == "heretic";
        },
        "theme status selected actual preset");
    preset->setCurrentIndex(preset->findData("polar"));
    for (auto pair : {std::pair{"planTheme", "--plan|polar\n"},
                      {"applyTheme", "--apply|polar\n"},
                      {"restoreTheme", "--restore\n"}}) {
      auto *action = hub.findChild<QPushButton *>(pair.first);
      check(action, "theme action exists");
      action->click();
      check(!hub.close(), "operation runs to completion before closing");
      await(
          [&] {
            return action->isEnabled() &&
                   bytes(temp.path() + "/doroshell-theme") == pair.second &&
                   log->toPlainText() == "Fixture finished";
          },
          "theme action");
    }
    tabs->setCurrentIndex(5);
    auto *source = hub.findChild<QComboBox *>("cursorSource");
    source->setCurrentIndex(source->findData("gif"));
    hub.findChild<QCheckBox *>("pinkPointer")->setChecked(true);
    for (auto pair :
         {std::pair{"planCursor", "--plan|--asset|gif|--pink-pointer\n"},
          {"applyCursor", "--apply|--asset|gif|--pink-pointer\n"},
          {"rollbackCursor", "--rollback\n"}}) {
      auto *action = hub.findChild<QPushButton *>(pair.first);
      action->click();
      await(
          [&] {
            return action->isEnabled() &&
                   bytes(temp.path() + "/doroshell-cursor") == pair.second;
          },
          "cursor settings action");
    }
    check(hub.close(), "finished hub closes");
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
  return 0;
}
