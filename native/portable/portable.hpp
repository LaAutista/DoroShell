#pragma once
#include <QtCore>
#include <jansson.h>
namespace portable {
[[noreturn]] void fail(const QString& msg);
struct Json {
    std::shared_ptr<json_t> handle;
    explicit Json(json_t* owned = nullptr) : handle(owned, json_decref) {}
    json_t* ptr() const { return handle.get(); }
    Json get(const char* key) const { return Json(json_incref(json_object_get(ptr(), key))); }
    bool has(const char* key) const { return bool(get(key).ptr()); }
    bool object() const { return json_is_object(ptr()); }
    bool array() const { return json_is_array(ptr()); }
    bool string() const { return json_is_string(ptr()); }
    bool boolean() const { return json_is_boolean(ptr()); }
    QString str() const { return QString::fromUtf8(json_string_value(ptr()), json_string_length(ptr())); }
    bool flag() const { return json_is_true(ptr()); }
    qint64 integer() const { return json_integer_value(ptr()); }
    void set(const char* key, const Json& v) const;
    void add(const Json& v) const;
    QList<Json> list() const;
    QStringList keys() const;
    bool operator==(const Json& other) const { return json_equal(ptr(), other.ptr()); }
};
inline Json object() { return Json(json_object()); }
inline Json array() { return Json(json_array()); }
inline Json str(const QString& s) {
    auto bytes = s.toUtf8();
    return Json(json_stringn(bytes.constData(), bytes.size()));
}
inline Json flag(bool b) { return Json(json_boolean(b)); }
inline Json number(qint64 n) { return Json(json_integer(n)); }
inline Json null() { return Json(json_null()); }
constexpr qsizetype limit = 128 * 1024;
const QStringList files{"session-button.json", "recent.json", "folders.json"};
Json decode(const QByteArray& raw, qsizetype cap = limit);
QByteArray encode(const Json& v);
void validatePortable(const Json& v);
void validateLocal(const QString& name, const Json& v);
using Values = QMap<QString, Json>;
Json exportValues(const Values& local);
Values importValues(const Values& local, const Json& portable);
QString summary(const Json& value);
struct State {
    QByteArray bytes;
    int mode = 0600;
    bool operator==(const State& b) const {
        return bytes.isNull() == b.bytes.isNull() && bytes == b.bytes && (bytes.isNull() || mode == b.mode);
    }
};
struct Change {
    State before, after;
};
using Changes = QMap<QString, Change>;
class Store {
  public:
    explicit Store(const QString& config);
    static State read(const QString& file, qsizetype cap = limit);
    Json exportSettings() const;
    void exportFile(const QString& name, bool overwrite = false) const;
    Changes plan(const Json& v) const;
    void apply(const Changes& changes) const;
    void restore() const;

  private:
    QString base;
    QMap<QString, State> snapshot(Values& local) const;
    void transaction(const Changes& changes) const;
};
} // namespace portable
