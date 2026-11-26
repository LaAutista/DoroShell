// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once
#include <atomic>
#include <QtGlobal>
#include <QImage>
#include <cstring>
struct DoroVideoSlot { std::atomic<quint32> sequence{0}; quint32 width=0, height=0; };
struct DoroVideoHeader {
    std::atomic<quint32> current{0};
    std::atomic<qint64> position{0};
    std::atomic<int> state{0};
    DoroVideoSlot buffers[2];
};
static_assert(std::atomic<quint32>::is_always_lock_free && std::atomic<qint64>::is_always_lock_free);

inline void doroCopyVideoPixels(char* destination, const QImage& image) {
    const size_t stride=size_t(image.width())*4;
    for(int row=0;row<image.height();++row)
        std::memcpy(destination+size_t(row)*stride,image.constScanLine(row),stride);
}
