// SPDX-License-Identifier: LGPL-2.1-or-later
// Standalone Qt input check, using only temporary desktop entries.
#include "doroshellpinsdialog.h"
#include <LXQt/Settings>
#include "pluginsettings_p.h"
#include <QApplication>
#include <QDialogButtonBox>
#include <QFile>
#include <QFileDialog>
#include <QLineEdit>
#include <QListWidget>
#include <QMessageBox>
#include <QPushButton>
#include <QTemporaryDir>
#include <QTest>
#include <QTimer>
#include <cassert>
#include <iostream>

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    QTemporaryDir temp;
    assert(temp.isValid());
    auto entry = [&temp](const QString &name, const QString &identity) {
        QString path = temp.path() + '/' + name + ".desktop";
        QFile file(path); assert(file.open(QIODevice::WriteOnly));
        file.write(("[Desktop Entry]\nType=Application\nName=" + name + "\nExec=/usr/bin/true\nStartupWMClass=" + identity + "\n").toUtf8());
        return path;
    };
    const auto alpha = entry("Alpha", "Alpha"), beta = entry("Beta", "Beta"), gamma = entry("Gamma", "Gamma");
    auto click = [](QWidget &widget, const char *name) {
        auto button = widget.findChild<QPushButton*>(QString::fromLatin1(name)); assert(button);
        QTest::mouseClick(button, Qt::LeftButton);
    };
    auto save = [](DoroShellPinsDialog &dialog) {
        QTest::mouseClick(dialog.findChild<QDialogButtonBox*>()->button(QDialogButtonBox::Save), Qt::LeftButton);
    };
    const QStringList original{alpha, beta};
    LXQt::Settings config(temp.path() + "/panel.conf", QSettings::IniFormat);
    auto settings = PluginSettingsFactory::create(&config, QStringLiteral("taskbar"), &app);
    settings->setValue(QStringLiteral("doroshellPinned"), original);
    settings->sync();
    settings->setValue(QStringLiteral("doroshellPinned"), QStringList({beta}));
    settings->syncKeepingResetState();
    QSettings disk(temp.path() + "/panel.conf", QSettings::IniFormat);
    assert(disk.value("taskbar/doroshellPinned").toStringList() == QStringList({beta}));
    disk.setValue("taskbar/doroshellPinned", QStringList({gamma})); disk.sync();
    settings->syncKeepingResetState();
    assert(settings->value("doroshellPinned").toStringList() == QStringList({gamma}));
    settings->loadFromCache();
    assert(settings->value("doroshellPinned").toStringList() == original);
    delete settings;

    DoroShellPinsDialog editor(original);
    editor.show(); QTest::qWait(150);
    click(editor, "movePinDown");
    assert(editor.paths() == QStringList({beta, alpha}));
    click(editor, "removePin");
    assert(editor.paths() == QStringList({beta}));
    QTimer::singleShot(200, [&] {
        auto picker = qobject_cast<QFileDialog*>(QApplication::activeModalWidget()); assert(picker);
        auto filename = picker->findChild<QLineEdit*>(QStringLiteral("fileNameEdit")); assert(filename);
        filename->setFocus(); QTest::keyClicks(filename, gamma); QTest::keyClick(filename, Qt::Key_Return);
    });
    click(editor, "addPin");
    assert(editor.paths() == QStringList({beta, gamma}));
    save(editor);
    assert(editor.result() == QDialog::Accepted);
    DoroShellPinsDialog cancelled(original);
    cancelled.show(); QTest::qWait(50); click(cancelled, "movePinDown");
    QTest::keyClick(&cancelled, Qt::Key_Escape);
    assert(cancelled.result() == QDialog::Rejected && original == QStringList({alpha,beta}));
    const auto duplicate = entry("Another Alpha", "Alpha");
    for (const auto &invalid : {duplicate, temp.path() + "/missing.desktop"})
    {
        DoroShellPinsDialog rejected({alpha, invalid});
        rejected.show(); QTest::qWait(50);
        QTimer::singleShot(100, [] {
            auto warning = qobject_cast<QMessageBox*>(QApplication::activeModalWidget()); assert(warning);
            QTest::keyClick(warning, Qt::Key_Return);
        });
        save(rejected);
        assert(rejected.result() == QDialog::Rejected && rejected.isVisible());
        rejected.reject();
    }
    std::cout << "PASS native pin editor: add, remove, order, save, Escape, duplicate/missing-entry rejection, external refresh and Reset preservation\n";
}
