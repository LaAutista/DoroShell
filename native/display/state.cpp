// SPDX-License-Identifier: GPL-2.0-or-later
#include "state.hpp"

#include <QCryptographicHash>
#include <QMap>
#include <QRegularExpression>
#include <QStringList>

namespace display
{
namespace
{
QString digest(const QByteArray &bytes)
{
    return QString::fromLatin1(QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex());
}

QJsonObject hashes(const QMap<QString, QStringList> &groups)
{
    QJsonObject result;
    for (auto it = groups.begin(); it != groups.end(); ++it)
        result.insert(it.key(), digest(it.value().join('\n').toUtf8()));
    return result;
}

// Match the RC2 token encoding so a pending selection survives a helper upgrade.
QByteArray canonical(const QJsonValue &value)
{
    QByteArrayList items;
    if (value.isObject()) {
        const auto object = value.toObject();
        for (const auto &key : object.keys())
            items << canonical(key) + ": " + canonical(object.value(key));
        return '{' + items.join(", ") + '}';
    }
    if (value.isArray()) {
        for (const auto &item : value.toArray())
            items << canonical(item);
        return '[' + items.join(", ") + ']';
    }
    if (value.isNull())
        return "null";
    if (value.isDouble())
        return QByteArray::number(value.toInteger());
    if (value.isBool())
        return value.toBool() ? "true" : "false";
    QByteArray result = "\"";
    for (auto c : value.toString()) {
        switch (c.unicode()) {
        case '"':
            result += "\\\"";
            break;
        case '\\':
            result += "\\\\";
            break;
        case '\b':
            result += "\\b";
            break;
        case '\f':
            result += "\\f";
            break;
        case '\n':
            result += "\\n";
            break;
        case '\r':
            result += "\\r";
            break;
        case '\t':
            result += "\\t";
            break;
        default:
            if (c.unicode() < 32 || c.unicode() >= 127)
                result += "\\u" + QByteArray::number(c.unicode(), 16).rightJustified(4, '0');
            else
                result += c.toLatin1();
        }
    }
    return result + '"';
}

bool progressive(const QJsonObject &mode)
{
    const auto flags = mode["flags"].toString();
    return !flags.contains("Interlace") && !flags.contains("DoubleScan");
}
} // namespace

Error::Error(QString message, QString cause, QJsonArray diff)
    : std::runtime_error([&] {
          QStringList details;
          for (const auto &v : diff) {
              const auto d = v.toObject();
              details << QString("%1 (output %2)").arg(d["field"].toString()).arg(d["output"].toInt());
          }
          return (message + (details.isEmpty() ? "" : ": " + details.join(", "))).toStdString();
      }()),
      reason(std::move(cause)), changes(std::move(diff))
{
}

void Error::phase(const QString &name)
{
    if (!diagnostics.isEmpty())
        return;
    QJsonArray fields;
    for (const auto &v : changes) {
        auto key = v.toObject()["field"].toString();
        if (!fields.contains(key))
            fields.append(key);
        if (fields.size() == 6)
            break;
    }
    diagnostics.append(QJsonObject{{"phase", name}, {"reason", reason}, {"fields", fields}});
}

State parse(const QByteArray &text)
{
    using Rx = QRegularExpression;
    static const Rx framebuffer(R"(^Screen \d+:.* current (\d+) x (\d+),)");
    static const Rx heading(R"(^(\S+) (connected|disconnected|unknown connection)(.*)$)");
    static const Rx safeOutput(R"(^[A-Za-z0-9][A-Za-z0-9_.:-]*$)");
    static const Rx active(R"(\b\d+x\d+[+-]\d+[+-]\d+ \((0x[0-9a-f]+)\))");
    static const Rx crtc(R"(^\s+CRTC:\s+(\d+)$)");
    static const Rx entry(R"(^  (\S+) \((0x[0-9a-f]+)\) .*MHz(.*)$)");
    static const Rx horizontal(R"(h: width\s+(\d+))");
    static const Rx vertical(R"(v: height\s+(\d+).*clock\s+([\d.]+)Hz)");
    static const Rx stamp(R"(^\s*Timestamp:)");
    static const Rx modeID(R"( \(0x[0-9a-f]+\))");
    static const Rx physical(R"( ([1-9]\d*mm x [1-9]\d*mm)$)");
    static const Rx trailing(R"(\s+$)");
    static const QMap<QString, QString> categories{
        {"Gamma", "gamma"},         {"Brightness", "brightness"},  {"CRTC", "CRTC assignment"},
        {"Transform", "transform"}, {"Border", "border"},          {"_KDE_SCREEN_INDEX", "screen index"},
        {"CTM", "color transform"}, {"CscMatrix", "color matrix"}, {"h", "mode timings/flags"},
        {"v", "mode timings/flags"}};
    static const QStringList properties{"BorderDimensions", "link-status",   "Colorspace",     "Dithering",
                                        "dithering",        "DitheringMode", "DitheringDepth", "Broadcast RGB",
                                        "max bpc",          "non-desktop"};
    const auto input = QString::fromUtf8(text);
    const auto screen = framebuffer.match(input);
    if (!screen.hasMatch())
        throw Error("No X11 RandR screen found");

    QJsonArray outputs, modes;
    QJsonObject output, mode;
    auto finishMode = [&] {
        if (mode.isEmpty())
            return;
        if (!mode.contains("width") || !mode.contains("height") || !mode.contains("hz"))
            throw Error("Incomplete RandR mode timings");
        modes.append(mode);
        mode = {};
    };
    auto finishOutput = [&] {
        if (output.isEmpty())
            return;
        finishMode();
        bool currentFound = output["current"].isNull();
        for (const auto &m : modes)
            currentFound |= m.toObject()["id"] == output["current"];
        if (!currentFound)
            throw Error("Current RandR mode missing");
        output["modes"] = modes;
        outputs.append(output);
        modes = {};
        output = {};
    };
    QMap<QString, QStringList> fields, details;
    QStringList signature;
    QString category = "screen geometry", detail = category;
    auto lines = input.split('\n');
    if (!lines.isEmpty() && lines.last().isEmpty())
        lines.removeLast();
    for (QString line : lines) {
        if (line.endsWith('\r'))
            line.chop(1);
        auto head = heading.match(line), item = entry.match(line);
        if (head.hasMatch()) {
            finishOutput();
            auto name = head.captured(1);
            if (!safeOutput.match(name).hasMatch() || name.startsWith("XWAYLAND"))
                throw Error("Unsupported output name or Xwayland display");
            auto selected = active.match(head.captured(3));
            output = {{"name", name},
                      {"connection", head.captured(2)},
                      {"current", QJsonValue::Null},
                      {"crtc", QJsonValue::Null}};
            if (selected.hasMatch())
                output["current"] = selected.captured(1);
        }
        if (auto m = crtc.match(line); m.hasMatch() && !output.isEmpty())
            output["crtc"] = m.captured(1).toInt();
        if (item.hasMatch() && !output.isEmpty()) {
            finishMode();
            mode = {{"name", item.captured(1)},
                    {"id", item.captured(2)},
                    {"flags", item.captured(3).remove("*current").simplified()}};
        }
        if (!mode.isEmpty()) {
            if (auto m = horizontal.match(line); m.hasMatch())
                mode["width"] = m.captured(1).toInt();
            if (auto m = vertical.match(line); m.hasMatch()) {
                mode["height"] = m.captured(1).toInt();
                mode["hz"] = m.captured(2);
            }
        }
        if (stamp.match(line).hasMatch())
            continue;
        if (head.hasMatch()) {
            line.remove(modeID);
            if (auto m = physical.match(line); !output["current"].isNull() && m.hasMatch()) {
                output["reported_mm"] = m.captured(1);
                line.truncate(m.capturedStart());
            }
            detail = category = "connection/geometry/rotation";
        } else if (item.hasMatch())
            detail = category = "mode timings/flags";
        else if (line.contains(':')) {
            const auto label = line.trimmed().section(':', 0, 0);
            category = categories.value(label, "other protected properties");
            detail = properties.contains(label) ? label : category;
        }
        line.remove(" *current").remove(trailing);
        signature << line;
        const auto prefix = QString::number(output.isEmpty() ? -1 : outputs.size()) + ":";
        fields[prefix + category] << line;
        details[prefix + detail] << line;
    }
    finishOutput();
    return {{{"framebuffer", screen.captured(1) + "x" + screen.captured(2)},
             {"outputs", outputs},
             {"layout_fields", hashes(fields)},
             {"layout", digest(signature.join('\n').toUtf8())}},
            hashes(details)};
}

QString token(const State &state) { return digest(canonical(state.values)); }

int namedOutput(const QJsonArray &list, const QJsonValue &name)
{
    for (int i = 0; i < list.size(); ++i)
        if (list[i].toObject()["name"] == name)
            return i;
    return -1;
}

QJsonObject options(const State &state)
{
    QJsonArray allowed;
    const auto outputs = state.values["outputs"].toArray();
    for (const auto &v : outputs) {
        const auto o = v.toObject();
        const auto modes = o["modes"].toArray();
        QJsonObject current;
        for (const auto &m : modes)
            if (m.toObject()["id"] == o["current"]) {
                current = m.toObject();
                break;
            }
        if (current.isEmpty() || o["crtc"].isNull() || !progressive(current))
            continue;
        int shared = 0;
        for (const auto &s : outputs) {
            auto sibling = s.toObject();
            if (!sibling["current"].isNull() && sibling["crtc"] == o["crtc"])
                ++shared;
        }
        if (shared != 1)
            continue;
        QJsonArray rates;
        for (const auto &m : modes) {
            auto rate = m.toObject();
            if (rate["width"] == current["width"] && rate["height"] == current["height"] &&
                rate["hz"].toString().toDouble() > 0 && progressive(rate))
                rates.append(rate);
        }
        if (!rates.isEmpty())
            allowed.append(QJsonObject{{"name", o["name"]}, {"current", o["current"]}, {"modes", rates}});
    }
    return {{"token", token(state)},
            {"vsync", state.values["vsync"]},
            {"vsync_reason", state.values["vsync_reason"]},
            {"outputs", allowed}};
}

QJsonArray differences(const State &before, const State &after)
{
    QJsonArray changes;
    auto add = [&](int index, const QString &field) {
        if (changes.size() < 32)
            changes.append(QJsonObject{{"output", index}, {"field", field}});
    };
    if (before.values["framebuffer"] != after.values["framebuffer"])
        add(-1, "framebuffer geometry");
    auto a = before.values["outputs"].toArray(), b = after.values["outputs"].toArray();
    QStringList oldNames, newNames;
    for (int i = 0; i < a.size(); ++i) {
        auto x = a[i].toObject();
        oldNames << x["name"].toString();
        int other = namedOutput(b, x["name"]);
        if (other < 0) {
            add(i, "output disappeared");
            continue;
        }
        auto y = b[other].toObject();
        const std::pair<const char *, const char *> labels[] = {{"connection", "connection status changed"},
                                                                {"reported_mm", "connection/geometry/rotation"},
                                                                {"current", "current mode mismatch"},
                                                                {"crtc", "CRTC assignment"},
                                                                {"modes", "advertised mode timings/flags"}};
        for (auto [field, label] : labels)
            if (x.value(field) != y.value(field))
                add(i, label);
    }
    for (const auto &item : b)
        newNames << item.toObject()["name"].toString();
    if (std::any_of(newNames.begin(), newNames.end(), [&](const auto &n) { return !oldNames.contains(n); }))
        add(-1, "output added");
    if (oldNames != newNames)
        add(-1, "output enumeration changed");
    if (before.values["vsync"] != after.values["vsync"])
        add(-1, "NVIDIA OpenGL VSync");
    auto keys = before.fields.keys() + after.fields.keys();
    keys.removeDuplicates();
    keys.sort();
    for (const auto &key : keys)
        if (before.fields.value(key) != after.fields.value(key))
            add(key.section(':', 0, 0).toInt(), key.section(':', 1));
    if (before.values["layout"] != after.values["layout"] && before.fields == after.fields)
        add(-1, "protected layout fingerprint");
    return changes;
}
} // namespace display
