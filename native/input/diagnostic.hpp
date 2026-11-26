#pragma once
#include "preferences.hpp"
namespace input {
struct Directive {
    QString key;
    QStringList values;
};
struct Configuration {
    QList<QList<Directive>> rules;
    QSet<QString> issues;
    void parse(const QString& text);
    QString describe(const Device& device, bool runtimeCapability) const;
    static Configuration read(const QString& mainFile = "/etc/X11/xorg.conf",
                              const QStringList& directories = {"/etc/X11/xorg.conf.d",
                                                                "/usr/share/X11/xorg.conf.d"});
};
} // namespace input
