// SPDX-License-Identifier: GPL-2.0-or-later
// Pixel tests on the exported image. The first two cases are RC2's tests/test_menu_capture.py
// test_region_effects_exact_scaled_edge_crop_and_history and test_effect_interpolation_stacking_and_tiny_regions.
#include "render.hpp"
#include <QGuiApplication>
#include <QPainter>
#include <cmath>
#include <cstdio>
#include <stdexcept>

using namespace doro::capture;

namespace
{
void require(bool pass, const char *message)
{
    if (!pass)
        throw std::runtime_error(message);
}
Mark mark(const QString &tool, QPoint a, QPoint b, QColor color = QColor("#f04761"), int width = 3)
{
    return {tool, {a, b}, {}, color, width, {}};
}
bool allBlack(const QImage &image, QRect box)
{
    for (int y = box.top(); y <= box.bottom(); ++y)
        for (int x = box.left(); x <= box.right(); ++x)
            if (image.pixelColor(x, y) != QColor(Qt::black))
                return false;
    return true;
}

void scaledEffectsCropAndHistory()
{
    QImage image(60, 45, QImage::Format_RGB32);
    for (int y = 0; y < image.height(); ++y)
        for (int x = 0; x < image.width(); ++x) {
            const int v = 32 + 128 * (x % 2);
            image.setPixelColor(x, y, QColor(v, v, v));
        }
    image.setDevicePixelRatio(1.5);
    const QSize view(40, 30); // overlay shown at 2/3 of native size
    auto expected = [&](QRect rect) {
        QImage result = image.copy();
        result.setDevicePixelRatio(1);
        for (int y = rect.top(); y <= rect.bottom(); ++y)
            for (int x = rect.left(); x <= rect.right(); ++x)
                result.setPixelColor(x, y, QColor(96, 96, 96));
        return result;
    };
    const QRect original(52, 37, 8, 8), moved(0, 0, 8, 8), crop(3, 5, 24, 12);
    for (const char *tool : {"Blur", "Pixelate"}) {
        QList<Mark> marks;
        History history;
        history.apply(marks, 0, mark(tool, QPoint(39, 29), QPoint(35, 25)));
        require(render(image, marks, view) == expected(original), "effect covers whole native pixels at the scaled edge");
        history.apply(marks, 0, mark(tool, QPoint(0, 0), QPoint(4, 4)));
        require(markBounds(marks[0], view) == QRect(0, 0, 5, 5), "moved effect bounds");
        require(render(image, marks, view) == expected(moved), "moved effect");
        require(render(image, marks, view, crop) == expected(moved).copy(crop), "cropped export");
        history.apply(marks, 0, std::nullopt);
        require(marks.isEmpty() && render(image, marks, view, crop) == expected({}).copy(crop), "deleted effect leaves the capture untouched");
        const std::pair<bool, QRect> steps[] = {{true, moved}, {true, original}, {false, moved}, {false, {}}};
        for (const auto &[undo, rect] : steps) {
            require(undo ? history.undo(marks) : history.redo(marks), "history step available");
            require(render(image, marks, view, crop) == expected(rect).copy(crop), "exported pixels follow undo and redo");
        }
        require(!history.canRedo() && history.canUndo(), "history ends");
    }
}

void interpolationStackingAndTinyRegions()
{
    QImage image(40, 20, QImage::Format_RGB32);
    image.fill(QColor("magenta"));
    for (int y = 0; y < 12; ++y)
        for (int x = 0; x < 24; ++x) {
            const int v = x < 12 ? 40 : 200;
            image.setPixelColor(x, y, QColor(v, v, v));
        }
    QList<Mark> marks;
    History history;
    auto add = [&](const Mark &m) { history.apply(marks, int(marks.size()), m); };
    // One native pixel at the corner cannot draw in samples from outside it.
    add(mark("Blur", QPoint(39, 19), QPoint(39, 19)));
    add(mark("Pixelate", QPoint(39, 19), QPoint(45, 25)));
    require(render(image, marks) == image, "corner effects stay inside the image");
    const QPoint a(2, 2), b(23, 11);
    add(mark("Redact", QPoint(4, 3), QPoint(7, 7)));
    add(mark("Blur", a, b));
    const QImage blurred = render(image, marks);
    require(blurred.pixelColor(5, 5) == QColor(Qt::black), "a later blur does not cover an earlier redaction");
    require(blurred.pixelColor(12, 5).red() > 40 && blurred.pixelColor(12, 5).red() < 200, "blur interpolates");
    add(mark("Pixelate", a, b));
    const QImage pixelated = render(image, marks);
    require(pixelated.pixelColor(13, 5) == QColor(200, 200, 200), "pixelate keeps hard blocks");
    require(pixelated.pixelColor(8, 5) == pixelated.pixelColor(11, 5), "one block, one colour");
    require(pixelated != blurred && pixelated.pixelColor(24, 5) == image.pixelColor(24, 5), "pixelate replaces blur and stays in its box");
    require(history.undo(marks) && render(image, marks) == blurred, "undo restores the blurred export exactly");
    add(mark("Redact", QPoint(15, 5), QPoint(16, 6)));
    require(!history.canRedo() && render(image, marks).pixelColor(15, 5) == QColor(Qt::black), "new edit clears redo");
}

// The property that matters for what leaves the editor: a solid redaction is opaque black in every
// order, and effects never sample ink or redactions (they would smear them into neighbours).
void redactionAndEffectOrder()
{
    QImage image(64, 48, QImage::Format_RGB32);
    for (int y = 0; y < image.height(); ++y)
        for (int x = 0; x < image.width(); ++x)
            image.setPixelColor(x, y, QColor((x * 37 + y * 11) % 256, (x * 5 + y * 53) % 256, (x * 91 + y * 7) % 256));
    const Mark redact = mark("Redact", QPoint(20, 12), QPoint(39, 27)), blur = mark("Blur", QPoint(10, 6), QPoint(53, 39)),
               pixelate = mark("Pixelate", QPoint(16, 10), QPoint(47, 31)), box = mark("Rectangle", QPoint(14, 8), QPoint(50, 36), QColor("#00ff00"));
    const QRect secret(20, 12, 20, 16);
    const QList<Mark> orders[] = {{redact, blur, pixelate, box}, {blur, pixelate, redact, box}, {box, pixelate, redact, blur}, {pixelate, box, blur, redact}};
    require(paintOrder(orders[2]) == QList<int>({1, 3, 0, 2}), "effects first, each group in insertion order");
    for (const auto &marks : orders) {
        QList<Mark> withoutInk;
        for (const auto &m : marks)
            if (m.tool != "Rectangle")
                withoutInk << m;
        const QImage out = render(image, marks), effectsOnly = render(image, withoutInk);
        require(allBlack(out, secret), "redaction is solid black in every order");
        require(out.pixelColor(14, 20) == QColor("#00ff00"), "ink stays above effects in every order");
        // Away from the ink, the result is exactly what the same marks give without the ink.
        require(out.pixelColor(11, 20) == effectsOnly.pixelColor(11, 20) && out.pixelColor(44, 30) == effectsOnly.pixelColor(44, 30),
                "ink is never part of an effect sample");
        require(out.pixelColor(2, 2) == image.pixelColor(2, 2) && out.pixelColor(60, 44) == image.pixelColor(60, 44), "outside every mark is untouched");
    }
    // Blur over Pixelate and Pixelate over Blur differ only by which effect was added last.
    require(render(image, {blur, pixelate}).pixelColor(30, 30) == render(image, {pixelate}).pixelColor(30, 30), "later effect replaces the earlier one");
    // The same redaction survives a scaled overlay and a crop.
    const QImage scaled = render(image, {blur, mark("Redact", QPoint(10, 6), QPoint(19, 13))}, QSize(32, 24), QRect(16, 8, 40, 32));
    require(scaled.size() == QSize(40, 32) && allBlack(scaled, QRect(4, 4, 20, 16)), "scaled, cropped redaction is solid");
}

QImage pattern(QSize size)
{
    QImage image(size, QImage::Format_RGB32);
    for (int y = 0; y < size.height(); ++y)
        for (int x = 0; x < size.width(); ++x)
            image.setPixelColor(x, y, QColor((x * 37 + y * 11) % 256, (x * 5 + y * 53) % 256, (x * 91 + y * 7) % 256));
    return image;
}

// What the overlay does on screen and on export when it keeps one EffectCache for a capture.
QImage exportWith(EffectCache &cache, const QImage &capture, const QList<Mark> &marks, QSize view)
{
    QImage result = capture.copy();
    QPainter painter(&result);
    painter.scale(qreal(result.width()) / view.width(), qreal(result.height()) / view.height());
    paint(painter, capture, view, marks, {}, &cache);
    return result;
}

// Two captures that differ only under a redaction must export identically everywhere: nothing
// hidden may reach the pixels around it through a blur, a pixelate, a scaled edge or a reused cache.
void redactionDifferential()
{
    const QSize size(96, 60);
    const QPoint a(21, 9), b(41, 25); // odd view coordinates: fractional native edges at 1.5x
    for (QSize view : {QSize(64, 40), size}) {
        // Native pixels the redaction must cover, worked out independently: floor/ceil of the scaled box.
        const double sx = double(size.width()) / view.width(), sy = double(size.height()) / view.height();
        const QRect hidden(QPoint(int(std::floor(a.x() * sx)), int(std::floor(a.y() * sy))),
                           QPoint(int(std::ceil((b.x() + 1) * sx)) - 1, int(std::ceil((b.y() + 1) * sy)) - 1));
        const QImage plain = pattern(size);
        QImage secret = plain.copy();
        for (int y = hidden.top(); y <= hidden.bottom(); ++y)
            for (int x = hidden.left(); x <= hidden.right(); ++x)
                secret.setPixelColor(x, y, QColor(255 - plain.pixelColor(x, y).red(), (x * 113 + y * 29) % 256, (x + y) % 2 ? 255 : 0));
        const Mark redact = mark("Redact", a, b), across = mark("Blur", QPoint(8, 3), QPoint(55, 33)),
                   overlap = mark("Pixelate", QPoint(30, 15), QPoint(60, 36)), inside = mark("Blur", QPoint(25, 12), QPoint(35, 20)),
                   touching = mark("Pixelate", QPoint(42, 9), QPoint(50, 25)), pen = mark("Line", QPoint(2, 2), QPoint(60, 38));
        require(render(plain, {across}, view) != render(secret, {across}, view), "the two captures really differ without the redaction");
        const QList<Mark> cases[] = {{across, redact}, {redact, across}, {redact, overlap}, {across, overlap, redact, pen}, {inside, redact},
                                     {touching, redact}, {pen, overlap, redact, across, inside, touching}};
        for (const auto &marks : cases) {
            const QImage one = render(plain, marks, view), two = render(secret, marks, view);
            require(one == two, "exports differ outside a solid redaction");
            if (marks.last().tool != "Line") // ink added after a redaction is drawn over it, as in RC2
                require(allBlack(one, hidden), "every native pixel under the redaction is black");
            require(render(plain, marks, view, QRect(10, 5, 70, 40)) == render(secret, marks, view, QRect(10, 5, 70, 40)), "cropped exports differ");
            EffectCache first, second;
            require(exportWith(first, plain, marks, view) == one && exportWith(second, secret, marks, view) == one, "cached paint matches export");
            require(exportWith(second, secret, marks, view) == one, "a warm cache gives the same pixels");
        }
        // One cache for one capture while the mask is moved, deleted and put back.
        EffectCache cache;
        const Mark movedMask = mark("Redact", QPoint(4, 28), QPoint(18, 36));
        const QImage masked = exportWith(cache, secret, {across, overlap, redact}, view);
        require(masked == render(secret, {across, overlap, redact}, view) && cache.size() == 2, "cache holds this frame's tiles");
        const QImage moved = exportWith(cache, secret, {across, overlap, movedMask}, view);
        require(moved == render(secret, {across, overlap, movedMask}, view) && moved != masked, "moving the mask re-samples the effects");
        require(exportWith(cache, secret, {across, overlap}, view) == render(secret, {across, overlap}, view), "deleting the mask restores the unmasked effect");
        require(exportWith(cache, secret, {across, overlap, redact}, view) == masked && cache.size() == 2, "restoring the mask cannot reuse an unmasked tile");
        require(exportWith(cache, secret, {redact}, view) == render(secret, {redact}, view) && cache.empty(), "unused tiles are dropped");
    }
}

// Scaled rectangle math on frames wide enough that coordinate * width does not fit in 32 bits.
void ultrawideFrames()
{
    QImage image(50000, 4, QImage::Format_RGB32);
    for (int y = 0; y < image.height(); ++y)
        for (int x = 0; x < image.width(); ++x)
            image.setPixel(x, y, x % 2 ? 0xffa0a0a0 : 0xff202020);
    auto untouchedLeftOf = [&](const QImage &out, int limit) {
        for (int x : {0, 1, 20000, 42949, 42950, limit - 2, limit - 1})
            if (out.pixel(x, 2) != image.pixel(x, 2))
                return false;
        return true;
    };
    QImage out = render(image, {mark("Blur", QPoint(49990, 0), QPoint(49999, 3))});
    require(untouchedLeftOf(out, 49990) && out.pixel(49995, 2) != image.pixel(49995, 2) && out.pixel(49999, 2) != image.pixel(49999, 2), "blur lands at the far edge");
    out = render(image, {mark("Redact", QPoint(24990, 0), QPoint(30000, 9))}, QSize(25000, 2));
    require(untouchedLeftOf(out, 49980) && allBlack(out, QRect(49980, 0, 20, 4)), "scaled redaction lands at the far edge and is clipped to the frame");
    out = render(image, {mark("Pixelate", QPoint(-2000000000, -5), QPoint(11, 2000000000))});
    require(out.pixel(5, 2) != image.pixel(5, 2) && out.pixel(12, 2) == image.pixel(12, 2), "far out-of-frame points are clipped, not wrapped");
}

void drawingMarks()
{
    QImage image(120, 90, QImage::Format_RGB32);
    image.fill(Qt::white);
    const QColor ink("#f04761");
    auto changed = [&](const QImage &out, QRect area) {
        int count = 0;
        for (int y = 0; y < out.height(); ++y)
            for (int x = 0; x < out.width(); ++x)
                if (out.pixelColor(x, y) != QColor(Qt::white)) {
                    require(area.contains(x, y), "a mark painted outside its bounds");
                    ++count;
                }
        return count;
    };
    QImage out = render(image, {mark("Rectangle", QPoint(20, 20), QPoint(60, 50))});
    require(out.pixelColor(20, 35) == ink && out.pixelColor(40, 50) == ink && out.pixelColor(40, 35) == QColor(Qt::white), "rectangle is an outline");
    out = render(image, {mark("Line", QPoint(10, 40), QPoint(100, 40))});
    require(out.pixelColor(50, 40) == ink && out.pixelColor(50, 44) == QColor(Qt::white), "line");
    out = render(image, {mark("Ellipse", QPoint(20, 20), QPoint(80, 60))});
    require(out.pixelColor(50, 20) == ink && out.pixelColor(50, 40) == QColor(Qt::white), "ellipse is an outline");
    const Mark arrow = mark("Arrow", QPoint(20, 45), QPoint(90, 45));
    out = render(image, {arrow});
    require(out.pixelColor(50, 45) == ink && out.pixelColor(80, 40) != QColor(Qt::white) && out.pixelColor(80, 50) != QColor(Qt::white), "arrow has both barbs at its end");
    require(changed(out, markBounds(arrow, image.size())) > 0, "arrow stays in its bounds");
    const Mark pen{"Pen", {QPoint(10, 10), QPoint(40, 10), QPoint(40, 60)}, {}, ink, 3, {}};
    out = render(image, {pen});
    require(out.pixelColor(25, 10) == ink && out.pixelColor(40, 35) == ink && changed(out, markBounds(pen, image.size())) > 0, "pen follows its points");
    require(render(image, {Mark{"Pen", {QPoint(30, 30)}, {}, ink, 3, {}}}).pixelColor(30, 30) != QColor(Qt::white), "single-point pen draws a dot");
    QColor marker("#ffda00");
    marker.setAlpha(115);
    out = render(image, {mark("Line", QPoint(10, 70), QPoint(100, 70), Qt::black, 3), mark("Highlight", QPoint(10, 70), QPoint(100, 70), marker, 15)});
    const QColor over = out.pixelColor(50, 70), beside = out.pixelColor(50, 75);
    require(beside.blue() > 100 && beside.blue() < 255 && beside.red() == 255, "highlight tints the page");
    require(over.red() > 60 && over.red() < 200, "highlight is translucent over ink below it");

    Style style;
    style.font = QGuiApplication::font();
    for (const auto &[color, dark] : {std::pair{QColor("#ffda00"), true}, {QColor("#10206a"), false}}) {
        const Mark number{"Number", {QPoint(60, 45)}, "7", color, 3, {}};
        const QRect circle = markBounds(number, image.size(), style);
        out = render(image, {number}, {}, {}, style);
        require(circle.width() == circle.height() && changed(out, circle) > 0, "number stamp stays in its circle");
        require(out.pixelColor(circle.left() + 3, circle.center().y()) == color, "number stamp is filled with its colour");
        int extreme = dark ? 255 : 0;
        for (int y = circle.top(); y <= circle.bottom(); ++y)
            for (int x = circle.left(); x <= circle.right(); ++x)
                extreme = dark ? std::min(extreme, out.pixelColor(x, y).lightness()) : std::max(extreme, out.pixelColor(x, y).lightness());
        require(dark ? extreme < 60 : extreme > 215, "number label picks the contrasting black or white");
    }
    QFont big = style.font;
    big.setPointSizeF(18);
    const Mark small{"Text", {QPoint(15, 40)}, "Doro", ink, 3, {}}, large{"Text", {QPoint(15, 40)}, "Doro", ink, 3, big};
    const QRect smallBox = markBounds(small, image.size(), style), largeBox = markBounds(large, image.size(), style);
    require(changed(render(image, {small}, {}, {}, style), smallBox.adjusted(-2, -2, 2, 2)) > 0, "text draws inside its bounds");
    require(changed(render(image, {large}, {}, {}, style), largeBox.adjusted(-2, -2, 2, 2)) > 0 && largeBox.height() > smallBox.height(), "text keeps its own font");
    // Ink painted before an effect is still on top of it in the export.
    out = render(image, {mark("Rectangle", QPoint(20, 20), QPoint(60, 50)), mark("Blur", QPoint(0, 0), QPoint(119, 89))});
    require(out.pixelColor(20, 35) == ink, "ink is not blurred by a later effect");
    const QList<Mark> pointless{Mark{"Pen", {}, {}, ink, 3, {}}};
    require(render(QImage(), {arrow}).isNull() && render(image, pointless) == image, "empty inputs are harmless");
}
} // namespace

int main(int argc, char **argv)
{
    qputenv("QT_QPA_PLATFORM", "offscreen"); // fonts only; no display is opened
    QGuiApplication app(argc, argv);
    const std::pair<const char *, void (*)()> cases[] = {{"scaled effects, crop, undo/redo", scaledEffectsCropAndHistory},
                                                         {"interpolation, stacking, tiny regions", interpolationStackingAndTinyRegions},
                                                         {"redaction and effect order", redactionAndEffectOrder},
                                                         {"redaction differential and cache", redactionDifferential},
                                                         {"ultrawide frames", ultrawideFrames},
                                                         {"drawing marks", drawingMarks}};
    int failed = 0;
    for (const auto &[name, run] : cases) {
        try {
            run();
            std::printf("ok   %s\n", name);
        } catch (const std::exception &error) {
            std::printf("FAIL %s: %s\n", name, error.what());
            ++failed;
        }
    }
    return failed ? 1 : 0;
}
