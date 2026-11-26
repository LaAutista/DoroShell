// SPDX-License-Identifier: GPL-2.0-or-later
// Native PCManFM Advanced-tab controls; the helper owns the confirmation deadline.
#pragma once
#include <QDir>
#include <QFileInfo>
#include <QSaveFile>
#include <QDialogButtonBox>
#include <unistd.h>
#include <QCheckBox>
#include <QCoreApplication>
#include <QCryptographicHash>
#include <QFile>
#include <QComboBox>
#include <QGroupBox>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QPointer>
#include <QProcess>
#include <QPushButton>
#include <QTimer>
#include <QDialog>
#include <QMessageBox>
#include <QVBoxLayout>
#include <functional>
#include <utility>

// One fixed-schema, owner-only record, atomically replaced; never append raw errors.
namespace DoroDisplayFailure {
inline bool record(QString reason, const QJsonArray &differences, const QJsonArray &diagnostics = {}) {
    const QStringList reasons{QStringLiteral("guard_error"), QStringLiteral("abnormal_exit"), QStringLiteral("guard_start_failed")};
    if (!reasons.contains(reason)) reason = QStringLiteral("guard_error");
    const QStringList allowed{QStringLiteral("framebuffer geometry"), QStringLiteral("output disappeared"),
        QStringLiteral("output added"), QStringLiteral("output enumeration changed"), QStringLiteral("connection status changed"),
        QStringLiteral("current mode mismatch"), QStringLiteral("CRTC assignment"), QStringLiteral("advertised mode timings/flags"),
        QStringLiteral("NVIDIA OpenGL VSync"), QStringLiteral("connection/geometry/rotation"), QStringLiteral("mode timings/flags"),
        QStringLiteral("gamma"), QStringLiteral("brightness"), QStringLiteral("transform"), QStringLiteral("border"),
        QStringLiteral("screen index"), QStringLiteral("color transform"), QStringLiteral("color matrix"),
        QStringLiteral("other protected properties"), QStringLiteral("protected layout fingerprint"), QStringLiteral("screen geometry"),
        QStringLiteral("BorderDimensions"), QStringLiteral("link-status"), QStringLiteral("Colorspace"),
        QStringLiteral("Dithering"), QStringLiteral("dithering"), QStringLiteral("DitheringMode"), QStringLiteral("DitheringDepth"),
        QStringLiteral("Broadcast RGB"), QStringLiteral("max bpc"), QStringLiteral("non-desktop")};
    QJsonArray fields;
    for (const auto &entry : differences) {
        const auto field = entry.toObject().value(QStringLiteral("field")).toString();
        if (allowed.contains(field) && !fields.contains(field)) fields.append(field);
        if (fields.size() == 16) break;
    }
    const QStringList phases{QStringLiteral("preflight"), QStringLiteral("apply"), QStringLiteral("apply_verification"), QStringLiteral("periodic_verification"), QStringLiteral("keep_verification"), QStringLiteral("recovery")};
    const QStringList causes{QStringLiteral("operation_failed"), QStringLiteral("state_mismatch"), QStringLiteral("external_change"), QStringLiteral("command_timeout"), QStringLiteral("command_failed"), QStringLiteral("command_unavailable"), QStringLiteral("deadline")};
    QJsonArray events;
    for (const auto &entry : diagnostics) {
        auto event = entry.toObject();
        const auto phase = event[QStringLiteral("phase")].toString();
        const auto cause = event[QStringLiteral("reason")].toString();
        if (!phases.contains(phase) || !causes.contains(cause)) continue;
        QJsonArray labels;
        for (const auto &field : event[QStringLiteral("fields")].toArray()) {
            if (allowed.contains(field.toString()) && !labels.contains(field.toString())) labels.append(field.toString());
            if (labels.size() == 6) break;
        }
        events.append(QJsonObject{{QStringLiteral("phase"), phase}, {QStringLiteral("reason"), cause}, {QStringLiteral("fields"), labels}});
        if (events.size() == 3) break;
    }
    QString state = qEnvironmentVariable("XDG_STATE_HOME");
    if (!QDir::isAbsolutePath(state)) state = QDir::homePath() + QStringLiteral("/.local/state");
    const QString directory = QDir::cleanPath(state + QStringLiteral("/doroshell-display-errors"));
    for (QString path = directory;; path = QFileInfo(path).path()) {
        if (QFileInfo(path).isSymLink()) return false;
        if (path == QStringLiteral("/")) break;
    }
    if (!QDir().mkpath(QFileInfo(directory).path())) return false;
    if (!QFileInfo::exists(directory)) {
        if (!QDir().mkdir(directory) || !QFile::setPermissions(directory, QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner)) return false;
    }
    const QFileInfo info(directory);
    const auto privateBits = QFile::ReadOwner | QFile::WriteOwner | QFile::ExeOwner | QFile::ReadUser | QFile::WriteUser | QFile::ExeUser;
    if (!info.isDir() || info.ownerId() != geteuid() || (info.permissions() & ~privateBits)) return false;
    const QString path = directory + QStringLiteral("/last-failure.json");
    if (QFileInfo(path).isSymLink()) return false;
    const auto bytes = QJsonDocument(QJsonObject{{QStringLiteral("schema"), 2}, {QStringLiteral("reason"), reason},
        {QStringLiteral("recovery"), QStringLiteral("unverified")}, {QStringLiteral("fields"), fields}, {QStringLiteral("diagnostics"), events}}).toJson(QJsonDocument::Compact);
    if (bytes.size() > 2048) return false;
    QSaveFile file(path); file.setDirectWriteFallback(false);
    if (!file.open(QIODevice::WriteOnly) || !file.setPermissions(QFile::ReadOwner | QFile::WriteOwner)) return false;
    return file.write(bytes) == bytes.size() && file.commit();
}
}

