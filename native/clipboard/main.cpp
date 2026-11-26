#include "entry.hpp"
#include <QApplication>
#include <QCheckBox>
#include <QClipboard>
#include <QCloseEvent>
#include <QCryptographicHash>
#include <QDBusConnectionInterface>
#include <QDBusServiceWatcher>
#include <QDir>
#include <QFile>
#include <QImageReader>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QLocalServer>
#include <QLocalSocket>
#include <QLockFile>
#include <QProcess>
#include <QPushButton>
#include <QShortcut>
#include <QStandardPaths>
#include <QTimer>
#include <QVBoxLayout>
#include <cstdio>
#include <sys/resource.h>
#include <unistd.h>

namespace {
class History : public QWidget {
  QList<clip::Entry> entries;
  QLineEdit search;
  QListWidget items;
  QLabel empty{"Copy text or an image to begin. Nothing is saved to disk."};
  QPushButton copy{"Copy selected"}, remove{"Delete"}, clear{"Clear history"};
  QCheckBox pause{"Pause collection"};
  QProcess *worker = nullptr;
  bool retaining = false;
  bool writing = false;

  void cancel() {
    if (!worker)
      return;
    auto *old = std::exchange(worker, nullptr);
    old->kill();
  }
  void add(clip::Entry entry) {
    auto key = entry.identity();
    entries.removeIf([&](const auto &e) { return e.identity() == key; });
    entries.prepend(std::move(entry));
    qsizetype used = 0;
    for (qsizetype i = 0; i < entries.size(); ++i) {
      used += entries[i].size();
      if (i >= 50 || used > 16 * 1024 * 1024) {
        entries.resize(i);
        break;
      }
    }
  }
  void refresh() {
    auto selected =
        items.currentItem()
            ? items.currentItem()->data(Qt::UserRole + 1).toByteArray()
            : QByteArray{};
    items.clear();
    for (qsizetype i = 0; i < entries.size(); ++i) {
      const auto &entry = entries.at(i);
      if (!entry.text.contains(search.text(), Qt::CaseInsensitive))
        continue;
      auto text = entry.text.simplified().left(160);
      if (text.isEmpty())
        text = QString("Image %1 × %2")
                   .arg(entry.image.width())
                   .arg(entry.image.height());
      auto *item = new QListWidgetItem(text, &items);
      auto key = entry.identity();
      item->setData(Qt::UserRole, i);
      item->setData(Qt::UserRole + 1, key);
      if (!entry.image.isNull())
        item->setIcon(QPixmap::fromImage(
            entry.image.scaled(64, 64, Qt::KeepAspectRatio)));
      if (key == selected)
        items.setCurrentItem(item);
    }
    if (!items.currentItem() && items.count())
      items.setCurrentRow(0);
    empty.setVisible(!items.count());
    copy.setEnabled(items.count());
    remove.setEnabled(items.count());
  }
  void publish(const clip::Entry &entry, bool replay) {
    writing = true;
    QApplication::clipboard()->setMimeData(entry.mime(replay).release());
    writing = false;
  }
  void activate() {
    if (!items.currentItem())
      return;
    cancel();
    auto entry = entries.at(items.currentItem()->data(Qt::UserRole).toInt());
    publish(entry, true);
    add(std::move(entry));
    refresh();
    hide();
  }
  void changed(QClipboard::Mode mode) {
    if (mode != QClipboard::Clipboard || writing)
      return;
    cancel();
    if (pause.isChecked())
      return;
    worker = new QProcess(this);
    auto *process = worker;
    process->setStandardErrorFile(QProcess::nullDevice());
    auto *timer = new QTimer(process);
    timer->setSingleShot(true);
    connect(timer, &QTimer::timeout, process, &QProcess::kill);
    // Keep output in the process buffer until exit. The child serializes at
    // most one bounded entry.
    connect(process, &QProcess::finished, this,
            [this, process, timer](int code, QProcess::ExitStatus status) {
              timer->stop();
              if (worker == process) {
                worker = nullptr;
                if (status == QProcess::NormalExit && code == 0 &&
                    !pause.isChecked()) {
                  auto entry = clip::decode(process->readAllStandardOutput());
                  if (entry) {
                    if (entry->complete && !retaining)
                      publish(*entry, false);
                    add(std::move(*entry));
                    refresh();
                  }
                }
              }
              process->deleteLater();
            });
    connect(process, &QProcess::errorOccurred, this,
            [this, process](QProcess::ProcessError error) {
              if (error == QProcess::FailedToStart) {
                if (worker == process)
                  worker = nullptr;
                process->deleteLater();
              }
            });
    process->start(QCoreApplication::applicationFilePath(), {"--capture"});
    timer->start(1500);
  }

public:
  History() {
    setWindowFlag(Qt::Tool);
    setWindowTitle("DoroClipboard");
    setWindowIcon(QIcon::fromTheme("edit-paste"));
    resize(440, 500);
    auto *layout = new QVBoxLayout(this);
    layout->addWidget(new QLabel("DoroClipboard"));
    auto *note =
        new QLabel("Session-only history • up to 50 copies\nPasswords may be "
                   "copied as plain text. Pause before copying secrets.");
    note->setWordWrap(true);
    layout->addWidget(note);
    search.setPlaceholderText("Search copied text");
    search.setAccessibleName("Search clipboard history");
    items.setAccessibleName("Clipboard history");
    layout->addWidget(&search);
    layout->addWidget(&items);
    layout->addWidget(&empty);
    auto *row = new QHBoxLayout;
    layout->addLayout(row);
    for (auto *button : {&copy, &remove, &clear})
      row->addWidget(button);
    layout->addWidget(&pause);
    auto *quit = new QPushButton("Quit and forget history");
    layout->addWidget(quit);
    connect(quit, &QPushButton::clicked, qApp, &QApplication::quit);
    connect(&copy, &QPushButton::clicked, this, &History::activate);
    connect(&items, &QListWidget::itemActivated, this, &History::activate);
    connect(&remove, &QPushButton::clicked, this, [this] {
      if (items.currentItem())
        entries.removeAt(items.currentItem()->data(Qt::UserRole).toInt());
      refresh();
    });
    connect(&clear, &QPushButton::clicked, this, [this] {
      cancel();
      entries.clear();
      refresh();
    });
    connect(&pause, &QCheckBox::toggled, this, &History::cancel);
    connect(&search, &QLineEdit::textChanged, this, &History::refresh);
    connect(&search, &QLineEdit::returnPressed, this, &History::activate);
    connect(new QShortcut(Qt::Key_Escape, this), &QShortcut::activated, this,
            &QWidget::hide);
    auto bus = QDBusConnection::sessionBus();
    QString service = "org.lxqt.lxqt-clip";
    auto *watch = new QDBusServiceWatcher(
        service, bus, QDBusServiceWatcher::WatchForOwnerChange, this);
    connect(watch, &QDBusServiceWatcher::serviceOwnerChanged, this,
            [this](auto, auto, const QString &owner) {
              retaining = !owner.isEmpty();
            });
    retaining = bus.isConnected() &&
                bus.interface()->isServiceRegistered(service).value();
    connect(QApplication::clipboard(), &QClipboard::changed, this,
            &History::changed);
    refresh();
  }
  ~History() override {
    // QProcess destruction may synchronously emit finished. Disconnect while
    // members are valid.
    for (auto *process : findChildren<QProcess *>()) {
      process->disconnect(this);
      process->kill();
      process->waitForFinished(500);
    }
  }
  void open() {
    refresh();
    show();
    raise();
    activateWindow();
    search.setFocus();
  }
  void closeEvent(QCloseEvent *event) override {
    event->ignore();
    hide();
  }
};

int capture() {
  QFile statm("/proc/self/statm");
  if (!statm.open(QIODevice::ReadOnly))
    return 1;
  bool valid;
  auto pages =
      statm.readLine().simplified().split(' ').value(0).toULongLong(&valid);
  auto page = sysconf(_SC_PAGESIZE);
  if (!valid || page <= 0)
    return 1;
  rlimit limit{pages * static_cast<unsigned long>(page) + 128u * 1024u * 1024u,
               0};
  limit.rlim_max = limit.rlim_cur;
  if (setrlimit(RLIMIT_AS, &limit))
    return 1;
  try {
    auto entry = clip::snapshot(QApplication::clipboard()->mimeData());
    auto data = entry ? clip::encode(*entry) : QByteArray("null");
    return fwrite(data.data(), 1, data.size(), stdout) ==
                   static_cast<size_t>(data.size())
               ? 0
               : 1;
  } catch (const std::bad_alloc &) {
    return 1;
  }
}

QStringList managerConflicts() {
  static const QStringList managers = {"copyq",  "qlipper",    "klipper",
                                       "clipit", "parcellite", "xfce4-clipman"};
  QStringList found;
  for (const auto &info :
       QDir("/proc").entryInfoList(QDir::Dirs | QDir::NoDotAndDotDot)) {
    if (!info.fileName().toUInt() || info.ownerId() != getuid())
      continue;
    QFile comm(info.filePath() + "/comm");
    if (!comm.open(QIODevice::ReadOnly))
      continue;
    auto name = QString::fromLocal8Bit(comm.readLine().trimmed());
    if (managers.contains(name) && !found.contains(name))
      found.append(name);
  }
  return found;
}
} // namespace

