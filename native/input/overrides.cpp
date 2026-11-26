#include <QtWidgets>
#include "diagnostic.hpp"
#include "xinput.hpp"
#include <gio/gdesktopappinfo.h>
using namespace input;
class Overrides : public QWidget {
  public:
    Overrides()
        : store(QDir::homePath(), QCoreApplication::applicationDirPath() + "/doroshell-input-preferences"),
          native(g_desktop_app_info_new("lxqt-config-input.desktop"), g_object_unref) {
        setWindowTitle("Mouse and Touchpad");
        resize(440, 450);
        auto layout = new QVBoxLayout(this);
        auto nativeButton = new QPushButton("Open Mouse and Touchpad settings…");
        nativeButton->setEnabled(bool(native));
        layout->addWidget(nativeButton);
        connect(nativeButton, &QPushButton::clicked, this, [this] {
            GError* error = nullptr;
            if (!g_app_info_launch(G_APP_INFO(native.get()), nullptr, nullptr, &error)) {
                status->setText(QString::fromUtf8(error->message));
                g_error_free(error);
            }
        });
        layout->addWidget(new QLabel("Per-device overrides"));
        devices->setAccessibleName("Input device");
        layout->addWidget(devices);
        layout->addWidget(enabled);
        layout->addWidget(status);
        layout->addWidget(evidence);
        for (auto text : {status, evidence}) {
            text->setWordWrap(true);
            text->setTextFormat(Qt::PlainText);
        }
        evidence->setAccessibleName("Read-only input capability evidence");
        evidence->hide();
        auto refresh = new QPushButton("Refresh devices");
        layout->addWidget(refresh);
        layout->addWidget(apply);
        auto restore = new QPushButton("Stop managing and restore");
        layout->addWidget(restore);
        layout->addStretch();
        connect(refresh, &QPushButton::clicked, this, [this] { inspect(); });
        connect(apply, &QPushButton::clicked, this, [this] { save(false); });
        connect(restore, &QPushButton::clicked, this, [this] { save(true); });
        connect(devices, &QComboBox::currentIndexChanged, this, [this] { selectDevice(); });
        apply->setEnabled(false);
        enabled->setEnabled(false);
    }

  private:
    Preferences store;
    std::unique_ptr<GDesktopAppInfo, decltype(&g_object_unref)> native;
    Saved snapshot;
    QList<Device> inputs;
    Configuration configuration;
    QComboBox* devices = new QComboBox;
    QCheckBox* enabled = new QCheckBox("Disable selected option");
    QLabel* status = new QLabel("Choose Refresh to inspect devices.");
    QLabel* evidence = new QLabel;
    QPushButton* apply = new QPushButton("Save and apply");
    void inspect() {
        try {
            snapshot = store.read();
            XInput x;
            inputs = x.devices();
            configuration = Configuration::read();
            {
                QSignalBlocker block(devices);
                devices->clear();
                for (const auto& d : inputs)
                    devices->addItem(d.name + " — " + d.kind);
            }
            selectDevice();
            if (inputs.isEmpty())
                status->setText("No identified input devices available.");
        } catch (const std::exception& e) {
            apply->setEnabled(false);
            enabled->setEnabled(false);
            evidence->hide();
            status->setText(QString::fromUtf8(e.what()));
        }
    }
    void selectDevice() {
        auto pos = devices->currentIndex();
        if (pos < 0 || pos >= inputs.size()) {
            enabled->setEnabled(false);
            apply->setEnabled(false);
            evidence->hide();
            return;
        }
        auto d = inputs[pos];
        auto cap = capability(d);
        auto rule = snapshot.data["rules"].toObject()[d.key].toObject();
        enabled->setEnabled(bool(cap));
        apply->setEnabled(bool(cap));
        enabled->setChecked(rule["enabled"].toBool());
        enabled->setText(d.kind == "touchpad" ? "Disable touchpad" : "Disable acceleration");
        QString observed = "not exposed";
        if (cap) {
            auto current = d.get(cap->property)["values"].toArray();
            if (current != cap->values)
                observed = "enabled / other profile";
            else if (d.kind == "touchpad")
                observed = "touchpad disabled";
            else if (cap->property == libinputProp)
                observed = "libinput flat profile (no acceleration)";
            else
                observed = "profile -1 (no velocity-dependent acceleration)";
        }
        status->setText(QString("User preference: %1. Observed property: %2. Driver properties: %3.")
                            .arg(rule["enabled"].toBool() ? "disable" : "unmanaged", observed, d.driver));
        evidence->setVisible(d.kind == "mouse");
        if (d.kind == "mouse")
            evidence->setText(configuration.describe(d, bool(cap)));
    }
    void save(bool stop) {
        try {
            Edit edit;
            if (stop) {
                edit.stop = true;
                edit.revision = digest(store.read().raw);
            } else {
                int pos = devices->currentIndex();
                if (pos < 0 || pos >= inputs.size())
                    return;
                auto d = inputs[pos];
                auto cap = capability(d);
                if (!cap)
                    return;
                edit.key = d.key;
                edit.rule = {{"name", d.name}, {"enabled", enabled->isChecked()}, {"action", cap->action}};
                edit.revision = digest(snapshot.raw);
            }
            XInput backend;
            auto messages = store.run(backend, edit);
            if (Preferences::needed(store.read().data))
                store.startWatcher();
            inspect();
            status->setText(messages.join('\n'));
        } catch (const std::exception& e) {
            status->setText(QString::fromUtf8(e.what()));
        }
    }
};
int main(int argc, char** argv) {
    QApplication app(argc, argv);
    Overrides page;
    page.show();
    return app.exec();
}
