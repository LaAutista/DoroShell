// SPDX-License-Identifier: GPL-2.0-or-later
// Native PCManFM Advanced-tab controls; the helper owns the confirmation deadline.
#pragma once
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
        // Do not parent the guard to the window: QProcess destruction would kill rollback.
        if (guard_) { guard_->write("revert\n"); guard_->closeWriteChannel(); }
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
        if (helper_.isEmpty()) { status_->setText(tr("Display helper is not configured.")); return; }
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
        status_->setText(tr("Display helper missing or changed. Restore the matching build; no display changes were applied."));
        return false;
    }
    void query() {
        if (guard_ || !verifyHelper()) return;
        setBusy(true); status_->setText(tr("Reading display capabilities…"));
        auto process = new QProcess(this);
        auto timer = new QTimer(process); timer->setSingleShot(true); timer->start(12000);
        connect(timer, &QTimer::timeout, process, [process] { process->kill(); });
        connect(process, &QProcess::errorOccurred, this, [this, process](QProcess::ProcessError e) {
            if (e == QProcess::FailedToStart) {
                state_ = {}; output_->clear(); rate_->clear(); vsync_->setTristate(true); vsync_->setCheckState(Qt::PartiallyChecked); setBusy(false);
                status_->setText(tr("Cannot start display helper.")); process->deleteLater();
            }
        });
        connect(process, qOverload<int,QProcess::ExitStatus>(&QProcess::finished), this,
            [this, process](int code, QProcess::ExitStatus) {
                auto result = QJsonDocument::fromJson(process->readAllStandardOutput()).object();
                state_ = {}; output_->clear(); rate_->clear(); vsync_->setTristate(true); vsync_->setCheckState(Qt::PartiallyChecked);
                if (code == 0 && result.contains(QStringLiteral("token"))) {
                    state_ = result;
                    for (const auto &entry : result[QStringLiteral("outputs")].toArray()) output_->addItem(entry.toObject()[QStringLiteral("name")].toString());
                    fillRates();
                    vsync_->setTristate(result[QStringLiteral("vsync")].isNull());
                    vsync_->setCheckState(result[QStringLiteral("vsync")].isNull() ? Qt::PartiallyChecked : (result[QStringLiteral("vsync")].toInt() ? Qt::Checked : Qt::Unchecked));
                    status_->setText(result[QStringLiteral("vsync_reason")].toString().isEmpty()
                        ? tr("Test changes, then Keep within 15 seconds. Rollback commands may take longer. Use these buttons; PCManFM Apply does not apply display changes.")
                        : result[QStringLiteral("vsync_reason")].toString());
                } else status_->setText(result[QStringLiteral("error")].toString(tr("Could not read display capabilities. Reload to retry.")));
                setBusy(false); process->deleteLater();
            });
        start(process, {QStringLiteral("query")});
    }
    void answer(const QByteArray &text) {
        if (!guard_) return;
        keep_->setEnabled(false); revert_->setEnabled(false);
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
        status_->setText(tr("Testing display changes…"));
        connect(process, qOverload<int,QProcess::ExitStatus>(&QProcess::finished), process, &QObject::deleteLater);
        connect(process, &QProcess::errorOccurred, this, [this, process](QProcess::ProcessError e) {
            if (e == QProcess::FailedToStart) {
                guard_ = nullptr; setBusy(false); status_->setText(tr("Cannot start display guard. No changes applied."));
                process->deleteLater();
            }
        });
        connect(process, &QProcess::readyReadStandardOutput, this, [this, process] {
            while (process->canReadLine()) {
                const auto message = QJsonDocument::fromJson(process->readLine()).object();
                if (message[QStringLiteral("pending")].toBool()) {
                    keep_->setEnabled(true); revert_->setEnabled(true); revert_->setFocus();
                    status_->setText(tr("Keep these settings? Rollback starts after 15 seconds; driver commands may delay completion. Closing this window also requests rollback."));
                }
                if (message.contains(QStringLiteral("error")) || message[QStringLiteral("done")].toBool())
                    process->setProperty("displayTerminalMessage", true);
                if (message.contains(QStringLiteral("error"))) status_->setText(message[QStringLiteral("error")].toString());
                if (message[QStringLiteral("done")].toBool()) status_->setText(message[QStringLiteral("kept")].toBool()
                    ? tr("Kept for this session. Reload before making another change.")
                    : tr("Original settings restored. Reload before making another change."));
            }
        });
        connect(process, qOverload<int,QProcess::ExitStatus>(&QProcess::finished), this,
            [this, process](int, QProcess::ExitStatus exitStatus) {
                guard_ = nullptr;
                state_ = {}; output_->clear(); rate_->clear(); vsync_->setTristate(true); vsync_->setCheckState(Qt::PartiallyChecked); setBusy(false);
                if (exitStatus == QProcess::CrashExit || !process->property("displayTerminalMessage").toBool()) status_->setText(tr("Display guard stopped unexpectedly. Recovery is unverified; reload and inspect your display settings."));
            });
        start(process, {QStringLiteral("apply"), QString::fromUtf8(QJsonDocument(request).toJson(QJsonDocument::Compact))});
    }
};
