#!/usr/bin/env python3
"""Compile the actual holiday/DST calendar marking helpers with offscreen Qt and check known 2026 dates.

Uses a disposable HOME, offscreen QPA and fixed en_US locale; never a panel process.
"""
import argparse
import os
from pathlib import Path
import shlex
import subprocess
import tempfile

TEST = r'''
#include <QtWidgets>
#include <QTimeZone>
#include <iostream>
#include "marks.inc"
static int failures = 0;
static void expect(bool ok, const QString &what) { if (!ok) { ++failures; std::cerr << "FAIL " << what.toStdString() << "\n"; } }
static QString tip(QCalendarWidget &c, QDate d) { return c.dateTextFormat(d).toolTip(); }
int main(int argc, char **argv) {
    QLocale::setDefault(QLocale(QLocale::English, QLocale::UnitedStates));
    QApplication app(argc, argv);
    QCalendarWidget c;
    const QTimeZone la("America/Los_Angeles");
    const struct { int m, d; const char *name; } expected[] = {
        {1,1,"New Year's Day"},{1,19,"Martin Luther King Jr. Day"},{2,16,"Washington's Birthday"},
        {5,25,"Memorial Day"},{6,19,"Juneteenth"},{7,4,"Independence Day"},{9,7,"Labor Day"},
        {10,12,"Columbus Day"},{11,11,"Veterans Day"},{11,26,"Thanksgiving Day"},{12,25,"Christmas Day"}};
    for (const auto &e : expected) {
        c.setCurrentPage(2026, e.m);
        doroshellMarkCalendar(&c, la, 2026, e.m);
        expect(tip(c, QDate(2026, e.m, e.d)) == QLatin1String(e.name), QStringLiteral("%1 on 2026-%2-%3").arg(e.name).arg(e.m).arg(e.d));
    }
    doroshellMarkCalendar(&c, la, 2026, 3);
    expect(tip(c, QDate(2026,3,8)) == "Daylight saving time begins", "LA DST begins 2026-03-08");
    expect(tip(c, QDate(2026,3,9)).isEmpty(), "no mark on 2026-03-09");
    doroshellMarkCalendar(&c, la, 2026, 11);
    expect(tip(c, QDate(2026,11,1)) == "Daylight saving time ends", "LA DST ends 2026-11-01");
    expect(c.dateTextFormat(QDate(2026,11,26)).fontWeight() == QFont::Bold, "holiday is bold");
    expect(tip(c, QDate(2026,3,8)).isEmpty(), "old month marks cleared on page change");
    doroshellMarkCalendar(&c, QTimeZone("Europe/Berlin"), 2026, 3);
    expect(tip(c, QDate(2026,3,29)) == "Daylight saving time begins", "Berlin DST begins 2026-03-29");
    doroshellMarkCalendar(&c, QTimeZone("Asia/Tokyo"), 2026, 3);
    expect(c.dateTextFormat().isEmpty(), "no DST mark in Tokyo");
    QLocale::setDefault(QLocale(QLocale::German, QLocale::Germany));
    doroshellMarkCalendar(&c, QTimeZone("Europe/Berlin"), 2026, 12);
    expect(tip(c, QDate(2026,12,25)).isEmpty(), "US holidays hidden for non-US locale");
    // Week grid of January 2027 shows Dec 2026 days; marks must cover them.
    QLocale::setDefault(QLocale(QLocale::English, QLocale::UnitedStates));
    doroshellMarkCalendar(&c, la, 2027, 1);
    expect(tip(c, QDate(2026,12,25)) == "Christmas Day", "adjacent-month holiday marked");
    // Qt shows the format tooltip in the calendar view.
    c.setCurrentPage(2026, 11);
    doroshellMarkCalendar(&c, la, 2026, 11);
    auto *view = c.findChild<QTableView*>();
    bool shown = false;
    for (int r = 0; r < view->model()->rowCount(); ++r)
        for (int col = 0; col < view->model()->columnCount(); ++col)
            shown |= view->model()->index(r, col).data(Qt::ToolTipRole).toString() == "Thanksgiving Day";
    expect(shown, "tooltip exposed by calendar view model");
    std::cout << (failures ? "FAILED" : "OK") << "\n";
    return failures ? 1 : 0;
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True, help='patched lxqtworldclock.cpp')
    args = parser.parse_args()
    data = args.source.read_text()
    start = data.index('// shortcut: US federal holidays')
    helpers = data[start:data.index('LXQtWorldClock::LXQtWorldClock(', start)]
    if 'doroshellMarkCalendar(calendarWidget, timeZone' not in data or 'currentPageChanged' not in data:
        raise SystemExit('calendar popup does not call doroshellMarkCalendar')
    with tempfile.TemporaryDirectory(prefix='doro-calendar-marks-') as temporary:
        root = Path(temporary)
        (root / 'marks.inc').write_text(helpers)
        (root / 'test.cpp').write_text(TEST)
        flags = shlex.split(subprocess.check_output(['pkg-config', '--cflags', '--libs', 'Qt6Widgets'], text=True))
        exe = root / 'marks'
        subprocess.run(['c++', '-std=c++17', '-fPIC', str(root / 'test.cpp'), '-I' + str(root), '-o', str(exe), *flags], check=True, timeout=120)
        home = root / 'home'; home.mkdir(); runtime = root / 'runtime'; runtime.mkdir(mode=0o700)
        env = dict(os.environ, HOME=str(home), XDG_CONFIG_HOME=str(home / 'config'), XDG_RUNTIME_DIR=str(runtime),
                   QT_QPA_PLATFORM='offscreen', LANG='en_US.UTF-8', LC_ALL='en_US.UTF-8',
                   DBUS_SESSION_BUS_ADDRESS='unix:path=' + str(root / 'absent-bus'))
        for key in ['DISPLAY', 'WAYLAND_DISPLAY', 'TZ']:
            env.pop(key, None)
        raise SystemExit(subprocess.run([str(exe)], env=env, timeout=60).returncode)


if __name__ == '__main__':
    main()
