#pragma once
#include <QIcon>
#include <QJsonDocument>
#include <QJsonObject>
#include <QStringList>
#include <gio/gdesktopappinfo.h>
#include <memory>
#include <optional>

struct Entry {
  std::shared_ptr<GDesktopAppInfo> app;
  QString id, name, filename, executable, wmClass, description;
  QStringList categories;
  QStringList fields;
  QList<QStringList> tokens;
  QIcon icon;
};
using Catalog = QList<Entry>;
Catalog loadCatalog();
QStringList searchApps(const Catalog &apps, const QString &query);
QStringList defaultPins(const Catalog &apps);
QString identifyApp(const Catalog &apps, const QStringList &names,
                    const QStringList &classes);
QString configPath(const QString &name);
struct Preference {
  QString path;
  QByteArray original;
  QJsonDocument value;
  bool exists = false;
  QString error;
  void save(const QJsonDocument &next, bool backup);
};
Preference readPreference(const QString &name, QJsonDocument initial);
Preference readPins(const Catalog &apps);
Preference readRecent();
QStringList recentItems(const QJsonObject &history, qint64 now);
void updateHistory(const QString &id, std::optional<bool> enabled = {},
                   bool clear = false, std::optional<int> limit = {},
                   std::optional<int> days = {});