class DoroDisplayControls : public QGroupBox {
public:
    explicit DoroDisplayControls(const QStringList &helper, QWidget *parent = nullptr, const QByteArray &helperHash = {})
        : QGroupBox(tr("Display (current session)"), parent), helper_(helper), helperHash_(helperHash) {
        auto form = new QFormLayout(this);
        form->setRowWrapPolicy(QFormLayout::WrapLongRows);
        output_ = new QComboBox(this); output_->setObjectName("displayOutput");
        rate_ = new QComboBox(this); rate_->setObjectName("displayRate");
        form->addRow(tr("Display:"), output_);
        form->addRow(tr("Refresh rate:"), rate_);
        vsync_ = new QCheckBox(tr("VSync — NVIDIA OpenGL (X screen 0)"), this);
        vsync_->setObjectName("displayVsync");
        form->addRow(vsync_);
        auto scope = new QLabel(tr("NVIDIA VSync affects newly started OpenGL apps; apps may override it. "
            "Not universal Vulkan/game VSync. Intel/AMD: use app settings. No compositor or login changes."), this);
        scope->setWordWrap(true);
        scope->setMinimumHeight(scope->fontMetrics().lineSpacing() * 5);
        form->addRow(scope);
        auto row = new QHBoxLayout;
        reload_ = new QPushButton(tr("Reload"), this); reload_->setObjectName("displayReload");
        apply_ = new QPushButton(tr("Test display changes"), this); apply_->setObjectName("displayApply");
        keep_ = new QPushButton(tr("Keep"), this); keep_->setObjectName("displayKeep");
        revert_ = new QPushButton(tr("Revert"), this); revert_->setObjectName("displayRevert");
        for (auto button : {reload_, apply_, keep_, revert_}) {
            button->setAutoDefault(false); row->addWidget(button);
        }
        form->addRow(row);
        status_ = new QLabel(this); status_->setWordWrap(true); status_->setMinimumHeight(status_->fontMetrics().lineSpacing() * 4); status_->setObjectName("displayStatus");
        form->addRow(status_);
        connect(output_, &QComboBox::currentIndexChanged, this, [this] { fillRates(); });
        connect(reload_, &QPushButton::clicked, this, [this] { query(); });
        connect(apply_, &QPushButton::clicked, this, [this] { apply(); });
        connect(keep_, &QPushButton::clicked, this, [this] { answer("keep\n"); });
        connect(revert_, &QPushButton::clicked, this, [this] { answer("revert\n"); });
        setBusy(true); QTimer::singleShot(0, this, [this] { query(); });
    }
    ~DoroDisplayControls() override {
        if (queryProcess_) { queryProcess_->disconnect(this); queryProcess_->kill(); }
        // Do not parent the guard to the window: QProcess destruction would kill rollback.
        if (guard_) { guard_->write("revert\n"); guard_->closeWriteChannel(); }
    }

