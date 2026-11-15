// SPDX-License-Identifier: GPL-2.0-or-later
// Actual source snippets run with synthetic screen/panel inputs, never a panel process.
#include <QtWidgets>
#include <QtTest>
#include <stdexcept>
#include <iostream>

static void require(bool ok, const char* reason) {
    if (!ok) throw std::runtime_error(reason);
}
struct FixtureScreen {
    QRect full, available;
    QRect geometry() const { return full; }
    QRect availableGeometry() const { return available; }
};
struct FixtureAnchor : QWidget {
    FixtureScreen* fixture;
    explicit FixtureAnchor(FixtureScreen* screen, QWidget* parent): QWidget(parent), fixture(screen) {}
    FixtureScreen* screen() const { return fixture; }
};
struct ILXQtPanel {
    enum Position { PositionBottom, PositionTop };
    Position side;
    Position position() const { return side; }
};
class ClockFixture {
public:
    FixtureScreen screen;
    QWidget bar;
    FixtureAnchor* mMainWidget;
    QWidget* mRotatedWidget = nullptr;
    QDialog* mPopup;
    bool mShowWeekNumber;
    ILXQtPanel panelFixture;
    ClockFixture(QRect available, bool top, bool weeks, bool workarea):
        screen{QRect(0,0,1000,800),available}, mShowWeekNumber(weeks),
        panelFixture{top ? ILXQtPanel::PositionTop : ILXQtPanel::PositionBottom} {
        bar.setWindowFlags(Qt::FramelessWindowHint);
        if (workarea)
            bar.setGeometry(0, top ? 0 : 760, 1000,40);
        else {
            bar.setGeometry(available.x(), top ? available.top()-40 : available.bottom()+1, available.width(),40);
            screen.full=available.united(bar.geometry());
        }
        mMainWidget = new FixtureAnchor(&screen,&bar);
        mMainWidget->setGeometry(bar.width()-100,0,100,40);
        bar.show();
        mPopup = new QDialog(mMainWidget, Qt::Window | Qt::WindowStaysOnTopHint |
            Qt::CustomizeWindowHint | Qt::Popup | Qt::X11BypassWindowManagerHint);
        mPopup->setAttribute(Qt::WA_DeleteOnClose);
        mPopup->setLayout(new QHBoxLayout);
        mPopup->layout()->setContentsMargins(0,0,0,0);
        constructCalendar();
        calendar()->setFirstDayOfWeek(Qt::Monday);
        calendar()->setSelectedDate(QDate(2026,8,31)); // six-week month
        mPopup->adjustSize();
        positionPopup();
        mPopup->show();
        QApplication::processEvents();
    }
    ~ClockFixture() { delete mPopup; }
    ILXQtPanel* panel() { return &panelFixture; }
    QRect calculatePopupWindowPos(const QSize& size) { return QRect(QPoint(1,1),size); }
    QCalendarWidget* calendar() { return mPopup->findChild<QCalendarWidget*>(); }
    void constructCalendar();
    void positionPopup();
};
#include "calendar_from_source.inc"

