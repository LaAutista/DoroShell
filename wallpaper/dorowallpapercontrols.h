// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QWidget>
#include <QFormLayout>
#include <QComboBox>
#include <QCheckBox>
#include <QLineEdit>
#include <QPushButton>
#include <QSlider>
#include <QGroupBox>
#include <QStyle>
#include <QLabel>
#include <QFileDialog>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSaveFile>
#include <QLockFile>
#include <QStandardPaths>
#include <QDir>
#include <QProcess>

class DoroWallpaperControls : public QGroupBox {
public:
    explicit DoroWallpaperControls(QWidget* parent=nullptr): QGroupBox(tr("Animated Wallpaper"), parent) {
        path_=QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation)+QStringLiteral("/doroshell/wallpaper.json");
        QFile file(path_); existed_=file.exists();
        if(existed_ && !file.open(QIODevice::ReadOnly)) valid_=false;
        baseline_=file.readAll();
        QJsonParseError error; auto document=QJsonDocument::fromJson(baseline_, &error);
        if(existed_ && (error.error!=QJsonParseError::NoError || !document.isObject())) valid_=false;
        values_=document.object();
        preview_.setParent(this);preview_.setObjectName(QStringLiteral("wallpaperPreviewProcess"));
        auto form=new QFormLayout(this);
        type_=new QComboBox; type_->setObjectName(QStringLiteral("wallpaperType"));type_->addItems({tr("Static image"),tr("Animated video / GIF")});type_->setCurrentIndex(values_[QStringLiteral("enabled")].toBool()?1:0);form->addRow(tr("Wallpaper type:"),type_);
        media_=new QLineEdit(values_[QStringLiteral("file")].toString());media_->setObjectName(QStringLiteral("wallpaperMedia"));
        auto row=new QHBoxLayout;row->addWidget(media_);auto browse=new QPushButton(tr("Browse"));row->addWidget(browse);form->addRow(tr("Video or GIF:"),row);
        connect(browse,&QPushButton::clicked,this,[this]{auto file=QFileDialog::getOpenFileName(this,tr("Choose animated wallpaper"),media_->text(),tr("Media (*.mp4 *.webm *.mkv *.mov *.gif);;All files (*)"));if(!file.isEmpty())media_->setText(file);});
        // The approved layout omits fit; retain the existing controller's choice.
        fit_=new QComboBox(this);fit_->addItems({QStringLiteral("fit"),QStringLiteral("crop"),QStringLiteral("stretch")});fit_->setCurrentText(values_[QStringLiteral("fit")].toString(QStringLiteral("crop")));fit_->hide();
        fullscreen_=new QCheckBox(tr("Pause when fullscreen"));fullscreen_->setChecked(values_[QStringLiteral("pause_fullscreen")].toBool(true));form->addRow(fullscreen_);
        mute_=new QCheckBox(tr("Mute audio"));mute_->setChecked(values_[QStringLiteral("muted")].toBool(true));form->addRow(mute_);
        fps_=new QComboBox;for(int fps: {15,30,60})fps_->addItem(tr("%1 FPS").arg(fps),fps);fps_->setCurrentIndex(fps_->findData(values_[QStringLiteral("fps")].toInt(30)));
        auto fpsRow=new QHBoxLayout;fpsRow->addWidget(fps_,1);fpsRow->addStretch(1);form->addRow(tr("Frame rate limit:"),fpsRow);
        volume_=new QSlider(Qt::Horizontal);volume_->setObjectName(QStringLiteral("wallpaperVolume"));volume_->setRange(0,100);volume_->setValue(values_[QStringLiteral("volume")].toInt(100));
        auto volumeText=new QLabel(QString::number(volume_->value())+QStringLiteral("%"));auto volumeRow=new QHBoxLayout;volumeRow->addWidget(volume_,2);volumeRow->addWidget(volumeText);volumeRow->addStretch(1);form->addRow(tr("Volume:"),volumeRow);
        connect(volume_,&QSlider::valueChanged,this,[volumeText](int value){volumeText->setText(QString::number(value)+QStringLiteral("%"));});
        auto updateMute=[this,volumeText]{volume_->setEnabled(!mute_->isChecked());volumeText->setEnabled(!mute_->isChecked());};connect(mute_,&QCheckBox::toggled,this,updateMute);updateMute();
        auto buttons=new QHBoxLayout;auto preview=new QPushButton(style()->standardIcon(QStyle::SP_MediaPlay),tr("Preview"));preview->setObjectName(QStringLiteral("wallpaperPreview"));auto stop=new QPushButton(style()->standardIcon(QStyle::SP_MediaStop),tr("Stop"));stop->setObjectName(QStringLiteral("wallpaperStop"));stop->setEnabled(false);buttons->addWidget(preview);buttons->addWidget(stop);buttons->addStretch();form->addRow(buttons);
        preview->setToolTip(tr("Preview in a separate silent window; desktop settings are unchanged."));
        connect(&preview_,&QProcess::stateChanged,this,[stop](QProcess::ProcessState state){stop->setEnabled(state!=QProcess::NotRunning);});
        status_=new QLabel;status_->setWordWrap(true);status_->setObjectName(QStringLiteral("wallpaperStatus"));form->addRow(status_);status_->hide();
        connect(preview,&QPushButton::clicked,this,[this]{startPreview();});connect(stop,&QPushButton::clicked,this,[this]{stopPreview();});
        connect(&preview_,&QProcess::errorOccurred,this,[this]{status_->show();status_->setText(tr("Preview failed: ")+preview_.errorString());stopPreview();});
        connect(&preview_,&QProcess::finished,this,[this](int code,QProcess::ExitStatus){if(code!=0){status_->show();status_->setText(tr("Preview ended without playing. Check the local media file."));}});
        initial_=selection();
        if(!valid_){status_->show();status_->setText(tr("Cannot read wallpaper settings. No changes will be saved."));}
    }
    ~DoroWallpaperControls() override {stopPreview();}
    void stopPreview() {if(preview_.state()!=QProcess::NotRunning){preview_.terminate();if(!preview_.waitForFinished(500)){preview_.kill();preview_.waitForFinished(500);}}}
    bool apply() {
        stopPreview();
        auto fail=[this](const QString& message){status_->show();status_->setText(message);return false;};
        if(!valid_)return fail(tr("Invalid wallpaper configuration; repair it before saving."));
        auto next=selection();
        if(next==initial_) return true;
        if(next[QStringLiteral("enabled")].toBool() && !localMedia())return fail(tr("Choose an existing absolute local media file."));
        if(!QDir().mkpath(QFileInfo(path_).absolutePath()))return fail(tr("Cannot create settings directory."));
        QLockFile lock(path_+QStringLiteral(".lock"));if(!lock.tryLock(0))return fail(tr("Wallpaper settings are busy."));
        QFile current(path_);if(current.exists()!=existed_ || QFileInfo(path_).isSymLink() || (existed_ && !current.open(QIODevice::ReadOnly)) || current.readAll()!=baseline_)return fail(tr("Wallpaper settings changed elsewhere; reopen Preferences."));
        if(existed_ && !QFile::exists(path_+QStringLiteral(".before-native-prefs"))) {
            QFile backup(path_+QStringLiteral(".before-native-prefs"));if(!backup.open(QIODevice::WriteOnly|QIODevice::NewOnly))return fail(tr("Cannot create wallpaper backup."));
            backup.setPermissions(QFile::ReadOwner|QFile::WriteOwner);
            if(backup.write(baseline_)!=baseline_.size() || !backup.flush()){backup.remove();return fail(tr("Cannot write wallpaper backup."));}
        }
        next[QStringLiteral("generation")]=values_[QStringLiteral("generation")].toInt()+1;
        auto bytes=QJsonDocument(next).toJson();QSaveFile output(path_);if(!output.open(QIODevice::WriteOnly))return fail(tr("Cannot save wallpaper settings."));output.setPermissions(QFile::ReadOwner|QFile::WriteOwner);
        if(output.write(bytes)!=bytes.size() || !output.commit())return fail(tr("Could not save wallpaper settings; previous settings retained."));
        baseline_=bytes;values_=next;initial_=selection();existed_=true;status_->show();status_->setText(tr("Wallpaper settings saved."));return true;
    }