    void cancelPending() {
        onKept_ = {};
        answer("revert\n");
        closeConfirmation();
    }
    bool hasPendingChanges() const {
        const auto outputs = state_[QStringLiteral("outputs")].toArray();
        if (rate_->isEnabled() && output_->currentIndex() >= 0 && output_->currentIndex() < outputs.size()
            && rate_->currentData().toString() != outputs[output_->currentIndex()].toObject()[QStringLiteral("current")].toString()) return true;
        return vsync_->isEnabled() && vsync_->isChecked() != bool(state_[QStringLiteral("vsync")].toInt());
    }
    // True defers dialog acceptance until the existing guarded transaction settles.
    bool submitFromDialog(std::function<void()> onKept = {}) {
        if (!guard_ && !hasPendingChanges()) return false;
        if (onKept) onKept_ = std::move(onKept);
        if (!guard_) apply();
        if (guard_) showConfirmation();
        else {
            onKept_ = {};
            auto error = new QMessageBox(QMessageBox::Warning, tr("Display changes not applied"), status_->text(), QMessageBox::Ok, this);
            error->setAttribute(Qt::WA_DeleteOnClose); error->open();
        }
        return true;
    }

private:
    QStringList helper_;
    QByteArray helperHash_;
    QByteArray verifiedHelper_;
    QJsonObject state_;
    QComboBox *output_, *rate_;
    QCheckBox *vsync_;
    QPushButton *reload_, *apply_, *keep_, *revert_;
    QLabel *status_;
    QPointer<QProcess> guard_;
    QPointer<QProcess> queryProcess_;
    QPointer<QDialog> confirmation_;
    QPointer<QDialog> failure_;
    QPointer<QLabel> confirmationStatus_;
    QPointer<QPushButton> confirmationKeep_, confirmationRevert_;
    std::function<void()> onKept_;

