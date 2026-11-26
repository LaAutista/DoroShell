#include "theme.hpp"
int main(int argc, char** argv) {
    QCoreApplication app(argc, argv);
    const auto args = app.arguments().mid(1);
    auto out = QTextStream(stdout);
    try {
        if (args == QStringList{"--list"})
            out << theme::presets().join('\n') << Qt::endl;
        else if (args == QStringList{"--status"})
            out << QJsonDocument(theme::status(QDir::homePath())).toJson(QJsonDocument::Compact)
                << Qt::endl;
        else if (args.size() == 3 && args[0] == "--generate")
            theme::generate(args[1], args[2]);
        else if ((args.size() == 2 && (args[0] == "--plan" || args[0] == "--apply")) ||
                 args == QStringList{"--restore"}) {
            bool restore = args.front() == "--restore";
            auto preset = restore ? QString("windows") : args[1];
            out << theme::change(QDir::homePath(), preset, args[0] == "--plan", restore).join('\n')
                << Qt::endl;
        } else {
            QTextStream(stderr) << "Use --list, --status, --plan PRESET, --apply PRESET, --restore or "
                                   "--generate PRESET NEW_DIRECTORY.\n";
            return 2;
        }
        return 0;
    } catch (const std::exception& e) {
        QTextStream(stderr) << e.what() << Qt::endl;
        return 1;
    }
}
