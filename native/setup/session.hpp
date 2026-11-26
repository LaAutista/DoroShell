#pragma once
#include <QByteArray>
#include <QString>
// These transformations operate on the user's previous bytes. Only known
// default shortcuts or unassigned keys can be claimed on a fresh install.
QByteArray openboxBindings(const QByteArray &original, const QString &binary);
QByteArray lxqtBindings(const QByteArray &original, const QString &start,
                        const QString &capture);