int main(int argc, char **argv) {
  rlimit zero{0, 0};
  if (setrlimit(RLIMIT_CORE, &zero))
    return 1;
  const QByteArray option = argc == 2 ? argv[1] : "";
  if (argc > 2 || !(option.isEmpty() || option == "--show" ||
                    option == "--stop" || option == "--capture"))
    return 2;
  if (option == "--capture")
    alarm(2);
  QApplication app(argc, argv);
  app.setQuitOnLastWindowClosed(false);
  if (app.platformName() != "xcb") {
    fputs("DoroClipboard requires X11.\n", stderr);
    return 1;
  }
  QImageReader::setAllocationLimit(16);
  if (option == "--capture")
    return capture();
  auto key =
      QCryptographicHash::hash(qgetenv("DISPLAY"), QCryptographicHash::Sha256)
          .toHex()
          .left(16);
  auto name = QString("doroshell-clipboard-%1-%2")
                  .arg(getuid())
                  .arg(QString::fromLatin1(key));
  QLocalSocket client;
  client.connectToServer(name);
  if (client.waitForConnected(300)) {
    client.write(option == "--stop"   ? "stop\n"
                 : option == "--show" ? "show\n"
                                      : "ping\n");
    client.flush();
    return !client.bytesToWrite() || client.waitForBytesWritten(300) ? 0 : 1;
  }
  if (option == "--stop")
    return 0;
  auto conflicts = managerConflicts();
  if (!conflicts.isEmpty()) {
    qWarning().noquote() << "Another clipboard manager is running:"
                         << conflicts.join(", ");
    return 2;
  }
  QLockFile lock(
      QStandardPaths::writableLocation(QStandardPaths::RuntimeLocation) + '/' +
      name + ".lock");
  if (!lock.tryLock(0))
    return 0;
  QLocalServer server;
  server.setSocketOptions(QLocalServer::UserAccessOption);
  QLocalServer::removeServer(name);
  if (!server.listen(name))
    return 1;
  History window;
  QObject::connect(&server, &QLocalServer::newConnection, &app, [&] {
    while (auto *s = server.nextPendingConnection()) {
      s->setReadBufferSize(32);
      auto read = [&, s] {
        if (!s->canReadLine() && s->bytesAvailable() < 32)
          return;
        auto command = s->readLine(32);
        if (command == "stop\n")
          app.quit();
        if (command == "show\n")
          window.open();
        s->disconnectFromServer();
      };
      QObject::connect(s, &QLocalSocket::readyRead, s, read);
      QObject::connect(s, &QLocalSocket::disconnected, s,
                       &QObject::deleteLater);
      read();
    }
  });
  if (option == "--show")
    QTimer::singleShot(0, &window, &History::open);
  return app.exec();
}
