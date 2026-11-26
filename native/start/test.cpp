#include "browse.hpp"
#include "model.hpp"
#include "preferences.hpp"
#include <QApplication>
#include <QDateTime>
#include <QDialogButtonBox>
#include <QDir>
#include <QFile>
#include <QJsonArray>
#include <QPushButton>
#include <QTableWidget>
#include <QTemporaryDir>
#include <QTimer>
#include <iostream>
#include <stdexcept>

namespace {
void check(bool ok, const char *message) {
  if (!ok)
    throw std::runtime_error(message);
}
void write(const QString &path, const QByteArray &data) {
  QFile f(path);
  check(f.open(QIODevice::WriteOnly | QIODevice::Truncate) &&
            f.write(data) == data.size(),
        "fixture write");
}
} // namespace
int main(int argc, char **argv) {
  QTemporaryDir temp;
  if (!temp.isValid())
    return 1;
  qputenv("HOME", temp.path().toUtf8());
  qputenv("XDG_CONFIG_HOME", (temp.path() + "/config").toUtf8());
  qputenv("XDG_DATA_HOME", (temp.path() + "/data").toUtf8());
  qputenv("XDG_DATA_DIRS", (temp.path() + "/system").toUtf8());
  qputenv("QT_QPA_PLATFORM", "offscreen");
  QApplication app(argc, argv);
  try {
    auto dir = temp.path() + "/data/applications";
    check(QDir().mkpath(dir), "mkdir");
    auto desktop =
        QByteArray("[Desktop Entry]\nType=Application\nName=Café "
                   "Editor\nExec=/usr/bin/"
                   "true\nStartupWMClass=FixtureWM\nKeywords=words;script;\n");
    write(dir + "/fixture.desktop", desktop);
    write(dir + "/hidden.desktop", desktop + "NoDisplay=true\n");
    auto apps = loadCatalog();
    check(apps.size() == 1, "catalog visibility");
    check(searchApps(apps, "CAFE scr") == QStringList{"fixture.desktop"},
          "ranked keyword search");
    check(identifyApp(apps, {}, {"fixturewm"}) == "fixture.desktop",
          "focus identity");
    check(identifyApp(apps, {dir + "/fixture.desktop"}, {}) ==
              "fixture.desktop",
          "absolute desktop identity");
    auto docs = parseDocuments(
        R"(<xbel xmlns:b="http://www.freedesktop.org/standards/desktop-bookmarks"><bookmark href="file:///tmp/hidden"/><bookmark href="file:///tmp/hidden"><b:private/></bookmark><bookmark href="https://example.org/x"/><bookmark href="file:///tmp/../bad"/><bookmark href="file:///tmp/sample%20file"/></xbel>)");
    check(docs.size() == 1 && docs.first().toObject()["name"] == "sample file",
          "private duplicates and nonlocal documents excluded");
    bool dtd = false;
    try {
      parseDocuments("<!DOCTYPE xbel><xbel/>");
    } catch (...) {
      dtd = true;
    }
    check(dtd, "doctype refused");
    QTimer::singleShot(0, [] {
      auto *d = QApplication::activeModalWidget();
      auto *table = d->findChild<QTableWidget *>();
      table->item(0, 0)->setText("My home");
      d->findChild<QDialogButtonBox *>()
          ->button(QDialogButtonBox::Save)
          ->click();
    });
    editFolderPreferences(nullptr);
    auto folders =
        readPreference("folders.json", {}).value.object()["folders"].toArray();
    check(folders.size() == 6 &&
              folders.first().toObject()["label"] == "My home" &&
              !folders.first().toObject().contains("type"),
          "folder editing preserves valid RC2 links");
    auto duplicate = apps.first();
    duplicate.id = "other.desktop";
    apps << duplicate;
    check(identifyApp(apps, {}, {"fixturewm"}).isEmpty(),
          "ambiguous windows excluded");
    auto pins = readPins(apps);
    pins.save(QJsonDocument(QJsonArray{"fixture.desktop"}), true);
    check(readPins(apps).value.array().first() == "fixture.desktop",
          "pins persisted");
    write(configPath("favorites.json"), "[ \"owner.desktop\" ]");
    bool conflict = false;
    try {
      pins.save(QJsonDocument(QJsonArray{"lost"}), true);
    } catch (const std::exception &) {
      conflict = true;
    }
    check(conflict, "never overwrite changed pin file");
    updateHistory("one.desktop");
    updateHistory("two.desktop");
    updateHistory("one.desktop");
    auto history = readRecent();
    check(recentItems(history.value.object(), 0) ==
              QStringList{"one.desktop", "two.desktop"},
          "recency");
    updateHistory({}, {}, false, 1, 1);
    check(readRecent().value.object()["items"].toArray().isEmpty(),
          "no invented times");
    updateHistory("timed.desktop");
    check(recentItems(readRecent().value.object(),
                      QDateTime::currentSecsSinceEpoch() + 86401)
              .isEmpty(),
          "retention");
    updateHistory({}, false);
    updateHistory("private.desktop");
    check(readRecent().value.object()["items"].toArray().isEmpty(),
          "disabled history");
    write(configPath("recent.json"),
          R"({"enabled":false,"enabled":true,"items":[]})");
    check(!readRecent().error.isEmpty(), "ambiguous recording setting refused");
    QFile::remove(configPath("recent.json"));
    check(QFile::link(configPath("favorites.json"), configPath("recent.json")),
          "symlink setup");
    check(!readRecent().error.isEmpty(), "reject symlink");
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
  return 0;
}
