#include "chooser.hpp"
#include <QtWidgets>
#include <gio/gdesktopappinfo.h>
extern "C" {
#include <nma-wifi-dialog.h>
}
#include <gdk/gdkx.h>
#undef None
#undef Status
#undef Bool
#include <functional>

using namespace net;
struct Target {
    std::shared_ptr<NMDevice> device;
    std::shared_ptr<NMAccessPoint> ap;
    bool operator==(const Target&) const = default;
    NMActiveConnection* active() const { return nm_device_get_active_connection(device.get()); }
    bool selected() const {
        return active() &&
               (!ap || nm_device_wifi_get_active_access_point(NM_DEVICE_WIFI(device.get())) == ap.get());
    }
    bool carrier() const {
        return NM_IS_DEVICE_ETHERNET(device.get()) &&
               nm_device_ethernet_get_carrier(NM_DEVICE_ETHERNET(device.get()));
    }
    QVector<NMRemoteConnection*> saved() const { return profiles(device.get(), ap.get()); }
};
static QString id(NMRemoteConnection* profile) {
    return QString::fromUtf8(nm_connection_get_id(NM_CONNECTION(profile)));
}
static QString uuid(NMRemoteConnection* profile) {
    return QString::fromUtf8(nm_connection_get_uuid(NM_CONNECTION(profile)));
}
static bool personal(const QString& key) { return key == "sae" || key == "wpa-psk"; }
static NMRemoteConnection* newest(const QVector<NMRemoteConnection*>& matches) {
    auto stamp = [](auto item) {
        return nm_setting_connection_get_timestamp(
            nm_connection_get_setting_connection(NM_CONNECTION(item)));
    };
    return matches.isEmpty() ? nullptr
                             : *std::max_element(matches.begin(), matches.end(),
                                                 [&](auto a, auto b) { return stamp(a) < stamp(b); });
}

void styleChooser() {
    QString name = QSettings(QDir::home().filePath(".config/doroshell/theme.conf"), QSettings::IniFormat)
                       .value("Theme/name", "windows")
                       .toString();
    struct Colors {
        QString base, window, ink, edge, selection;
    };
    const QMap<QString, Colors> palettes{
        {"windows", {"#fff5fb", "#f4dce9", "#351329", "#b9799e", "#edafd2"}},
        {"polar", {"#f4fbff", "#dceef9", "#14324a", "#7aa7c5", "#a8d5f4"}},
        {"heretic", {"#222124", "#302c30", "#f8eeee", "#a65c68", "#70323d"}},
        {"spring", {"#fffdf0", "#e6edd0", "#243b23", "#849b64", "#c0d89c"}}};
    auto p = palettes.value(name, palettes["windows"]);
    qApp->setStyleSheet(
        QStringLiteral(
            "QWidget {color:%3;} QWidget#chooser,QDialog,QMessageBox "
            "{background:qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 %1,stop:1 %2);}"
            "QGroupBox {font-weight:bold;border:1px solid "
            "%4;border-radius:6px;margin-top:0.65em;padding-top:0.55em;}"
            "QGroupBox::title {subcontrol-origin:margin;left:8px;} QListWidget,QLineEdit,QMenu "
            "{background:%1;border:1px solid %4;}"
            "QListWidget::item {padding:5px;} QListWidget::item:selected,QMenu::item:selected "
            "{background:%5;color:%3;}"
            "QMenu::item {padding:4px 18px;} QPushButton {padding:4px 9px;border:1px solid "
            "%4;border-radius:4px;"
            "background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 %1,stop:1 %2);}"
            "QPushButton#primary {font-weight:bold;background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 "
            "%1,stop:1 %5);}"
            "QPushButton:focus,QLineEdit:focus {border:2px solid %4;} QPushButton:disabled "
            "{color:palette(disabled,text);}"
            "QPushButton#link {text-decoration:underline;border:0;background:transparent;}")
            .arg(p.base, p.window, p.ink, p.edge, p.selection));
}
static QIcon bars(int strength) {
    QPixmap icon(32, 24);
    icon.fill(Qt::transparent);
    QPainter paint(&icon);
    for (int i = 0; i < 4; ++i) {
        int h = 5 + i * 5;
        paint.fillRect(2 + i * 7, 23 - h, 5, h, strength > i * 25 ? QColor("#258321") : QColor("#a49ba0"));
    }
    return QIcon(icon);
}
static QLabel* plainLabel(const QString& text) {
    auto label = new QLabel(text);
    label->setTextFormat(Qt::PlainText);
    label->setWordWrap(true);
    return label;
}
class NetworkList : public QListWidget {
  public:
    std::function<void(QListWidgetItem*, QPoint)> openMenu;

