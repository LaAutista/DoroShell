// Real Qt widget events on a private X server, synthetic driver state only.
#include "dorodisplaycontrols.h"
#include <QApplication>
#include <QDialog>
#include <QFile>
#include <QSaveFile>
#include <QTabWidget>
#include <QTest>
#include <functional>
#include <stdexcept>
static void require(bool value, const char *message) { if (!value) throw std::runtime_error(message); }
static bool waitFor(const std::function<bool()> &predicate, int ms=5000) {
    for (int i=0;i<ms;i+=20) { QApplication::processEvents();if(predicate())return true;QTest::qWait(20); }return false;
}
static QJsonObject fixture() { QFile file(qEnvironmentVariable("DOROSHELL_DISPLAY_FIXTURE"));require(file.open(QIODevice::ReadOnly),"read fixture");return QJsonDocument::fromJson(file.readAll()).object(); }
static void save(const QJsonObject &value) { QSaveFile file(qEnvironmentVariable("DOROSHELL_DISPLAY_FIXTURE"));require(file.open(QIODevice::WriteOnly),"write fixture");file.write(QJsonDocument(value).toJson());require(file.commit(),"commit fixture"); }
static QString mode() { return fixture()["state"].toObject()["outputs"].toArray()[0].toObject()["current"].toString(); }
int main(int argc,char **argv) {
    QApplication app(argc,argv);
    try {
        require(qEnvironmentVariable("DISPLAY")==qEnvironmentVariable("DOROSHELL_TEST_DISPLAY") && qEnvironmentVariable("DISPLAY")!=":0", "private display required");
        auto original=fixture();
        auto dialog=new QDialog;dialog->setWindowTitle("Desktop Preferences — private display test");dialog->resize(600,650);
        auto layout=new QVBoxLayout(dialog);auto tabs=new QTabWidget;layout->addWidget(tabs);
        tabs->addTab(new QWidget,"General");tabs->addTab(new QWidget,"Background");tabs->addTab(new QWidget,"Slide Show");
        QFile backend(QString::fromLocal8Bit(argv[1]));require(backend.open(QIODevice::ReadOnly),"fixture helper read");auto helperBytes=backend.readAll();backend.close();
        bool integrity=argc>2 && QString(argv[2])=="integrity";
        auto controls=new DoroDisplayControls({"/usr/bin/python3",QString::fromLocal8Bit(argv[1])},nullptr,
            QCryptographicHash::hash(helperBytes,QCryptographicHash::Sha256).toHex());
        tabs->addTab(controls,"Advanced");tabs->setCurrentIndex(3);
        dialog->show();
        auto button=[&](const char *name){return controls->findChild<QPushButton*>(name);};
        auto status=controls->findChild<QLabel*>("displayStatus");auto rate=controls->findChild<QComboBox*>("displayRate");
        auto reload=[&]{QTest::mouseClick(button("displayReload"),Qt::LeftButton);require(waitFor([&]{return button("displayReload")->isEnabled();}),"query finish");};
        auto begin=[&]{rate->setCurrentIndex(1);QTest::mouseClick(button("displayApply"),Qt::LeftButton);require(waitFor([&]{return button("displayKeep")->isEnabled();}),"pending confirmation");};
        require(waitFor([&]{return button("displayApply")->isEnabled();}),"initial capabilities");
        require(rate->count()==2,"advertised refresh rates");
        if(integrity) {
            require(backend.open(QIODevice::WriteOnly|QIODevice::Append),"tamper private helper");backend.write("\n# synthetic tamper\n");backend.close();
            rate->setCurrentIndex(1);QTest::mouseClick(button("displayApply"),Qt::LeftButton);
            require(!button("displayApply")->isEnabled(),"changed helper disables apply");
            require(status->text().contains("helper missing or changed"),"changed helper error visible");
            require(fixture()==original,"tampered helper never ran");
            require(backend.remove(),"remove private fixture helper");reload();
            require(!button("displayApply")->isEnabled(),"missing helper disables apply");
            require(fixture()==original,"missing helper never ran");
            fprintf(stdout,"PASS native helper integrity: changed/missing backend rejected before launch\n");
            delete dialog;return 0;
        }
        if(argc>2 && QString(argv[2])=="exit") {
            begin();QTimer::singleShot(100,&app,&QApplication::quit);return app.exec();
        }
        begin();require(mode()=="0x12","applied exact mode");require(!button("displayApply")->isEnabled(),"duplicate apply disabled");
        QTest::mouseClick(button("displayRevert"),Qt::LeftButton);
        require(waitFor([&]{return mode()=="0x11" && button("displayReload")->isEnabled();}),"explicit revert");
        reload();begin();QTest::mouseClick(button("displayKeep"),Qt::LeftButton);
        require(waitFor([&]{return button("displayReload")->isEnabled();}),"keep finished");require(mode()=="0x12","keep mode");
        reload();QTest::mouseClick(button("displayApply"),Qt::LeftButton);require(waitFor([&]{return button("displayKeep")->isEnabled();}),"repeated apply");
        QTest::mouseClick(button("displayRevert"),Qt::LeftButton);require(waitFor([&]{return button("displayReload")->isEnabled();}),"repeat revert");require(mode()=="0x12","repeat baseline retained");
        save(original);reload();begin();
        require(waitFor([&]{return button("displayReload")->isEnabled();},18000),"timeout completed");require(mode()=="0x11","timeout rollback");
        auto error=original;error["error"]=true;save(error);reload();require(!button("displayApply")->isEnabled(),"query error disabled");require(status->text().contains("failure"),"query error visible");
        error=original;error["fail"]=true;save(error);reload();rate->setCurrentIndex(1);QTest::mouseClick(button("displayApply"),Qt::LeftButton);
        require(waitFor([&]{return button("displayReload")->isEnabled();}),"apply error finished");require(mode()=="0x11","failed apply preserves state");require(status->text().contains("failure"),"apply error visible");
        auto unsupported=original;auto state=unsupported["state"].toObject();state["vsync"]=QJsonValue::Null;state["vsync_reason"]="Intel/AMD: use application VSync settings.";unsupported["state"]=state;save(unsupported);reload();
        require(!controls->findChild<QCheckBox*>("displayVsync")->isEnabled(),"unsupported vsync disabled");require(button("displayApply")->isEnabled(),"RandR independent of NVIDIA");
        auto outputs=state["outputs"].toArray();auto clone=outputs[0].toObject();clone["name"]="DP-1";outputs.append(clone);state["outputs"]=outputs;unsupported["state"]=state;save(unsupported);reload();require(!button("displayApply")->isEnabled(),"shared CRTC disabled");
        save(original);reload();begin();auto disconnected=fixture();state=disconnected["state"].toObject();outputs=state["outputs"].toArray();auto output=outputs[0].toObject();output["current"]=QJsonValue::Null;outputs[0]=output;state["outputs"]=outputs;state["layout"]="disconnected";disconnected["state"]=state;save(disconnected);
        require(waitFor([&]{return button("displayReload")->isEnabled();}),"disconnect handled");require(status->text().contains("disconnected"),"disconnect visible");
        save(original);reload();begin();auto unexpected=fixture();unexpected["unexpected_exit"]=true;save(unexpected);
        require(waitFor([&]{return button("displayReload")->isEnabled();}),"unexpected guard exit finished");
        require(status->text().contains("Recovery is unverified"),"missing terminal protocol must not imply rollback");
        save(original);reload();QTest::qWait(150);dialog->grab().save(qEnvironmentVariable("DOROSHELL_DISPLAY_SCREENSHOT"));begin();delete dialog;
        require(waitFor([&]{return mode()=="0x11";}),"closing preferences reverts");
        fprintf(stdout,"PASS native UI: rates, keep, revert, repeated apply, timeout, errors, unsupported drivers, shared CRTC, disconnect, closing preferences\n");
        return 0;
    } catch(const std::exception &e) {qCritical("FAIL %s",e.what());return 1;}
}
