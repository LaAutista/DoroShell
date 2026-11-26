#pragma once
#include <QJsonArray>
#include <QMenu>
#include <functional>
QJsonArray readDocuments();
QJsonArray parseDocuments(const QByteArray &xml);
QJsonArray listFolder(const QString &path);
void browseWorker(QMenu *menu, QStringList arguments,
                  std::function<void(QJsonArray)> finished);
