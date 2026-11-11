// SPDX-License-Identifier: GPL-2.0-or-later
#include "dorovideotransport.h"
#include <QApplication>
#include <sys/mman.h>
#include <sys/stat.h>
#include <QMediaPlayer>
#include <QAudioOutput>
#include <QVideoSink>
#include <QVideoFrame>
#include <QElapsedTimer>
#include <QSocketNotifier>
#include <QJsonDocument>
#include <QJsonObject>
#include <QImage>
#include <unistd.h>
#include <cstring>
int main(int argc, char** argv) {
    QApplication app(argc,argv);
    app.setQuitOnLastWindowClosed(false);
    if (argc != 5) return 2;
    const int width=QString::fromLocal8Bit(argv[2]).toInt(), height=QString::fromLocal8Bit(argv[3]).toInt();
    if(width<1 || height<1 || width>16384 || height>16384 || qint64(width)*height>33554432) return 2;
    const qint64 capacity=qint64(width)*height*4;
    const int fd=QString::fromLocal8Bit(argv[1]).toInt();
    const size_t bytes=sizeof(DoroVideoHeader)+2*capacity;
    struct stat info;
    if(fd!=198 || fstat(fd,&info)!=0 || info.st_size!=off_t(bytes)) return 3;
    void* memory=mmap(nullptr,bytes,PROT_READ|PROT_WRITE,MAP_SHARED,fd,0);
    ::close(fd); if(memory==MAP_FAILED) return 3;
    auto header=static_cast<DoroVideoHeader*>(memory);
    auto data=reinterpret_cast<char*>(memory)+sizeof(DoroVideoHeader);
    QMediaPlayer player; QVideoSink sink; QAudioOutput audio;
    audio.setMuted(true); player.setAudioOutput(&audio); player.setVideoSink(&sink); player.setLoops(QMediaPlayer::Infinite);
    QElapsedTimer throttle; throttle.start(); int fps=30; bool play=false;
    QObject::connect(&sink,&QVideoSink::videoFrameChanged,&app,[&](const QVideoFrame& frame){
        if(!play || throttle.elapsed()<1000/fps) return;
        QImage image=frame.toImage(); if(image.isNull()) return;
        if(image.width()>width || image.height()>height) image=image.scaled(width,height,Qt::KeepAspectRatio,Qt::FastTransformation);
        image=image.convertToFormat(QImage::Format_RGB32);
        const quint32 slot=1-header->current.load(std::memory_order_acquire);
        auto& info=header->buffers[slot];
        info.sequence.fetch_add(1,std::memory_order_acq_rel);
        info.width=image.width(); info.height=image.height();
        doroCopyVideoPixels(data+capacity*slot,image);
        info.sequence.fetch_add(1,std::memory_order_release);
        header->position.store(player.position(),std::memory_order_relaxed);
        header->current.store(slot,std::memory_order_release);
        throttle.restart();
        if(::write(STDOUT_FILENO,"f\n",2)<0) app.quit();
    });
    QObject::connect(&player,&QMediaPlayer::playbackStateChanged,&app,[&](QMediaPlayer::PlaybackState state){header->state.store(int(state));});
    QObject::connect(&player,&QMediaPlayer::errorOccurred,&app,[&](QMediaPlayer::Error,const QString& error){
        QByteArray message="e"+QJsonDocument(QJsonObject{{QStringLiteral("error"),error.left(1024)}}).toJson(QJsonDocument::Compact)+'\n';
        ::write(STDOUT_FILENO,message.constData(),size_t(message.size())); player.stop();
    });
    QByteArray input;
    QSocketNotifier notifier(STDIN_FILENO,QSocketNotifier::Read);
    QObject::connect(&notifier,&QSocketNotifier::activated,&app,[&]{
        char bytes[4096]; const auto n=::read(STDIN_FILENO,bytes,sizeof(bytes));
        if(n<=0){app.quit();return;} input.append(bytes,n);
        if(input.size()>16384){app.quit();return;}
        while(input.contains('\n')){
            const auto end=input.indexOf('\n'); const auto cfg=QJsonDocument::fromJson(input.left(end)).object(); input.remove(0,end+1);
            fps=qBound(1,cfg.value(QStringLiteral("fps")).toInt(30),60); audio.setMuted(cfg.value(QStringLiteral("muted")).toBool(true));
            audio.setVolume(qBound(0, cfg.value(QStringLiteral("volume")).toInt(100), 100)/100.0f);
            play=cfg.value(QStringLiteral("play")).toBool(); if(play) player.play(); else player.pause();
        }
    });
    player.setSource(QUrl::fromLocalFile(QString::fromLocal8Bit(argv[4])));
    return app.exec();
}
