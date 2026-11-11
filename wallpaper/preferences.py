"""Add native Background controls after the optional Advanced display patch."""
from pathlib import Path
import shutil


def prepare(source):
    target = Path(source)/'pcmanfm'
    path = target/'desktoppreferencesdialog.cpp'
    text = path.read_text()
    edits = {
        '#include "desktoppreferencesdialog.h"': '#include "desktoppreferencesdialog.h"\n#include "dorowallpapercontrols.h"\n#include <QScrollArea>\n#include <QScreen>',
        '  ui.setupUi(this);': '''  ui.setupUi(this);
  wallpaperControls_ = new DoroWallpaperControls(this);
  ui.verticalLayout_3->insertWidget(2, wallpaperControls_);
  auto backgroundContent = new QWidget;
  backgroundContent->setLayout(ui.verticalLayout_3);
  auto backgroundScroll = new QScrollArea(ui.bgPage);
  backgroundScroll->setWidgetResizable(true);
  backgroundScroll->setWidget(backgroundContent);
  auto backgroundLayout = new QVBoxLayout(ui.bgPage);
  backgroundLayout->setContentsMargins(0, 0, 0, 0);
  backgroundLayout->addWidget(backgroundScroll);
  connect(this, &QDialog::rejected, wallpaperControls_, &DoroWallpaperControls::stopPreview);''',
        '  resize(sizeHint()); // show it compact': '  resize(sizeHint().expandedTo(QSize(545, 700)).boundedTo(screen()->availableGeometry().size() - QSize(40, 60)));',
        '  applySettings();': '  if(!wallpaperControls_->apply()) return;\n  applySettings();',
    }
    for old, new in edits.items():
        expected = 2 if old == '  applySettings();' else 1
        if text.count(old) != expected:
            raise ValueError('Unexpected native Preferences source: '+old)
        text = text.replace(old, new)
    # Refuse a wallpaper conflict before beginning an independent display change.
    text = text.replace('  displayControls_->submitFromDialog();\n  if(!wallpaperControls_->apply()) return;',
                        '  if(!wallpaperControls_->apply()) return;\n  displayControls_->submitFromDialog();')
    path.write_text(text)
    path = target/'desktoppreferencesdialog.h'
    text = path.read_text().replace('namespace PCManFM {', 'class DoroWallpaperControls;\n\nnamespace PCManFM {', 1)
    text = text.replace('  Ui::DesktopPreferencesDialog ui;', '  DoroWallpaperControls* wallpaperControls_;\n  Ui::DesktopPreferencesDialog ui;', 1)
    path.write_text(text)
    shutil.copy2(Path(__file__).with_name('dorowallpapercontrols.h'), target/'dorowallpapercontrols.h')
