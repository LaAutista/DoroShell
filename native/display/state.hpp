// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QJsonArray>
#include <QJsonObject>
#include <stdexcept>

namespace display
{
struct State {
    QJsonObject values;
    QJsonObject fields;
    bool operator==(const State &other) const { return values == other.values; }
};

struct Error : std::runtime_error {
    QString reason;
    QJsonArray changes;
    QJsonArray diagnostics;
    explicit Error(QString message, QString reason = "operation_failed", QJsonArray changes = {});
    void phase(const QString &name);
};

State parse(const QByteArray &randr);
QString token(const State &state);
QJsonObject options(const State &state);
QJsonArray differences(const State &before, const State &after);
int namedOutput(const QJsonArray &list, const QJsonValue &name);
} // namespace display