  protected:
    void contextMenuEvent(QContextMenuEvent* event) override {
        const bool keyboard = event->reason() == QContextMenuEvent::Keyboard;
        auto item = keyboard ? currentItem() : itemAt(event->pos());
        if (!item || !(item->flags() & Qt::ItemIsEnabled) || !openMenu)
            return;
        setCurrentItem(item);
        openMenu(item, keyboard ? viewport()->mapToGlobal(visualItemRect(item).bottomLeft())
                                : event->globalPos());
        event->accept();
    }
};
static NetworkList* listBox() {
    auto list = new NetworkList;
    list->setSelectionMode(QAbstractItemView::SingleSelection);
    list->setIconSize({32, 24});
    return list;
}

class Chooser : public QWidget {
    Q_OBJECT
    Q_CLASSINFO("D-Bus Interface", "org.doroshell.NetworkChooser")
  public:
    explicit Chooser(std::shared_ptr<NMClient> nm) : client(std::move(nm)) {
        setObjectName("chooser");
        rows->setObjectName("wireless");
        setWindowTitle("Wi-Fi & Network");
        setWindowIcon(QIcon::fromTheme("network-workgroup"));
        resize(455, 450);
        auto layout = new QVBoxLayout(this);
        auto wiredGroup = new QGroupBox("Wired network");
        (new QVBoxLayout(wiredGroup))->addWidget(wires);
        layout->addWidget(wiredGroup);
        wires->setMaximumHeight(100);
        auto tools = new QHBoxLayout;
        tools->addWidget(radio);
        tools->addStretch();
        tools->addWidget(scan);
        layout->addLayout(tools);
        auto group = new QGroupBox("Available Wi-Fi");
        (new QVBoxLayout(group))->addWidget(rows);
        layout->addWidget(group, 1);
        auto actions = new QHBoxLayout;
        change->setObjectName("link");
        actions->addWidget(change);
        actions->addLayout(hotspots);
        actions->addStretch();
        joinButton->setObjectName("primary");
        actions->addWidget(joinButton);
        layout->addLayout(actions);
        layout->addWidget(feedback);
        auto footer = new QHBoxLayout;
        auto advanced = new QPushButton("Advanced settings…");
        advanced->setObjectName("link");
        hidden->setObjectName("link");
        footer->addWidget(hidden);
        footer->addStretch();
        footer->addWidget(advanced);
        layout->addLayout(footer);
        connect(advanced, &QPushButton::clicked, this, [this] { editAdvanced(); });
        connect(hidden, &QPushButton::clicked, this, [this] { nativeDialog({}, {}); });
        connect(scan, &QPushButton::clicked, this, [this] {
            for (auto dev : devices())
                if (NM_IS_DEVICE_WIFI(dev) && nm_device_get_managed(dev))
                    nm_device_wifi_request_scan_async(NM_DEVICE_WIFI(dev), nullptr, complete,
                                                      operation([](auto obj, auto result, auto err) {
                                                          nm_device_wifi_request_scan_finish(
                                                              NM_DEVICE_WIFI(obj), result, err);
                                                      }));
        });
        connect(radio, &QCheckBox::clicked, this, [this](bool checked) {
            nm_client_dbus_set_property(client.get(), NM_DBUS_PATH, NM_DBUS_INTERFACE, "WirelessEnabled",
                                        g_variant_new_boolean(checked), 5000, nullptr, complete,
                                        operation([](auto obj, auto result, auto err) {
                                            nm_client_dbus_set_property_finish(NM_CLIENT(obj), result, err);
                                        }));
        });
        connect(rows, &QListWidget::currentRowChanged, this, [this] { selected(); });
        connect(change, &QPushButton::clicked, this, [this] {
            auto t = target(rows, rows->currentItem());
            if (t.device)
                if (auto saved = newest(t.saved()))
                    profileAction(t, retain(saved), false, nm_remote_connection_get_version_id(saved));
        });
        connect(joinButton, &QPushButton::clicked, this,
                [this] { defaultAction(target(rows, rows->currentItem())); });
        for (auto list : {rows, wires}) {
            connect(list, &QListWidget::itemActivated, this,
                    [this, list](auto item) { defaultAction(target(list, item)); });
            list->openMenu = [this, list](auto item, QPoint pos) { menu(target(list, item), pos); };
        }
        for (auto prop :
             {"notify::devices", "notify::nm-running", "notify::wireless-enabled",
              "notify::wireless-hardware-enabled", "notify::active-connections", "notify::connections"})
            g_signal_connect(client.get(), prop, G_CALLBACK(notify), this);
        refresh();
    }
    ~Chooser() override {
        g_signal_handlers_disconnect_by_data(client.get(), this);
        for (const auto& device : watched)
            g_signal_handlers_disconnect_by_data(device.get(), this);
        for (const auto& conn : connecting)
            if (conn)
                g_signal_handlers_disconnect_by_data(conn.get(), this);
    }
  public Q_SLOTS:
    Q_SCRIPTABLE void Present() {
        showNormal();
        raise();
        activateWindow();
    }

