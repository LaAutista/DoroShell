// SPDX-License-Identifier: GPL-2.0-or-later
#include "dorowallpaper.h"
#include <QPainter>
#include "dorovideotransport.h"
#include <sys/mman.h>
#include <sys/prctl.h>
#include <signal.h>
#include <unistd.h>
#include <fcntl.h>
#include <cstring>
#include <new>
#include <QTimer>
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonArray>
#include <QStandardPaths>
#include <QScreen>
#include <QSaveFile>
#include <QDBusConnection>
#include <QDBusMessage>
#include <QDBusPendingCallWatcher>
#include <QDBusPendingReply>
#include <QDBusVariant>
#include <KX11Extras>
#include <KWindowInfo>
#include <X11/Xlib.h>
#include <X11/extensions/dpms.h>
#include <X11/extensions/scrnsaver.h>

DoroWallpaper::DoroWallpaper(QWidget* desktop) : QObject(desktop), desktop_(desktop) {
    throttle_.start();
    connect(&movie_, &QMovie::frameChanged, this, [this] { frame(movie_.currentImage()); });
    connect(&movie_, &QMovie::finished, this, [this] { if (enabled_ && !failed_) movie_.start(); });
    connect(&movie_, &QMovie::error, this, [this] { failed_ = true; error_ = movie_.lastErrorString(); });
    auto timer = new QTimer(this);
    connect(timer, &QTimer::timeout, this, [this] { tick(); });
    timer->start(500);
    tick();
}

DoroWallpaper::~DoroWallpaper() {
    stopWorker();
    QFile status(statusPath_);
    if (status.open(QIODevice::ReadOnly) && QJsonDocument::fromJson(status.readAll()).object().value(QStringLiteral("pid")).toInteger() == QCoreApplication::applicationPid()) {
        status.close(); status.remove();
    }
}

void DoroWallpaper::stopWorker() {
    playing_ = false;
    auto old = worker_; worker_ = nullptr;
    if (old) {
        old->setParent(QCoreApplication::instance());
        old->disconnect(this);
        connect(old, qOverload<int,QProcess::ExitStatus>(&QProcess::finished), old, &QObject::deleteLater);
        old->closeWriteChannel(); old->terminate();
        QTimer::singleShot(1000, old, [old] { if(old->state()!=QProcess::NotRunning) old->kill(); else old->deleteLater(); });
    }
    if(memory_) munmap(memory_,memorySize_);
    if(memoryFd_>=0) ::close(memoryFd_);
    memory_=nullptr; memoryFd_=-1; command_.clear(); messages_.clear(); sequence_=0;
}

void DoroWallpaper::startWorker(const QString& file) {
    const QSize size = desktop_->screen()->size()*desktop_->screen()->devicePixelRatio();
    if(size.isEmpty() || size.width()>16384 || size.height()>16384 || qint64(size.width())*size.height()>33554432) { failed_=true; error_=QStringLiteral("Unsupported desktop size"); return; }
    capacity_=qint64(size.width())*size.height()*4;
    memorySize_=sizeof(DoroVideoHeader)+2*capacity_;
    memoryFd_=memfd_create("doroshell-video",MFD_CLOEXEC);
    if(memoryFd_<0 || ftruncate(memoryFd_,off_t(memorySize_))!=0) {stopWorker();failed_=true;error_=QStringLiteral("Cannot allocate video transport");return;}
    memory_=mmap(nullptr,memorySize_,PROT_READ|PROT_WRITE,MAP_SHARED,memoryFd_,0);
    if(memory_==MAP_FAILED) {memory_=nullptr;stopWorker();failed_=true;error_=QStringLiteral("Cannot map video transport");return;}
    new(memory_) DoroVideoHeader;
    worker_=new QProcess(this);
    auto process = worker_;
    connect(worker_, &QProcess::readyReadStandardOutput, this, &DoroWallpaper::receiveFrame);
    connect(worker_, &QProcess::errorOccurred, this, [this,process](QProcess::ProcessError){if(worker_==process){failed_=true; error_=process->errorString();}});
    connect(worker_, qOverload<int,QProcess::ExitStatus>(&QProcess::finished), this, [this,process](int,QProcess::ExitStatus){if(worker_==process){failed_=true;error_=QStringLiteral("Video worker stopped");}});
    worker_->setProcessChannelMode(QProcess::ForwardedErrorChannel);
    const int fd=memoryFd_;
    const pid_t parent=getpid();
    worker_->setChildProcessModifier([fd,parent] {
        if(prctl(PR_SET_PDEATHSIG,SIGKILL)!=0 || getppid()!=parent || dup2(fd,198)<0 || fcntl(198,F_SETFD,0)<0) _exit(3);
    });
    worker_->start(QCoreApplication::applicationDirPath()+QStringLiteral("/doroshell-video-worker"),{QStringLiteral("198"),QString::number(size.width()),QString::number(size.height()),file});
}

