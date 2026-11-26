#include "theme.hpp"
#include <QColor>
namespace theme {
void fail(const QString& reason) { throw std::runtime_error(reason.toStdString()); }
QStringList presets() { return {"windows", "polar", "heretic", "spring"}; }
static QMap<QByteArray, QByteArray> palette(const QString& preset) {
    static const QMap<QString, QByteArray> rows{
        {"windows", "#fff5fb #f4dce9 #351329 #715064 #934369 #edafd2 #773353 #b9799e #a2748a"},
        {"polar", "#f4fbff #dceef9 #14324a #46647a #28618d #a8d5f4 #244f73 #7aa7c5 #67849e"},
        {"heretic", "#222124 #302c30 #f8eeee #c3aeb6 #d97682 #70323d #211c20 #a65c68 #838083"},
        {"spring", "#fffdf0 #e6edd0 #243b23 #53694d #466e37 #c0d89c #3c5a30 #849b64 #728869"}};
    if (!rows.contains(preset))
        fail("Choose windows, polar, heretic or spring.");
    auto colors = rows[preset].split(' ');
    auto roles = QByteArray("base window ink muted accent selection side edge tray").split(' ');
    QMap<QByteArray, QByteArray> p;
    for (qsizetype i = 0; i < roles.size(); ++i) {
        auto rgb = QColor::fromString(QString::fromLatin1(colors[i]));
        p[roles[i]] = colors[i];
        p[roles[i] + "RGB"] = QByteArray::number(rgb.red()) + ',' + QByteArray::number(rgb.green()) + ',' +
                              QByteArray::number(rgb.blue());
    }
    return p;
}
static QByteArray render(const QString& file, QMap<QByteArray, QByteArray> p, bool glass = false) {
    auto shaded = [&](const QByteArray& key, const QByteArray& alpha) {
        return glass ? "#" + alpha + p[key].mid(1) : p[key];
    };
    p["frame_top"] = shaded("window", "ed");
    p["frame_accent"] = shaded("selection", "e0");
    p["place_side"] = shaded("side", "ed");
    p["surface"] = shaded("window", "f0");
    p["shine"] = shaded("selection", "f0");
    QFile resource(":/theme/" + file);
    if (!resource.open(QIODevice::ReadOnly))
        fail("Missing theme resource " + file);
    auto bytes = resource.readAll();
    for (auto i = p.cbegin(); i != p.cend(); ++i)
        bytes.replace("@" + i.key() + "@", i.value());
    // Existing RC2 receipts compare the entire stylesheet, including the
    // indentation after its final newline.
    if (file.endsWith(".qss"))
        bytes += "    ";
    return bytes;
}
QList<Edit> edits(const QString& preset) {
    auto p = palette(preset);
    QList<Edit> all;
    auto file = [&](const QString& name, const QString& source, bool glass = false) {
        all << Edit{name, "file", {}, {}, QString::fromLatin1(render(source, p, glass).toBase64())};
    };
    for (auto prefix : {QString("start-theme"), QString("panel-theme")})
        for (bool glass : {false, true})
            file(".config/doroshell/" + prefix + (glass ? "-glass.qss" : ".qss"), prefix + "-glass.qss",
                 glass);
    file(".local/share/color-schemes/DoroShell.colors", "scheme.colors");
    file(".local/share/org.kde.syntax-highlighting/themes/doroshell.theme", "kate.json");
    file(".local/share/themes/DoroShell/openbox-3/themerc", "themerc");
    auto ini = [&](QString path, QString section, QString key, QString value) {
        all << Edit{".config/" + path, "ini", section, key, value};
    };
    ini("doroshell/theme.conf", "Theme", "name", preset);
    for (auto app : {QString("katerc"), QString("dolphinrc")}) {
        ini(app, "UiSettings", "ColorScheme", "DoroShell");
        ini(app, "KDE", "widgetStyle", "Fusion");
    }
    ini("katerc", "KTextEditor Renderer", "Color Theme", "DoroShell");
    ini("katerc", "KTextEditor Renderer", "Auto Color Theme Selection", "false");
    const QList<QPair<QString, QByteArray>> roles{
        {"base_color", "base"},       {"window_color", "window"},       {"text_color", "ink"},
        {"window_text_color", "ink"}, {"highlight_color", "selection"}, {"highlighted_text_color", "ink"},
        {"link_color", "accent"},     {"link_visited_color", "muted"},  {"tooltip_base_color", "base"},
        {"tooltip_text_color", "ink"}};
    for (const auto& [key, role] : roles)
        ini("lxqt/lxqt.conf", "Palette", key, QString::fromLatin1(p[role]));
    ini("lxqt/lxqt.conf", "Qt", "style", "Fusion");
    ini("lxqt/lxqt.conf", "General", "icon_theme", preset == "heretic" ? "breeze-dark" : "breeze");
    ini("lxqt/lxqt.conf", "General", "icon_follow_color_scheme", "false");
    all << Edit{".config/openbox/rc.xml", "obtheme", {}, {}, "DoroShell"};
    return all;
}
void generate(const QString& preset, const QString& destination) {
    auto plan = edits(preset);
    auto root = QFileInfo(destination).absoluteFilePath();
    if (QFileInfo(root).exists() || QFileInfo(root).isSymLink())
        fail("Choose a new output directory.");
    if (!QDir().mkdir(root))
        fail("Cannot create theme output directory.");
    for (const auto& e : plan)
        if (e.kind == "file") {
            auto file = root + "/" + e.path;
            if (!QDir().mkpath(QFileInfo(file).absolutePath()))
                fail("Cannot create theme output path.");
            QSaveFile f(file);
            auto bytes = QByteArray::fromBase64(e.desired.toString().toLatin1());
            if (!f.open(QIODevice::WriteOnly) || f.write(bytes) != bytes.size() || !f.commit())
                fail("Cannot write " + file);
        }
}
} // namespace theme
