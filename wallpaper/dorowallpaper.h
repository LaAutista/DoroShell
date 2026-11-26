// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <QWidget>
#include <QProcess>
#include <cstddef>
#include <QMovie>
#include <QElapsedTimer>
#include <QJsonObject>
#include <memory>

// Paint into the existing desktop background; never add an input/desktop layer.
class DoroWallpaper : public QObject {
public:
    explicit DoroWallpaper(QWidget* desktop);
    ~DoroWallpaper() override;
    bool paint(QPainter& painter, const QRect& area);
private:
    void tick();
    void stopWorker();
    void startWorker(const QString& file);
    void receiveFrame();
    void frame(const QImage& image);
    QWidget* desktop_;
    QProcess* worker_ = nullptr;
    void* memory_ = nullptr;
    int memoryFd_ = -1;
    size_t memorySize_ = 0;
    QByteArray command_, messages_;
    qint64 capacity_ = 0;
    quint32 sequence_ = 0;
    bool playing_ = false;
    QMovie movie_;
    QImage image_;
    QElapsedTimer throttle_;
    QString identity_, fit_, statusPath_;
    qint64 frames_ = 0, paints_ = 0;
    int fps_ = 30;
    bool failed_ = false, enabled_ = false, locked_ = true, lockQuery_ = false;
    QString error_;
};
