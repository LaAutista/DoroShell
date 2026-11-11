// Test-only instrumentation of actual PCManFM Preferences on a private X server.
#include <QApplication>
#include <QDialog>
#include <QDialogButtonBox>
#include <QComboBox>
#include <QLineEdit>
#include <QPushButton>
#include <QProcess>
#include <QLabel>
#include <QTabWidget>
#include <QFile>
#include <QJsonDocument>
#include <QPalette>
#include <QSlider>
#include <QGroupBox>
#include <QJsonObject>
#include <QTimer>
#include <QTest>
#include <stdexcept>
#include <functional>
static void check(bool ok,const char* why){if(!ok)throw std::runtime_error(why);}
static QByteArray read(const QString& p){QFile f(p);check(f.open(QIODevice::ReadOnly),"read settings");return f.readAll();}
static bool wait(std::function<bool()> f){for(int n=0;n<100;++n){QApplication::processEvents();if(f())return true;QTest::qWait(20);}return false;}
static void run(QDialog* d){try {
    QWidget survivor;survivor.show();
    auto path=qEnvironmentVariable("XDG_CONFIG_HOME")+"/doroshell/wallpaper.json";auto baseline=read(path);
    auto scenario=qEnvironmentVariable("DORO_WALLPAPER_SCENARIO");
    auto type=d->findChild<QComboBox*>("wallpaperType");auto media=d->findChild<QLineEdit*>("wallpaperMedia");auto buttons=d->findChild<QDialogButtonBox*>();check(type && media && buttons,"native controls present");
    d->findChild<QTabWidget*>()->setCurrentIndex(1);
    auto volume=d->findChild<QSlider*>("wallpaperVolume");check(volume && !volume->isEnabled(),"muted volume slider disabled");
    check(!d->findChild<QPushButton*>("wallpaperStop")->isEnabled(),"Stop initially disabled");
    check(d->findChild<QGroupBox*>("groupBox_2")->mapTo(d,QPoint()).y()<type->mapTo(d,QPoint()).y(),"static controls precede animation group");
    if(!qEnvironmentVariable("DORO_WALLPAPER_SCREENSHOT").isEmpty()) {QTest::qWait(100);d->grab().save(qEnvironmentVariable("DORO_WALLPAPER_SCREENSHOT"));}
    if(scenario=="unchanged") {QTest::mouseClick(buttons->button(QDialogButtonBox::Apply),Qt::LeftButton);check(read(path)==baseline,"unchanged Apply preserves exact bytes");}
    type->setCurrentIndex(1);media->setText(qEnvironmentVariable("DORO_TEST_MEDIA"));
    if(scenario=="preview-failure") {
        media->setText(qEnvironmentVariable("DORO_BAD_MEDIA"));QTest::mouseClick(d->findChild<QPushButton*>("wallpaperPreview"),Qt::LeftButton);
        auto process=d->findChild<QProcess*>("wallpaperPreviewProcess");check(wait([&]{return process->state()==QProcess::NotRunning;}),"failed preview ends");check(read(path)==baseline,"failed preview preserves baseline");
    } else if(scenario=="preview" || scenario=="preview-cancel"){
        QTest::mouseClick(d->findChild<QPushButton*>("wallpaperPreview"),Qt::LeftButton);
        auto process=d->findChild<QProcess*>("wallpaperPreviewProcess");check(wait([&]{return process->state()==QProcess::Running;}),"real preview process started");
        QTest::qWait(500);check(read(path)==baseline,"preview preserves settings");
        if(scenario=="preview")QTest::mouseClick(d->findChild<QPushButton*>("wallpaperStop"),Qt::LeftButton);
        else QTest::mouseClick(buttons->button(QDialogButtonBox::Cancel),Qt::LeftButton);
        check(process->state()==QProcess::NotRunning,"stop/cancel ends preview");check(read(path)==baseline,"stop/cancel preserves baseline");
    } else if(scenario=="cancel"){
        QTest::mouseClick(buttons->button(QDialogButtonBox::Cancel),Qt::LeftButton);check(read(path)==baseline,"cancel preserves baseline");
    } else if(scenario=="invalid"){
        media->setText("/does-not-exist");QTest::mouseClick(buttons->button(QDialogButtonBox::Ok),Qt::LeftButton);check(d->isVisible(),"invalid OK remains open");check(read(path)==baseline,"invalid file preserves baseline");
    } else if(scenario=="conflict"){
        QFile f(path);check(f.open(QIODevice::Append),"external edit");f.write("\n");f.close();QTest::mouseClick(buttons->button(QDialogButtonBox::Apply),Qt::LeftButton);check(read(path)==baseline+"\n","conflicting edit preserved");check(d->findChild<QLabel*>("wallpaperStatus")->text().contains("changed elsewhere"),"conflict visible");
    } else {
        QTest::mouseClick(buttons->button(scenario=="ok"?QDialogButtonBox::Ok:QDialogButtonBox::Apply),Qt::LeftButton);
        auto saved=read(path);check(QJsonDocument::fromJson(saved).object()["enabled"].toBool(),"Apply/OK saved animation");check(read(path+".before-native-prefs")==baseline,"exact backup");
        if(scenario=="static") {type->setCurrentIndex(0);QTest::mouseClick(buttons->button(QDialogButtonBox::Apply),Qt::LeftButton);check(!QJsonDocument::fromJson(read(path)).object()["enabled"].toBool(),"static fallback disables renderer");}
        else if(scenario=="ok")check(!d->isVisible(),"OK closes");else {
            type->setCurrentIndex(0);QTest::mouseClick(buttons->button(QDialogButtonBox::Cancel),Qt::LeftButton);check(read(path)==saved,"Cancel retains last Apply");
        }
    }
    QFile result(qEnvironmentVariable("DORO_WALLPAPER_RESULT"));check(result.open(QIODevice::WriteOnly),"result");result.write("PASS");result.close();QCoreApplication::exit(0);
}catch(const std::exception& e){qCritical("FAIL wallpaper: %s",e.what());QCoreApplication::exit(77);}}
static void startup(){qunsetenv("LD_PRELOAD");
    if(qEnvironmentVariable("DORO_TEST_DARK")=="1") {
        QPalette palette;palette.setColor(QPalette::Window,QColor("#3b393d"));palette.setColor(QPalette::WindowText,QColor("#eeeeee"));palette.setColor(QPalette::Base,QColor("#252426"));palette.setColor(QPalette::Text,QColor("#eeeeee"));palette.setColor(QPalette::Button,QColor("#424045"));palette.setColor(QPalette::ButtonText,QColor("#eeeeee"));palette.setColor(QPalette::Highlight,QColor("#7e4853"));palette.setColor(QPalette::HighlightedText,Qt::white);palette.setColor(QPalette::Disabled,QPalette::Text,QColor("#999999"));palette.setColor(QPalette::Disabled,QPalette::ButtonText,QColor("#999999"));qApp->setPalette(palette);
    }
if(qEnvironmentVariable("DISPLAY")!=qEnvironmentVariable("DOROSHELL_TEST_DISPLAY")||qEnvironmentVariable("DISPLAY")==":0")return;auto timer=new QTimer(qApp);timer->setInterval(50);QObject::connect(timer,&QTimer::timeout,[timer]{for(auto w:QApplication::topLevelWidgets())if(auto d=qobject_cast<QDialog*>(w))if(d->windowTitle()=="Desktop Preferences"){timer->stop();run(d);return;}});timer->start();}
Q_COREAPP_STARTUP_FUNCTION(startup)
