#include "theme.hpp"
#include <expat.h>
#include <memory>
namespace theme {
namespace {
#if XML_MAJOR_VERSION > 2 || (XML_MAJOR_VERSION == 2 && XML_MINOR_VERSION >= 9)
constexpr auto byteIndex = XML_GetCurrentByteIndex64;
constexpr auto byteCount = XML_GetCurrentByteCount64;
#else
constexpr auto byteIndex = XML_GetCurrentByteIndex;
constexpr auto byteCount = XML_GetCurrentByteCount;
#endif
struct Span {
    qsizetype begin = -1, inside = -1, endInside = -1, end = -1;
    bool empty = false;
};
struct Openbox {
    XML_Parser parser;
    QStringList tags;
    QByteArray bytes;
    Span root, theme, name;
    bool ambiguous = false;
    explicit Openbox(const QByteArray& source) : parser(XML_ParserCreateNS(nullptr, '|')), bytes(source) {
        if (!parser)
            fail("Cannot initialize the XML parser.");
        auto cleanup = qScopeGuard([&] { XML_ParserFree(parser); });
        XML_SetUserData(parser, this);
        XML_SetElementHandler(parser, start, finish);
        XML_SetStartDoctypeDeclHandler(parser, [](void* state, const char*, const char*, const char*, int) {
            static_cast<Openbox*>(state)->ambiguous = true;
        });
        if (!XML_Parse(parser, source.constData(), source.size(), XML_TRUE) || ambiguous || root.begin < 0)
            fail("Expected one unambiguous Openbox root, theme section and theme name.");
    }
    Span* selected() {
        if (tags == QStringList{"openbox_config"})
            return &root;
        if (tags == QStringList{"openbox_config", "theme"})
            return &theme;
        if (tags == QStringList{"openbox_config", "theme", "name"})
            return &name;
        return nullptr;
    }
    static void start(void* state, const char* raw, const char**) {
        auto self = static_cast<Openbox*>(state);
        if (self->selected() == &self->name)
            self->ambiguous = true;
        self->tags << QString::fromUtf8(raw).section('|', -1);
        if (auto span = self->selected()) {
            if (span->begin != -1) {
                self->ambiguous = true;
                return;
            }
            span->begin = byteIndex(self->parser);
            span->inside = span->begin + byteCount(self->parser);
            span->empty = self->bytes.sliced(span->begin, span->inside - span->begin).endsWith("/>");
        }
    }
    static void finish(void* state, const char*) {
        auto self = static_cast<Openbox*>(state);
        if (auto span = self->selected()) {
            span->endInside = span->empty ? span->inside : byteIndex(self->parser);
            span->end = span->empty ? span->inside : span->endInside + byteCount(self->parser);
        }
        self->tags.removeLast();
    }
};
struct Ini {
    qsizetype body = -1, end = 0, line = -1, lineEnd = -1, value = -1, valueEnd = -1;
};
Ini locate(const QByteArray& text, const Edit& edit) {
    Ini ini;
    bool inside = false;
    auto header = "[" + edit.section.toUtf8() + "]", key = edit.key.toUtf8();
    for (qsizetype at = 0; at < text.size();) {
        auto nl = text.indexOf('\n', at);
        auto end = nl < 0 ? text.size() : nl + 1;
        auto contentEnd = nl < 0 ? end : nl;
        if (contentEnd > at && text[contentEnd - 1] == '\r')
            --contentEnd;
        auto line = text.sliced(at, contentEnd - at);
        auto trim = line.trimmed();
        if (trim.startsWith('[')) {
            if (inside)
                ini.end = at;
            inside = trim == header;
            if (inside) {
                if (ini.body >= 0)
                    fail("Duplicate theme section in " + edit.path);
                ini.body = end;
                ini.end = text.size();
            }
        } else if (inside && !trim.startsWith('#') && !trim.startsWith(';')) {
            auto eq = line.indexOf('=');
            if (eq >= 0 && line.left(eq).trimmed() == key) {
                if (ini.line != -1)
                    fail("Duplicate theme key in " + edit.path);
                ini.line = at;
                ini.lineEnd = end;
                ini.value = at + eq + 1;
                ini.valueEnd = contentEnd;
            }
        }
        at = end;
    }
    return ini;
}
} // namespace
QJsonValue readValue(const Edit& e, const QByteArray& b) {
    if (e.kind == "file")
        return b.isNull() ? QJsonValue(QJsonValue::Null) : QJsonValue(QString::fromLatin1(b.toBase64()));
    if (!b.isValidUtf8() || b.contains('\0'))
        fail("Expected a UTF-8 configuration: " + e.path);
    if (e.kind == "obtheme") {
        Openbox xml(b);
        const auto& span = xml.name;
        if (span.begin < 0)
            return QJsonValue::Null;
        return QString::fromUtf8(b.sliced(span.inside, span.endInside - span.inside));
    }
    auto ini = locate(b, e);
    if (ini.line < 0)
        return QJsonValue::Null;
    return QString::fromUtf8(b.sliced(ini.value, ini.valueEnd - ini.value));
}
QByteArray setValue(const Edit& e, const QByteArray& source, const QJsonValue& value) {
    if (e.kind == "file") {
        if (value.isNull())
            return {};
        auto result = QByteArray::fromBase64Encoding(value.toString().toLatin1(),
                                                     QByteArray::AbortOnBase64DecodingErrors);
        if (!result)
            fail("Invalid saved theme file.");
        return result.decoded.isNull() ? QByteArray("") : result.decoded;
    }
    if (readValue(e, source) == value)
        return source;
    auto text = source;
    auto v = value.toString().toUtf8();
    if (e.kind == "obtheme") {
        Openbox xml(source);
        auto n = xml.name, t = xml.theme, r = xml.root;
        auto prefix = [&](const Span& span) {
            auto end = span.begin + 1;
            while (end < span.inside && !QByteArray(" \n\r\t/>").contains(source[end]))
                ++end;
            auto tag = source.sliced(span.begin + 1, end - span.begin - 1);
            return tag.left(tag.indexOf(':') + 1);
        };
        if (n.begin >= 0) {
            if (value.isNull())
                return text.remove(n.begin, n.end - n.begin);
            if (!n.empty)
                return text.replace(n.inside, n.endInside - n.inside, v);
            return text.replace(n.inside - 2, 2, ">" + v + "</" + prefix(n) + "name>");
        }
        auto ns = prefix(t.begin >= 0 ? t : r);
        auto entry = "<" + ns + "name>" + v + "</" + ns + "name>";
        if (t.begin >= 0) {
            if (t.empty)
                return text.replace(t.inside - 2, 2, ">" + entry + "</" + ns + "theme>");
            return text.insert(t.inside, entry);
        }
        auto theme = "<" + ns + "theme>" + entry + "</" + ns + "theme>";
        if (r.empty)
            return text.replace(r.inside - 2, 2, ">" + theme + "</" + ns + "openbox_config>");
        return text.insert(r.endInside, theme);
    }
    auto i = locate(source, e);
    if (i.line >= 0) {
        if (value.isNull())
            return text.remove(i.line, i.lineEnd - i.line);
        return text.replace(i.value, i.valueEnd - i.value, v);
    }
    if (value.isNull())
        return source;
    auto newline = source.contains("\r\n") ? QByteArray("\r\n") : QByteArray("\n");
    QByteArray insert;
    auto pos = i.body < 0 ? source.size() : i.end;
    if (pos && source[pos - 1] != '\n')
        insert += newline;
    if (i.body < 0)
        insert += (pos ? newline : QByteArray()) + "[" + e.section.toUtf8() + "]" + newline;
    insert += e.key.toUtf8() + "=" + v + newline;
    return text.insert(pos, insert);
}
// RC2 inserted blank lines and trimmed trailing section whitespace. Reproduce
// its image only for recognizing a byte-exact restoration of an RC2 backup.
QByteArray rc2Value(const Edit& edit, const QByteArray& source, const QJsonValue& value) {
    if (edit.kind != "ini")
        return setValue(edit, source, value);
    auto text = QString::fromUtf8(source);
    auto match = QRegularExpression("(?m)^\\[" + QRegularExpression::escape(edit.section) + "\\]\\s*\\n")
                     .match(text);
    auto rstrip = [](QString s) {
        while (!s.isEmpty() && s.back().isSpace())
            s.chop(1);
        return s;
    };
    auto line = edit.key + "=" + value.toString();
    if (!match.hasMatch())
        return (rstrip(text) + "\n\n[" + edit.section + "]\n" + line + "\n").toUtf8();
    auto pos = match.capturedEnd();
    auto end = text.indexOf(QRegularExpression("(?m)^\\["), pos);
    if (end < 0)
        end = text.size();
    auto body = text.sliced(pos, end - pos);
    auto field = QRegularExpression("(?m)^" + QRegularExpression::escape(edit.key) + "\\s*=.*$");
    auto found = field.match(body);
    if (found.hasMatch())
        body.replace(found.capturedStart(), found.capturedLength(), line);
    else
        body = rstrip(body) + "\n" + line + "\n";
    return text.replace(pos, end - pos, body).toUtf8();
}
} // namespace theme