private:
    QJsonObject selection() const {
        auto next=values_;next[QStringLiteral("enabled")]=type_->currentIndex()==1;next[QStringLiteral("file")]=media_->text();next[QStringLiteral("fit")]=fit_->currentText();next[QStringLiteral("fps")]=fps_->currentData().toInt();next[QStringLiteral("muted")]=mute_->isChecked();next[QStringLiteral("volume")]=volume_->value();next[QStringLiteral("pause_fullscreen")]=fullscreen_->isChecked();
        return next;
    }
    bool localMedia() const {QFileInfo info(media_->text());return info.isAbsolute() && info.isFile() && info.isReadable();}
    void startPreview() {
        stopPreview();if(!localMedia()){status_->show();status_->setText(tr("Choose an existing absolute local media file."));return;}
        auto mpv=QStandardPaths::findExecutable(QStringLiteral("mpv"));if(mpv.isEmpty()){status_->show();status_->setText(tr("Install optional mpv to preview."));return;}
        preview_.setStandardOutputFile(QProcess::nullDevice());preview_.setStandardErrorFile(QProcess::nullDevice());
        preview_.start(mpv,{QStringLiteral("--no-config"),QStringLiteral("--mute=yes"),QStringLiteral("--audio=no"),QStringLiteral("--loop-file=inf"),QStringLiteral("--title=DoroShell wallpaper preview"),QStringLiteral("--"),media_->text()});
    }
    QString path_;QByteArray baseline_;QJsonObject values_,initial_;bool existed_=false,valid_=true;
    QComboBox *type_,*fit_,*fps_;QLineEdit* media_;QCheckBox *fullscreen_,*mute_;QSlider* volume_;QLabel* status_;QProcess preview_;
};
