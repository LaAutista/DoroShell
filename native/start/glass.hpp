// Experimental wallpaper-only glass. No compositor, screen capture or polling.
// Copyright 2026 DoroShell contributors. SPDX-License-Identifier:
// LGPL-2.1-or-later
#pragma once
#include <QApplication>
#include <QDateTime>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QFileSystemWatcher>
#include <QFrame>
#include <QImageReader>
#include <QJsonDocument>
#include <QJsonObject>
#include <QPainter>
#include <QPainterPath>
#include <QPointer>
#include <QRunnable>
#include <QScreen>
#include <QSettings>
#include <QStandardPaths>
#include <QThreadPool>
#include <QTimer>
#include <algorithm>
#include <sys/stat.h>

class DoroWallpaperGlass final : public QFrame {
public:
  explicit DoroWallpaperGlass(QWidget *parent) : QFrame(parent) {
    config = QStandardPaths::writableLocation(QStandardPaths::ConfigLocation) +
             QStringLiteral("/doroshell/wallpaper-glass.json");
    const QString root =
        QStandardPaths::writableLocation(QStandardPaths::ConfigLocation);
    pcConfig = root + QStringLiteral("/pcmanfm-qt/lxqt/settings.conf");
    QSettings theme(root + QStringLiteral("/doroshell/theme.conf"),
                    QSettings::IniFormat);
    savedPalette =
        theme.value(QStringLiteral("Theme/name"), QStringLiteral("windows"))
            .toString();
    watch.addPath(root);
    if (QFileInfo(config).dir().exists())
      watch.addPath(QFileInfo(config).absolutePath());
    connect(&watch, &QFileSystemWatcher::fileChanged, this,
            [this] { readConfig(); });
    connect(&watch, &QFileSystemWatcher::directoryChanged, this,
            [this] { readConfig(); });
    geometryTimer.setSingleShot(true);
    connect(&geometryTimer, &QTimer::timeout, this, [this] { compose(); });
    parent->installEventFilter(this);
    QTimer::singleShot(0, this, [this] { readConfig(); });
  }

protected:
  bool eventFilter(QObject *, QEvent *e) override {
    if (e->type() == QEvent::Move || e->type() == QEvent::Resize ||
        e->type() == QEvent::Show ||
        e->type() == QEvent::ScreenChangeInternal ||
        e->type() == QEvent::DevicePixelRatioChange)
      geometryTimer.start(0);
    return false;
  }
  void resizeEvent(QResizeEvent *e) override {
    QFrame::resizeEvent(e);
    geometryTimer.start(0);
  }
  void paintEvent(QPaintEvent *e) override {
    if (surface.isNull()) {
      QFrame::paintEvent(e);
      return;
    }
    QPainter p(this);
    QPainterPath outline;
    outline.addRoundedRect(rect(), 15, 15);
    p.setRenderHint(QPainter::Antialiasing);
    p.setClipPath(outline);
    p.drawImage(0, 0, surface);
  }

private:
  bool tintedChildren = false;
  void tintPanels(bool active) {
    if (tintedChildren == active)
      return;
    tintedChildren = active;
    const QStringList colors =
        palette == "heretic"  ? QStringList{"#87211c20", "#ec222124"}
        : palette == "polar"  ? QStringList{"#87244f73", "#ecf4fbff"}
        : palette == "spring" ? QStringList{"#873c5a30", "#ecfffdf0"}
                              : QStringList{"#87773353", "#ecfff5fb"};
    const QStringList names = {"placesPanel", "applicationsPanel"};
    for (int i = 0; i < names.size(); ++i)
      if (auto *panel = findChild<QWidget *>(names[i]))
        panel->setStyleSheet(active
                                 ? QStringLiteral("QWidget#%1{background:%2}")
                                       .arg(names[i], colors[i])
                                 : QString{});
  }
  QFileSystemWatcher watch;
  QTimer geometryTimer;
  QString config, pcConfig, file, mode, palette, signature, background,
      savedPalette;
  bool transform = false;
  QImage atlas, surface;
  QSize screenPixels;
  QColor tint;
  quint64 generation = 0;
  bool busy = false, pending = false, enabled = false;

