#include "portable.hpp"
namespace portable {
void fail(const QString& msg) { throw std::runtime_error(msg.toStdString()); }
void Json::set(const char* key, const Json& v) const {
    if (json_object_set(ptr(), key, v.ptr()))
        fail("Invalid settings object.");
}
void Json::add(const Json& v) const {
    if (json_array_append(ptr(), v.ptr()))
        fail("Invalid settings array.");
}
QList<Json> Json::list() const {
    QList<Json> list;
    for (size_t i = 0; i < json_array_size(ptr()); ++i)
        list << Json(json_incref(json_array_get(ptr(), i)));
    return list;
}
QStringList Json::keys() const {
    QStringList keys;
    for (void* i = json_object_iter(ptr()); i; i = json_object_iter_next(ptr(), i))
        keys << QString::fromUtf8(json_object_iter_key(i));
    keys.sort();
    return keys;
}
Json decode(const QByteArray& raw, qsizetype cap) {
    if (raw.size() > cap)
        fail("Settings file is too large.");
    json_error_t error{};
    Json result(json_loadb(raw.constData(), raw.size(), JSON_REJECT_DUPLICATES | JSON_ALLOW_NUL, &error));
    if (!result.object())
        fail(QString("Invalid settings file at line %1: %2").arg(error.line).arg(error.text));
    return result;
}
QByteArray encode(const Json& v) {
    auto data = json_dumps(v.ptr(), JSON_ENSURE_ASCII | JSON_INDENT(2));
    if (!data)
        fail("Could not encode settings.");
    QByteArray result(data);
    free(data);
    return result + '\n';
}
namespace {
const QStringList actions{"shutdown", "reboot", "logout", "suspend", "hibernate", "lockscreen"};
struct Folder {
    const char* label;
    const char* id;
    const char* icon;
};
const QList<Folder> folders{{"Home", "HomeLocation", "user-home"},
                            {"Documents", "DocumentsLocation", "folder-documents"},
                            {"Downloads", "DownloadLocation", "folder-download"},
                            {"Pictures", "PicturesLocation", "folder-pictures"},
                            {"Music", "MusicLocation", "folder-music"},
                            {"Videos", "MoviesLocation", "folder-videos"}};
bool known(const QString& id) {
    return std::any_of(folders.begin(), folders.end(), [&](auto f) { return id == f.id; });
}
bool keys(const Json& o, QStringList wanted) {
    wanted.sort();
    return o.object() && o.keys() == wanted;
}
bool integer(const Json& v, qint64 lo, qint64 hi) {
    return json_is_integer(v.ptr()) && v.integer() >= lo && v.integer() <= hi;
}
Json sep() {
    auto o = object();
    o.set("type", str("separator"));
    return o;
}
Json choice(const QString& key, bool visible) {
    auto o = object();
    o.set("standard", str(key));
    o.set("visible", flag(visible));
    return o;
}
Json link(const Folder& f, bool visible) {
    auto o = choice(f.id, visible);
    o.set("label", str(f.label));
    o.set("icon", str(f.icon));
    return o;
}
void validateFolders(const Json& v) {
    if (!integer(v.get("version"), 1, 2) || !v.get("folders").array() ||
        v.get("folders").list().size() > 100)
        fail("Invalid local folders.");
    QSet<QString> seen;
    for (const auto& item : v.get("folders").list()) {
        if (item.has("type")) {
            if (v.get("version").integer() != 2 || item != sep())
                fail("Invalid local separator.");
            continue;
        }
        auto label = item.get("label").str();
        if (!item.object() || label.trimmed().isEmpty() || label.toUcs4().size() > 100 ||
            !item.get("visible").boolean() || (item.has("icon") && !item.get("icon").string()))
            fail("Invalid local folder link.");
        if (item.has("standard")) {
            auto key = item.get("standard").str();
            if (!known(key) || seen.contains(key) || item.has("path"))
                fail("Invalid or duplicate standard folder; resolve duplicates in Start.");
            seen.insert(key);
        } else {
            auto path = item.get("path").str();
            if (!path.startsWith('/') || path.contains(QChar::Null))
                fail("Invalid custom folder path.");
        }
    }
    if (v.has("hiddenSystemLinks")) {
        if (!v.get("hiddenSystemLinks").array())
            fail("Invalid hidden links.");
        for (auto entry : v.get("hiddenSystemLinks").list())
            if (!entry.string())
                fail("Invalid hidden link.");
    }
    auto portrait = v.get("portrait");
    if (portrait.ptr() &&
        (!portrait.string() || (!portrait.str().isEmpty() && !QDir::isAbsolutePath(portrait.str()))))
        fail("Invalid portrait.");
    auto crop = v.get("portraitCrop");
    if (crop.ptr() && !json_is_null(crop.ptr())) {
        if (!keys(crop, {"x", "y", "zoom"}))
            fail("Invalid portrait crop.");
        for (auto k : {"x", "y", "zoom"}) {
            auto n = crop.get(k);
            auto val = json_number_value(n.ptr());
            bool zoom = QByteArray(k) == "zoom";
            if (!json_is_number(n.ptr()) || val < (zoom ? 1 : 0) || val > (zoom ? 4 : 1))
                fail("Invalid portrait crop.");
        }
    }
}
void recent(const Json& v, bool portable) {
    if (!v.get("enabled").boolean() || ((portable || v.has("limit")) && !integer(v.get("limit"), 1, 50)) ||
        (v.has("retention_days") && !integer(v.get("retention_days"), 0, 365)))
        fail("Invalid recent-program preferences.");
    if (portable) {
        if (!keys(v, {"enabled", "limit"}) && !keys(v, {"enabled", "limit", "retention_days"}))
            fail("Unexpected recent-program fields.");
        return;
    }
    if ((v.has("version") && !integer(v.get("version"), 1, 1)) || !v.get("items").array() ||
        v.get("items").list().size() > (v.has("limit") ? v.get("limit").integer() : 20))
        fail("Invalid local recent history.");
    for (auto item : v.get("items").list())
        if (item.str().isEmpty() || item.str().toUcs4().size() > 4096)
            fail("Invalid history entry.");
    if (v.has("launched_at")) {
        auto stamps = v.get("launched_at");
        if (!stamps.object() || stamps.keys().size() > 50)
            fail("Invalid launch timestamps.");
        for (const auto& key : stamps.keys())
            if (key.isEmpty() || key.toUcs4().size() > 4096 ||
                !integer(stamps.get(key.toUtf8().constData()), 0, 253402300799))
                fail("Invalid launch timestamp.");
    }
}
} // namespace
void validateLocal(const QString& name, const Json& v) {
    if (!v.object())
        fail("Invalid local settings.");
    if (name == files[0]) {
        if (!integer(v.get("version"), 1, 1) || !actions.contains(v.get("action").str()))
            fail("Invalid local session button.");
    } else if (name == files[1])
        recent(v, false);
    else if (name == files[2])
        validateFolders(v);
    else
        fail("Invalid local settings file.");
}
void validatePortable(const Json& v) {
    if (!keys(v, {"format", "version", "preferences"}) ||
        v.get("format").str() != "DoroShell portable Start settings" || !integer(v.get("version"), 1, 2))
        fail("Unsupported portable settings format.");
    auto p = v.get("preferences");
    if (!keys(p, {"primary", "recent", "folders"}) || !actions.contains(p.get("primary").str()))
        fail("Invalid portable preferences.");
    recent(p.get("recent"), true);
    auto items = p.get("folders");
    auto list = items.list();
    bool v2 = v.get("version").integer() == 2;
    if (!items.array() || list.size() > 106 || (!v2 && list.size() != 6))
        fail("Invalid standard folders.");
    QSet<QString> seen;
    for (const auto& item : list) {
        if (v2 && item == sep())
            continue;
        auto id = item.get("standard").str();
        if (!keys(item, {"standard", "visible"}) || !known(id) || !item.get("visible").boolean() ||
            seen.contains(id))
            fail("Invalid portable folder.");
        seen.insert(id);
    }
    if (seen.size() != folders.size())
        fail("Missing standard folders.");
}
Json exportValues(const Values& values) {
    auto p = object(), v = object(), r = object(), list = array();
    QSet<QString> seen;
    auto local = values.value(files[2]);
    for (const auto& item : local.get("folders").list()) {
        if (item == sep())
            list.add(sep());
        else if (item.has("standard")) {
            auto id = item.get("standard").str();
            list.add(choice(id, item.get("visible").flag()));
            seen.insert(id);
        }
    }
    for (const auto& f : folders)
        if (!seen.contains(f.id))
            list.add(choice(f.id, !values.contains(files[2])));
    auto history = values.value(files[1]);
    r.set("enabled", history.has("enabled") ? history.get("enabled") : flag(true));
    r.set("limit", history.has("limit") ? history.get("limit") : number(20));
    if (history.has("retention_days"))
        r.set("retention_days", history.get("retention_days"));
    auto button = values.value(files[0]);
    p.set("primary", button.has("action") ? button.get("action") : str("shutdown"));
    p.set("recent", r);
    p.set("folders", list);
    v.set("format", str("DoroShell portable Start settings"));
    v.set("version", number(2));
    v.set("preferences", p);
    validatePortable(v);
    return v;
}
Values importValues(const Values& local, const Json& portable) {
    validatePortable(portable);
    Values after;
    for (const auto& name : files)
        after[name] = local.contains(name) ? Json(json_deep_copy(local[name].ptr())) : object();
    auto p = portable.get("preferences");
    auto button = after[files[0]], history = after[files[1]], folder = after[files[2]], r = p.get("recent");
    button.set("version", number(1));
    button.set("action", p.get("primary"));
    if (history.get("items").list().size() > r.get("limit").integer())
        fail("Choose a count at least as large as the existing history, or clear it in Start.");
    for (auto key : {"enabled", "limit", "retention_days"})
        if (r.has(key))
            history.set(key, r.get(key));
    if (!history.has("items"))
        history.set("items", array());
    auto links = folder.get("folders");
    if (!links.ptr()) {
        links = array();
        for (const auto& f : folders)
            links.add(link(f, true));
    }
    QMap<QString, Json> standards;
    for (auto item : links.list())
        if (item.has("standard"))
            standards[item.get("standard").str()] = item;
    QList<Json> replacements;
    for (auto item : p.get("folders").list()) {
        if (item == sep()) {
            replacements << sep();
            continue;
        }
        auto id = item.get("standard").str();
        if (standards.contains(id)) {
            auto updated = standards[id];
            updated.set("visible", item.get("visible"));
            replacements << updated;
        } else if (item.get("visible").flag()) {
            for (auto f : folders)
                if (id == f.id)
                    replacements << link(f, true);
        }
    }
    auto merged = array();
    bool separators = false;
    auto add = [&](const Json& i) {
        merged.add(i);
        separators |= i == sep();
    };
    auto next = replacements.cbegin();
    for (auto item : links.list()) {
        if (standards.contains(item.get("standard").str()) ||
            (portable.get("version").integer() == 2 && item == sep())) {
            if (next != replacements.cend())
                add(*next++);
        } else
            add(item);
    }
    while (next != replacements.cend())
        add(*next++);
    folder.set("version", number(separators ? 2 : 1));
    folder.set("folders", merged);
    if (!folder.has("hiddenSystemLinks"))
        folder.set("hiddenSystemLinks", array());
    if (!folder.has("portrait"))
        folder.set("portrait", str(""));
    for (auto name : files)
        validateLocal(name, after[name]);
    return after;
}
QString summary(const Json& value) {
    validatePortable(value);
    auto p = value.get("preferences"), r = p.get("recent");
    QStringList lines{"Primary button: " + p.get("primary").str(),
                      QString("Record recent programs: ") + (r.get("enabled").flag() ? "on" : "off"),
                      "Recent count: " + QString::number(r.get("limit").integer()),
                      "Age limit (days): " + (r.has("retention_days")
                                                  ? QString::number(r.get("retention_days").integer())
                                                  : QString("unchanged")),
                      "Standard folders and separators:"};
    for (auto item : p.get("folders").list()) {
        if (item == sep())
            lines << "— Separator —";
        else
            lines << item.get("standard").str().chopped(QStringLiteral("Location").size()) +
                         (item.get("visible").flag() ? " (shown)" : " (hidden)");
    }
    if (value.get("version").integer() == 1)
        lines << "Existing local separators will be preserved.";
    return lines.join('\n');
}
} // namespace portable
