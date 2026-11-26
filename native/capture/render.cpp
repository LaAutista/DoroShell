// SPDX-License-Identifier: GPL-2.0-or-later
#include "render.hpp"
#include <QFontMetrics>
#include <QPainter>
#include <QPolygon>
#include <algorithm>
#include <cmath>

namespace doro::capture
{
namespace
{
QRect span(const Mark &mark) // inclusive rectangle over the first and last point, like QPolygon.boundingRect
{
    const QPoint a = mark.points.first(), b = mark.points.last();
    return QRect(QPoint(std::min(a.x(), b.x()), std::min(a.y(), b.y())), QPoint(std::max(a.x(), b.x()), std::max(a.y(), b.y())));
}

// Keep logical glyph size consistent across the overlay and native-image paint devices.
QFont textFont(const Mark &mark, const Style &style)
{
    QFont font = mark.font.value_or(style.font);
    if (font.pointSizeF() > 0)
        font.setPixelSize(std::max(1, int(std::lround(font.pointSizeF() * style.dpiY / 72))));
    return font;
}

std::pair<QFont, QRect> stampLayout(QPoint center, const QString &label, const Style &style)
{
    QFont font = style.font;
    font.setPixelSize(14);
    font.setBold(true);
    const QFontMetrics metrics(font);
    const int diameter = std::max(metrics.height(), metrics.horizontalAdvance(label)) + 10;
    QRect box(0, 0, diameter, diameter);
    box.moveCenter(center);
    return {font, box};
}

// View rectangle -> native pixels, rounded outwards so no pixel under the box is left partly covered.
// 64-bit products: coordinate * image width overflows int beyond ~46000 px.
QRect rawRect(QRect box, QSize image, QSize view)
{
    box = box.intersected(QRect(QPoint(), view));
    if (box.isEmpty())
        return {};
    const qint64 iw = image.width(), ih = image.height(), vw = view.width(), vh = view.height();
    const qint64 left = box.x() * iw / vw, top = box.y() * ih / vh;
    const qint64 right = ((qint64(box.right()) + 1) * iw + vw - 1) / vw, bottom = ((qint64(box.bottom()) + 1) * ih + vh - 1) / vh;
    return QRect(int(left), int(top), int(right - left), int(bottom - top));
}

void drawRaw(QPainter &painter, QSize image, QSize view, auto &&draw)
{
    painter.save();
    painter.scale(qreal(view.width()) / image.width(), qreal(view.height()) / image.height());
    painter.setRenderHint(QPainter::Antialiasing, false);
    painter.setCompositionMode(QPainter::CompositionMode_Source); // replace, never blend with what is below
    draw();
    painter.restore();
}

// `masks` are the native rectangles of every Redact mark. Samples are taken from the capture with those
// blacked out, so nothing under a redaction can reach the pixels around it through a blur or pixelate.
// Returns the cache key, which names the tool, the rectangle and the redactions inside it.
QByteArray drawEffect(QPainter &painter, const QImage &capture, QSize view, const QString &tool, QRect raw, const QList<QRect> &masks, EffectCache *cache)
{
    QList<QRect> hidden;
    QByteArray key = tool.toUtf8();
    for (QRect part : QList<QRect>{raw} + masks) {
        part = part.intersected(raw);
        if (part.isEmpty())
            continue;
        key += QByteArray::number(part.x()) + ',' + QByteArray::number(part.y()) + ',' + QByteArray::number(part.width()) + ',' + QByteArray::number(part.height()) + ';';
        hidden << part.translated(-raw.topLeft());
    }
    hidden.removeFirst(); // the first entry was the effect rectangle itself
    QImage samples = cache && cache->contains(key) ? cache->at(key) : QImage();
    if (samples.isNull()) {
        const int pitch = tool == "Blur" ? 6 : 12;
        QImage source = capture.copy(raw);
        if (!hidden.isEmpty()) {
            QPainter mask(&source);
            for (const QRect &part : hidden)
                mask.fillRect(part, Qt::black);
        }
        samples = source.scaled((raw.width() + pitch - 1) / pitch, (raw.height() + pitch - 1) / pitch, Qt::IgnoreAspectRatio, Qt::SmoothTransformation);
        samples.setDevicePixelRatio(1);
        if (cache)
            (*cache)[key] = samples;
    }
    drawRaw(painter, capture.size(), view, [&] {
        painter.setRenderHint(QPainter::SmoothPixmapTransform, tool == "Blur");
        painter.drawImage(raw, samples, samples.rect());
    });
    return key;
}

void drawMark(QPainter &painter, const Mark &mark, const Style &style)
{
    QPen pen(mark.color, mark.width, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin);
    pen.setCosmetic(true);
    painter.setPen(pen);
    const QPoint first = mark.points.first(), last = mark.points.last();
    const QRect box = QRect(first, last).normalized();
    if (mark.tool == "Line") {
        painter.drawLine(first, last);
    } else if (mark.tool == "Number") {
        const auto [font, circle] = stampLayout(first, mark.text, style);
        painter.save();
        painter.setPen(Qt::NoPen);
        painter.setBrush(mark.color);
        painter.drawEllipse(circle);
        painter.setFont(font);
        // Choose the higher-contrast black or white label (sRGB luminance).
        auto linear = [](float v) { return v > .04045f ? std::pow((v + .055f) / 1.055f, 2.4f) : v / 12.92f; };
        const float light = .2126f * linear(mark.color.redF()) + .7152f * linear(mark.color.greenF()) + .0722f * linear(mark.color.blueF());
        painter.setPen(light > .179f ? Qt::black : Qt::white);
        painter.drawText(circle, Qt::AlignCenter, mark.text);
        painter.restore();
    } else if (mark.tool == "Rectangle") {
        painter.drawRect(box);
    } else if (mark.tool == "Ellipse") {
        painter.drawEllipse(box);
    } else if (mark.tool == "Text") {
        painter.save();
        painter.setFont(textFont(mark, style));
        painter.drawText(first, mark.text);
        painter.restore();
    } else if (mark.tool == "Arrow") {
        const double angle = std::atan2(first.y() - last.y(), first.x() - last.x());
        painter.drawLine(first, last);
        for (double offset : {-.5, .5})
            painter.drawLine(last, last + QPoint(int(std::lround(14 * std::cos(angle + offset))), int(std::lround(14 * std::sin(angle + offset)))));
    } else if (mark.points.size() == 1) {
        painter.drawPoint(first);
    } else {
        painter.drawPolyline(QPolygon(mark.points));
    }
}
} // namespace

bool isRegionEffect(const QString &tool) { return tool == "Blur" || tool == "Pixelate"; }

QList<int> paintOrder(const QList<Mark> &marks)
{
    QList<int> order;
    for (bool effects : {true, false})
        for (int i = 0; i < marks.size(); ++i)
            if (isRegionEffect(marks[i].tool) == effects)
                order << i;
    return order;
}

QRect markBounds(const Mark &mark, QSize view, const Style &style)
{
    if (mark.points.isEmpty())
        return {};
    if (isRegionEffect(mark.tool))
        return span(mark).intersected(QRect(QPoint(), view));
    if (mark.tool == "Number")
        return stampLayout(mark.points.first(), mark.text, style).second;
    if (mark.tool == "Text")
        return QFontMetrics(textFont(mark, style)).boundingRect(mark.text).translated(mark.points.first());
    const int margin = (mark.width + 1) / 2 + (mark.tool == "Arrow" ? 14 : 0);
    return QPolygon(mark.points).boundingRect().adjusted(-margin, -margin, margin, margin);
}

void paint(QPainter &painter, const QImage &capture, QSize view, const QList<Mark> &marks, const Style &style, EffectCache *cache)
{
    if (capture.isNull() || view.isEmpty())
        return;
    painter.save();
    painter.setRenderHint(QPainter::Antialiasing);
    QList<QRect> masks;
    for (const Mark &mark : marks)
        if (mark.tool == "Redact" && !mark.points.isEmpty())
            masks << rawRect(span(mark), capture.size(), view);
    QList<QByteArray> used;
    for (int index : paintOrder(marks)) {
        const Mark &mark = marks[index];
        if (mark.points.isEmpty())
            continue;
        if (isRegionEffect(mark.tool)) {
            if (const QRect raw = rawRect(span(mark), capture.size(), view); !raw.isEmpty())
                used << drawEffect(painter, capture, view, mark.tool, raw, masks, cache);
        } else if (mark.tool == "Redact") {
            // Whole native pixels, no antialiasing: a redaction never leaves a half-covered edge.
            drawRaw(painter, capture.size(), view, [&] { painter.fillRect(rawRect(span(mark), capture.size(), view), Qt::black); });
        } else {
            drawMark(painter, mark, style);
        }
    }
    if (cache) // keep only this frame's tiles, as RC2 did, so dragging a mark cannot grow the cache
        std::erase_if(*cache, [&](const auto &entry) { return !used.contains(entry.first); });
    painter.restore();
}

QImage render(const QImage &capture, const QList<Mark> &marks, QSize view, QRect crop, const Style &style)
{
    QImage result = capture.copy();
    result.setDevicePixelRatio(1);
    if (view.isEmpty())
        view = result.size();
    if (!marks.isEmpty() && !result.isNull()) {
        QPainter painter(&result);
        painter.scale(qreal(result.width()) / view.width(), qreal(result.height()) / view.height());
        paint(painter, capture, view, marks, style);
    }
    return crop.isEmpty() ? result : result.copy(crop);
}

void History::replace(QList<Mark> &marks, int index, const std::optional<Mark> &from, const std::optional<Mark> &to)
{
    if (!from)
        marks.insert(index, *to);
    else if (!to)
        marks.removeAt(index);
    else
        marks[index] = *to;
}

void History::apply(QList<Mark> &marks, int index, const std::optional<Mark> &after)
{
    const std::optional<Mark> before = index < marks.size() ? std::optional(marks[index]) : std::nullopt;
    if (before == after || index < 0 || index > marks.size())
        return;
    replace(marks, index, before, after);
    done.append({index, before, after});
    undone.clear();
}

bool History::undo(QList<Mark> &marks)
{
    if (done.isEmpty())
        return false;
    const Change change = done.takeLast();
    replace(marks, change.index, change.after, change.before);
    undone.append(change);
    return true;
}

bool History::redo(QList<Mark> &marks)
{
    if (undone.isEmpty())
        return false;
    const Change change = undone.takeLast();
    replace(marks, change.index, change.before, change.after);
    done.append(change);
    return true;
}
} // namespace doro::capture
