#include "diagnostic.hpp"
#include <fcntl.h>
#include <sys/stat.h>
#include <unistd.h>
#include <fnmatch.h>

namespace input {
static QString normalized(QString value) { return value.toLower().remove('_').remove(' '); }
static std::optional<QStringList> lex(const QString& line) {
    QStringList tokens;
    QString word;
    QChar quote;
    bool started = false;
    for (qsizetype i = 0; i < line.size(); ++i) {
        auto c = line[i];
        if (c == '\\' && quote != '\'') {
            if (i + 1 == line.size())
                return {};
            auto next = line[++i];
            if (quote == '"' && next != '"' && next != '\\')
                word += '\\';
            word += next;
            started = true;
        } else if (!quote.isNull()) {
            if (c == quote)
                quote = {};
            else
                word += c;
        } else if (c == '"' || c == '\'') {
            quote = c;
            started = true;
        } else if (c == '#')
            break;
        else if (c.isSpace()) {
            if (started)
                tokens << word;
            word.clear();
            started = false;
        } else {
            word += c;
            started = true;
        }
    }
    if (!quote.isNull())
        return {};
    if (started)
        tokens << word;
    return tokens;
}
void Configuration::parse(const QString& text) {
    QList<QList<Directive>> parsed;
    QList<Directive> section;
    QString kind;
    bool malformed = false;
    for (const auto& line : text.split('\n')) {
        auto row = lex(line);
        if (!row) {
            malformed = true;
            continue;
        }
        if (row->isEmpty())
            continue;
        auto key = normalized(row->takeFirst());
        auto args = *row;
        if (key == "section") {
            malformed |= !kind.isEmpty() || args.size() != 1;
            kind = args.size() == 1 ? normalized(args[0]) : "unknown";
            section.clear();
        } else if (key == "endsection") {
            malformed |= kind.isEmpty() || !args.isEmpty();
            bool scheme = false;
            int identifiers = 0;
            for (const auto& entry : section) {
                if (entry.key == "option" && entry.values.size() == 2 &&
                    normalized(entry.values.front()) == "accelerationscheme")
                    scheme = true;
                if (entry.key == "identifier" && entry.values.size() == 1 &&
                    !entry.values.front().isEmpty())
                    ++identifiers;
            }
            if (scheme) {
                if (kind != "inputclass")
                    issues.insert("unsupported");
                else if (identifiers != 1)
                    malformed = true;
                else
                    parsed << section;
            }
            kind.clear();
            section.clear();
        } else if (kind.isEmpty())
            malformed = true;
        else {
            section << Directive{key, args};
            if ((key == "identifier" || key == "driver") && args.size() != 1)
                malformed = true;
            if (key == "option" && (args.isEmpty() || args.size() > 2 ||
                                    (normalized(args[0]) == "accelerationscheme" && args.size() != 2)))
                malformed = true;
        }
    }
    if (malformed || !kind.isEmpty())
        issues.insert("malformed");
    else
        rules += parsed;
}
Configuration Configuration::read(const QString& mainFile, const QStringList& directories) {
    Configuration result;
    QStringList files;
    if (QFileInfo::exists(mainFile) || QFileInfo(mainFile).isSymLink())
        files << mainFile;
    for (const auto& directory : directories) {
        QFileInfo info(directory);
        if (info.isSymLink()) {
            result.issues.insert("unreadable");
            continue;
        }
        if (!info.exists())
            continue;
        if (!info.isDir() || !info.isReadable()) {
            result.issues.insert("unreadable");
            continue;
        }
        QDirIterator it(directory, {"*.conf"}, QDir::Files | QDir::Hidden | QDir::System);
        while (it.hasNext()) {
            if (files.size() >= 64) {
                result.issues.insert("bounded");
                break;
            }
            files << it.next();
        }
    }
    std::sort(files.begin(), files.end());
    qint64 remaining = 262144;
    for (const auto& file : files) {
        auto fd =
            ::open(QFile::encodeName(file).constData(), O_RDONLY | O_CLOEXEC | O_NOFOLLOW | O_NONBLOCK);
        auto close = qScopeGuard([fd] {
            if (fd >= 0)
                ::close(fd);
        });
        struct stat initial{}, final{};
        if (fd < 0 || fstat(fd, &initial) || !S_ISREG(initial.st_mode)) {
            result.issues.insert("unreadable");
            continue;
        }
        auto limit = std::min<qint64>(65536, remaining);
        if (initial.st_size > limit) {
            result.issues.insert("bounded");
            continue;
        }
        QByteArray bytes(limit + 1, Qt::Uninitialized);
        auto size = ::read(fd, bytes.data(), bytes.size());
        if (size < 0 || fstat(fd, &final)) {
            result.issues.insert("unreadable");
            continue;
        }
        remaining -= size;
        if (size > limit) {
            result.issues.insert("bounded");
            continue;
        }
        if (size != initial.st_size || final.st_size != initial.st_size ||
            initial.st_mtim.tv_sec != final.st_mtim.tv_sec ||
            initial.st_mtim.tv_nsec != final.st_mtim.tv_nsec) {
            result.issues.insert("changed");
            continue;
        }
        bytes.truncate(size);
        if (!bytes.isValidUtf8()) {
            result.issues.insert("malformed");
            continue;
        }
        result.parse(QString::fromUtf8(bytes));
    }
    return result;
}
QString Configuration::describe(const Device& device, bool runtime) const {
    auto problems = issues;
    QSet<QString> requested;
    for (const auto& rule : rules) {
        bool unknown = false, matched = true;
        QStringList schemes;
        for (const auto& entry : rule) {
            auto name = entry.key;
            auto values = entry.values;
            if (name == "identifier" || name == "driver")
                continue;
            if (name == "option") {
                if (values.size() == 2 && normalized(values[0]) == "accelerationscheme")
                    schemes << normalized(values[1]);
                continue;
            }
            if (values.size() != 1) {
                unknown = true;
                continue;
            }
            auto alternatives = values[0].split('|');
            if (alternatives.contains("")) {
                unknown = true;
                continue;
            }
            bool neg = name.startsWith("nomatch");
            auto key = neg ? name.mid(2) : name;
            bool found = false;
            if (key == "matchproduct") {
                for (const auto& part : alternatives)
                    found |= device.name.contains(part);
            } else if (key == "matchdevicepath") {
                for (const auto& part : alternatives)
                    found |= fnmatch(part.toUtf8().constData(), device.node.toUtf8().constData(), 0) == 0;
            } else if (name == "matchispointer" || name == "matchistouchpad") {
                auto expected = normalized(values.front());
                bool yes = QStringList{"on", "true", "yes", "1"}.contains(expected);
                if (!yes && !QStringList{"off", "false", "no", "0"}.contains(expected)) {
                    unknown = true;
                    continue;
                }
                found = (name == "matchistouchpad"
                             ? device.kind == "touchpad"
                             : device.kind == "mouse" || device.kind == "touchpad") == yes;
            } else {
                unknown = true;
                continue;
            }
            if (found == neg) {
                matched = false;
                break;
            }
        }
        if (!matched)
            continue;
        if (unknown) {
            problems.insert("unsupported");
            continue;
        }
        if (std::any_of(schemes.begin(), schemes.end(), [](const QString& s) {
                return s != "none" && s != "predictable" && s != "lightweight";
            })) {
            problems.insert("malformed");
            continue;
        }
        for (const auto& s : schemes)
            requested.insert(s);
    }
    QString intent = requested.isEmpty() ? "no matching scheme request established in standard locations"
                     : requested.size() > 1
                         ? "conflicting matching scheme requests; effective scheme unknown"
                         : "matching rule requests " + *requested.begin() + " (intent only)";
    auto sorted = problems.values();
    sorted.sort();
    if (!sorted.isEmpty())
        intent += "; incomplete: " + sorted.join(", ");
    return QString("Runtime acceleration-profile control: %1.\nSystem configuration: %2.\nCurrent Xorg "
                   "initialization: unverified; XInput supplies no current-device/session proof. "
                   "Historical logs and a missing profile do not prove acceleration is disabled.\nThis "
                   "page cannot change the system scheme. No physical motion test is performed.")
        .arg(runtime ? "available" : "unavailable for this device/driver", intent);
}
} // namespace input
