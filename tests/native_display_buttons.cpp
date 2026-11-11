// Test-only preload drives the real PCManFM dialog; never linked into the candidate.
#include <QApplication>
#include <QDialog>
#include <QPointer>
#include <QCheckBox>
#include <QDialogButtonBox>
#include <QComboBox>
#include <QPushButton>
#include <QLabel>
#include <QTabWidget>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QTimer>
#include <QTest>
#include <functional>
#include <stdexcept>
static void require(bool ok,const char *message) { if(!ok) throw std::runtime_error(message); }
static bool waitFor(std::function<bool()> f,int limit=6000) { for(int i=0;i<limit;i+=20) { QApplication::processEvents();if(f())return true;QTest::qWait(20); }return false; }
static QJsonObject fixture() { QFile f(qEnvironmentVariable("DORO_NATIVE_FIXTURE"));require(f.open(QIODevice::ReadOnly),"fixture read");return QJsonDocument::fromJson(f.readAll()).object(); }
static QString mode() {return fixture()["mode"].toString();}
static void run(QDialog *dialog) {
    try {
        QPointer<QDialog> window(dialog);
        QWidget survivor; survivor.setWindowTitle("Private test keeps process alive"); survivor.show();
        auto scenario=qEnvironmentVariable("DORO_NATIVE_SCENARIO");
        auto tabs=dialog->findChild<QTabWidget*>();require(tabs,"native tabs");tabs->setCurrentIndex(tabs->count()-1);
        dialog->resize(520,680);
        auto rate=dialog->findChild<QComboBox*>("displayRate");require(rate,"native display selector");
        auto reload=dialog->findChild<QPushButton*>("displayReload");
        auto buttons=dialog->findChild<QDialogButtonBox*>("buttonBox");require(buttons,"native bottom button box");
        if(scenario=="query-close") {
            QTest::qWait(100); dialog->close(); QTest::qWait(1300);
            require(fixture()["calls"].toArray().isEmpty(),"closing query never writes");
            QFile result(qEnvironmentVariable("DORO_NATIVE_RESULT"));require(result.open(QIODevice::WriteOnly),"query close result");result.write("PASS");result.close();QCoreApplication::exit(0);return;
        }
        require(waitFor([&]{return reload->isEnabled() && rate->count()==2;}),"capabilities loaded");
        auto ordinary=dialog->findChild<QCheckBox*>("noItemTooltip");require(ordinary,"ordinary native preference");ordinary->setChecked(true);
        if(scenario=="unchanged") {
            QTest::mouseClick(buttons->button(QDialogButtonBox::Apply),Qt::LeftButton);
            QTest::qWait(200);require(fixture()["calls"].toArray().isEmpty(),"unchanged Apply must not call driver");
            require(!dialog->findChild<QDialog*>("displayConfirmation"),"no unnecessary confirmation");
            QTest::mouseClick(buttons->button(QDialogButtonBox::Ok),Qt::LeftButton);
            require(!dialog->isVisible(),"unchanged OK closes normally");
        } else {
            int index=rate->findData("0x12");require(index>=0 && rate->itemText(index).contains("59.95"),"advertised 59.95 Hz");
            rate->setCurrentIndex(index);
            QTest::mouseClick(buttons->button(scenario.startsWith("apply")?QDialogButtonBox::Apply:QDialogButtonBox::Ok),Qt::LeftButton);
            require(dialog->isVisible(),"Preferences must stay open while guard starts");
            auto confirm=dialog->findChild<QDialog*>("displayConfirmation");require(confirm && confirm->isVisible(),"visible confirmation despite Advanced scrolling");
            auto keep=confirm->findChild<QPushButton*>("confirmDisplayKeep");auto revert=confirm->findChild<QPushButton*>("confirmDisplayRevert");
            if(scenario=="error" || scenario.endsWith("external") || scenario=="abnormal" || scenario=="log-error") {
                require(waitFor([&]{return reload->isEnabled();}),"failed transaction finishes");
                require(dialog->isVisible() && mode()==((scenario.endsWith("external") || scenario=="abnormal")?"0x12":"0x11"),"failed OK preserves original and stays open");
                require(dialog->findChild<QLabel*>("displayStatus")->text().contains(scenario.endsWith("external")?"brightness":(scenario=="abnormal"?"Recovery is unverified":"Synthetic")),"error reported");
                require(rate->count()==2 && rate->currentData().toString()==mode(),"error refresh repopulates actual mode");
                auto failure=dialog->findChild<QDialog*>("displayFailure");require(failure && failure->isVisible(),"terminal failure remains prominent");
                auto failureText=failure->findChild<QLabel*>("displayFailureText");require(failureText && failureText->text().contains("Recovery is unverified"),"honest recovery wording");
                auto failureButtons=failure->findChild<QDialogButtonBox*>("displayFailureButtons");
                require(failureButtons && failureButtons->standardButtons()==QDialogButtonBox::Close,"failure offers only Close, never Keep");
                QFile record(qEnvironmentVariable("XDG_STATE_HOME")+"/doroshell-display-errors/last-failure.json");
                if(scenario=="log-error") require(!record.exists() && failureText->text().contains("could not be saved"),"log failure does not hide dialog");
                else {
                    require(record.open(QIODevice::ReadOnly),"private failure record");auto bytes=record.readAll();
                    require(bytes.size()<=2048 && !bytes.contains("Synthetic") && !bytes.contains("DP-0"),"record redacted and bounded");
                    auto data=QJsonDocument::fromJson(bytes).object();
                    require(data["reason"].toString()==(scenario=="abnormal"?"abnormal_exit":"guard_error"),"structured failure reason");
                    require(data["recovery"].toString()=="unverified","record does not claim restoration");
                    require(data["schema"].toInt()==2,"schema 2 reached actual native writer");
                    require(!bytes.contains("BT2020_RGB"),"property value excluded from native record");
                    auto events=data["diagnostics"].toArray();
                    if(scenario.endsWith("external")) {
                        require(events.size()==2,"initial verification and recovery both retained through UI");
                        require(events[0].toObject()["phase"]=="apply_verification" && events[0].toObject()["reason"]=="state_mismatch","apply verification classification");
                        require(events[1].toObject()["phase"]=="recovery" && events[1].toObject()["reason"]=="external_change","recovery refusal classification");
                        for(const auto &event:events) {
                            auto fields=event.toObject()["fields"].toArray();
                            require(fields.contains("brightness") && fields.contains("Colorspace"),"exact property labels reach private record");
                        }
                    } else if(scenario=="error") {
                        require(events.size()==1 && events[0].toObject()["phase"]=="apply" && events[0].toObject()["reason"]=="command_failed","driver failure retained through UI");
                    }

                }
                QTest::qWait(400);require(failure->isVisible(),"error remains until dismissed");
                if(!qEnvironmentVariable("DORO_NATIVE_SCREENSHOTS").isEmpty()) failure->grab().save(qEnvironmentVariable("DORO_NATIVE_SCREENSHOTS")+"/"+scenario+"-failure.png");
                QTest::mouseClick(failureButtons->button(QDialogButtonBox::Close),Qt::LeftButton);
                require(dialog->isVisible(),"dismissing failure keeps Preferences open");
                const auto count=fixture()["calls"].toArray().size();
                require(count==((scenario.endsWith("external") || scenario=="abnormal")?1:0),"no forced recovery write");
                QTest::qWait(600);
                require(fixture()["calls"].toArray().size()==count,"read-only refresh never retries writes");
            } else {
                require(waitFor([&]{return keep->isEnabled();}),"guard asks confirmation");
                require(mode()=="0x12","59.95 exact mode applied to fake driver");
                if(!qEnvironmentVariable("DORO_NATIVE_SCREENSHOTS").isEmpty()) confirm->grab().save(qEnvironmentVariable("DORO_NATIVE_SCREENSHOTS")+"/"+scenario+".png");
                require(fixture()["calls"].toArray().size()==1,"only one apply transaction");
                if(scenario=="close") {
                    dialog->close();
                    require(waitFor([&]{return mode()=="0x11";},4000),"closing Preferences promptly reverts even with process alive");
                    QFile result(qEnvironmentVariable("DORO_NATIVE_RESULT"));require(result.open(QIODevice::WriteOnly),"close result");result.write("PASS");result.close();QCoreApplication::exit(0);return;
                }
                if(scenario.endsWith("keep")) QTest::mouseClick(keep,Qt::LeftButton);
                else if(scenario!="timeout") QTest::mouseClick(revert,Qt::LeftButton);
                if(scenario=="ok-keep") {
                    require(waitFor([&]{return !window || !window->isVisible();}),"OK closes after successful Keep");
                    require(mode()=="0x12","Keep persists fake mode");
                } else {
                    require(waitFor([&]{return reload->isEnabled();},scenario=="timeout"?19000:6000),"guard settles");
                    require(dialog->isVisible(),"Apply/revert/timeout leaves preferences open");
                    require(mode()==(scenario=="apply-keep"?"0x12":"0x11"),"expected kept/restored mode");
                    require(rate->count()==2 && rate->currentData().toString()==mode(),"completed refresh repopulates actual mode");
                    require(fixture()["calls"].toArray().size()==(scenario=="apply-keep"?1:2),"refresh has no write side effect");
                }
            }
        }
        QFile result(qEnvironmentVariable("DORO_NATIVE_RESULT"));require(result.open(QIODevice::WriteOnly),"result file");result.write("PASS");result.close();
        QCoreApplication::exit(0);
    } catch(const std::exception &e) {qCritical("FAIL native display buttons: %s",e.what());QCoreApplication::exit(77);}
}
static void startup() {
    qunsetenv("LD_PRELOAD"); // Child Python guards/drivers do not inherit test instrumentation.
    if(qEnvironmentVariable("DISPLAY")!=qEnvironmentVariable("DOROSHELL_TEST_DISPLAY") || qEnvironmentVariable("DISPLAY")==":0") return;
    auto timer=new QTimer(qApp);timer->setInterval(50);
    QObject::connect(timer,&QTimer::timeout,[timer]{for(auto w:QApplication::topLevelWidgets()) if(auto d=qobject_cast<QDialog*>(w)) if(d->windowTitle()=="Desktop Preferences") {timer->stop();run(d);return;}});
    timer->start();
}
Q_COREAPP_STARTUP_FUNCTION(startup)