void DoroWallpaper::receiveFrame() {
    messages_ += worker_->readAllStandardOutput();
    if(messages_.size()>65536) {failed_=true;error_=QStringLiteral("Invalid video worker output");return;}
    bool ready=false;
    while(messages_.contains('\n')) {
        const auto end=messages_.indexOf('\n'); const QByteArray line=messages_.left(end);messages_.remove(0,end+1);
        if(line=="f") ready=true;
        else if(line.startsWith('e')) {failed_=true;error_=QJsonDocument::fromJson(line.mid(1)).object().value(QStringLiteral("error")).toString();}
    }
    if(!ready || !playing_ || !memory_ || failed_) return;
    auto header=static_cast<DoroVideoHeader*>(memory_);
    const quint32 slot=header->current.load(std::memory_order_acquire);
    if(slot>1) return;
    const auto& info=header->buffers[slot]; const quint32 before=info.sequence.load(std::memory_order_acquire);
    const auto width=info.width,height=info.height;
    if((before&1) || !width || !height || width>16384 || height>16384 || qint64(width)*height*4>capacity_) return;
    const auto bytes=reinterpret_cast<uchar*>(memory_)+sizeof(DoroVideoHeader)+capacity_*slot;
    QImage image(bytes,width,height,width*4,QImage::Format_RGB32);
    QImage copy=image.copy();
    if(before!=info.sequence.load(std::memory_order_acquire)) return;
    frame(copy);
}

void DoroWallpaper::frame(const QImage& image) {
    if (!enabled_ || failed_ || image.isNull()) return;
    ++frames_;
    image_ = image;
    throttle_.restart();
    desktop_->update();
}

bool DoroWallpaper::paint(QPainter& p, const QRect& area) {
    if (!enabled_ || failed_ || image_.isNull()) return false;
    ++paints_;
    p.fillRect(area, Qt::black);
    QRect target = area;
    if (fit_ != QStringLiteral("stretch")) {
        QSize size = image_.size();
        size.scale(area.size(), fit_ == QStringLiteral("crop") ? Qt::KeepAspectRatioByExpanding : Qt::KeepAspectRatio);
        target = QRect(QPoint(), size); target.moveCenter(area.center());
    }
    p.setClipRect(area);
    p.drawImage(target, image_);
    return true;
}