static void checkCalendar(ClockFixture& clock, QRect bounds) {
    auto* popup=clock.mPopup;
    auto* calendar=clock.calendar();
    auto* scroll=popup->findChild<QScrollArea*>();
    require(bounds.contains(popup->geometry()), "popup escapes available work area");
    const QSize natural=calendar->minimumSizeHint();
    const int hbar=scroll->horizontalScrollBar()->sizeHint().height();
    const int vbar=scroll->verticalScrollBar()->sizeHint().width();
    const bool horizontal=natural.width()>bounds.width();
    const bool vertical=natural.height()>bounds.height();
    if (natural.height()+(horizontal ? hbar : 0)<=bounds.height()) {
        require(scroll->verticalScrollBar()->maximum()==0,
                "horizontal scrollbar clips final week despite spare work-area height");
        auto* table=calendar->findChild<QTableView*>();
        QRect last=table->visualRect(table->model()->index(table->model()->rowCount()-1,1));
        require(table->viewport()->rect().contains(last), "final week clipped inside table");
        const int bottom=table->viewport()->mapTo(scroll->viewport(),last.bottomLeft()).y();
        require(bottom<scroll->viewport()->height(), "final week outside scroll viewport");
    }
    if (natural.width()+(vertical ? vbar : 0)<=bounds.width())
        require(scroll->horizontalScrollBar()->maximum()==0,
                "vertical scrollbar clips columns despite spare work-area width");
    // Constrained content remains reachable using the existing scrollbars.
    scroll->horizontalScrollBar()->setValue(scroll->horizontalScrollBar()->maximum());
    scroll->verticalScrollBar()->setValue(scroll->verticalScrollBar()->maximum());
    QApplication::processEvents();
    const QPoint bottomRight=calendar->mapTo(scroll->viewport(),calendar->rect().bottomRight());
    require(scroll->viewport()->rect().contains(bottomRight), "bottom/right content unreachable");
    scroll->horizontalScrollBar()->setValue(0);
    scroll->verticalScrollBar()->setValue(0);
    for (const char* name: {"qt_calendar_monthbutton","qt_calendar_yearbutton"}) {
        auto* button=calendar->findChild<QToolButton*>(name);
        require(button && button->width()>=button->sizeHint().width(), "month/year header clipped internally");
    }
}
int main(int argc, char** argv) {
    QApplication app(argc,argv);
    app.setStyle("Fusion");
    QLocale::setDefault(QLocale(QLocale::English,QLocale::UnitedStates));
    const QString out=argc>1 ? QString::fromLocal8Bit(argv[1]) : QString();
    const QString boundsCase=argc>2 ? QString::fromLocal8Bit(argv[2]) : QStringLiteral("all");
    int cases=0;
    try {
        for (bool workarea: {false,true}) {
        if ((boundsCase=="screen" && workarea) || (boundsCase=="workarea" && !workarea)) continue;
        for (int font: {10,18,28}) for (QSize size: {QSize(740,650),QSize(320,400),QSize(700,170),QSize(200,170)})
        for (bool top: {false,true}) for (bool weeks: {false,true}) for (int reopen=0;reopen<2;++reopen) {
            app.setFont(QFont("DejaVu Sans",font));
            QRect bounds(QPoint(30,60),size);
            ClockFixture clock(bounds,top,weeks,workarea);
            if (!out.isEmpty() && font==18 && !top && !weeks && reopen==0)
                clock.mPopup->grab().save(out+QStringLiteral("/initial-%1-%2x%3.png").arg(workarea ? "workarea" : "screen").arg(size.width()).arg(size.height()));
            checkCalendar(clock,bounds);
            auto* calendar=clock.calendar();
            auto* scroll=clock.mPopup->findChild<QScrollArea*>();
            auto* next=calendar->findChild<QToolButton*>("qt_calendar_nextmonth");
            scroll->ensureWidgetVisible(next);QApplication::processEvents();
            require(scroll->viewport()->rect().contains(next->mapTo(scroll->viewport(),next->rect().center())),"next month unreachable");
            QTest::mouseClick(next,Qt::LeftButton);
            require(calendar->monthShown()==9,"next month mouse navigation changed");
            auto* previous=calendar->findChild<QToolButton*>("qt_calendar_prevmonth");
            scroll->ensureWidgetVisible(previous);QApplication::processEvents();
            require(scroll->viewport()->rect().contains(previous->mapTo(scroll->viewport(),previous->rect().center())),"previous month unreachable");
            QTest::mouseClick(previous,Qt::LeftButton);
            require(calendar->monthShown()==8,"previous month mouse navigation changed");
            calendar->setSelectedDate(QDate(2026,8,31));
            auto* table=calendar->findChild<QTableView*>();table->setFocus();
            QTest::keyClick(table,Qt::Key_Left);
            require(calendar->selectedDate()==QDate(2026,8,30),"native date arrow navigation changed");
            calendar->setCurrentPage(2030,12);QApplication::processEvents();
            checkCalendar(clock,bounds);
            if (!out.isEmpty() && workarea && font==18 && !top && !weeks && reopen==0) {
                scroll->horizontalScrollBar()->setValue(0);scroll->verticalScrollBar()->setValue(0);
                require(clock.mPopup->grab().save(out+QStringLiteral("/calendar-%1x%2.png").arg(size.width()).arg(size.height())),"capture failed");
            }
            QPointer<QDialog> guard=clock.mPopup;
            QTest::keyClick(clock.mPopup,Qt::Key_Escape);
            require(!guard || !guard->isVisible(),"Escape did not dismiss popup");
            clock.mPopup=nullptr;QCoreApplication::sendPostedEvents(nullptr,QEvent::DeferredDelete);
            ++cases;
        }
        }
        std::cout << "PASS " << cases << " native snippet calendar cases; DPR " << app.devicePixelRatio() << std::endl;
    } catch (const std::exception& error) {
        std::cerr << "FAIL " << error.what() << " after " << cases << " cases" << std::endl;
        return 1;
    }
}
