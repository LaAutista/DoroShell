// SPDX-License-Identifier: GPL-2.0-or-later
// Screenshot annotation rendering, ported from RC2 runtime/menu_capture.py (paint_order, draw_effect,
// draw_mark, rendered_image, record/undo/redo). The overlay paints with paint(); export uses render().
#pragma once
#include <QByteArray>
#include <QColor>
#include <QFont>
#include <QImage>
#include <QList>
#include <QPoint>
#include <QRect>
#include <QString>
#include <map>
#include <optional>

class QPainter;

namespace doro::capture
{
// Tools: Pen, Highlight, Line, Arrow, Rectangle, Ellipse, Text, Number, Redact, Blur, Pixelate.
// Points are in view (overlay widget) coordinates; two-point tools use the first and last point.
struct Mark {
    QString tool;
    QList<QPoint> points;
    QString text;
    QColor color;
    int width = 3;
    std::optional<QFont> font; // Text only; absent uses Style::font
    bool operator==(const Mark &) const = default;
};
struct Style {
    QFont font;      // overlay font: Number stamps and Text marks without their own font
    int dpiY = 96;   // overlay logicalDpiY, so point-sized text matches between screen and export
};
// Downsampled effect tiles keyed by tool, native rectangle and the redactions inside it. Pass one to
// paint() to reuse tiles across repaints; paint() drops tiles the current frame did not use.
using EffectCache = std::map<QByteArray, QImage>;

bool isRegionEffect(const QString &tool);
// Indices in drawing order: Blur/Pixelate first, then everything else, each group in insertion order.
// Effects sample the capture with every redaction blacked out and no ink, so ink and redactions stay
// above them and nothing under a redaction reaches the pixels around it.
QList<int> paintOrder(const QList<Mark> &marks);
// Rectangle a mark occupies in view coordinates (used for effects, selection and hit-testing).
QRect markBounds(const Mark &mark, QSize view, const Style &style = {});
// Draw every mark. The painter must already map view coordinates onto its device.
void paint(QPainter &painter, const QImage &capture, QSize view, const QList<Mark> &marks, const Style &style = {},
           EffectCache *cache = nullptr);
// The image that leaves the editor: capture at native resolution with marks applied, cut to `crop`
// (native pixels; empty keeps everything). An empty `view` means the overlay is shown 1:1.
QImage render(const QImage &capture, const QList<Mark> &marks, QSize view = {}, QRect crop = {}, const Style &style = {});

// RC2 edit history: each entry is one mark slot before and after. nullopt before = added, after = deleted.
class History
{
    struct Change {
        int index;
        std::optional<Mark> before, after;
    };
    QList<Change> undone, done;
    static void replace(QList<Mark> &marks, int index, const std::optional<Mark> &from, const std::optional<Mark> &to);

public:
    // Apply `after` to slot `index` and remember it. No-ops (before == after) are not recorded.
    void apply(QList<Mark> &marks, int index, const std::optional<Mark> &after);
    bool undo(QList<Mark> &marks);
    bool redo(QList<Mark> &marks);
    bool canUndo() const { return !done.isEmpty(); }
    bool canRedo() const { return !undone.isEmpty(); }
};
} // namespace doro::capture
