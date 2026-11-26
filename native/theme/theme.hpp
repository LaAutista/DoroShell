#pragma once
#include <QtCore>
namespace theme {
[[noreturn]] void fail(const QString& reason);
struct Edit {
    QString path, kind, section, key;
    QJsonValue desired;
};
QStringList presets();
QList<Edit> edits(const QString& preset);
QJsonValue readValue(const Edit& edit, const QByteArray& bytes);
QByteArray setValue(const Edit& edit, const QByteArray& bytes, const QJsonValue& value);
QByteArray rc2Value(const Edit& edit, const QByteArray& bytes, const QJsonValue& value);
void generate(const QString& preset, const QString& destination);
QJsonObject status(const QString& home);
QStringList change(const QString& home, const QString& preset, bool preview, bool restore);
} // namespace theme
