#include "import.hpp"
#include <QtConcurrentRun>
#include <QFutureWatcher>
#include "overlay.hpp"
#include <QtWidgets>
#include <cmath>
#include <memory>
#include <xcb/xcb.h>

namespace {
bool editLabel(QWidget *parent, Mark &mark) {
  QDialog dialog(parent);
  dialog.setWindowTitle(mark.tool == "Text" ? "Text annotation" : "Number stamp");
  QFormLayout layout(&dialog);
  QPlainTextEdit label(mark.text);
  label.setTabChangesFocus(true);
  layout.addRow("Label", &label);
  auto font = mark.font.value_or(parent->font());
  auto color = mark.color;
  QPushButton fontButton("Choose font…"), colorButton("Choose color…");
  if (mark.tool == "Text") {
    layout.addRow(&fontButton);
    QObject::connect(&fontButton, &QPushButton::clicked, &dialog, [&] {
      bool ok = false;
      auto chosen = QFontDialog::getFont(&ok, font, &dialog);
      if (ok) { font = chosen; label.setFont(font); }
    });
    label.setFont(font);
  }
  layout.addRow(&colorButton);
  QObject::connect(&colorButton, &QPushButton::clicked, &dialog, [&] {
    auto chosen = QColorDialog::getColor(color, &dialog);
    if (chosen.isValid()) color = chosen;
  });
  QDialogButtonBox buttons(QDialogButtonBox::Ok | QDialogButtonBox::Cancel);
  layout.addRow(&buttons);
  QObject::connect(&buttons, &QDialogButtonBox::accepted, &dialog, &QDialog::accept);
  QObject::connect(&buttons, &QDialogButtonBox::rejected, &dialog, &QDialog::reject);
  if (dialog.exec() != QDialog::Accepted || label.toPlainText().isEmpty()) return false;
  mark.text = label.toPlainText();
  mark.color = color;
  if (mark.tool == "Text") mark.font = font;
  return true;
}
template <class T> using Reply = std::unique_ptr<T, decltype(&std::free)>;
template <class T> Reply<T> reply(T *ptr) { return {ptr, &std::free}; }
xcb_atom_t atom(xcb_connection_t *c, QByteArray name) {
  auto a = reply(xcb_intern_atom_reply(
      c, xcb_intern_atom(c, 1, name.size(), name.data()), nullptr));
  return a ? a->atom : XCB_ATOM_NONE;
}
QList<uint32_t> property(xcb_connection_t *c, xcb_window_t w, xcb_atom_t key) {
  if (!key)
    return {};
  auto p = reply(xcb_get_property_reply(
      c, xcb_get_property(c, 0, w, key, XCB_GET_PROPERTY_TYPE_ANY, 0, 65536),
      nullptr));
  if (!p || p->format != 32)
    return {};
  auto *data = static_cast<uint32_t *>(xcb_get_property_value(p.get()));
  return {data, data + xcb_get_property_value_length(p.get()) / 4};
}
} // namespace
QList<WindowBounds> windowsAtCapture() {
  int screen = 0;
  std::unique_ptr<xcb_connection_t, decltype(&xcb_disconnect)> owner(
      xcb_connect(nullptr, &screen), &xcb_disconnect);
  auto *c = owner.get();
  if (xcb_connection_has_error(c))
    return {};
  auto roots = xcb_setup_roots_iterator(xcb_get_setup(c));
  while (screen-- && roots.rem)
    xcb_screen_next(&roots);
  if (!roots.rem)
    return {};
  auto root = roots.data->root;
  auto stacking = property(c, root, atom(c, "_NET_CLIENT_LIST_STACKING"));
  auto type = atom(c, "_NET_WM_WINDOW_TYPE"),
       dock = atom(c, "_NET_WM_WINDOW_TYPE_DOCK");
  auto desktop = atom(c, "_NET_WM_WINDOW_TYPE_DESKTOP"),
       ext = atom(c, "_NET_FRAME_EXTENTS");
  QList<WindowBounds> result;
  for (auto it = stacking.crbegin(); it != stacking.crend(); ++it) {
    auto w = *it;
    auto attr = reply(xcb_get_window_attributes_reply(
        c, xcb_get_window_attributes(c, w), nullptr));
    if (!attr || attr->map_state != XCB_MAP_STATE_VIEWABLE)
      continue;
    auto types = property(c, w, type);
    if (types.contains(dock) || types.contains(desktop))
      continue;
    auto geom =
        reply(xcb_get_geometry_reply(c, xcb_get_geometry(c, w), nullptr));
    auto pos = reply(xcb_translate_coordinates_reply(
        c, xcb_translate_coordinates(c, w, root, 0, 0), nullptr));
    if (!geom || !pos)
      continue;
    QRect client(pos->dst_x, pos->dst_y, geom->width, geom->height);
    auto edges = property(c, w, ext);
    auto frame = edges.size() == 4
                     ? client.adjusted(-int(edges[0]), -int(edges[2]),
                                       int(edges[1]), int(edges[3]))
                     : client;
    result.append({client, frame});
  }
  return result;
}
Overlay::Overlay(QImage image, QRect bounds, QList<WindowBounds> candidates)
    : QDialog(nullptr, Qt::FramelessWindowHint | Qt::WindowStaysOnTopHint),
      frozen(std::move(image)), windows(std::move(candidates)) {
  setWindowTitle("DoroShell capture");
  setGeometry(bounds);
  setCursor(Qt::CrossCursor);
  setMouseTracking(true);
  bar = new QWidget(this);
  bar->setStyleSheet("QWidget { background:#eff0f1; color:#232629; } "
                     "QPushButton { padding:3px; }");
  bar->setCursor(Qt::ArrowCursor);
  auto *layout = new QGridLayout(bar);
  layout->setContentsMargins(4, 4, 4, 4);
  auto *menu = new QComboBox;
  menu->addItems({"Select", "Window", "Pen", "Highlight", "Rectangle",
                  "Ellipse", "Arrow", "Line", "Text", "Number", "Redact",
                  "Blur", "Pixelate", "Edit marks"});
  layout->addWidget(menu, 0, 0);
  connect(menu, &QComboBox::currentTextChanged, this, &Overlay::chooseTool);
  auto button = [&](const QString &name, int row, int col, auto action) {
    auto *b = new QPushButton(name);
    b->setAutoDefault(false);
    layout->addWidget(b, row, col);
    connect(b, &QPushButton::clicked, this, action);
  };
  button("Color", 0, 1, [this] {
    auto c = QColorDialog::getColor(color, this);
    if (c.isValid())
      color = c;
  });
  width = new QSpinBox;
  width->setRange(1, 100);
  width->setValue(3);
  width->setAccessibleName("Stroke width");
  layout->addWidget(width, 0, 2);
  button("Undo", 0, 3, [this] { undo(); });
  button("Redo", 0, 4, [this] { redo(); });
  borders = new QCheckBox("Include window borders");
  borders->setChecked(true);
  layout->addWidget(borders, 1, 0, 1, 2);
  button("Copy", 1, 2, [this] { accept(); });
  button("Save…", 1, 3, [this] {
    auto name = QFileDialog::getSaveFileName(this, "Save screenshot", {},
                                             "PNG image (*.png)");
    if (name.isEmpty())
      return;
    QSaveFile file(name);
    if (!file.open(QIODevice::WriteOnly) || !resultImage().save(&file, "PNG") ||
        !file.commit())
      QMessageBox::warning(this, "Save screenshot",
                           "Could not save this image.");
    else
      done(2);
  });
  button("Open in ScreenGrab", 1, 5, [this] {
    auto program = QCoreApplication::applicationDirPath() + "/doroshell-screengrab-import";
    QProgressDialog progress("Opening screenshot in ScreenGrab…", {}, 0, 0, this);
    progress.setWindowModality(Qt::WindowModal);
    progress.setCancelButton(nullptr);
    QFutureWatcher<bool> transfer;
    connect(&transfer, &QFutureWatcher<bool>::finished, &progress, &QDialog::accept);
    transfer.setFuture(QtConcurrent::run(importScreenshot, resultImage(), program, 8000));
    if (!transfer.isFinished())
      progress.exec();
    if (transfer.result())
      done(2);
    else
      QMessageBox::warning(this, "ScreenGrab", "ScreenGrab could not open this image. Your screenshot is still here.");
  });
  button("Cancel", 1, 4, [this] { reject(); });
  button("New capture…", 0, 5, [this] {
    QDialog options(this);
    options.setWindowTitle("New capture");
    QFormLayout form(&options);
    QComboBox scope;
    scope.addItems({"Full desktop", "Monitor under pointer"});
    QSpinBox delay;
    delay.setRange(0, 60);
    delay.setSuffix(" s");
    QCheckBox pointer("Include pointer");
    form.addRow("Area", &scope);
    form.addRow("Delay", &delay);
    form.addRow(&pointer);
    QDialogButtonBox buttons(QDialogButtonBox::Ok | QDialogButtonBox::Cancel);
    form.addRow(&buttons);
    connect(&buttons, &QDialogButtonBox::accepted, &options, &QDialog::accept);
    connect(&buttons, &QDialogButtonBox::rejected, &options, &QDialog::reject);
    if (options.exec() == QDialog::Accepted) {
      nextCapture = Request{scope.currentIndex() == 1, pointer.isChecked(),
                            delay.value()};
      done(3);
    }
  });
  bar->adjustSize();
  auto *screen = QGuiApplication::screenAt(QCursor::pos());
  if (!screen)
    screen = QGuiApplication::primaryScreen();
  auto area = screen->geometry().translated(-bounds.topLeft());
  bar->move(area.x() + qMax(0, (area.width() - bar->width()) / 2),
            area.y() + 8);
}
void Overlay::chooseTool(const QString &name) {
  tool = name;
  active = -1;
  update();
}
void Overlay::checkpoint() {
  rendered = {};
  past.append(marks);
  future.clear();
}
void Overlay::undo() {
  if (!past.isEmpty()) {
    future.append(marks);
    marks = past.takeLast();
    rendered = {};
    active = -1;
    update();
  }
}
void Overlay::redo() {
  if (!future.isEmpty()) {
    past.append(marks);
    marks = future.takeLast();
    rendered = {};
    active = -1;
    update();
  }
}
QRect Overlay::hitWindow(QPoint at) const {
  for (const auto &w : windows) {
    auto box = borders->isChecked() ? w.frame : w.client;
    if (box.contains(at))
      return box.intersected(frozen.rect());
  }
  return {};
}
const QImage &Overlay::annotatedImage() const {
  if (rendered.isNull()) {
    rendered = doro::capture::render(frozen, marks, size(), {}, {font(), logicalDpiY()});
  }
  return rendered;
}
QImage Overlay::resultImage() const {
  const auto &out = annotatedImage();
  return selection.isEmpty() ? out : out.copy(selection);
}
void Overlay::paintEvent(QPaintEvent *) {
  QPainter p(this);
  const auto &image = annotatedImage();
  p.drawImage(0, 0, image);
  auto box =
      tool == "Window" ? hitWindow(mapFromGlobal(QCursor::pos())) : selection;
  if (!box.isEmpty()) {
    p.setClipRegion(QRegion(rect()).subtracted(QRegion(box)));
    p.fillRect(rect(), QColor(0, 0, 0, 90));
    p.setClipping(false);
    p.setPen(QPen(Qt::white, 1, Qt::DashLine));
    p.drawRect(box.adjusted(0, 0, -1, -1));
  }
  if (tool == "Select" && lens) {
    const QPoint at = *lens;
    const auto *screen = QGuiApplication::screenAt(mapToGlobal(at));
    if (!screen)
      return;
    auto area = screen->geometry().translated(-geometry().topLeft());
    for (int dy : {12, -89})
      for (int dx : {12, -89}) {
        QRect target(at + QPoint(dx, dy), QSize(77, 77));
        if (!area.contains(target) || bar->geometry().intersects(target))
          continue;
        p.fillRect(target, Qt::black);
        p.drawImage(target, image, QRect(at - QPoint(5, 5), QSize(11, 11)));
        p.setPen(Qt::white);
        p.drawRect(target.adjusted(0, 0, -1, -1));
        p.drawRect(QRect(target.center() - QPoint(3, 3), QSize(7, 7)));
        return;
      }
  }
}
void Overlay::mousePressEvent(QMouseEvent *ev) {
  if (ev->button() != Qt::LeftButton)
    return;
  origin = ev->position().toPoint();
  if (tool == "Window") {
    auto win = hitWindow(origin);
    if (!win.isEmpty()) {
      selection = win;
      accept();
    }
    return;
  }
  dragging = true;
  if (tool == "Select") {
    previous = selection;
    moving = selection.contains(origin);
    resizeEdges = {};
    if (!selection.isEmpty() &&
        selection.adjusted(-5, -5, 5, 5).contains(origin)) {
      if (qAbs(origin.x() - selection.left()) <= 5)
        resizeEdges |= Qt::LeftEdge;
      else if (qAbs(origin.x() - selection.right()) <= 5)
        resizeEdges |= Qt::RightEdge;
      if (qAbs(origin.y() - selection.top()) <= 5)
        resizeEdges |= Qt::TopEdge;
      else if (qAbs(origin.y() - selection.bottom()) <= 5)
        resizeEdges |= Qt::BottomEdge;
    }
    if (!moving && !resizeEdges)
      selection = QRect(origin, origin);
  } else if (tool == "Edit marks") {
    active = -1;
    const auto order = doro::capture::paintOrder(marks);
    for (auto at = order.crbegin(); at != order.crend(); ++at) {
      int i = *at;
      auto box = doro::capture::markBounds(marks[i], size(), {font(), logicalDpiY()}).adjusted(-5, -5, 5, 5);
      if (box.contains(origin)) {
        checkpoint();
        active = i;
        break;
      }
    }
  } else {
    Mark m;
    m.tool = tool;
    m.points = {origin, origin};
    m.width = width->value();
    m.color = color;
    if (tool == "Highlight") {
      m.color = Qt::yellow;
      m.color.setAlpha(115);
      m.width = qMax(m.width, 15);
    }
    if (tool == "Text") {
      if (!editLabel(this, m)) {
        dragging = false;
        return;
      }
    }
    if (tool == "Number")
      m.text = QString::number(
          1 + std::count_if(marks.begin(), marks.end(),
                            [](const Mark &v) { return v.tool == "Number"; }));
    checkpoint();
    marks.append(m);
    active = marks.size() - 1;
  }
  update();
}
void Overlay::mouseMoveEvent(QMouseEvent *ev) {
  auto at = ev->position().toPoint();
  at.setX(qBound(0, at.x(), frozen.width() - 1));
  at.setY(qBound(0, at.y(), frozen.height() - 1));
  if (ev->modifiers().testFlag(Qt::ShiftModifier))
    lens = at;
  else
    lens.reset();
  if (dragging) {
    if (tool == "Select") {
      if (resizeEdges) {
        selection = previous;
        if (resizeEdges.testFlag(Qt::LeftEdge))
          selection.setLeft(qMin(at.x(), previous.right()));
        if (resizeEdges.testFlag(Qt::RightEdge))
          selection.setRight(qMax(at.x(), previous.left()));
        if (resizeEdges.testFlag(Qt::TopEdge))
          selection.setTop(qMin(at.y(), previous.bottom()));
        if (resizeEdges.testFlag(Qt::BottomEdge))
          selection.setBottom(qMax(at.y(), previous.top()));
      } else if (moving) {
        selection = previous;
        auto pos = previous.topLeft() + at - origin;
        selection.moveTo(
            qBound(0, pos.x(), frozen.width() - selection.width()),
            qBound(0, pos.y(), frozen.height() - selection.height()));
      } else
        selection = QRect(origin, at).normalized();
    } else if (active >= 0 && active < marks.size()) {
      rendered = {};
      auto &m = marks[active];
      if (tool == "Edit marks") {
        auto d = at - origin;
        for (auto &point : m.points) point += d;
        origin = at;
      } else {
        if (m.tool == "Pen" || m.tool == "Highlight")
          m.points.append(at);
        else
          m.points.last() = at;
        if (ev->modifiers().testFlag(Qt::ShiftModifier) &&
            (m.tool == "Line" || m.tool == "Arrow")) {
          QLineF line(m.points.first(), at);
          line.setAngle(45 * qRound(line.angle() / 45));
          m.points.last() = line.p2().toPoint();
        }
      }
    }
  }
  update();
}
void Overlay::mouseReleaseEvent(QMouseEvent *ev) {
  if (ev->button() != Qt::LeftButton || !dragging)
    return;
  mouseMoveEvent(ev);
  dragging = false;
}
void Overlay::keyPressEvent(QKeyEvent *ev) {
  const bool fine = ev->modifiers().testFlag(Qt::ShiftModifier);
  const bool resize = ev->modifiers().testFlag(Qt::AltModifier) ||
                      (fine && ev->modifiers().testFlag(Qt::ControlModifier));
  if (!dragging && tool == "Select" && !selection.isEmpty()) {
    int step = fine ? 1 : 15;
    QPoint delta;
    switch (ev->key()) {
    case Qt::Key_Left:
      delta.setX(-step);
      break;
    case Qt::Key_Right:
      delta.setX(step);
      break;
    case Qt::Key_Up:
      delta.setY(-step);
      break;
    case Qt::Key_Down:
      delta.setY(step);
      break;
    }
    if (!delta.isNull()) {
      if (resize) {
        selection.setRight(qBound(selection.left(),
                                  selection.right() + delta.x(),
                                  frozen.width() - 1));
        selection.setBottom(qBound(selection.top(),
                                   selection.bottom() + delta.y(),
                                   frozen.height() - 1));
      } else {
        QPoint at = selection.topLeft() + delta;
        selection.moveTo(
            qBound(0, at.x(), frozen.width() - selection.width()),
            qBound(0, at.y(), frozen.height() - selection.height()));
      }
      if (fine)
        lens = resize ? selection.bottomRight() : selection.center();
      update();
      return;
    }
  }
  if (tool == "Edit marks" && ev->key() == Qt::Key_F2 && active >= 0 &&
      active < marks.size()) {
    auto mark = marks[active];
    if (mark.tool == "Text" || mark.tool == "Number") {
      if (editLabel(this, mark) && mark != marks[active]) {
        checkpoint();
        marks[active] = mark;
        update();
      }
    }
    return;
  }
  if (ev->matches(QKeySequence::Copy)) {
    accept();
    return;
  }
  if (ev->matches(QKeySequence::Undo)) {
    undo();
    return;
  }
  if (ev->matches(QKeySequence::Redo)) {
    redo();
    return;
  }
  if (ev->key() == Qt::Key_Delete && active >= 0 && active < marks.size()) {
    checkpoint();
    marks.removeAt(active);
    active = -1;
    update();
    return;
  }
  if (ev->key() == Qt::Key_Return || ev->key() == Qt::Key_Enter) {
    accept();
    return;
  }
  if (ev->key() == Qt::Key_W) {
    bar->findChild<QComboBox *>()->setCurrentText("Window");
    return;
  }
  if (ev->key() == Qt::Key_B) {
    borders->toggle();
    update();
    return;
  }
  QDialog::keyPressEvent(ev);
}
void Overlay::keyReleaseEvent(QKeyEvent *event) {
  if (event->key() == Qt::Key_Shift) {
    lens.reset();
    update();
  }
  QDialog::keyReleaseEvent(event);
}