  private:
    std::shared_ptr<NMClient> client;
    QVector<std::shared_ptr<NMDevice>> watched;
    QHash<NMDevice*, std::shared_ptr<NMActiveConnection>> connecting;
    QVector<Target> wifiItems, wireItems;
    NetworkList* rows = listBox();
    NetworkList* wires = listBox();
    QCheckBox* radio = new QCheckBox("Wi-Fi on");
    QPushButton* scan = new QPushButton("Rescan");
    QPushButton* change = new QPushButton("Change password…");
    QPushButton* joinButton = new QPushButton("Connect");
    QPushButton* hidden = new QPushButton("Hidden network…");
    QLabel* feedback = plainLabel({});
    QVBoxLayout* hotspots = new QVBoxLayout;
    bool pending = false;

    using Finish = std::function<void(GObject*, GAsyncResult*, GError**)>;
    struct Request {
        QPointer<Chooser> window;
        Finish finish;
    };
    Request* operation(Finish f) { return new Request{this, std::move(f)}; }
    static void complete(GObject* obj, GAsyncResult* result, gpointer data) {
        std::unique_ptr<Request> request(static_cast<Request*>(data));
        if (!request->window)
            return;
        GError* error = nullptr;
        request->finish(obj, result, &error);
        if (error) {
            request->window->feedback->setText(QString::fromUtf8(error->message));
            g_error_free(error);
        }
        request->window->schedule();
    }
    static void notify(GObject*, GParamSpec*, gpointer data) { static_cast<Chooser*>(data)->schedule(); }
    void schedule() {
        if (pending)
            return;
        pending = true;
        QTimer::singleShot(0, this, [this] {
            pending = false;
            refresh();
        });
    }
    auto devices() const -> QVector<NMDevice*> {
        return objects<NMDevice>(nm_client_get_devices(client.get()));
    }
    Target target(QListWidget* list, QListWidgetItem* item) const {
        auto index = list->row(item);
        return (list == rows ? wifiItems : wireItems).value(index);
    }
    bool present(const Target& t) const {
        auto d = t.device.get();
        if (!d || !devices().contains(d) || !nm_device_get_managed(d) || connecting.contains(d))
            return false;
        return !t.ap || (nm_client_wireless_get_enabled(client.get()) &&
                         nm_client_wireless_hardware_get_enabled(client.get()) &&
                         objects<NMAccessPoint>(nm_device_wifi_get_access_points(NM_DEVICE_WIFI(d)))
                             .contains(t.ap.get()));
    }
    void stale() {
        feedback->setText("The network changed. Open its menu again.");
        schedule();
    }
    void selected() {
        auto t = target(rows, rows->currentItem());
        joinButton->setEnabled(t.device && present(t));
        joinButton->setText(t.device && t.selected() ? "Disconnect" : "Connect");
        change->setVisible(t.ap && personal(security(t.ap.get())) && !t.saved().isEmpty());
        change->setEnabled(t.device && present(t));
    }
    void fillDevices(const QVector<NMDevice*>& current) {
        for (auto it = watched.begin(); it != watched.end();) {
            if (current.contains(it->get())) {
                ++it;
                continue;
            }
            g_signal_handlers_disconnect_by_data(it->get(), this);
            it = watched.erase(it);
        }
        for (auto device : current) {
            if (std::any_of(watched.begin(), watched.end(),
                            [device](const auto& ptr) { return ptr.get() == device; }))
                continue;
            if (!NM_IS_DEVICE_WIFI(device) && !NM_IS_DEVICE_ETHERNET(device))
                continue;
            watched.push_back(retain(device));
            for (auto prop : {"notify::managed", "notify::state", "notify::active-connection",
                              "notify::available-connections"})
                g_signal_connect(device, prop, G_CALLBACK(notify), this);
            if (NM_IS_DEVICE_ETHERNET(device))
                g_signal_connect(device, "notify::carrier", G_CALLBACK(notify), this);
            else
                for (auto prop :
                     {"notify::access-points", "notify::active-access-point", "notify::last-scan"})
                    g_signal_connect(device, prop, G_CALLBACK(notify), this);
        }
    }
    void refresh() {
        checkActivations();
        auto previous = target(rows, rows->currentItem());
        auto wire = target(wires, wires->currentItem());
        QSignalBlocker blockRows(rows), blockRadio(radio);
        rows->clear();
        wires->clear();
        wifiItems.clear();
        wireItems.clear();
        while (auto item = hotspots->takeAt(0)) {
            item->widget()->deleteLater();
            delete item;
        }
        auto current = devices();
        fillDevices(current);
        auto enabled = nm_client_wireless_get_enabled(client.get());
        auto hardware = nm_client_wireless_hardware_get_enabled(client.get());
        int wifiCount =
            std::count_if(current.begin(), current.end(), [](auto d) { return NM_IS_DEVICE_WIFI(d); });
        int wireCount =
            std::count_if(current.begin(), current.end(), [](auto d) { return NM_IS_DEVICE_ETHERNET(d); });
        bool available = false;
        for (auto d : current) {
            Target dev{retain(d), {}};
            if (NM_IS_DEVICE_ETHERNET(d)) {
                auto name = wireCount > 1 ? QString("Ethernet · %1").arg(nm_device_get_iface(d))
                                          : QString("Ethernet");
                auto item = new QListWidgetItem(wires);
                auto content = new QWidget;
                auto hbox = new QHBoxLayout(content);
                hbox->setContentsMargins(5, 2, 5, 2);
                auto icon = new QLabel;
                icon->setPixmap(QIcon::fromTheme("video-display").pixmap(32, 32));
                hbox->addWidget(icon);
                hbox->addWidget(plainLabel(name + "\n" + stateLabel(d)), 1);
                item->setData(Qt::AccessibleTextRole, name + ", " + stateLabel(d));
                if (dev.active() || (dev.carrier() && nm_device_get_managed(d))) {
                    auto action = new QPushButton(dev.active() ? "Disconnect" : "Connect");
                    auto active = retain(dev.active());
                    action->setEnabled(present(dev));
                    hbox->addWidget(action);
                    connect(action, &QPushButton::clicked, this, [this, dev, active] {
                        if (dev.active() != active.get())
                            stale();
                        else
                            defaultAction(dev);
                    });
                }
                item->setSizeHint(content->sizeHint());
                wires->setItemWidget(item, content);
                wireItems.push_back(dev);
                if (wire == dev)
                    wires->setCurrentItem(item);
                if (dev.active())
                    item->setToolTip(
                        QString::fromUtf8(nm_active_connection_get_id(dev.active())).toHtmlEscaped());
                continue;
            }
            if (!NM_IS_DEVICE_WIFI(d) || !enabled || !hardware || !nm_device_get_managed(d))
                continue;
            available = true;
            auto wifi = NM_DEVICE_WIFI(d);
            for (auto ap : nearby(wifi)) {
                Target row{retain(d), retain(ap)};
                auto name = ssidName(nm_access_point_get_ssid(ap));
                auto strength = nm_access_point_get_strength(ap);
                auto key = security(ap);
                QStringList parts{name};
                if (wifiCount > 1)
                    parts << QString::fromUtf8(nm_device_get_iface(d));
                if (row.selected())
                    parts << stateLabel(d);
                else if (!row.saved().isEmpty())
                    parts << "Saved";
                parts << (key == "open" ? "Open" : key == "owe" ? "Enhanced open" : "🔒");
                auto item = new QListWidgetItem(bars(strength), parts.join("    "), rows);
                auto desc = parts.join(", ") + QString(", Signal %1%").arg(strength);
                item->setData(Qt::AccessibleTextRole, desc);
                item->setToolTip(desc.toHtmlEscaped());
                wifiItems.push_back(row);
                if (previous == row)
                    rows->setCurrentItem(item);
            }
            if (supportsHotspot(wifi)) {
                auto button = new QPushButton(
                    wifiCount > 1 ? QString("Create hotspot on %1…").arg(nm_device_get_iface(d))
                                  : "Create hotspot…");
                button->setObjectName("link");
                hotspots->addWidget(button);
                connect(button, &QPushButton::clicked, this, [this, dev] { hotspot(dev); });
            }
            if (dev.active() && !nm_device_wifi_get_active_access_point(wifi)) {
                auto button = new QPushButton(
                    QString("Disconnect %1").arg(nm_active_connection_get_id(dev.active())));
                hotspots->addWidget(button);
                auto active = retain(dev.active());
                connect(button, &QPushButton::clicked, this, [this, dev, active] {
                    if (present(dev) && dev.active() == active.get())
                        disconnectActive(active);
                    else
                        stale();
                });
            }
        }
        radio->setChecked(enabled);
        radio->setEnabled(wifiCount && hardware);
        scan->setEnabled(available);
        hidden->setEnabled(available);
        if (!wireCount)
            placeholder(wires, "No Ethernet adapter detected.");
        if (!rows->count()) {
            QString reason;
            if (!nm_client_get_nm_running(client.get()))
                reason = "NetworkManager is not running.";
            else if (!wifiCount)
                reason = "No Wi-Fi adapter detected.";
            else if (!hardware)
                reason = "Wi-Fi is blocked by hardware.";
            else if (!enabled)
                reason = "Wi-Fi is off.";
            else if (!available)
                reason = "Wi-Fi adapter is unmanaged.";
            else
                reason = "No networks found. Turn on your phone hotspot or rescan.";
            placeholder(rows, reason);
        }
        selected();
    }
    static void placeholder(QListWidget* list, const QString& text) {
        auto item = new QListWidgetItem(text, list);
        item->setFlags(Qt::NoItemFlags);
    }
    void disconnectActive(const std::shared_ptr<NMActiveConnection>& active) {
        if (!active)
            return;
        feedback->clear();
        nm_client_deactivate_connection_async(
            client.get(), active.get(), nullptr, complete, operation([](auto obj, auto result, auto err) {
                nm_client_deactivate_connection_finish(NM_CLIENT(obj), result, err);
            }));
    }
    void defaultAction(const Target& t) {
        if (!t.device)
            return;
        if (!present(t)) {
            stale();
            return;
        }
        if (t.selected())
            disconnectActive(retain(t.active()));
        else if (t.ap)
            join(t);
        else if (t.carrier())
            activate(t, nullptr, false);
    }
    void menu(const Target& t, const QPoint& pos) {
        if (!t.device)
            return;
        if (!present(t)) {
            stale();
            return;
        }
        QMenu popup(this);
        auto original = retain(t.active());
        bool active = t.selected();
        auto action = popup.addAction(active ? "Disconnect" : "Connect");
        action->setEnabled(active || t.ap || t.carrier());
        connect(action, &QAction::triggered, this, [this, t, original, active] {
            if (!present(t) || t.active() != original.get() || t.selected() != active) {
                stale();
                return;
            }
            defaultAction(t);
        });
        auto saved = t.saved();
        auto addProfileAction = [&](const QString& title, bool forget) {
            auto submenu = saved.size() > 1 ? popup.addMenu(title) : nullptr;
            for (auto raw : saved) {
                auto profile = retain(raw);
                auto version = nm_remote_connection_get_version_id(raw);
                auto label = id(raw);
                if (std::count_if(saved.begin(), saved.end(), [&](auto p) { return id(p) == label; }) > 1)
                    label += " · " + uuid(raw);
                auto item = submenu ? submenu->addAction(label.replace('&', "&&")) : popup.addAction(title);
                connect(item, &QAction::triggered, this, [this, t, profile, forget, version] {
                    profileAction(t, profile, forget, version);
                });
            }
        };
        if (!saved.isEmpty()) {
            if (t.ap && personal(security(t.ap.get())))
                addProfileAction("Change password…", false);
            addProfileAction("Forget saved network…", true);
        }
        popup.exec(pos);
    }
    void editAdvanced(const QString& profileId = {}) {
        if (!profileId.isEmpty()) {
            if (!QProcess::startDetached("/usr/bin/nm-connection-editor", {"--edit", profileId}))
                feedback->setText("Could not open the connection editor.");
            return;
        }
        auto entry = own(g_desktop_app_info_new("nm-connection-editor.desktop"));
        if (!entry) {
            feedback->setText("Install nm-connection-editor to manage saved networks.");
            return;
        }
        GError* error = nullptr;
        if (!g_app_info_launch(G_APP_INFO(entry.get()), nullptr, nullptr, &error)) {
            feedback->setText(QString::fromUtf8(error->message));
            g_error_free(error);
        }
    }
    bool askPassword(NMConnection* profile, const QString& key, bool changing = false) {
        QDialog dialog(this);
        dialog.setWindowTitle("Connect to Wi-Fi");
        auto layout = new QVBoxLayout(&dialog);
        auto heading = plainLabel(QString::fromUtf8(nm_connection_get_id(profile)));
        auto font = heading->font();
        font.setBold(true);
        heading->setFont(font);
        layout->addWidget(heading);
        layout->addWidget(
            plainLabel("Enter the Wi-Fi password from your router or phone’s hotspot settings."));
        auto field = new QLineEdit;
        field->setEchoMode(QLineEdit::Password);
        field->setAccessibleName("Wi-Fi password");
        layout->addWidget(field);
        auto show = new QCheckBox("Show password");
        layout->addWidget(show);
        connect(show, &QCheckBox::toggled, &dialog,
                [field](bool on) { field->setEchoMode(on ? QLineEdit::Normal : QLineEdit::Password); });
        auto buttons = new QDialogButtonBox(QDialogButtonBox::Cancel);
        auto ok =
            buttons->addButton(changing ? "Save and connect" : "Connect", QDialogButtonBox::AcceptRole);
        ok->setObjectName("primary");
        ok->setDefault(true);
        ok->setEnabled(false);
        layout->addWidget(buttons);
        field->setFocus();
        connect(field, &QLineEdit::textChanged, &dialog, [ok, key](const QString& text) {
            ok->setEnabled(!text.isEmpty() &&
                           (key == "sae" || nm_utils_wpa_psk_valid(text.toUtf8().constData())));
        });
        connect(buttons, &QDialogButtonBox::accepted, &dialog, &QDialog::accept);
        connect(buttons, &QDialogButtonBox::rejected, &dialog, &QDialog::reject);
        if (dialog.exec() != QDialog::Accepted)
            return false;
        g_object_set(nm_connection_get_setting_wireless_security(profile), "psk",
                     field->text().toUtf8().constData(), nullptr);
        field->clear();
        return true;
    }
    void profileAction(const Target& t, const std::shared_ptr<NMRemoteConnection>& saved, bool forget,
                       guint64 version) {
        auto identity = uuid(saved.get());
        auto current = [&] {
            return present(t) && t.saved().contains(saved.get()) &&
                   nm_client_get_connection_by_uuid(client.get(), identity.toUtf8().constData()) ==
                       saved.get() &&
                   nm_remote_connection_get_version_id(saved.get()) == version;
        };
        if (!current()) {
            stale();
            return;
        }
        if (forget) {
            auto active = retain(t.active());
            auto inUse = [&] {
                return t.active() && nm_active_connection_get_connection(t.active()) == saved.get();
            };
            bool wasActive = inUse();
            auto name = id(saved.get());
            auto matches = t.saved();
            if (std::count_if(matches.begin(), matches.end(), [&](auto p) { return id(p) == name; }) > 1)
                name += " · " + identity;
            auto text = QString("Remove the saved connection “%1” from NetworkManager?").arg(name);
            if (wasActive)
                text += " This connection is currently active.";
            QMessageBox confirm(QMessageBox::Question, "Forget saved network?", text, QMessageBox::Cancel,
                                this);
            confirm.setTextFormat(Qt::PlainText);
            auto accept = confirm.addButton("Forget", QMessageBox::DestructiveRole);
            confirm.setDefaultButton(QMessageBox::Cancel);
            confirm.exec();
            if (confirm.clickedButton() != accept)
                return;
            if (!current() || inUse() != wasActive || (wasActive && t.active() != active.get())) {
                stale();
                return;
            }
            nm_remote_connection_delete_async(
                saved.get(), nullptr, complete, operation([](auto obj, auto result, auto err) {
                    nm_remote_connection_delete_finish(NM_REMOTE_CONNECTION(obj), result, err);
                }));
            return;
        }
        if (!editableSecret(saved.get())) {
            editAdvanced(identity);
            return;
        }
        auto copy = own(nm_simple_connection_new_clone(NM_CONNECTION(saved.get())));
        auto setting = nm_connection_get_setting_wireless_security(copy.get());
        if (!setting)
            return;
        QString key = QString::fromUtf8(nm_setting_wireless_security_get_key_mgmt(setting));
        if (!personal(key) || !askPassword(copy.get(), key, true))
            return;
        if (!current()) {
            stale();
            return;
        }
        GVariantBuilder options;
        g_variant_builder_init(&options, G_VARIANT_TYPE_VARDICT);
        g_variant_builder_add(&options, "{sv}", "version-id", g_variant_new_uint64(version));
        connecting.insert(t.device.get(), {});
        schedule();
        nm_remote_connection_update2(
            saved.get(), nm_connection_to_dbus(copy.get(), NM_CONNECTION_SERIALIZE_ALL),
            NM_SETTINGS_UPDATE2_FLAG_NONE, g_variant_builder_end(&options), nullptr, complete,
            operation([this, t, saved](auto obj, auto result, auto err) {
                connecting.remove(t.device.get());
                auto response = nm_remote_connection_update2_finish(NM_REMOTE_CONNECTION(obj), result, err);
                if (!response)
                    return;
                g_variant_unref(response);
                if (!present(t) || !t.saved().contains(saved.get())) {
                    stale();
                    return;
                }
                activate(t, NM_CONNECTION(saved.get()), false);
            }));
    }
    void join(const Target& t) {
        if (auto profile = newest(t.saved())) {
            activate(t, NM_CONNECTION(profile), false);
            return;
        }
        auto key = security(t.ap.get());
        if (key == "unsupported") {
            feedback->setText("Unsupported wireless security. Open advanced settings for more options.");
            return;
        }
        auto profile = wifiProfile(nm_access_point_get_ssid(t.ap.get()), key);
        if (!profile) {
            feedback->setText("Could not create a personal Wi-Fi profile.");
            return;
        }
        if (personal(key)) {
            if (!askPassword(profile.get(), key))
                return;
        } else if (key != "open" && key != "owe") {
            nativeDialog(t, profile);
            return;
        }
        if (!present(t) || key != security(t.ap.get())) {
            stale();
            return;
        }
        activate(t, profile.get(), true);
    }
    void nativeDialog(const Target& t, const std::shared_ptr<NMConnection>& initial) {
        if (!gtk_init_check(nullptr, nullptr)) {
            feedback->setText("Could not open the Wi-Fi security dialog.");
            return;
        }
        GtkWidget* dialog =
            initial ? nma_wifi_dialog_new(client.get(), initial.get(), t.device.get(), t.ap.get(), false)
                    : nma_wifi_dialog_new_for_hidden(client.get());
        if (!dialog) {
            feedback->setText("Could not open the Wi-Fi security dialog.");
            return;
        }
        gtk_widget_realize(dialog);
        auto display = gtk_widget_get_display(dialog);
        if (QGuiApplication::platformName() == "xcb" && GDK_IS_X11_DISPLAY(display)) {
            auto parent = gdk_x11_window_foreign_new_for_display(display, winId());
            if (parent) {
                gdk_window_set_transient_for(gtk_widget_get_window(dialog), parent);
                g_object_unref(parent);
            }
        }
        setEnabled(false);
        if (gtk_dialog_run(GTK_DIALOG(dialog)) == GTK_RESPONSE_OK) {
            NMDevice* device = nullptr;
            NMAccessPoint* ap = nullptr;
            auto profile = own(nma_wifi_dialog_get_connection(NMA_WIFI_DIALOG(dialog), &device, &ap));
            Target chosen{retain(device), retain(ap)};
            if (initial && (!profile || !nm_connection_get_setting_wireless_security(profile.get())))
                feedback->setText("Select the security required by this network.");
            else if (!profile || !present(chosen) || (t.device && (chosen != t || !present(t))))
                stale();
            else
                activate(chosen, profile.get(), !NM_IS_REMOTE_CONNECTION(profile.get()));
        }
        gtk_widget_destroy(dialog);
        setEnabled(true);
    }
    void hotspot(const Target& t) {
        QDialog dialog(this);
        dialog.setWindowTitle("Create a Wi-Fi hotspot");
        auto layout = new QFormLayout(&dialog);
        layout->addRow(plainLabel("Starting a hotspot replaces the Wi-Fi connection on this adapter."));
        auto name = new QLineEdit("My hotspot");
        auto secret = new QLineEdit;
        const QString alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";
        QString initial;
        for (int i = 0; i < 16; ++i)
            initial += alphabet.at(QRandomGenerator::system()->bounded(64));
        secret->setText(initial);
        secret->setEchoMode(QLineEdit::Password);
        layout->addRow("Network name", name);
        layout->addRow("Password", secret);
        auto show = new QCheckBox("Show password");
        layout->addRow(show);
        connect(show, &QCheckBox::toggled, &dialog,
                [secret](bool on) { secret->setEchoMode(on ? QLineEdit::Normal : QLineEdit::Password); });
        auto buttons = new QDialogButtonBox(QDialogButtonBox::Cancel);
        auto start = buttons->addButton("Start hotspot", QDialogButtonBox::AcceptRole);
        auto valid = [=] { start->setEnabled(validHotspot(name->text(), secret->text())); };
        connect(name, &QLineEdit::textChanged, &dialog, valid);
        connect(secret, &QLineEdit::textChanged, &dialog, valid);
        layout->addRow(plainLabel(
            "Use a name of up to 32 bytes and a password of 8 to 63 printable ASCII characters."));
        layout->addRow(buttons);
        connect(buttons, &QDialogButtonBox::accepted, &dialog, &QDialog::accept);
        connect(buttons, &QDialogButtonBox::rejected, &dialog, &QDialog::reject);
        if (dialog.exec() != QDialog::Accepted)
            return;
        if (!present(t) || !nm_client_wireless_get_enabled(client.get()) ||
            !nm_client_wireless_hardware_get_enabled(client.get()) ||
            !supportsHotspot(NM_DEVICE_WIFI(t.device.get()))) {
            stale();
            return;
        }
        auto raw = name->text().toUtf8();
        auto bytes = g_bytes_new(raw.constData(), raw.size());
        auto profile = wifiProfile(bytes, "wpa-psk", true);
        g_bytes_unref(bytes);
        if (!profile) {
            feedback->setText("Could not create a personal hotspot profile.");
            return;
        }
        g_object_set(nm_connection_get_setting_wireless_security(profile.get()), "psk",
                     secret->text().toUtf8().constData(), nullptr);
        activate(t, profile.get(), true);
    }
    void activate(const Target& t, NMConnection* profile, bool create) {
        if (!present(t)) {
            stale();
            return;
        }
        if (NM_IS_DEVICE_WIFI(t.device.get()))
            wifiActivations.insert(t.device.get());
        connecting.insert(t.device.get(), {});
        feedback->setText("Connecting…");
        schedule();
        auto done = operation([this, t, create](auto obj, auto result, auto err) {
            auto active =
                own(create ? nm_client_add_and_activate_connection_finish(NM_CLIENT(obj), result, err)
                           : nm_client_activate_connection_finish(NM_CLIENT(obj), result, err));
            if (!active) {
                connecting.remove(t.device.get());
                wifiActivations.remove(t.device.get());
                return;
            }
            connecting.insert(t.device.get(), active);
            g_signal_connect(active.get(), "notify::state", G_CALLBACK(notify), this);
        });
        auto method =
            create ? nm_client_add_and_activate_connection_async : nm_client_activate_connection_async;
        method(client.get(), profile, t.device.get(),
               t.ap ? nm_object_get_path(NM_OBJECT(t.ap.get())) : nullptr, nullptr, complete, done);
    }
    void checkActivations() {
        for (auto it = connecting.begin(); it != connecting.end();) {
            if (!it.value()) {
                ++it;
                continue;
            }
            auto active = it.value().get();
            auto state = nm_active_connection_get_state(active);
            if (state == NM_ACTIVE_CONNECTION_STATE_ACTIVATED)
                feedback->clear();
            else if (state == NM_ACTIVE_CONNECTION_STATE_DEACTIVATED)
                feedback->setText(wifiActivations.contains(it.key())
                                      ? "Could not connect. Check the Wi-Fi password, then use Change "
                                        "password if it is saved. Rescan if the network disappeared."
                                      : "Could not connect. Check the Ethernet cable and try again.");
            else {
                ++it;
                continue;
            }
            g_signal_handlers_disconnect_by_data(active, this);
            wifiActivations.remove(it.key());
            it = connecting.erase(it);
        }
    }
    QSet<NMDevice*> wifiActivations;
};

std::unique_ptr<QWidget> createChooser(std::shared_ptr<NMClient> client) {
    return std::make_unique<Chooser>(std::move(client));
}
#include "chooser.moc"
