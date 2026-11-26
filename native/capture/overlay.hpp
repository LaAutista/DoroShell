#pragma once
#include <QColor>
#include <QDialog>
#include <QImage>
#include <QList>
#include "render.hpp"
#include <QPoint>
#include <optional>

class QWidget;
class QLabel;
class QCheckBox;
class QSpinBox;
struct WindowBounds {
  QRect client, frame;
};
QList<WindowBounds> windowsAtCapture();
using doro::capture::Mark;
class Overlay : public QDialog {
  QImage frozen;
  mutable QImage rendered;
  QList<WindowBounds> windows;
  QRect selection, previous;
  QPoint origin;
  QString tool = "Select";
  QColor color{"#e83759"};
  QList<Mark> marks;
  QList<QList<Mark>> past, future;
  int active = -1;
  bool dragging = false, moving = false;
  std::optional<QPoint> lens;
  Qt::Edges resizeEdges;
  QWidget *bar;
  QSpinBox *width;
  QCheckBox *borders;
  QRect hitWindow(QPoint at) const;
  void checkpoint();
  void undo();
  void redo();
  const QImage &annotatedImage() const;
  void chooseTool(const QString &name);

protected:
  void paintEvent(QPaintEvent *) override;
  void mousePressEvent(QMouseEvent *) override;
  void mouseReleaseEvent(QMouseEvent *) override;
  void mouseMoveEvent(QMouseEvent *) override;
  void keyPressEvent(QKeyEvent *) override;
  void keyReleaseEvent(QKeyEvent *) override;

public:
  struct Request {
    bool monitor = false;
    bool pointer = false;
    int delay = 0;
  };
  std::optional<Request> nextCapture;
  Overlay(QImage image, QRect bounds, QList<WindowBounds> windows);
  QImage resultImage() const;
};