  static QImage blur(QImage image) {
    image = image.convertToFormat(QImage::Format_RGB32);
    // Small separable radius-2 box blur twice, operating only on the 1/8 atlas.
    for (int pass = 0; pass < 2; ++pass)
      for (int axis = 0; axis < 2; ++axis) {
        QImage out(image.size(), QImage::Format_RGB32);
        for (int y = 0; y < image.height(); ++y) {
          auto *row = reinterpret_cast<QRgb *>(out.scanLine(y));
          for (int x = 0; x < image.width(); ++x) {
            int r = 0, g = 0, b = 0;
            for (int offset = -2; offset <= 2; ++offset) {
              int sx = std::clamp(x + (axis == 0 ? offset : 0), 0,
                                  image.width() - 1);
              int sy = std::clamp(y + (axis == 1 ? offset : 0), 0,
                                  image.height() - 1);
              QRgb c =
                  reinterpret_cast<const QRgb *>(image.constScanLine(sy))[sx];
              r += qRed(c);
              g += qGreen(c);
              b += qBlue(c);
            }
            row[x] = qRgb(r / 5, g / 5, b / 5);
          }
        }
        image = out;
      }
    return image;
  }
  static QImage loadAtlas(const QString &path, const QString &fit,
                          QSize screenSize, const QString &background,
                          bool transform) {
    QFileInfo info(path);
    if (!info.isFile() || info.size() > 64 * 1024 * 1024)
      return {};
    QImageReader reader(path);
    reader.setAutoTransform(transform);
    QSize source = reader.size();
    const bool rotated =
        transform && (int(reader.transformation()) &
                      int(QImageIOHandler::TransformationRotate90)) != 0;
    if (rotated)
      source.transpose();
    if (source.isEmpty() || qint64(source.width()) * source.height() > 40000000)
      return {};
    QSize small(std::max(1, screenSize.width() / 8),
                std::max(1, screenSize.height() / 8));
    QSize decode =
        fit == QStringLiteral("stretch")
            ? small
            : source.scaled(small, fit == QStringLiteral("fit")
                                       ? Qt::KeepAspectRatio
                                       : Qt::KeepAspectRatioByExpanding);
    if (decode.isEmpty() || qint64(decode.width()) * decode.height() > 4000000)
      return {};
    reader.setScaledSize(rotated ? QSize(decode.height(), decode.width())
                                 : decode);
    QImage sourceImage = reader.read();
    if (sourceImage.isNull())
      return {};
    sourceImage = sourceImage.scaled(decode, Qt::IgnoreAspectRatio,
                                     Qt::SmoothTransformation);
    QImage canvas(small, QImage::Format_RGB32);
    canvas.fill(QColor(background));
    QPainter p(&canvas);
    p.drawImage((small.width() - decode.width()) / 2,
                (small.height() - decode.height()) / 2, sourceImage);
    p.end();
    return blur(canvas);
  }
  void readConfig() {
    const QString configRoot =
        QStandardPaths::writableLocation(QStandardPaths::ConfigLocation);
    for (const QString &path : {config, pcConfig}) {
      if (QFileInfo(path).isFile() && !watch.files().contains(path))
        watch.addPath(path);
      for (const QString &dir :
           {QFileInfo(path).absolutePath(),
            QFileInfo(QFileInfo(path).absolutePath()).absolutePath()})
        if (QDir(dir).exists() && !watch.directories().contains(dir))
          watch.addPath(dir);
    }
    QFile input(config);
    QJsonObject object;
    if (input.open(QIODevice::ReadOnly) && input.size() < 16384)
      object = QJsonDocument::fromJson(input.readAll()).object();
    if (object.value(QStringLiteral("version")).toInt() != 1 ||
        !object.value(QStringLiteral("enabled")).toBool(false) ||
        !QFileInfo(pcConfig).isFile() ||
        QFileInfo(pcConfig).size() >= 2 * 1024 * 1024) {
      enabled = false;
      pending = false;
      ++generation;
      signature.clear();
      tintPanels(false);
      atlas = {};
      surface = {};
      update();
      return;
    }
    QSettings desktop(pcConfig, QSettings::IniFormat);
    const QString nextFile =
        desktop.value(QStringLiteral("Desktop/Wallpaper")).toString();
    QString nextMode =
        desktop.value(QStringLiteral("Desktop/WallpaperMode")).toString();
    if (nextMode == QStringLiteral("zoom"))
      nextMode = QStringLiteral("crop");
    const QString nextPalette = savedPalette;
    const QFileInfo info(nextFile);
    QString nextBackground =
        desktop
            .value(QStringLiteral("Desktop/BgColor"), QStringLiteral("#000000"))
            .toString();
    if (!QColor(nextBackground).isValid())
      nextBackground = QStringLiteral("#000000");
    bool intervalOK = false;
    int interval = desktop.value(QStringLiteral("Desktop/SlideShowInterval"), 0)
                       .toInt(&intervalOK);
    bool nextTransform =
        desktop.value(QStringLiteral("Desktop/TransformWallpaper"), false)
            .toBool() &&
        (info.suffix().compare(QStringLiteral("jpg"), Qt::CaseInsensitive) ==
             0 ||
         info.suffix().compare(QStringLiteral("jpeg"), Qt::CaseInsensitive) ==
             0);
    const bool nextEnabled =
        object.value(QStringLiteral("version")).toInt() == 1 &&
        object.value(QStringLiteral("enabled")).toBool(false) &&
        info.isAbsolute() && desktop.status() == QSettings::NoError &&
        QFileInfo(pcConfig).size() < 2 * 1024 * 1024 &&
        !desktop.value(QStringLiteral("Desktop/PerScreenWallpaper"), false)
             .toBool() &&
        intervalOK && interval == 0 &&
        (nextMode == QStringLiteral("stretch") ||
         nextMode == QStringLiteral("crop") ||
         nextMode == QStringLiteral("fit"));
    struct stat stamp{};
    ::stat(QFile::encodeName(nextFile).constData(), &stamp);
    const QString identity = QStringLiteral("%1:%2:%3|")
                                 .arg(qulonglong(stamp.st_ino))
                                 .arg(qlonglong(stamp.st_mtim.tv_sec))
                                 .arg(qlonglong(stamp.st_mtim.tv_nsec));
    const QString nextSignature =
        identity + nextBackground +
        QStringLiteral("%1|%2|%3|%4|%5|%6|%7")
            .arg(nextFile, nextMode, nextPalette)
            .arg(nextEnabled)
            .arg(info.lastModified().toMSecsSinceEpoch())
            .arg(info.size())
            .arg(nextTransform);
    if (info.isFile() && !watch.files().contains(nextFile))
      watch.addPath(nextFile);
    if (nextSignature == signature)
      return;
    signature = nextSignature;
    background = nextBackground;
    file = nextFile;
    mode = nextMode;
    palette = nextPalette;
    enabled = nextEnabled;
    transform = nextTransform;
    ++generation;
    for (const QString &path : watch.files())
      if (path != config && path != pcConfig && path != file)
        watch.removePath(path);
    const QStringList keepDirs = {
        configRoot, QFileInfo(config).absolutePath(),
        QFileInfo(pcConfig).absolutePath(),
        QFileInfo(QFileInfo(pcConfig).absolutePath()).absolutePath(),
        info.absolutePath()};
    for (const QString &path : watch.directories())
      if (!keepDirs.contains(path))
        watch.removePath(path);
    if (!file.isEmpty() && info.dir().exists() &&
        !watch.directories().contains(info.absolutePath()))
      watch.addPath(info.absolutePath());
    tint = QColor(
        palette == QStringLiteral("polar")     ? QStringLiteral("#dceef9")
        : palette == QStringLiteral("heretic") ? QStringLiteral("#302c30")
        : palette == QStringLiteral("spring")  ? QStringLiteral("#e6edd0")
                                               : QStringLiteral("#f4dce9"));
    atlas = {};
    surface = {};
    tintPanels(false);
    update();
    pending = enabled;
    startDecode();
  }
  QSize physicalScreen() const {
    if (!screen())
      return {};
    const QSize size = screen()->geometry().size();
    const qreal dpr = devicePixelRatioF();
    return QSize(qRound(size.width() * dpr), qRound(size.height() * dpr));
  }
  void startDecode() {
    if (!pending || busy || !enabled)
      return;
    screenPixels = physicalScreen();
    if (screenPixels.isEmpty() ||
        qint64(screenPixels.width()) * screenPixels.height() > 40000000) {
      pending = false;
      return;
    }
    pending = false;
    busy = true;
    const quint64 id = generation;
    const QString path = file, fit = mode, bg = background;
    const QSize size = screenPixels;
    const bool orientation = transform;
    QPointer<DoroWallpaperGlass> guard(this);
    QThreadPool::globalInstance()->start(
        QRunnable::create([guard, id, path, fit, size, bg, orientation] {
          QImage result = loadAtlas(path, fit, size, bg, orientation);
          QMetaObject::invokeMethod(
              qApp,
              [guard, id, result] {
                if (!guard)
                  return;
                guard->busy = false;
                if (id == guard->generation) {
                  guard->atlas = result;
                  guard->compose();
                }
                guard->startDecode();
              },
              Qt::QueuedConnection);
        }));
  }
  void compose() {
    if (!enabled || !screen())
      return;
    const QSize pixels = physicalScreen();
    if (screenPixels != pixels) {
      ++generation;
      pending = true;
      atlas = {};
      surface = {};
      startDecode();
      update();
      return;
    }
    if (atlas.isNull())
      return;
    const qreal dpr = devicePixelRatioF();
    const QPoint point = mapToGlobal(QPoint()) - screen()->geometry().topLeft();
    const QSize dims(qRound(width() * dpr), qRound(height() * dpr));
    if (dims.isEmpty() || qint64(dims.width()) * dims.height() > 16000000)
      return;
    surface = QImage(dims, QImage::Format_RGB32);
    surface.fill(tint);
    QPainter p(&surface);
    p.setRenderHint(QPainter::SmoothPixmapTransform);
    p.drawImage(QRect(-qRound(point.x() * dpr), -qRound(point.y() * dpr),
                      pixels.width(), pixels.height()),
                atlas);
    QColor color = tint;
    color.setAlpha(palette == QStringLiteral("heretic") ? 170 : 115);
    p.fillRect(surface.rect(), color);
    QLinearGradient sheen(0, 0, 0, dims.height());
    sheen.setColorAt(0, QColor(255, 255, 255, 95));
    sheen.setColorAt(.49, QColor(255, 255, 255, 20));
    sheen.setColorAt(.50, QColor(0, 0, 0, 16));
    sheen.setColorAt(1, QColor(0, 0, 0, 25));
    p.fillRect(surface.rect(), sheen);
    p.setPen(QColor(255, 255, 255, 180));
    p.drawLine(0, 0, dims.width(), 0);
    p.end();
    surface.setDevicePixelRatio(dpr);
    tintPanels(true);
    update();
  }
};
