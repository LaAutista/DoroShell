// SPDX-License-Identifier: GPL-2.0-or-later
#pragma once

#include <QImage>
#include <QScopeGuard>
#include <QVideoFrame>
#include <utility>
#include <vector>

// Source column or row that Qt's fast scaling reads for each destination one. The
// original path converts the whole frame and then scales it; reading luma at these
// indices and chroma at half of them selects exactly the samples it would have used.
// Scaling each plane separately rounds chroma on its own and drifts on sharp detail.
inline bool doroScaleIndices(int from, int to, bool horizontal, QImage::Format format, std::vector<int>& indices) {
    QImage strip(horizontal ? QSize(from, 1) : QSize(1, from), format);
    if (strip.isNull() || strip.depth() != 32)
        return false;
    for (int i=0; i<from; ++i) {
        uchar* pixel = strip.scanLine(horizontal ? 0 : i) + (horizontal ? 4*i : 0);
        pixel[0] = i; pixel[1] = i>>8; pixel[2] = i>>16; pixel[3] = 255;  // opaque in every 32-bit layout
    }
    const QImage scaled = strip.scaled(horizontal ? QSize(to, 1) : QSize(1, to), Qt::IgnoreAspectRatio, Qt::FastTransformation);
    if (scaled.format() != format || scaled.size() != (horizontal ? QSize(to, 1) : QSize(1, to)))
        return false;
    indices.resize(to);
    for (int i=0; i<to; ++i) {
        const uchar* pixel = scaled.constScanLine(horizontal ? 0 : i) + (horizontal ? 4*i : 0);
        indices[i] = pixel[0] | pixel[1]<<8 | pixel[2]<<16;
        if (pixel[3] != 255 || indices[i] >= from)
            return false;
    }
    return true;
}

// Sample directly at display size before Qt converts YUV to RGB.
inline QImage doroDownscaleVideo(QVideoFrame frame, const QSize& maximum) {
    const QVideoFrameFormat format = frame.surfaceFormat();
    const QSize source = frame.size();
    if (source.isEmpty() || maximum.isEmpty())
        return {};
    const QSize target = source.scaled(maximum, Qt::KeepAspectRatio);
    if (target.isEmpty() || target.width() > source.width()/2 || target.height() > source.height()/2
            || source.width()%2 || source.height()%2 || frame.handleType() != QVideoFrame::NoHandle
            || format.pixelFormat() != QVideoFrameFormat::Format_YUV420P
            || (format.colorSpace() != QVideoFrameFormat::ColorSpace_BT601 && format.colorSpace() != QVideoFrameFormat::ColorSpace_BT709)
            || (format.colorTransfer() != QVideoFrameFormat::ColorTransfer_BT601 && format.colorTransfer() != QVideoFrameFormat::ColorTransfer_BT709)
            || format.colorRange() == QVideoFrameFormat::ColorRange_Unknown
            || format.viewport() != QRect(QPoint(), source) || format.scanLineDirection() != QVideoFrameFormat::TopToBottom
            || format.rotation() != QtVideo::Rotation::None || frame.rotation() != QtVideo::Rotation::None
            || format.isMirrored() || frame.mirrored())
        return {};
    // The indices depend only on the two sizes and on the image format Qt converts this
    // kind of frame to, so one wallpaper computes them once.
    static QSize mappedSource, mappedTarget;
    static std::vector<int> columns, rows;
    if (mappedSource != source || mappedTarget != target) {
        mappedSource = mappedTarget = QSize();
        QVideoFrame probe(QVideoFrameFormat(QSize(2, 2), format.pixelFormat()));
        const QImage::Format converted = probe.toImage().format();
        if (!doroScaleIndices(source.width(), target.width(), true, converted, columns)
                || !doroScaleIndices(source.height(), target.height(), false, converted, rows))
            return {};
        mappedSource = source; mappedTarget = target;
    }
    if (!frame.map(QVideoFrame::ReadOnly))
        return {};
    const auto unmap = qScopeGuard([&frame] { frame.unmap(); });
    if (frame.planeCount() != 3)
        return {};
    const uchar* planes[3];
    int strides[3];
    for (int i=0; i<3; ++i) {
        const int divisor = i == 0 ? 1 : 2;
        const int w = source.width()/divisor, h = source.height()/divisor;
        strides[i] = frame.bytesPerLine(i);
        planes[i] = std::as_const(frame).bits(i);
        if (!planes[i] || strides[i] < w || frame.mappedBytes(i) < qint64(h-1)*strides[i] + w)
            return {};
    }
    QVideoFrameFormat packed(target, QVideoFrameFormat::Format_AYUV);
    packed.setColorRange(format.colorRange());
    packed.setColorSpace(format.colorSpace());
    packed.setColorTransfer(format.colorTransfer());
    QVideoFrame reduced(packed);
    if (!reduced.map(QVideoFrame::WriteOnly))
        return {};
    for (int y=0; y<target.height(); ++y) {
        uchar* row = reduced.bits(0) + qsizetype(y)*reduced.bytesPerLine(0);
        const uchar* luma = planes[0] + qsizetype(rows[y])*strides[0];
        const uchar* cb = planes[1] + qsizetype(rows[y]/2)*strides[1];
        const uchar* cr = planes[2] + qsizetype(rows[y]/2)*strides[2];
        for (int x=0; x<target.width(); ++x) {
            const int column = columns[x];
            *row++ = 255;
            *row++ = luma[column];
            *row++ = cb[column/2];
            *row++ = cr[column/2];
        }
    }
    reduced.unmap();
    return reduced.toImage();
}