void DoroWallpaper::tick() {
    QFile input(QStandardPaths::writableLocation(QStandardPaths::ConfigLocation) + QStringLiteral("/doroshell/wallpaper.json"));
    QJsonObject cfg;
    if (input.open(QIODevice::ReadOnly)) cfg = QJsonDocument::fromJson(input.readAll()).object();
    const QString file = cfg.value(QStringLiteral("file")).toString();
    const QString monitor = cfg.value(QStringLiteral("monitor")).toString(QStringLiteral("all"));
    const QScreen* screen = desktop_->screen();
    enabled_ = cfg.value(QStringLiteral("enabled")).toBool() && screen &&
        (monitor == QStringLiteral("all") || monitor == screen->name()) && QGuiApplication::platformName() == QStringLiteral("xcb");
    if (!enabled_) locked_ = true;
    // Async logind query avoids blocking desktop input; an unknown lock state pauses playback.
    if (enabled_ && !lockQuery_) {
        lockQuery_ = true;
        auto request = QDBusMessage::createMethodCall(QStringLiteral("org.freedesktop.login1"),
            QStringLiteral("/org/freedesktop/login1/session/auto"), QStringLiteral("org.freedesktop.DBus.Properties"), QStringLiteral("Get"));
        request << QStringLiteral("org.freedesktop.login1.Session") << QStringLiteral("LockedHint");
        auto watcher = new QDBusPendingCallWatcher(QDBusConnection::systemBus().asyncCall(request, 1500), this);
        connect(watcher, &QDBusPendingCallWatcher::finished, this, [this, watcher] {
            QDBusPendingReply<QDBusVariant> reply = *watcher;
            locked_ = reply.isError() || reply.value().variant().toBool();
            lockQuery_ = false; watcher->deleteLater();
        });
    }
    // Disabled means no media source or decoder allocation, even when a file is selected.
    const QString identity = enabled_ ? file + QString::number(cfg.value(QStringLiteral("generation")).toInteger()) : QString();
    if (identity != identity_) {
        stopWorker();
        movie_.stop();
        if (!image_.isNull()) { image_ = QImage(); desktop_->update(); }
        identity_ = identity; failed_ = false; error_.clear();
        if (enabled_ && !file.isEmpty() && (!QFileInfo(file).isFile() || !QFileInfo(file).isAbsolute())) {
            failed_ = true; error_ = QStringLiteral("Choose an existing absolute local media path");
        }
        const bool gif = enabled_ && file.endsWith(QStringLiteral(".gif"), Qt::CaseInsensitive);
        movie_.setFileName(gif ? file : QString());
        if (enabled_ && !gif && !file.isEmpty() && !failed_) startWorker(file);
    }
    fps_ = qBound(1, cfg.value(QStringLiteral("fps")).toInt(30), 60);
    const QString fit = cfg.value(QStringLiteral("fit")).toString(QStringLiteral("crop"));
    if (fit != fit_) { fit_ = fit; desktop_->update(); }

    QStringList reasons;
    if (!enabled_) reasons << QStringLiteral("disabled");
    if (file.isEmpty()) reasons << QStringLiteral("no media");
    if (failed_) reasons << QStringLiteral("renderer error");
    if (cfg.value(QStringLiteral("paused")).toBool()) reasons << QStringLiteral("manual");
    if (enabled_ && locked_) reasons << QStringLiteral("locked or lock state unavailable");
    Display* display = enabled_ ? XOpenDisplay(nullptr) : nullptr;
    if (display) {
        int event, error;
        if (DPMSQueryExtension(display, &event, &error)) {
            CARD16 level; BOOL on;
            if (DPMSInfo(display, &level, &on) && on && level != DPMSModeOn) reasons << QStringLiteral("display off");
        }
        if (XScreenSaverQueryExtension(display, &event, &error)) {
            XScreenSaverInfo* info = XScreenSaverAllocInfo();
            if (XScreenSaverQueryInfo(display, DefaultRootWindow(display), info) && info->state == ScreenSaverOn)
                reasons << QStringLiteral("screen saver");
            XFree(info);
        }
        XCloseDisplay(display);
    } else if (enabled_) reasons << QStringLiteral("display unavailable");
    if (enabled_ && cfg.value(QStringLiteral("pause_fullscreen")).toBool(true)) {
        for (WId wid : KX11Extras::windows()) {
            KWindowInfo info(wid, NET::WMState | NET::WMDesktop | NET::WMGeometry);
            if (info.valid() && !info.isMinimized() && info.isOnDesktop(KX11Extras::currentDesktop()) &&
                (info.state() & NET::FullScreen) && info.geometry().intersects(screen->geometry())) {
                reasons << QStringLiteral("fullscreen"); break;
            }
        }
    }
    const bool play = reasons.isEmpty();
    if (!enabled_ || failed_) {
        if (failed_) stopWorker();
        if (movie_.state() != QMovie::NotRunning) movie_.stop();
        // Restore the static background once; idle/error ticks must not repaint it.
        if (!image_.isNull()) { image_ = QImage(); desktop_->update(); }
    }
    else if (file.endsWith(QStringLiteral(".gif"), Qt::CaseInsensitive)) {
        if (play && movie_.state() == QMovie::NotRunning) movie_.start();
        movie_.setPaused(!play);
    }
    playing_ = play;
    if (worker_) {
        const QByteArray command = QJsonDocument(QJsonObject{{QStringLiteral("play"),play},{QStringLiteral("muted"),cfg.value(QStringLiteral("muted")).toBool(true)},{QStringLiteral("fps"),fps_}}).toJson(QJsonDocument::Compact)+'\n';
        if (command != command_) { command_ = command; worker_->write(command); }
    }
    if (screen) {
        QString name = screen->name(); name.replace(QLatin1Char('/'), QLatin1Char('_'));
        statusPath_ = QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation) + QStringLiteral("/doroshell-wallpaper-") + name + QStringLiteral(".json");
        QSaveFile status(statusPath_);
        if (status.open(QIODevice::WriteOnly)) {
            status.write(QJsonDocument(QJsonObject{{QStringLiteral("pid"),QCoreApplication::applicationPid()},{QStringLiteral("binary"),QCoreApplication::applicationFilePath()},{QStringLiteral("display"),qEnvironmentVariable("DISPLAY")},{QStringLiteral("media_loaded"),bool(worker_)},{QStringLiteral("frames"),frames_},{QStringLiteral("paints"),paints_},{QStringLiteral("video_state"),memory_ ? static_cast<DoroVideoHeader*>(memory_)->state.load() : 0},{QStringLiteral("video_position_ms"),memory_ ? static_cast<DoroVideoHeader*>(memory_)->position.load() : qint64(0)},{QStringLiteral("playing"),play},{QStringLiteral("reasons"),QJsonArray::fromStringList(reasons)},{QStringLiteral("error"),error_}}).toJson());
            status.commit();
        }
    }
}
