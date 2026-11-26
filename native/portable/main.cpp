#include "portable.hpp"
#include <QtWidgets>
using namespace portable;
namespace {
const QString notice = "The export contains the primary Start button action, recent-program preferences "
                       "and standard folder order and visibility. Version 2 includes separators. Your "
                       "pins, history, custom paths, portrait and machine settings stay local.";
Store current() {
    auto config = qEnvironmentVariable("XDG_CONFIG_HOME");
    if (config.isEmpty())
        config = QDir::homePath() + "/.config";
    if (!QDir::isAbsolutePath(config))
        fail("XDG_CONFIG_HOME must be absolute.");
    return Store(config);
}
Json imported(const QString& name) {
    auto input = Store::read(QFileInfo(name).absoluteFilePath());
    if (input.bytes.isNull())
        fail("Import file does not exist.");
    auto v = decode(input.bytes);
    validatePortable(v);
    return v;
}
int cli(const QStringList& args) {
    auto store = current();
    if (args.size() == 2 && args[0] == "--export") {
        store.exportFile(args[1]);
        return 0;
    }
    if (args == QStringList{"--restore"}) {
        store.restore();
        return 0;
    }
    if (args.size() == 2 && (args[0] == "--plan" || args[0] == "--import")) {
        auto v = imported(args[1]);
        auto changes = store.plan(v);
        QTextStream(stdout) << summary(v) << Qt::endl;
        if (changes.isEmpty())
            QTextStream(stdout) << "Preferences already match." << Qt::endl;
        else if (args[0] == "--import") {
            store.apply(changes);
            QTextStream(stdout) << "Preferences saved. Reopen Start." << Qt::endl;
        }
        return 0;
    }
    QTextStream(stderr) << "Use --export NEW_FILE, --plan FILE, --import FILE, --restore, or open the "
                           "dialog without arguments.\n";
    return 2;
}
QMessageBox::StandardButton message(QWidget* owner, const QString& title, const QString& text,
                                    QMessageBox::Icon icon,
                                    QMessageBox::StandardButtons buttons = QMessageBox::Ok) {
    QMessageBox box(icon, title, text, buttons, owner);
    box.setTextFormat(Qt::PlainText);
    if (buttons.testFlag(QMessageBox::Cancel))
        box.setDefaultButton(QMessageBox::Cancel);
    return static_cast<QMessageBox::StandardButton>(box.exec());
}
int dialog() {
    auto store = current();
    QDialog dialog;
    dialog.setWindowTitle("Portable Start preferences");
    dialog.resize(465, 320);
    auto layout = new QVBoxLayout(&dialog);
    auto note = new QLabel(notice);
    note->setWordWrap(true);
    layout->addWidget(note);
    auto button = [&](const QString& label, std::function<void()> callback) {
        auto item = new QPushButton(label);
        layout->addWidget(item);
        QObject::connect(item, &QPushButton::clicked, &dialog, [&, callback = std::move(callback)] {
            try {
                callback();
            } catch (const std::exception& e) {
                message(&dialog, "Portable preferences could not complete", QString::fromUtf8(e.what()),
                        QMessageBox::Warning);
            }
        });
    };
    button("Export portable preferences…", [&] {
        auto filename = QFileDialog::getSaveFileName(&dialog, "Export portable preferences",
                                                     "DoroShell-preferences.json", "JSON (*.json)");
        if (!filename.isEmpty())
            store.exportFile(filename, true);
    });
    button("Preview and import…", [&] {
        auto filename =
            QFileDialog::getOpenFileName(&dialog, "Preview portable preferences", {}, "JSON (*.json)");
        if (filename.isEmpty())
            return;
        auto v = imported(filename);
        auto changes = store.plan(v);
        if (changes.isEmpty()) {
            message(&dialog, "Portable preferences", "These preferences already match.",
                    QMessageBox::Information);
            return;
        }
        if (message(&dialog, "Apply this preview?",
                    summary(v) + "\n\n" + notice + "\n\nThis replaces the previous import rollback.",
                    QMessageBox::Question, QMessageBox::Apply | QMessageBox::Cancel) != QMessageBox::Apply)
            return;
        store.apply(changes);
        message(&dialog, "Imported", "Portable preferences saved. Reopen Start.", QMessageBox::Information);
    });
    button("Restore last import", [&] {
        if (message(&dialog, "Restore last import?",
                    "Restore the exact local preferences from before the last import? Later personal edits "
                    "are preserved by refusing the restore.",
                    QMessageBox::Question, QMessageBox::Yes | QMessageBox::Cancel) != QMessageBox::Yes)
            return;
        store.restore();
        message(&dialog, "Restored", "Previous preferences restored. Reopen Start.",
                QMessageBox::Information);
    });
    button("Close", [&] { dialog.close(); });
    dialog.exec();
    return 0;
}
} // namespace
int main(int argc, char** argv) {
    try {
        if (argc > 1) {
            QCoreApplication app(argc, argv);
            return cli(app.arguments().mid(1));
        }
        QApplication app(argc, argv);
        return dialog();
    } catch (const std::exception& e) {
        QTextStream(stderr) << e.what() << Qt::endl;
        return 1;
    }
}