    void setStatus(const QString &text) {
        status_->setText(text);
        if (confirmationStatus_) confirmationStatus_->setText(text);
    }
    void showConfirmation() {
        if (confirmation_) { confirmation_->show(); confirmation_->raise(); return; }
        auto dialog = new QDialog(this); confirmation_ = dialog;
        dialog->setObjectName("displayConfirmation"); dialog->setWindowTitle(tr("Confirm display changes"));
        dialog->setWindowModality(Qt::WindowModal);
        auto layout = new QVBoxLayout(dialog);
        confirmationStatus_ = new QLabel(status_->text(), dialog); confirmationStatus_->setWordWrap(true);
        layout->addWidget(confirmationStatus_);
        auto row = new QHBoxLayout;
        confirmationKeep_ = new QPushButton(tr("Keep"), dialog); confirmationKeep_->setObjectName("confirmDisplayKeep");
        confirmationRevert_ = new QPushButton(tr("Revert"), dialog); confirmationRevert_->setObjectName("confirmDisplayRevert");
        for (auto button : {confirmationKeep_.data(), confirmationRevert_.data()}) { button->setAutoDefault(false); row->addWidget(button); }
        layout->addLayout(row); dialog->resize(440, 170);
        confirmationKeep_->setEnabled(keep_->isEnabled()); confirmationRevert_->setEnabled(revert_->isEnabled());
        connect(confirmationKeep_, &QPushButton::clicked, this, [this] { answer("keep\n"); });
        connect(confirmationRevert_, &QPushButton::clicked, this, [this] { answer("revert\n"); });
        connect(dialog, &QDialog::rejected, this, [this] { answer("revert\n"); });
        dialog->show(); confirmationRevert_->setFocus();
    }
    void showFailure(const QString &reason, const QJsonArray &differences = {}, const QJsonArray &diagnostics = {}) {
        closeConfirmation();
        if (failure_) { failure_->hide(); failure_->deleteLater(); }
        const bool saved = DoroDisplayFailure::record(reason, differences, diagnostics);
        auto dialog = new QDialog(this); failure_ = dialog;
        dialog->setAttribute(Qt::WA_DeleteOnClose);
        dialog->setObjectName("displayFailure"); dialog->setWindowTitle(tr("Display change failed — inspect settings"));
        dialog->setWindowModality(Qt::WindowModal);
        auto layout = new QVBoxLayout(dialog);
        auto label = new QLabel(tr("Display verification or recovery failed. Recovery is unverified. "
            "Inspect the actual refresh rate and restore it manually if needed. No automatic retry will be made.")
            + QStringLiteral("\n\n") + status_->text()
            + (saved ? tr("\n\nA redacted last-failure record was saved locally.") : tr("\n\nThe diagnostic record could not be saved.")), dialog);
        label->setObjectName("displayFailureText"); label->setTextFormat(Qt::PlainText); label->setWordWrap(true);
        layout->addWidget(label);
        auto buttons = new QDialogButtonBox(QDialogButtonBox::Close, dialog);
        buttons->setObjectName("displayFailureButtons"); layout->addWidget(buttons);
        connect(buttons, &QDialogButtonBox::rejected, dialog, &QDialog::reject);
        dialog->resize(500, 300); dialog->show(); buttons->button(QDialogButtonBox::Close)->setFocus();
    }
    void closeConfirmation() {
        if (confirmation_) { confirmation_->disconnect(this); confirmation_->hide(); confirmation_->deleteLater(); }
        confirmation_ = nullptr; confirmationStatus_ = nullptr; confirmationKeep_ = nullptr; confirmationRevert_ = nullptr;
    }

