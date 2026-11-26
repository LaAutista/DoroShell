#include "preferences.hpp"
#include <QtWidgets>
#include <cmath>

namespace {
struct Place {
  const char *label, *location, *icon;
  QStandardPaths::StandardLocation qt;
};
constexpr Place defaults[] = {
    {"Home", "HomeLocation", "user-home", QStandardPaths::HomeLocation},
    {"Documents", "DocumentsLocation", "folder-documents",
     QStandardPaths::DocumentsLocation},
    {"Downloads", "DownloadLocation", "folder-download",
     QStandardPaths::DownloadLocation},
    {"Pictures", "PicturesLocation", "folder-pictures",
     QStandardPaths::PicturesLocation},
    {"Music", "MusicLocation", "folder-music", QStandardPaths::MusicLocation},
    {"Videos", "MoviesLocation", "folder-videos",
     QStandardPaths::MoviesLocation}};
QString resolved(const QJsonObject &o) {
  for (auto p : defaults)
    if (o["standard"] == p.location)
      return QStandardPaths::writableLocation(p.qt);
  return o["path"].toString();
}
bool valid(const QJsonObject &settings) {
  auto folders = settings["folders"].toArray();
  int version = settings["version"].toInt();
  if ((version != 1 && version != 2) || !settings["folders"].isArray() ||
      folders.size() > 100)
    return false;
  for (auto v : folders) {
    auto o = v.toObject();
    if (o.contains("type")) {
      if (version != 2 || o.size() != 1 || o["type"] != "separator")
        return false;
      continue;
    }
    if (!o["visible"].isBool() || o["label"].toString().trimmed().isEmpty() ||
        o["label"].toString().size() > 100)
      return false;
    if (o.contains("icon") && !o["icon"].isString())
      return false;
    if (o.contains("standard") == o.contains("path") ||
        !QDir::isAbsolutePath(resolved(o)) || resolved(o).contains(QChar::Null))
      return false;
  }
  if (settings.contains("hiddenSystemLinks")) {
    if (!settings["hiddenSystemLinks"].isArray())
      return false;
    for (auto v : settings["hiddenSystemLinks"].toArray())
      if (!v.isString())
        return false;
  }
  if (settings.contains("portrait") &&
      (!settings["portrait"].isString() ||
       (!settings["portrait"].toString().isEmpty() &&
        !QDir::isAbsolutePath(settings["portrait"].toString()))))
    return false;
  if (settings.contains("portraitCrop") && !settings["portraitCrop"].isNull()) {
    auto c = settings["portraitCrop"].toObject();
    if (c.size() != 3)
      return false;
    for (auto k : {"x", "y", "zoom"}) {
      double n = c.value(k).toDouble(-1);
      bool zoom = QByteArray(k) == "zoom";
      if (n < (zoom ? 1 : 0) || n > (zoom ? 4 : 1))
        return false;
    }
  }
  return true;
}
Preference folderPreference() {
  QJsonArray links;
  for (auto p : defaults)
    links << QJsonObject{{"label", p.label},
                         {"standard", p.location},
                         {"icon", p.icon},
                         {"visible", true}};
  auto prefs = readPreference(
      "folders.json",
      QJsonDocument(QJsonObject{{"version", 1}, {"folders", links}}));
  if (!valid(prefs.value.object()))
    prefs.error = "Invalid folder preferences. Original file preserved.";
  return prefs;
}
bool save(QWidget *parent, Preference &p, const QJsonObject &value) {
  if (!valid(value)) {
    QMessageBox::warning(parent, "Folder links",
                         "Check the folder names and paths.");
    return false;
  }
  try {
    p.save(QJsonDocument(value), true);
    return true;
  } catch (const std::exception &e) {
    QMessageBox::warning(parent, "Preferences", QString::fromUtf8(e.what()));
    return false;
  }
}
class CropView final : public QWidget {
public:
  QImage image;
  QPointF center{.5, .5};
  double zoom = 1;
  explicit CropView(QImage source) : image(std::move(source)) {
    setMinimumSize(200, 200);
    setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Expanding);
    setFocusPolicy(Qt::StrongFocus);
    setAccessibleName("Crop preview. Drag or press arrows to reposition.");
    setCursor(Qt::OpenHandCursor);
  }
  QRectF sourceRect() const {
    const double side = qMin(image.width(), image.height()) / zoom;
    return {
        qBound(0., center.x() * image.width() - side / 2, image.width() - side),
        qBound(0., center.y() * image.height() - side / 2,
               image.height() - side),
        side, side};
  }
  QRectF target() const {
    double side = qMin(width(), height());
    return {(width() - side) / 2, (height() - side) / 2, side, side};
  }
  void normalize() {
    auto c = sourceRect().center();
    center = {c.x() / image.width(), c.y() / image.height()};
    update();
  }

protected:
  void paintEvent(QPaintEvent *) override {
    QPainter p(this);
    p.fillRect(rect(), Qt::darkGray);
    p.setRenderHint(QPainter::SmoothPixmapTransform);
    p.drawImage(target(), image, sourceRect());
  }
  void mousePressEvent(QMouseEvent *e) override {
    if (e->button() == Qt::LeftButton) {
      last = e->position();
      setCursor(Qt::ClosedHandCursor);
    }
  }
  void mouseMoveEvent(QMouseEvent *e) override {
    if (last) {
      auto d = e->position() - *last;
      last = e->position();
      shift(d);
    }
  }
  void mouseReleaseEvent(QMouseEvent *) override {
    last.reset();
    setCursor(Qt::OpenHandCursor);
  }
  void keyPressEvent(QKeyEvent *e) override {
    switch (e->key()) {
    case Qt::Key_Left:
      shift({-3, 0});
      break;
    case Qt::Key_Right:
      shift({3, 0});
      break;
    case Qt::Key_Up:
      shift({0, -3});
      break;
    case Qt::Key_Down:
      shift({0, 3});
      break;
    default:
      QWidget::keyPressEvent(e);
    }
  }

private:
  void shift(QPointF delta) {
    double scale = sourceRect().width() / target().width();
    center -= QPointF(delta.x() * scale / image.width(),
                      delta.y() * scale / image.height());
    normalize();
  }
  std::optional<QPointF> last;
};
bool choosePicture(QWidget *parent, QJsonObject &prefs) {
  QString path = QFileDialog::getOpenFileName(
      parent, "Choose Start portrait", prefs.value("portrait").toString(),
      "Images (*.png *.jpg *.jpeg *.bmp *.webp);;All files (*)");
  if (path.isEmpty())
    return false;
  QImageReader reader(path);
  reader.setAutoTransform(true);
  auto size = reader.size();
  if (size.isValid() && (size.width() > 4096 || size.height() > 4096))
    reader.setScaledSize(size.scaled(4096, 4096, Qt::KeepAspectRatio));
  auto image = reader.read();
  if (image.isNull()) {
    QMessageBox::warning(parent, "Start portrait", reader.errorString());
    return false;
  }
  QDialog dialog(parent);
  dialog.setWindowTitle("Frame Start portrait");
  auto *layout = new QVBoxLayout(&dialog);
  auto *view = new CropView(std::move(image));
  layout->addWidget(view);
  auto *slider = new QSlider(Qt::Horizontal);
  slider->setRange(100, 400);
  slider->setAccessibleName("Zoom");
  if (path == prefs.value("portrait").toString()) {
    auto c = prefs.value("portraitCrop").toObject();
    view->center = {c["x"].toDouble(.5), c["y"].toDouble(.5)};
    view->zoom = c["zoom"].toDouble(1.);
  }
  slider->setValue(qRound(view->zoom * 100));
  layout->addWidget(slider);
  QObject::connect(slider, &QSlider::valueChanged, &dialog, [view](int n) {
    view->zoom = n / 100.;
    view->normalize();
  });
  auto *box =
      new QDialogButtonBox(QDialogButtonBox::Ok | QDialogButtonBox::Cancel);
  layout->addWidget(box);
  QObject::connect(box, &QDialogButtonBox::accepted, &dialog, &QDialog::accept);
  QObject::connect(box, &QDialogButtonBox::rejected, &dialog, &QDialog::reject);
  dialog.resize(360, 430);
  if (dialog.exec() != QDialog::Accepted)
    return false;
  view->normalize();
  prefs["portrait"] = path;
  prefs["portraitCrop"] = QJsonObject{
      {"x", view->center.x()}, {"y", view->center.y()}, {"zoom", view->zoom}};
  return true;
}
} // namespace
Preference documentPreference() {
  auto p = readPreference(
      "recent-documents.json",
      QJsonDocument(QJsonObject{{"version", 1}, {"enabled", false}}));
  auto o = p.value.object();
  if (o.size() != 2 || o.value("version").toInt() != 1 ||
      !o.value("enabled").isBool())
    p.error = "Invalid document-history preferences";
  return p;
}
bool documentsEnabled() {
  auto p = documentPreference();
  return p.error.isEmpty() && p.value.object()["enabled"].toBool();
}
void editPortrait(QWidget *parent) {
  auto p = folderPreference();
  if (!p.error.isEmpty()) {
    QMessageBox::warning(parent, "Start portrait", p.error);
    return;
  }
  auto o = p.value.object();
  if (choosePicture(parent, o))
    save(parent, p, o);
}
void editFolderPreferences(QWidget *parent) {
  auto p = folderPreference();
  if (!p.error.isEmpty()) {
    QMessageBox::warning(parent, "Folder links", p.error);
    return;
  }
  auto o = p.value.object();
  QDialog dialog(parent);
  dialog.setWindowTitle("Start menu folder links");
  auto *layout = new QVBoxLayout(&dialog);
  auto *table = new QTableWidget(0, 3);
  table->setHorizontalHeaderLabels({"Name", "Folder", "Show"});
  table->horizontalHeader()->setSectionResizeMode(1, QHeaderView::Stretch);
  table->setSelectionBehavior(QAbstractItemView::SelectRows);
  layout->addWidget(table);
  auto insert = [table](int row, QJsonObject link) {
    table->insertRow(row);
    bool sep = link.value("type") == "separator";
    auto *label =
        new QTableWidgetItem(sep ? "— Separator —" : link["label"].toString());
    label->setData(Qt::UserRole, link);
    if (sep)
      label->setFlags(label->flags() & ~Qt::ItemIsEditable);
    table->setItem(row, 0, label);
    auto *path = new QTableWidgetItem(sep ? "" : resolved(link));
    path->setFlags(path->flags() & ~Qt::ItemIsEditable);
    table->setItem(row, 1, path);
    auto *show = new QTableWidgetItem;
    show->setFlags(Qt::ItemIsEnabled | Qt::ItemIsSelectable);
    if (!sep) {
      show->setFlags(show->flags() | Qt::ItemIsUserCheckable);
      show->setCheckState(link["visible"].toBool() ? Qt::Checked
                                                   : Qt::Unchecked);
    }
    table->setItem(row, 2, show);
    table->selectRow(row);
  };
  for (auto v : o.value("folders").toArray())
    insert(table->rowCount(), v.toObject());
  auto *tools = new QHBoxLayout;
  layout->addLayout(tools);
  auto button = [&](QString text, std::function<void()> fn) {
    auto *b = new QPushButton(text);
    tools->addWidget(b);
    QObject::connect(b, &QPushButton::clicked, &dialog, fn);
  };
  button("Add folder…", [&] {
    auto path = QFileDialog::getExistingDirectory(&dialog, "Choose folder");
    if (!path.isEmpty() && table->rowCount() < 100)
      insert(table->rowCount(),
             QJsonObject{{"label", QDir(path).dirName().isEmpty()
                                       ? path
                                       : QDir(path).dirName()},
                         {"path", path},
                         {"visible", true}});
  });
  button("Change folder…", [&] {
    auto row = table->currentRow();
    if (row < 0)
      return;
    auto *cell = table->item(row, 0);
    auto v = cell->data(Qt::UserRole).toJsonObject();
    if (v.value("type") == "separator")
      return;
    auto path = QFileDialog::getExistingDirectory(&dialog, "Choose folder",
                                                  resolved(v));
    if (path.isEmpty())
      return;
    v.remove("standard");
    v["path"] = path;
    cell->setData(Qt::UserRole, v);
    table->item(row, 1)->setText(path);
  });
  button("Separator", [&] {
    if (table->rowCount() < 100)
      insert(table->rowCount(), QJsonObject{{"type", "separator"}});
  });
  for (int delta : {-1, 1})
    button(delta < 0 ? "Up" : "Down", [table, delta] {
      int row = table->currentRow(), to = row + delta;
      if (row < 0 || to < 0 || to >= table->rowCount())
        return;
      for (int c = 0; c < 3; ++c) {
        auto *a = table->takeItem(row, c), *b = table->takeItem(to, c);
        table->setItem(row, c, b);
        table->setItem(to, c, a);
      }
      table->selectRow(to);
    });
  button("Remove", [table] {
    if (table->currentRow() >= 0)
      table->removeRow(table->currentRow());
  });
  auto *systems = new QGroupBox("System links");
  auto *grid = new QGridLayout(systems);
  layout->addWidget(systems);
  QStringList labels = {"Games",         "Computer",
                        "Control Panel", "Network connections",
                        "Printers",      "Default programs"};
  QList<QCheckBox *> toggles;
  for (int i = 0; i < labels.size(); ++i) {
    auto *b = new QCheckBox(labels[i]);
    b->setChecked(!o.value("hiddenSystemLinks").toArray().contains(labels[i]));
    grid->addWidget(b, i / 3, i % 3);
    toggles << b;
  }
  tools = new QHBoxLayout;
  layout->addLayout(tools);
  button("Choose portrait…", [&] { choosePicture(&dialog, o); });
  button("Use Start icon", [&] {
    o.remove("portrait");
    o.remove("portraitCrop");
  });
  auto *box =
      new QDialogButtonBox(QDialogButtonBox::Save | QDialogButtonBox::Cancel);
  layout->addWidget(box);
  QObject::connect(box, &QDialogButtonBox::rejected, &dialog, &QDialog::reject);
  QObject::connect(box, &QDialogButtonBox::accepted, &dialog, [&] {
    QJsonArray folders;
    int version = 1;
    for (int row = 0; row < table->rowCount(); ++row) {
      auto *cell = table->item(row, 0);
      auto v = cell->data(Qt::UserRole).toJsonObject();
      if (v.value("type") == "separator")
        version = 2;
      else {
        v["label"] = cell->text().trimmed();
        v["visible"] = table->item(row, 2)->checkState() == Qt::Checked;
      }
      folders << v;
    }
    o["folders"] = folders;
    o["version"] = version;
    QJsonArray hidden;
    for (auto *b : toggles)
      if (!b->isChecked())
        hidden << b->text();
    o["hiddenSystemLinks"] = hidden;
    if (save(&dialog, p, o))
      dialog.accept();
  });
  dialog.resize(660, 460);
  dialog.exec();
}
