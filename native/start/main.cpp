#include "browse.hpp"
#include "focus.hpp"
#include "glass.hpp"
#include "preferences.hpp"
#include <QCryptographicHash>
#include <QLocalServer>
#include <QLocalSocket>
#include <QLockFile>
#include <QtDBus>
#include <QtWidgets>
#include <signal.h>
#include <sys/prctl.h>
#include <unistd.h>

namespace {
constexpr int PathRole = Qt::UserRole + 1;
QByteArray runningVersion() {
  struct stat st{};
  if (::stat("/proc/self/exe", &st))
    return {};
  return QByteArray::number(qulonglong(st.st_dev)) + '-' +
         QByteArray::number(qulonglong(st.st_ino)) + '-' +
         QByteArray::number(qlonglong(st.st_mtim.tv_sec)) + '-' +
         QByteArray::number(qlonglong(st.st_mtim.tv_nsec));
}
bool hasCompositor() {
  if (QGuiApplication::platformName() != "xcb")
    return false;
  int screen = 0;
  std::unique_ptr<xcb_connection_t, decltype(&xcb_disconnect)> c(
      xcb_connect(nullptr, &screen), xcb_disconnect);
  if (xcb_connection_has_error(c.get()))
    return false;
  auto name = QByteArray("_NET_WM_CM_S") + QByteArray::number(screen);
  auto *a = xcb_intern_atom_reply(
      c.get(), xcb_intern_atom(c.get(), true, name.size(), name), nullptr);
  if (!a)
    return false;
  auto *r =
      a->atom ? xcb_get_selection_owner_reply(
                    c.get(), xcb_get_selection_owner(c.get(), a->atom), nullptr)
              : nullptr;
  bool found = r && r->owner;
  free(a);
  free(r);
  return found;
}
class AppList final : public QListWidget {
public:
  using QListWidget::QListWidget;
  bool dragging = false;
  std::function<void(QString, QString, bool)> reorder;
  bool internalDrop = false;

protected:
  void startDrag(Qt::DropActions) override {
    auto *item = currentItem();
    if (!item)
      return;
    auto path = item->data(PathRole).toString();
    if (!QFileInfo(path).isAbsolute() || !QFileInfo(path).isFile())
      return;
    auto *drag = new QDrag(this);
    auto *mime = new QMimeData;
    mime->setUrls({QUrl::fromLocalFile(path)});
    drag->setMimeData(mime);
    drag->setPixmap(item->icon().pixmap(iconSize()));
    dragging = true;
    internalDrop = false;
    if (drag->exec(Qt::CopyAction) == Qt::CopyAction && !internalDrop)
      window()->hide();
    QTimer::singleShot(0, this, [this] { dragging = false; });
  }
  void dragMoveEvent(QDragMoveEvent *e) override {
    if (e->source() == this && reorder)
      e->acceptProposedAction();
    else
      e->ignore();
  }
  void dropEvent(QDropEvent *e) override {
    auto *dest = itemAt(e->position().toPoint());
    auto *source = currentItem();
    if (e->source() != this || !dest || !source || !reorder)
      return;
    internalDrop = true;
    reorder(source->data(Qt::UserRole).toString(),
            dest->data(Qt::UserRole).toString(),
            e->position().y() > visualItemRect(dest).center().y());
    e->acceptProposedAction();
  }
  void mouseReleaseEvent(QMouseEvent *e) override {
    if (!dragging)
      QListWidget::mouseReleaseEvent(e);
    else
      e->accept();
  }
};

struct Place {
  const char *label;
  const char *key;
  QStandardPaths::StandardLocation location;
};
constexpr Place places[] = {
    {"Home", "HomeLocation", QStandardPaths::HomeLocation},
    {"Documents", "DocumentsLocation", QStandardPaths::DocumentsLocation},
    {"Downloads", "DownloadLocation", QStandardPaths::DownloadLocation},
    {"Pictures", "PicturesLocation", QStandardPaths::PicturesLocation},
    {"Music", "MusicLocation", QStandardPaths::MusicLocation},
    {"Videos", "MoviesLocation", QStandardPaths::MoviesLocation}};
class Menu final : public QWidget {
public:
  std::function<void()> requestReopen;
  explicit Menu(const Catalog &catalog)
      : QWidget(nullptr, Qt::Popup), apps(catalog), pins(readPins(apps)) {
    setWindowTitle("DoroShell Start");
    setObjectName("doroShellStart");
    setAttribute(Qt::WA_TranslucentBackground);
    auto *outer = new QVBoxLayout(this);
    outer->setContentsMargins(2, 48, 2, 2);
    auto cfg = QStandardPaths::writableLocation(
                   QStandardPaths::GenericConfigLocation) +
               "/doroshell/";
    auto *frame = QFileInfo::exists(cfg + "wallpaper-glass.json")
                      ? static_cast<QWidget *>(new DoroWallpaperGlass(this))
                      : new QWidget;
    frame->setObjectName("glassFrame");
    outer->addWidget(frame);
    auto *body = new QHBoxLayout(frame);
    auto *left = new QWidget;
    left->setObjectName("applicationsPanel");
    body->addWidget(left, 3);
    auto *l = new QVBoxLayout(left);
    heading = new QLabel("Pinned");
    heading->setObjectName("pinnedHeading");
    l->addWidget(heading);
    cat = new QComboBox;
    cat->addItems({"All applications", "Pinned", "Recent", "AudioVideo",
                   "Development", "Education", "Game", "Graphics", "Network",
                   "Office", "Science", "Settings", "System", "Utility"});
    l->addWidget(cat);
    list = new AppList;
    list->setIconSize({26, 26});
    list->setSpacing(2);
    list->setDragDropMode(QAbstractItemView::DragDrop);
    list->setDefaultDropAction(Qt::CopyAction);
    list->setDropIndicatorShown(true);
    l->addWidget(list, 1);
    notice = new QLabel;
    notice->setWordWrap(true);
    l->addWidget(notice);
    recentButton = new QPushButton("Recent programs");
    l->addWidget(recentButton);
    programs = new QPushButton("All Programs");
    programs->setObjectName("programsButton");
    l->addWidget(programs);
    search = new QLineEdit;
    search->setPlaceholderText("Search programs…");
    search->setAccessibleName("Search applications");
    l->addWidget(search);
    search->installEventFilter(this);
    list->installEventFilter(this);
    connect(search, &QLineEdit::textChanged, this, [this] { refresh(); });
    connect(search, &QLineEdit::returnPressed, this,
            [this] { launchSelected(); });
    connect(list, &QListWidget::itemClicked, this, [this] {
      if (!list->dragging)
        launchSelected();
    });
    connect(list, &QListWidget::itemActivated, this, [this] {
      if (isVisible())
        launchSelected();
    });
    connect(cat, &QComboBox::currentTextChanged, this, [this] { refresh(); });
    connect(programs, &QPushButton::clicked, this, [this] {
      if (browsing || !search->text().isEmpty())
        home();
      else
        browse("All applications");
    });
    connect(recentButton, &QPushButton::clicked, this,
            [this] { browse("Recent"); });
    list->setContextMenuPolicy(Qt::CustomContextMenu);
    connect(list, &QWidget::customContextMenuRequested, this,
            [this](QPoint p) { context(p); });
    auto *right = new QWidget;
    right->setObjectName("placesPanel");
    body->addWidget(right, 2);
    auto *r = new QVBoxLayout(right);
    r->setContentsMargins(4, 38, 4, 4);
    auto *scroll = new QScrollArea;
    scroll->setFrameShape(QFrame::NoFrame);
    scroll->setWidgetResizable(true);
    auto *contents = new QWidget;
    auto *links = new QVBoxLayout(contents);
    links->setContentsMargins(0, 0, 0, 0);
    scroll->setWidget(contents);
    r->addWidget(scroll, 1);
    auto prefs = readPreference("folders.json", QJsonDocument(QJsonObject{}))
                     .value.object();
    addPlaces(links, prefs);
    documents = new QPushButton("Recent documents");
    r->addWidget(documents);
    auto *docMenu = new QMenu(documents);
    documents->setMenu(docMenu);
    documents->setVisible(documentsEnabled());
    connect(docMenu, &QMenu::aboutToShow, this, [this, docMenu] {
      docMenu->clear();
      if (!documentsEnabled())
        return;
      browseWorker(
          docMenu, {"--read-recent-documents"},
          [this, docMenu](QJsonArray rows) {
            if (!documentsEnabled())
              return;
            if (rows.isEmpty())
              docMenu->addAction("No recent documents")->setEnabled(false);
            for (const auto v : rows) {
              auto row = v.toObject();
              QString path = row["path"].toString();
              docMenu->addAction(row["name"].toString().replace('&', "&&"),
                                 this, [this, path] {
                                   if (documentsEnabled())
                                     openPath(path);
                                 });
            }
          });
    });
    connect(docMenu, &QMenu::aboutToHide, this, [docMenu] {
      QTimer::singleShot(0, docMenu, [docMenu] {
        if (!docMenu->isVisible())
          docMenu->clear();
      });
    });
    auto *edit = new QPushButton("Edit folder links…");
    edit->setObjectName("menuControl");
    r->addWidget(edit);
    connect(edit, &QPushButton::clicked, this, [this] {
      hide();
      editFolderPreferences(this);
      reopenAfterEdit();
    });
    auto *opts = new QPushButton("Menu options…");
    opts->setObjectName("menuControl");
    r->addWidget(opts);
    auto *menu = new QMenu(opts);
    opts->setMenu(menu);
    connect(menu, &QMenu::aboutToShow, this, [this, menu] { options(menu); });
    auto *sessionRow = new QHBoxLayout;
    r->addLayout(sessionRow);
    sessionRow->setSpacing(0);
    const QList<QPair<QString, QString>> sessions = {
        {"shutdown", "Shut down"},  {"reboot", "Restart"},
        {"logout", "Log out"},      {"suspend", "Sleep"},
        {"hibernate", "Hibernate"}, {"lockscreen", "Lock screen"}};
    auto primary = readPreference("session-button.json", {})
                       .value.object()
                       .value("action")
                       .toString("shutdown");
    if (std::none_of(sessions.begin(), sessions.end(),
                     [&](const auto &s) { return s.first == primary; }))
      primary = "shutdown";
    primaryId = primary;
    power = new QPushButton;
    power->setProperty("sessionPrimary", true);
    auto *arrow = new QPushButton("▾");
    arrow->setAccessibleName("Session options");
    arrow->setObjectName("powerMenuArrow");
    arrow->setFixedWidth(34);
    auto *pm = new QMenu(arrow);
    arrow->setMenu(pm);
    for (const auto &[id, label] : sessions) {
      auto run = [this, id, label] {
        if (!available(id))
          return;
        if (id != "lockscreen" &&
            QMessageBox::question(this, label, label + " this computer?",
                                  QMessageBox::Yes | QMessageBox::Cancel,
                                  QMessageBox::Cancel) != QMessageBox::Yes)
          return;
        if (!available(id))
          return;
        launch("lxqt-" + id + ".desktop", false);
      };
      powerActions.insert(id, pm->addAction(label, this, run));
      if (id == primary) {
        power->setText(label + "…");
        connect(power, &QPushButton::clicked, this, run);
      }
    }
    pm->addAction("All session options…", this,
                  [this] { launch("lxqt-leave.desktop", false); });
    pm->addAction("Refresh power availability", this, [this] { checkPower(); });
    sessionRow->addWidget(power, 1);
    sessionRow->addWidget(arrow);
    for (auto *control : right->findChildren<QAbstractButton *>()) {
      if (control->focusPolicy() == Qt::NoFocus)
        continue;
      rightControls.append(control);
      control->installEventFilter(this);
    }
    portrait = new QLabel(this);
    portrait->setFixedSize(84, 84);
    portrait->setAlignment(Qt::AlignCenter);
    portrait->setObjectName("personalStartImage");
    loadPortrait(prefs);
    portrait->setFocusPolicy(Qt::StrongFocus);
    portrait->setCursor(Qt::PointingHandCursor);
    portrait->setAccessibleName("Choose Start portrait");
    portrait->installEventFilter(this);
    QFile baseline(":/doro/start.qss");
    QString css = baseline.open(QIODevice::ReadOnly)
                      ? QString::fromUtf8(baseline.readAll())
                      : QString();
    QString themeFile = "start-theme.qss";
    if (hasCompositor()) {
      for (QString color : {"#f8b9df", "#993d71", "#e19dc5", "#86345e",
                            "#b54e83", "#713452", "#b85187", "#f6b2d5"})
        css.replace(color, "#d8" + color.mid(1));
      for (QString color :
           {"#a24877", "#783251", "#9e4672", "#773353", "#9d4772"})
        css.replace(color, "#ed" + color.mid(1));
      if (QFileInfo::exists(cfg + "start-theme-glass.qss"))
        themeFile = "start-theme-glass.qss";
    }
    QFile custom(cfg + themeFile);
    if (custom.open(QIODevice::ReadOnly))
      css += QString::fromUtf8(custom.read(256 * 1024));
    setStyleSheet(css);
    home();
    new QShortcut(QKeySequence("Ctrl+F"), this, [this] { search->setFocus(); });
    new QShortcut(QKeySequence("Alt+F1"), this, [this] { hide(); });
    new QShortcut(QKeySequence(Qt::Key_Print), this, [this] {
      auto executable =
          QCoreApplication::applicationDirPath() + "/doroshell-screenshot";
      if (!QFileInfo(executable).isExecutable()) {
        warn("DoroShell Screenshot is unavailable.");
        return;
      }
      auto *capture = new QProcess(qApp);
      connect(capture, &QProcess::readyReadStandardOutput, this,
              [this, capture] {
                if (capture->canReadLine() && capture->readLine() == "FROZEN\n")
                  hide();
              });
      connect(capture, &QProcess::finished, capture, &QObject::deleteLater);
      connect(capture, &QProcess::errorOccurred, capture,
              [capture](QProcess::ProcessError e) {
                if (e == QProcess::FailedToStart)
                  capture->deleteLater();
              });
      capture->start(executable, {"--notify"});
    });
  }
  void present() {
    auto *screen = QGuiApplication::screenAt(QCursor::pos());
    if (!screen)
      screen = QGuiApplication::primaryScreen();
    auto area = screen->availableGeometry();
    resize(QSize(508, 634).boundedTo(area.size()));
    move(area.left(), area.bottom() - height() + 1);
    show();
    raise();
    activateWindow();
    search->setFocus();
    checkPower();
  }
  void refresh() {
    QStringList ids;
    const auto text = search->text().trimmed();
    bool pinned = !browsing && text.isEmpty();
    auto history = readRecent();
    auto items = history.error.isEmpty()
                     ? recentItems(history.value.object(),
                                   QDateTime::currentSecsSinceEpoch())
                     : QStringList{};
    if (!text.isEmpty())
      ids = searchApps(apps, text);
    else if (pinned || cat->currentText() == "Pinned")
      ids = favoriteIds();
    else if (cat->currentText() == "Recent")
      ids = items;
    else
      for (const auto &e : apps)
        if (cat->currentIndex() == 0 ||
            e.categories.contains(cat->currentText()))
          ids << e.id;
    auto current = list->currentItem()
                       ? list->currentItem()->data(Qt::UserRole).toString()
                       : QString{};
    list->clear();
    list->setAccessibleName(pinned ? "Pinned applications" : "Applications");
    for (const auto &id : ids) {
      auto i = find(id);
      if (i == apps.end())
        continue;
      if (!text.isEmpty() && list->count() >= 100)
        break;
      auto *item = new QListWidgetItem(i->icon, i->name, list);
      item->setData(Qt::UserRole, id);
      item->setData(PathRole, i->filename);
      item->setToolTip(i->description);
      if (current == id)
        list->setCurrentItem(item);
    }
    if (!list->currentItem() && list->count())
      list->setCurrentRow(0);
    notice->setText(
        list->count() == 0
            ? pinned ? "No pinned applications. Open All Programs or search."
                     : "No matching applications."
        : (!text.isEmpty() && ids.size() > 100)
            ? "Showing the first 100 matches. Refine your search."
            : "");
    if (pinned && !pins.error.isEmpty())
      notice->setText(pins.error);
    notice->setVisible(!notice->text().isEmpty());
    heading->setVisible(pinned);
    cat->setVisible(browsing);
    recentButton->setVisible(pinned && !items.isEmpty());
    programs->setText(pinned ? "All Programs" : "Back");
    if (text.isEmpty() && (pinned || cat->currentText() == "Pinned") &&
        pins.error.isEmpty())
      list->reorder = [this](QString src, QString dst, bool after) {
        if (src == dst)
          return;
        auto ids = favoriteIds();
        if (!ids.contains(src) || !ids.contains(dst))
          return;
        ids.removeAll(src);
        ids.insert(ids.indexOf(dst) + (after ? 1 : 0), src);
        savePins(ids);
      };
    else
      list->reorder = {};
  }
  bool dragging() const { return list->dragging; }
  void reopen() {
    pins = readPins(apps);
    if (!pins.exists && pins.error.isEmpty()) {
      try {
        pins.save(pins.value, false);
      } catch (const std::exception &e) {
        pins.error = QString::fromUtf8(e.what());
      }
    }
    documents->setVisible(documentsEnabled());
    auto recent = readRecent();
    if (recent.error.isEmpty() &&
        recent.value.object().value("retention_days").toInt()) {
      try {
        updateHistory({});
      } catch (const std::exception &) {
      }
    }
    home();
    present();
  }

protected:
  void resizeEvent(QResizeEvent *e) override {
    QWidget::resizeEvent(e);
    portrait->move(width() * 4 / 5 - 42, 0);
    portrait->raise();
    if (QGuiApplication::platformName() == "xcb") {
      auto *frame = findChild<QWidget *>("glassFrame");
      if (frame) {
        QPainterPath shape;
        shape.setFillRule(Qt::WindingFill);
        shape.addRoundedRect(frame->geometry(), 15, 15);
        shape.addRoundedRect(portrait->geometry(), 11, 11);
        setMask(QRegion(shape.toFillPolygon().toPolygon(), Qt::WindingFill));
      }
    }
  }
  bool eventFilter(QObject *o, QEvent *e) override {
    auto *button = qobject_cast<QAbstractButton *>(o);
    if (e->type() == QEvent::FocusIn && rightControls.contains(button))
      lastRight = button;
    if (o == portrait &&
        (e->type() == QEvent::MouseButtonRelease ||
         (e->type() == QEvent::KeyPress &&
          static_cast<QKeyEvent *>(e)->key() == Qt::Key_Return))) {
      hide();
      editPortrait(this);
      reopenAfterEdit();
      return true;
    }
    if (e->type() == QEvent::KeyPress) {
      auto key = static_cast<QKeyEvent *>(e)->key();
      if (static_cast<QKeyEvent *>(e)->modifiers() == Qt::NoModifier &&
          !list->dragging) {
        if (o == list && key == Qt::Key_Right) {
          auto *target = lastRight.data();
          if (!target || !target->isVisible() || !target->isEnabled()) {
            auto first = std::find_if(
                rightControls.begin(), rightControls.end(),
                [](auto *b) { return b->isVisible() && b->isEnabled(); });
            target = first == rightControls.end() ? nullptr : *first;
          }
          if (target) {
            target->setFocus(Qt::ShortcutFocusReason);
            return true;
          }
        }
        if (rightControls.contains(button) && key == Qt::Key_Left) {
          if (list->count())
            list->setFocus(Qt::ShortcutFocusReason);
          else
            search->setFocus();
          return true;
        }
      }
      if (o == search && (key == Qt::Key_Down || key == Qt::Key_Up) &&
          list->count()) {
        list->setFocus();
        list->setCurrentRow(key == Qt::Key_Down ? 0 : list->count() - 1);
        return true;
      }
      if (o == list &&
          ((key == Qt::Key_Up && list->currentRow() == 0) ||
           (key == Qt::Key_Down && list->currentRow() == list->count() - 1))) {
        search->setFocus();
        return true;
      }
    }
    return QWidget::eventFilter(o, e);
  }
  void keyPressEvent(QKeyEvent *e) override {
    if (e->key() == Qt::Key_Escape) {
      if (!search->text().isEmpty())
        search->clear();
      else if (browsing)
        home();
      else
        hide();
      return;
    }
    QWidget::keyPressEvent(e);
  }

private:
  void reopenAfterEdit() {
    // Recreate through the ordinary resident toggle so widgets use the saved
    // preference snapshot.
    if (requestReopen)
      QTimer::singleShot(0, qApp, requestReopen);
  }
  bool available(const QString &id) const {
    auto *entry = g_desktop_app_info_new(("lxqt-" + id + ".desktop").toUtf8());
    if (!entry)
      return false;
    g_object_unref(entry);
    return id == "lockscreen" || id == "logout" ||
           powerAvailable.value(id, false);
  }
  void setPowerState(const QString &id, bool yes, const QString &tip) {
    powerAvailable[id] = yes;
    powerActions.value(id)->setEnabled(available(id));
    powerActions.value(id)->setToolTip(tip);
    if (id == primaryId) {
      power->setEnabled(available(id));
      power->setToolTip(tip);
    }
  }
  void checkPower() {
    auto generation = ++powerGeneration;
    const QMap<QString, QString> methods = {{"shutdown", "CanPowerOff"},
                                            {"reboot", "CanReboot"},
                                            {"suspend", "CanSuspend"},
                                            {"hibernate", "CanHibernate"}};
    for (auto it = powerActions.begin(); it != powerActions.end(); ++it) {
      auto id = it.key();
      setPowerState(id, false,
                    methods.contains(id) ? "Checking availability…" : "");
      if (!methods.contains(id))
        continue;
      auto m = QDBusMessage::createMethodCall(
          "org.freedesktop.login1", "/org/freedesktop/login1",
          "org.freedesktop.login1.Manager", methods.value(id));
      m.setAutoStartService(false);
      m.setInteractiveAuthorizationAllowed(false);
      auto *watch = new QDBusPendingCallWatcher(
          QDBusConnection::systemBus().asyncCall(m, 1500), this);
      connect(watch, &QDBusPendingCallWatcher::finished, this,
              [this, watch, id, generation] {
                QDBusPendingReply<QString> reply = *watch;
                QString state = reply.isError() ? "unavailable" : reply.value();
                if (generation == powerGeneration)
                  setPowerState(id, state == "yes" || state == "challenge",
                                "Power availability: " + state);
                watch->deleteLater();
              });
    }
  }
  Catalog::const_iterator find(const QString &id) const {
    return std::find_if(apps.begin(), apps.end(),
                        [&](const Entry &e) { return e.id == id; });
  }
  QStringList favoriteIds() const {
    QStringList ids;
    for (auto x : pins.value.array())
      ids << x.toString();
    return ids;
  }
  void savePins(const QStringList &ids) {
    try {
      pins.save(QJsonDocument(QJsonArray::fromStringList(ids)), true);
      refresh();
    } catch (const std::exception &e) {
      warn(e.what());
    }
  }
  void home() {
    browsing = false;
    search->clear();
    cat->setCurrentIndex(0);
    refresh();
    search->setFocus();
  }
  void browse(const QString &v) {
    browsing = true;
    search->clear();
    cat->setCurrentText(v);
    refresh();
    search->setFocus();
  }
  void warn(const QString &s) {
    QMessageBox::warning(this, "DoroShell Start", s);
  }
  void options(QMenu *m) {
    m->clear();
    auto recent = readRecent();
    auto o = recent.value.object();
    auto change = [this](QString id, std::optional<bool> enabled, bool clear,
                         std::optional<int> limit, std::optional<int> days) {
      try {
        updateHistory(id, enabled, clear, limit, days);
        refresh();
      } catch (const std::exception &e) {
        warn(e.what());
      }
    };
    auto *enable = m->addAction("Remember recent programs");
    enable->setCheckable(true);
    enable->setChecked(o["enabled"].toBool());
    auto *docs =
        m->addAction("Show recent documents from shared desktop history");
    docs->setCheckable(true);
    docs->setChecked(documentsEnabled());
    connect(docs, &QAction::triggered, this, [this](bool on) {
      try {
        auto p = documentPreference();
        p.save(QJsonDocument(QJsonObject{{"version", 1}, {"enabled", on}}),
               true);
        documents->setVisible(on);
      } catch (const std::exception &e) {
        warn(e.what());
      }
    });
    connect(enable, &QAction::triggered, this,
            [change](bool checked) { change({}, checked, false, {}, {}); });
    auto *count = m->addMenu("Recent program count");
    for (int n : {5, 10, 15, 20, 30, 50}) {
      auto *a = count->addAction(QString::number(n), this,
                                 [change, n] { change({}, {}, false, n, {}); });
      a->setCheckable(true);
      a->setChecked(n == o.value("limit").toInt(20));
    }
    auto *age = m->addMenu("Recent program age");
    for (int days : {0, 1, 7, 30, 90, 365}) {
      auto *a =
          age->addAction(days ? QString("%1 days").arg(days) : "No limit", this,
                         [change, days] { change({}, {}, false, {}, days); });
      a->setCheckable(true);
      a->setChecked(days == o.value("retention_days").toInt(0));
    }
    m->addAction("Clear recent programs", this,
                 [change] { change({}, {}, true, {}, {}); });
    auto *session = m->addMenu("Primary session action");
    for (auto it = powerActions.begin(); it != powerActions.end(); ++it) {
      auto id = it.key();
      auto *a = session->addAction(it.value()->text(), this, [this, id] {
        auto p = readPreference(
            "session-button.json",
            QJsonDocument(QJsonObject{{"version", 1}, {"action", "shutdown"}}));
        auto o = p.value.object();
        if (o.value("version").toInt() != 1 ||
            !powerActions.contains(o.value("action").toString())) {
          warn("Invalid session preference");
          return;
        }
        o["action"] = id;
        try {
          p.save(QJsonDocument(o), true);
          hide();
          reopenAfterEdit();
        } catch (const std::exception &e) {
          warn(e.what());
        }
      });
      a->setCheckable(true);
      a->setChecked(primaryId == id);
    }
    m->addSeparator();
    m->addAction("DoroShell Settings…", this,
                 [this] { launch("doroshell-settings.desktop"); });
  }
  void context(QPoint pos) {
    auto *item = list->itemAt(pos);
    if (!item)
      return;
    auto id = item->data(Qt::UserRole).toString();
    auto i = find(id);
    if (i == apps.end())
      return;
    auto app = i->app;
    auto ids = favoriteIds();
    int index = ids.indexOf(id);
    QMenu m(this);
    m.addAction(index >= 0 ? "Unpin" : "Pin application", this,
                [this, ids, id, index]() mutable {
                  if (index >= 0)
                    ids.removeAll(id);
                  else
                    ids << id;
                  savePins(ids);
                });
    if (index >= 0)
      for (int d : {-1, 1}) {
        auto *move = m.addAction(d < 0 ? "Move pin up" : "Move pin down", this,
                                 [this, ids, index, d]() mutable {
                                   ids.swapItemsAt(index, index + d);
                                   savePins(ids);
                                 });
        move->setEnabled(index + d >= 0 && index + d < ids.size());
      }
    m.addAction("Properties…", this, [this, id] {
      auto i = find(id);
      if (i == apps.end())
        return;
      QMessageBox box(QMessageBox::Information, "Application properties",
                      i->name + "\n" + i->description + "\n" + i->id + "\n" +
                          i->executable + "\n" + i->filename,
                      QMessageBox::Ok, this);
      box.setTextFormat(Qt::PlainText);
      box.exec();
    });
    for (auto p = g_desktop_app_info_list_actions(app.get()); p && *p; ++p) {
      QByteArray action(*p);
      auto label = g_desktop_app_info_get_action_name(app.get(), action);
      m.addAction(QString::fromUtf8(label).replace('&', "&&"), this,
                  [this, app, action] {
                    g_desktop_app_info_launch_action(app.get(), action,
                                                     nullptr);
                    hide();
                  });
      g_free(label);
    }
    m.exec(list->viewport()->mapToGlobal(pos));
  }
  void launchSelected() {
    if (auto *item = list->currentItem())
      launch(item->data(Qt::UserRole).toString());
  }
  void launch(const QString &id, bool record = true) {
    auto *a = g_desktop_app_info_new(id.toUtf8());
    if (!a) {
      warn("Unavailable: " + id);
      return;
    }
    GError *err = nullptr;
    bool ok = g_app_info_launch(G_APP_INFO(a), nullptr, nullptr, &err);
    g_object_unref(a);
    if (!ok) {
      warn(err ? QString::fromUtf8(err->message)
               : "Could not open application");
      g_clear_error(&err);
      return;
    }
    if (record)
      try {
        updateHistory(id);
      } catch (const std::exception &e) {
        warn(e.what());
      }
    hide();
  }
  void openPath(const QString &path) {
    GError *err = nullptr;
    if (g_app_info_launch_default_for_uri(QUrl::fromLocalFile(path).toEncoded(),
                                          nullptr, &err))
      hide();
    else {
      warn(err ? QString::fromUtf8(err->message) : "Could not open folder");
      g_clear_error(&err);
    }
  }
  void folderMenu(QMenu *m, const QString &path, int depth = 0) {
    connect(m, &QMenu::aboutToShow, m, [this, m, path, depth] {
      m->clear();
      m->addAction("Open this folder", this, [this, path] { openPath(path); });
      m->addSeparator();
      browseWorker(m, {"--list-folder", path},
                   [this, m, path, depth](QJsonArray items) {
                     for (auto v : items) {
                       auto row = v.toObject();
                       if (row["limited"].toBool()) {
                         m->addAction("Open folder to see more…", this,
                                      [this, path] { openPath(path); });
                         continue;
                       }
                       auto name = row["name"].toString();
                       auto p = QDir(path).filePath(name);
                       name.replace('&', "&&");
                       if (row["directory"].toBool() && depth < 5)
                         folderMenu(m->addMenu(name), p, depth + 1);
                       else
                         m->addAction(name, this, [this, p] { openPath(p); });
                     }
                   });
    });
  }
  void addPlaces(QVBoxLayout *layout, const QJsonObject &prefs) {
    QJsonArray folders = prefs["folders"].toArray();
    if (!prefs.contains("folders"))
      for (auto p : places)
        folders.append(QJsonObject{
            {"label", p.label}, {"standard", p.key}, {"visible", true}});
    for (auto v : folders) {
      auto f = v.toObject();
      if (f["type"] == "separator") {
        auto *line = new QFrame;
        line->setFrameShape(QFrame::HLine);
        layout->addWidget(line);
        continue;
      }
      if (!f["visible"].toBool())
        continue;
      QString path = f["path"].toString();
      for (auto p : places)
        if (f["standard"] == p.key)
          path = QStandardPaths::writableLocation(p.location);
      if (!QDir::isAbsolutePath(path))
        continue;
      auto *row = new QHBoxLayout;
      row->setSpacing(0);
      layout->addLayout(row);
      auto *b = new QPushButton(f["label"].toString());
      b->setObjectName("folderLink");
      row->addWidget(b, 1);
      connect(b, &QPushButton::clicked, this, [this, path] { openPath(path); });
      auto *arrow = new QToolButton;
      arrow->setText("›");
      arrow->setAccessibleName("Browse " + f["label"].toString());
      arrow->setObjectName("folderBrowse");
      arrow->setPopupMode(QToolButton::InstantPopup);
      auto *fm = new QMenu(arrow);
      folderMenu(fm, path);
      arrow->setMenu(fm);
      row->addWidget(arrow);
    }
    auto hidden = prefs["hiddenSystemLinks"].toArray();
    auto link = [&](QString label, std::function<void()> run) {
      if (hidden.contains(label))
        return;
      auto *b = new QPushButton(label);
      b->setObjectName("folderLink");
      layout->addWidget(b);
      connect(b, &QPushButton::clicked, this, run);
    };
    link("Games", [this] { browse("Game"); });
    link("Computer", [this] { openPath("/"); });
    const QList<QPair<QString, QStringList>> groups = {
        {"Control Panel", {"lxqt-config.desktop"}},
        {"Network connections",
         {"doroshell-network.desktop", "nm-connection-editor.desktop"}},
        {"Printers", {"system-config-printer.desktop"}},
        {"Default programs", {"lxqt-config-file-associations.desktop"}}};
    for (const auto &[label, ids] : groups)
      for (const auto &id : ids) {
        auto *a = g_desktop_app_info_new(id.toUtf8());
        if (!a)
          continue;
        g_object_unref(a);
        link(label, [this, id] { launch(id); });
        break;
      }
    layout->addStretch();
  }
  void loadPortrait(const QJsonObject &prefs) {
    const auto data =
        QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation) +
        "/lxqt-comfort/";
    const auto custom = prefs["portrait"].toString();
    for (const auto &p :
         QStringList{custom, data + "framed-start-icon.png",
                     data + "start-icon.png", ":/doro/portrait.png", ":/doro/start.svg"}) {
      if (p.isEmpty())
        continue;
      QImageReader reader(p);
      reader.setAutoTransform(true);
      auto size = reader.size();
      if (!size.isValid())
        continue;
      if (size.width() > 4096 || size.height() > 4096)
        reader.setScaledSize(size.scaled(4096, 4096, Qt::KeepAspectRatio));
      auto image = reader.read();
      if (image.isNull())
        continue;
      if (p == custom && prefs["portraitCrop"].isObject()) {
        auto c = prefs["portraitCrop"].toObject();
        int side = qMax(1, int(qMin(image.width(), image.height()) /
                               qBound(1., c["zoom"].toDouble(1), 4.)));
        int x = qBound(
            0,
            int(qBound(0., c["x"].toDouble(.5), 1.) * image.width()) - side / 2,
            image.width() - side);
        int y =
            qBound(0,
                   int(qBound(0., c["y"].toDouble(.5), 1.) * image.height()) -
                       side / 2,
                   image.height() - side);
        image = image.copy(x, y, side, side);
      }
      portrait->setPixmap(QPixmap::fromImage(
          image.scaled(80, 80, Qt::KeepAspectRatio, Qt::SmoothTransformation)));
      break;
    }
  }
  QString primaryId;
  QList<QAbstractButton *> rightControls;
  QPointer<QAbstractButton> lastRight;
  QMap<QString, QAction *> powerActions;
  QMap<QString, bool> powerAvailable;
  int powerGeneration = 0;
  QPushButton *power, *documents;
  const Catalog &apps;
  Preference pins;
  bool browsing = false;
  AppList *list;
  QLineEdit *search;
  QComboBox *cat;
  QLabel *heading, *portrait, *notice;
  QPushButton *programs, *recentButton;
};
} // namespace
int main(int argc, char **argv) {
  if (argc >= 2 && (QByteArray(argv[1]) == "--list-folder" ||
                    QByteArray(argv[1]) == "--read-recent-documents")) {
    const pid_t parent = getppid();
    if (parent == 1 || prctl(PR_SET_PDEATHSIG, SIGKILL) || getppid() != parent)
      return 1;
    QCoreApplication core(argc, argv);
    QJsonArray rows;
    try {
      if (argc == 3 && core.arguments()[1] == "--list-folder")
        rows = listFolder(core.arguments()[2]);
      else if (argc == 2 && core.arguments()[1] == "--read-recent-documents" &&
               documentsEnabled())
        rows = readDocuments();
      else
        return 1;
    } catch (const std::exception &) {
      return 1;
    }
    auto bytes = QJsonDocument(rows).toJson(QJsonDocument::Compact);
    return fwrite(bytes.constData(), 1, bytes.size(), stdout) ==
                   static_cast<size_t>(bytes.size())
               ? 0
               : 1;
  }
  QApplication app(argc, argv);
  app.setApplicationName("DoroShell Start");
  app.setQuitOnLastWindowClosed(false);
  QCommandLineParser parser;
  parser.addHelpOption();
  parser.addOption(
      {"background", "Record recent foreground apps without opening Start"});
  parser.addOption(
      {"screenshot", "Save the menu as an image and exit", "file"});
  parser.addOption({"settings", "Edit Start folder links and portrait"});
  parser.addOption({"portrait", "Choose and frame a Start portrait"});
  parser.process(app);
  if (parser.isSet("settings") || parser.isSet("portrait")) {
    if (parser.optionNames().size() != 1)
      return 2;
    if (parser.isSet("settings"))
      editFolderPreferences(nullptr);
    else
      editPortrait(nullptr);
    return 0;
  }
  if (parser.isSet("screenshot")) {
    auto apps = loadCatalog();
    Menu menu(apps);
    menu.present();
    QTimer::singleShot(250, &menu, [&] {
      app.exit(menu.grab().save(parser.value("screenshot")) ? 0 : 1);
    });
    return app.exec();
  }
  auto runtime =
      QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation);
  if (runtime.isEmpty())
    return 1;
  auto endpoint =
      runtime + "/doroshell-native-start-" +
      QCryptographicHash::hash(qgetenv("DISPLAY"), QCryptographicHash::Sha256)
          .toHex()
          .left(16);
  QLockFile lock(endpoint + ".lock");
  lock.setStaleLockTime(0);
  const auto version = runningVersion();
  if (version.isEmpty())
    return 1;
  if (!lock.tryLock()) {
    QLocalSocket socket;
    for (int retry = 0; retry < 20; ++retry) {
      socket.connectToServer(endpoint);
      if (socket.waitForConnected(100))
        break;
      socket.abort();
      QThread::msleep(25);
    }
    if (socket.state() != QLocalSocket::ConnectedState)
      return 1;
    socket.write((parser.isSet("background") ? "PING " : "TOGGLE ") + version +
                 '\n');
    socket.flush();
    if (!socket.waitForReadyRead(2000))
      return 1;
    auto response = socket.readAll();
    if (response == "OK\n")
      return 0;
    if (response != "RELOAD\n" || !lock.tryLock(2500))
      return 1;
  }
  QLocalServer server;
  server.setSocketOptions(QLocalServer::UserAccessOption);
  QLocalServer::removeServer(endpoint);
  if (!server.listen(endpoint))
    return 1;
  auto apps = loadCatalog();
  std::unique_ptr<Menu> menu;
  QByteArray lastAppearance;
  std::function<void()> toggle = [&] {
    if (QApplication::activeModalWidget() || (menu && menu->dragging()) ||
        (QApplication::activePopupWidget() &&
         QApplication::activePopupWidget() != menu.get()))
      return;
    if (menu && menu->isVisible())
      menu->hide();
    else {
      QCryptographicHash hash(QCryptographicHash::Sha256);
      auto config = QStandardPaths::writableLocation(
          QStandardPaths::GenericConfigLocation);
      for (QString file :
           {"lxqt-comfort/folders.json", "lxqt-comfort/session-button.json",
            "doroshell/start-theme.qss", "doroshell/start-theme-glass.qss",
            "doroshell/theme.conf", "doroshell/wallpaper-glass.json"}) {
        QFile f(config + "/" + file);
        if (f.open(QIODevice::ReadOnly))
          hash.addData(f.read(256 * 1024));
        hash.addData(QByteArrayView("\0", 1));
      }
      const auto appearance = hash.result();
      if (!menu || appearance != lastAppearance) {
        menu = std::make_unique<Menu>(apps);
        menu->requestReopen = toggle;
        lastAppearance = appearance;
      }
      menu->reopen();
    }
  };
  auto *monitor = g_app_info_monitor_get();
  struct MonitorData {
    Catalog &apps;
    std::unique_ptr<Menu> &menu;
  } data{apps, menu};
  g_signal_connect(monitor, "changed",
                   G_CALLBACK(+[](GAppInfoMonitor *, gpointer p) {
                     auto &d = *static_cast<MonitorData *>(p);
                     d.apps = loadCatalog();
                     if (d.menu)
                       d.menu->refresh();
                   }),
                   &data);
  QObject::connect(&server, &QLocalServer::newConnection, &app, [&] {
    while (auto *s = server.nextPendingConnection()) {
      auto read = [&, s] {
        if (s->bytesAvailable() > 128) {
          s->abort();
          return;
        }
        if (!s->canReadLine())
          return;
        auto parts = s->readLine().trimmed().split(' ');
        if (parts.size() != 2 || (parts[0] != "PING" && parts[0] != "TOGGLE"))
          s->write("ERROR\n");
        else if (parts[1] != version) {
          server.close();
          s->write("RELOAD\n");
          s->flush();
          QTimer::singleShot(0, &app, &QApplication::quit);
        } else {
          if (parts[0] == "TOGGLE")
            toggle();
          s->write("OK\n");
        }
        s->disconnectFromServer();
      };
      QObject::connect(s, &QLocalSocket::readyRead, s, read);
      QObject::connect(s, &QLocalSocket::disconnected, s,
                       &QObject::deleteLater);
      read();
    }
  });
  std::unique_ptr<FocusTracker> tracker;
  if (app.platformName() == "xcb")
    tracker = std::make_unique<FocusTracker>(apps);
  if (!parser.isSet("background"))
    toggle();
  const int code = app.exec();
  g_signal_handlers_disconnect_by_data(monitor, &data);
  g_object_unref(monitor);
  return code;
}
