#pragma once
#include <QProcess>
#include <QStringList>
#include <QWidget>
class QComboBox;
class QPlainTextEdit;
class QFormLayout;
class QTabWidget;
class QPushButton;

class SettingsHub final : public QWidget {
public:
  explicit SettingsHub(QString binDirectory = QString());

protected:
  void closeEvent(QCloseEvent *event) override;

private:
  QString nativeExe(const QString &name, const QString &component) const;
  QString upstreamExe(const QString &name) const;
  QFormLayout *page(const QString &label);
  void commandButton(QFormLayout *form, QString label, QString path,
                     QStringList args = {});
  void desktopButton(QFormLayout *form, QString label, QString entry);
  void runTheme(QStringList arguments);
  void cursorPage();
  void runHelper(QString executable, QStringList arguments,
                 QPlainTextEdit *status);
  void error(const QString &msg);
  QTabWidget *tabs;
  QWidget *themePage;
  QComboBox *preset;
  QPlainTextEdit *themeStatus;
  QList<QPushButton *> themeControls;
  QProcess *operation = nullptr;
  QString binDir, themeExe;
  bool buildTree = false;
};
