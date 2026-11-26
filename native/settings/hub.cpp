#include "hub.hpp"
#include <QtWidgets>
#include <gio/gdesktopappinfo.h>
#include <memory>

namespace {
QString executable(const QString &path) {
  const QFileInfo f(path);
  return f.isFile() && f.isExecutable() ? f.absoluteFilePath() : QString{};
}
using DesktopRef = std::shared_ptr<GDesktopAppInfo>;
DesktopRef entry(const QString &id) {
  auto *p = g_desktop_app_info_new(id.toUtf8());
  return p ? DesktopRef(p, g_object_unref) : DesktopRef{};
}
} // namespace
SettingsHub::SettingsHub(QString binDirectory)
    : binDir(binDirectory.isEmpty() ? QCoreApplication::applicationDirPath()
                                    : std::move(binDirectory)) {
  setWindowTitle("DoroShell Settings");
  setWindowIcon(QIcon::fromTheme("preferences-desktop"));
  buildTree = QFileInfo(binDir).fileName() == "settings" &&
              QFileInfo::exists(binDir + "/../../CMakeCache.txt");
  auto *layout = new QVBoxLayout(this);
  tabs = new QTabWidget;
  layout->addWidget(tabs);
  auto *start = page("Start");
  auto nativeStart = nativeExe("doroshell-start", "start");
  commandButton(start, "Open Start menu", nativeStart);
  commandButton(start, "Edit folder links…", nativeStart, {"--settings"});
  commandButton(start, "Choose Start portrait…", nativeStart, {"--portrait"});
  commandButton(start, "Portable Start preferences…",
                nativeExe("doroshell-portable", "portable"));
  auto *windows = page("Desktop");
  QString pc = upstreamExe("pcmanfm-qt");
  if (!pc.isEmpty()) {
    commandButton(windows, "Desktop and wallpaper preferences…", pc,
                  {"--profile", "lxqt", "--desktop-pref=general"});
    commandButton(windows, "Advanced display controls…", pc,
                  {"--profile", "lxqt", "--desktop-pref=advanced"});
  } else {
    desktopButton(windows, "Desktop preferences…",
                  "pcmanfm-qt-desktop-pref.desktop");
    desktopButton(windows, "Display settings…", "lxqt-config-monitor.desktop");
  }
  desktopButton(windows, "Window manager settings…", "obconf-qt.desktop");
  auto *input = page("Mouse && Touchpad");
  QString unified = nativeExe("doroshell-config-input", "input");
  if (!unified.isEmpty())
    commandButton(input, "Mouse and Touchpad settings…", unified);
  else
    desktopButton(input, "Keyboard and Mouse settings…",
                  "lxqt-config-input.desktop");
  commandButton(input, "Device overrides…",
                nativeExe("doroshell-input-overrides", "input"));
  auto *apps = page("Applications");
  desktopButton(apps, "Choose default applications…",
                "lxqt-config-file-associations.desktop");
  commandButton(apps, "Wi-Fi && Network…",
                nativeExe("doroshell-network", "network"));
  commandButton(apps, "Clipboard history…",
                nativeExe("doroshell-clipboard", "clipboard"), {"--show"});
  auto *appearance = page("Appearance");
  const int themeIndex = tabs->count() - 1;
  themePage = tabs->widget(themeIndex);
  themeExe = nativeExe("doroshell-theme", "theme");
  preset = new QComboBox;
  preset->setObjectName("themePreset");
  for (const auto &[id, label] :
       QList<QPair<QString, QString>>{{"windows", "Windows Doro"},
                                      {"polar", "Polar Doro"},
                                      {"heretic", "Heretic Doro"},
                                      {"spring", "Spring Doro"}})
    preset->addItem(label, id);
  appearance->addRow("DoroShell theme", preset);
  auto *buttons = new QHBoxLayout;
  appearance->addRow(buttons);
  for (const auto &[op, text] : QList<QPair<QString, QString>>{
           {"--plan", "Preview"},
           {"--apply", "Apply"},
           {"--restore", "Restore previous theme"}}) {
    auto *b = new QPushButton(text);
    b->setObjectName(op.mid(2) + "Theme");
    buttons->addWidget(b);
    themeControls << b;
    connect(b, &QPushButton::clicked, this, [this, op] {
      QStringList args{op};
      if (op != "--restore")
        args << preset->currentData().toString();
      runTheme(args);
    });
  }
  themeStatus = new QPlainTextEdit;
  themeStatus->setObjectName("themeStatus");
  themeStatus->setReadOnly(true);
  themeStatus->setAccessibleName("Theme status and result");
  appearance->addRow(themeStatus);
  if (themeExe.isEmpty()) {
    preset->setEnabled(false);
    for (auto *b : themeControls)
      b->setEnabled(false);
    themeStatus->setPlainText(
        "The native DoroShell theme component is unavailable.");
  }
  desktopButton(appearance, "LXQt appearance settings…",
                "lxqt-config-appearance.desktop");
  cursorPage();
  connect(tabs, &QTabWidget::currentChanged, this, [this](int i) {
    if (tabs->widget(i) == themePage && !operation && !themeExe.isEmpty())
      runTheme({"--status"});
  });
  auto *close = new QDialogButtonBox(QDialogButtonBox::Close);
  layout->addWidget(close);
  connect(close, &QDialogButtonBox::rejected, this, &QWidget::close);
  resize(570, 380);
}
QFormLayout *SettingsHub::page(const QString &label) {
  auto *content = new QWidget;
  auto *form = new QFormLayout(content);
  form->setFieldGrowthPolicy(QFormLayout::AllNonFixedFieldsGrow);
  form->setRowWrapPolicy(QFormLayout::WrapLongRows);
  auto *scroll = new QScrollArea;
  scroll->setWidgetResizable(true);
  scroll->setWidget(content);
  scroll->setFrameShape(QFrame::NoFrame);
  tabs->addTab(scroll, label);
  return form;
}
QString SettingsHub::nativeExe(const QString &name,
                               const QString &component) const {
  auto same = executable(binDir + "/" + name);
  if (!same.isEmpty() || !buildTree)
    return same;
  return executable(binDir + "/../" + component + "/" + name);
}
QString SettingsHub::upstreamExe(const QString &name) const {
  auto local = executable(binDir + "/" + name);
  if (!local.isEmpty() && QFileInfo(local).canonicalFilePath() !=
                              QFileInfo("/usr/bin/" + name).canonicalFilePath())
    return local;
  return buildTree ? executable(binDir + "/../upstream/runtime/bin/" + name)
                   : QString{};
}
void SettingsHub::commandButton(QFormLayout *form, QString label, QString path,
                                QStringList args) {
  auto *button = new QPushButton(label);
  form->addRow(button);
  button->setEnabled(!path.isEmpty());
  if (path.isEmpty())
    button->setToolTip("This native component is unavailable.");
  connect(button, &QPushButton::clicked, this, [this, path, args] {
    if (!QProcess::startDetached(path, args))
      error("Cannot open " + QFileInfo(path).fileName());
  });
}
void SettingsHub::desktopButton(QFormLayout *form, QString label, QString id) {
  auto *button = new QPushButton(label);
  form->addRow(button);
  button->setEnabled(bool(entry(id)));
  if (!button->isEnabled())
    button->setToolTip("Missing " + id);
  connect(button, &QPushButton::clicked, this, [this, id] {
    auto desktop = entry(id);
    if (!desktop) {
      error("The application is unavailable.");
      return;
    }
    GError *detail = nullptr;
    if (!g_app_info_launch(G_APP_INFO(desktop.get()), nullptr, nullptr,
                           &detail))
      error(detail ? QString::fromUtf8(detail->message)
                   : "Could not open settings.");
    g_clear_error(&detail);
  });
}
void SettingsHub::runTheme(QStringList arguments) {
  runHelper(themeExe, arguments, themeStatus);
}
void SettingsHub::cursorPage() {
  auto *form = page("Cursor");
  const auto bin = nativeExe("doroshell-cursor", "cursor");
  auto *source = new QComboBox;
  source->setObjectName("cursorSource");
  source->addItem("Doro (transparent)", "apng");
  source->addItem("Doro (original GIF)", "gif");
  source->addItem("Choose animation…", "custom");
  form->addRow("Loading animation", source);
  auto *row = new QWidget;
  auto *layout = new QHBoxLayout(row);
  layout->setContentsMargins(0, 0, 0, 0);
  auto *file = new QLineEdit;
  file->setPlaceholderText("Animation file");
  file->setAccessibleName("Custom cursor animation");
  layout->addWidget(file);
  auto *browse = new QPushButton("Browse…");
  layout->addWidget(browse);
  form->addRow(row);
  connect(browse, &QPushButton::clicked, this, [this, file] {
    auto path = QFileDialog::getOpenFileName(
        this, "Choose animated cursor", file->text(),
        "Animations (*.png *.apng *.gif *.webp)");
    if (!path.isEmpty())
      file->setText(path);
  });
  connect(source, &QComboBox::currentIndexChanged, this, [source, row] {
    row->setVisible(source->currentData() == "custom");
  });
  row->hide();
  auto *pink = new QCheckBox("Use a pink normal pointer");
  pink->setObjectName("pinkPointer");
  form->addRow(pink);
  auto *buttons = new QHBoxLayout;
  form->addRow(buttons);
  auto *status = new QPlainTextEdit;
  status->setReadOnly(true);
  status->setAccessibleName("Cursor plan and result");
  form->addRow(status);
  for (const auto &[op, text] : QList<QPair<QString, QString>>{
           {"--plan", "Preview"},
           {"--apply", "Apply"},
           {"--rollback", "Restore previous cursor"}}) {
    auto *b = new QPushButton(text);
    b->setObjectName(op.mid(2) + "Cursor");
    buttons->addWidget(b);
    connect(b, &QPushButton::clicked, this,
            [this, op, source, pink, file, bin, status] {
              QStringList args{op};
              if (op != "--rollback") {
                if (source->currentData() == "custom") {
                  if (!QFileInfo(file->text()).isFile()) {
                    status->setPlainText("Choose an animation file first.");
                    return;
                  }
                  args << "--image" << file->text();
                } else
                  args << "--asset" << source->currentData().toString();
                if (pink->isChecked())
                  args << "--pink-pointer";
              }
              runHelper(bin, args, status);
            });
  }
  if (bin.isEmpty()) {
    form->parentWidget()->setEnabled(false);
    status->setPlainText("The native cursor component is unavailable.");
  }
}
void SettingsHub::runHelper(QString executable, QStringList arguments,
                            QPlainTextEdit *statusBox) {
  if (operation || executable.isEmpty())
    return;
  auto *p = new QProcess(this);
  operation = p;
  p->setProcessChannelMode(QProcess::MergedChannels);
  tabs->setEnabled(false);
  statusBox->setPlainText("Working…");
  auto finish = [this, p, statusBox](QString text) {
    if (operation != p)
      return;
    operation = nullptr;
    statusBox->setPlainText(text.trimmed());
    tabs->setEnabled(true);
    p->deleteLater();
  };
  connect(p, &QProcess::finished, this,
          [this, p, finish, arguments](int code, QProcess::ExitStatus status) {
            QString output = QString::fromUtf8(p->readAllStandardOutput());
            if (status != QProcess::NormalExit || code)
              output = QString("Operation failed (%1).\n").arg(code) + output;
            else if (arguments == QStringList{"--status"}) {
              auto obj = QJsonDocument::fromJson(output.toUtf8()).object();
              int index = preset->findData(obj.value("preset").toString());
              if (index >= 0 && obj.value("managed").isBool()) {
                preset->setCurrentIndex(index);
                output =
                    obj.value("managed").toBool()
                        ? "Current DoroShell theme: " + preset->currentText()
                        : "Using existing desktop settings.";
              }
            }
            finish(output.isEmpty() ? "Done." : output);
          });
  connect(p, &QProcess::errorOccurred, this,
          [p, finish](QProcess::ProcessError e) {
            if (e == QProcess::FailedToStart)
              finish(p->errorString());
          });
  p->start(executable, arguments);
}
void SettingsHub::error(const QString &msg) {
  QMessageBox box(QMessageBox::Warning, "DoroShell Settings", msg,
                  QMessageBox::Ok, this);
  box.setTextFormat(Qt::PlainText);
  box.exec();
}
void SettingsHub::closeEvent(QCloseEvent *event) {
  if (operation) {
    event->ignore();
    return;
  }
  QWidget::closeEvent(event);
}