    void setBusy(bool busy) {
        output_->setEnabled(!busy && output_->count()); rate_->setEnabled(!busy && rate_->count());
        vsync_->setEnabled(!busy && state_.contains(QStringLiteral("vsync")) && !state_[QStringLiteral("vsync")].isNull());
        apply_->setEnabled(!busy && (rate_->count() || vsync_->isEnabled())); reload_->setEnabled(!busy);
        keep_->setVisible(bool(guard_)); revert_->setVisible(bool(guard_));
        keep_->setEnabled(false); revert_->setEnabled(false);
    }
    void fillRates() {
        rate_->clear();
        const auto outputs = state_[QStringLiteral("outputs")].toArray();
        if (output_->currentIndex() < 0 || output_->currentIndex() >= outputs.size()) return;
        auto output = outputs[output_->currentIndex()].toObject();
        for (const auto &entry : output[QStringLiteral("modes")].toArray()) {
            auto mode = entry.toObject();
            rate_->addItem(tr("%1 Hz (%2 × %3)").arg(mode[QStringLiteral("hz")].toString())
                .arg(mode[QStringLiteral("width")].toInt()).arg(mode[QStringLiteral("height")].toInt()), mode[QStringLiteral("id")].toString());
        }
        rate_->setCurrentIndex(rate_->findData(output[QStringLiteral("current")].toString()));
    }
    void start(QProcess *process, const QStringList &args) {
        if (helper_.isEmpty()) { setStatus(tr("Display helper is not configured.")); return; }
        if (!helperHash_.isEmpty()) {
            // Execute the bytes just verified, not a pathname that can change before exec.
            const auto loader = QStringLiteral("import sys; source=sys.argv.pop(2); __file__=sys.argv[1]; sys.argv=sys.argv[1:]; exec(compile(source,__file__,'exec'))");
            process->start(helper_.first(), QStringList{QStringLiteral("-c"), loader, helper_.value(1), QString::fromUtf8(verifiedHelper_)} + args);
        } else process->start(helper_.first(), helper_.mid(1) + args);
    }
    bool verifyHelper() {
        if (helperHash_.isEmpty()) return true; // Synthetic test harness supplies its own driver.
        QFile file(helper_.value(1));
        verifiedHelper_.clear();
        if (file.open(QIODevice::ReadOnly)) {
            auto bytes = file.readAll();
            if (QCryptographicHash::hash(bytes, QCryptographicHash::Sha256).toHex() == helperHash_) {
                verifiedHelper_ = bytes;
                return true;
            }
        }
        state_ = {}; output_->clear(); rate_->clear();
        vsync_->setTristate(true); vsync_->setCheckState(Qt::PartiallyChecked); setBusy(false);
        setStatus(tr("Display helper missing or changed. Restore the matching build; no display changes were applied."));
        return false;
    }
    void query(const QString &outcome = {}) {
        if (guard_ || queryProcess_) return;
        if (!verifyHelper()) {
            if (!outcome.isEmpty()) setStatus(outcome + QStringLiteral("\n") + status_->text());
            return;
        }
        setBusy(true); setStatus(outcome.isEmpty() ? tr("Reading display capabilities…") : outcome + tr("\nReading actual display state…"));
        auto process = new QProcess(this); queryProcess_ = process;
        auto timer = new QTimer(process); timer->setSingleShot(true); timer->start(12000);
        connect(timer, &QTimer::timeout, process, [process] { process->kill(); });
        connect(process, &QProcess::errorOccurred, this, [this, process, outcome](QProcess::ProcessError e) {
            if (e == QProcess::FailedToStart) {
                state_ = {}; output_->clear(); rate_->clear(); vsync_->setTristate(true); vsync_->setCheckState(Qt::PartiallyChecked); setBusy(false);
                queryProcess_ = nullptr;
                setStatus(outcome + tr("\nCannot start display helper. Actual state could not be read.")); process->deleteLater();
            }
        });
        connect(process, qOverload<int,QProcess::ExitStatus>(&QProcess::finished), this,
            [this, process, outcome](int code, QProcess::ExitStatus) {
                auto result = QJsonDocument::fromJson(process->readAllStandardOutput()).object();
                state_ = {}; output_->clear(); rate_->clear(); vsync_->setTristate(true); vsync_->setCheckState(Qt::PartiallyChecked);
                if (code == 0 && result.contains(QStringLiteral("token"))) {
                    state_ = result;
                    for (const auto &entry : result[QStringLiteral("outputs")].toArray()) output_->addItem(entry.toObject()[QStringLiteral("name")].toString());
                    fillRates();
                    vsync_->setTristate(result[QStringLiteral("vsync")].isNull());
                    vsync_->setCheckState(result[QStringLiteral("vsync")].isNull() ? Qt::PartiallyChecked : (result[QStringLiteral("vsync")].toInt() ? Qt::Checked : Qt::Unchecked));
                    setStatus(result[QStringLiteral("vsync_reason")].toString().isEmpty()
                        ? tr("Test changes, then Keep within 15 seconds. Rollback commands may take longer. Apply or OK also starts this guarded test.")
                        : result[QStringLiteral("vsync_reason")].toString());
                } else setStatus(result[QStringLiteral("error")].toString(tr("Could not read display capabilities. Reload to retry.")));
                if (!outcome.isEmpty()) setStatus(outcome + (code == 0 && result.contains(QStringLiteral("token"))
                    ? tr("\nActual state reloaded; this does not confirm recovery.") : tr("\nActual state could not be read. Reload to retry.")));
                queryProcess_ = nullptr; setBusy(false); process->deleteLater();
            });
        start(process, {QStringLiteral("query")});
    }
    void answer(const QByteArray &text) {
        if (!guard_) return;
        keep_->setEnabled(false); revert_->setEnabled(false);
        if (confirmationKeep_) confirmationKeep_->setEnabled(false);
        if (confirmationRevert_) confirmationRevert_->setEnabled(false);
        guard_->write(text); guard_->closeWriteChannel();
    }
    void apply() {
        if (guard_ || !state_.contains(QStringLiteral("token")) || !verifyHelper()) return;
        QJsonObject request{{QStringLiteral("token"), state_[QStringLiteral("token")]}};
        if (rate_->currentIndex() >= 0) {
            request[QStringLiteral("output")] = output_->currentText(); request[QStringLiteral("mode")] = rate_->currentData().toString();
        }
        if (vsync_->isEnabled()) request[QStringLiteral("vsync")] = vsync_->isChecked() ? 1 : 0;
        // Unparented intentionally: EOF on application exit asks the independent helper to revert.
        auto process = new QProcess; guard_ = process; setBusy(true);
        setStatus(tr("Testing display changes…"));
        connect(process, qOverload<int,QProcess::ExitStatus>(&QProcess::finished), process, &QObject::deleteLater);
        connect(process, &QProcess::errorOccurred, this, [this, process](QProcess::ProcessError e) {
            if (e == QProcess::FailedToStart) {
                guard_ = nullptr; closeConfirmation(); onKept_ = {}; setBusy(false); setStatus(tr("Cannot start display guard. No changes applied."));
                showFailure(QStringLiteral("guard_start_failed")); query(status_->text());
                process->deleteLater();
            }
        });
        connect(process, &QProcess::readyReadStandardOutput, this, [this, process] {
            while (process->canReadLine()) {
                const auto message = QJsonDocument::fromJson(process->readLine()).object();
                if (message[QStringLiteral("pending")].toBool()) {
                    keep_->setEnabled(true); revert_->setEnabled(true); revert_->setFocus();
                    if (confirmationKeep_) confirmationKeep_->setEnabled(true);
                    if (confirmationRevert_) { confirmationRevert_->setEnabled(true); confirmationRevert_->setFocus(); }
                    setStatus(tr("Keep these settings? Rollback starts after 15 seconds; driver commands may delay completion. Closing this window also requests rollback."));
                }
                if (message.contains(QStringLiteral("error")) || message[QStringLiteral("done")].toBool())
                    process->setProperty("displayTerminalMessage", true);
                if (message.contains(QStringLiteral("error"))) {
                    process->setProperty("displayError", true);
                    process->setProperty("displayDifferences", message[QStringLiteral("differences")].toArray());
                    process->setProperty("displayDiagnostics", message[QStringLiteral("diagnostics")].toArray());
                }
                if (message[QStringLiteral("done")].toBool()) process->setProperty("displayKept", message[QStringLiteral("kept")].toBool());
                if (message.contains(QStringLiteral("error"))) setStatus(message[QStringLiteral("error")].toString());
                if (message[QStringLiteral("done")].toBool()) setStatus(message[QStringLiteral("kept")].toBool()
                    ? tr("Kept for this session.")
                    : tr("Original settings restored."));
            }
        });
        connect(process, qOverload<int,QProcess::ExitStatus>(&QProcess::finished), this,
            [this, process](int code, QProcess::ExitStatus exitStatus) {
                const bool kept = code == 0 && exitStatus == QProcess::NormalExit && process->property("displayKept").toBool() && !process->property("displayError").toBool();
                auto callback = std::exchange(onKept_, {});
                closeConfirmation();
                guard_ = nullptr;
                state_ = {}; output_->clear(); rate_->clear(); vsync_->setTristate(true); vsync_->setCheckState(Qt::PartiallyChecked); setBusy(false);
                if (exitStatus == QProcess::CrashExit || !process->property("displayTerminalMessage").toBool()) setStatus(tr("Display guard stopped unexpectedly. Recovery is unverified; reload and inspect your display settings."));
                if (code != 0 || exitStatus != QProcess::NormalExit || process->property("displayError").toBool() || !process->property("displayTerminalMessage").toBool())
                    showFailure(process->property("displayError").toBool() ? QStringLiteral("guard_error") : QStringLiteral("abnormal_exit"),
                                process->property("displayDifferences").value<QJsonArray>(), process->property("displayDiagnostics").value<QJsonArray>());
                if (kept && callback) QTimer::singleShot(0, this, std::move(callback));
                else query(status_->text());
            });
        start(process, {QStringLiteral("apply"), QString::fromUtf8(QJsonDocument(request).toJson(QJsonDocument::Compact))});
    }
};
