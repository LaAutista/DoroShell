#include "cursor.hpp"
#include <QCommandLineParser>
#include <QCoreApplication>
#include <QDir>
#include <QTextStream>

int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  app.setApplicationName("doroshell-cursor");
  QCommandLineParser p;
  p.setApplicationDescription("Generate and manage DoroShell animated loading "
                              "cursors. Default: preview.");
  p.addHelpOption();
  p.addOption(
      {{"image", "gif"}, "Use a local animated GIF, APNG or WebP.", "file"});
  p.addOption(
      {"asset", "Choose the included apng or gif animation.", "type", "apng"});
  p.addOption({"home", "Target user home.", "directory", QDir::homePath()});
  p.addOption({"base", "Inherited Xcursor theme directory.", "directory",
               "/usr/share/icons/breeze_cursors"});
  p.addOption({"pink-pointer", "Tint the normal pointer pink."});
  p.addOption({"apply", "Apply to the target profile."});
  p.addOption({"rollback", "Restore original cursor files and settings."});
  p.addOption({"plan", "Preview cursor changes."});
  p.process(app);
  try {
    auto type = p.value("asset");
    if (!p.positionalArguments().isEmpty() ||
        (int(p.isSet("apply")) + p.isSet("rollback") + p.isSet("plan") > 1) ||
        (p.isSet("asset") && p.isSet("image")) ||
        (type != "gif" && type != "apng"))
      cursor::fail("Incompatible cursor options.");
    QString image =
        p.isSet("image")
            ? QFileInfo(p.value("image")).absoluteFilePath()
            : ":/doro/cursors/" + QString(type == "gif"
                                              ? "spin-doro.gif"
                                              : "spin-doro-transparent.apng");
    if (!p.isSet("image") && !QFileInfo::exists(image))
      image.clear(); // A source distribution may omit the optional artwork.
    auto result = cursor::change(QDir::cleanPath(p.value("home")), image,
                                 p.value("base"), p.isSet("pink-pointer"),
                                 p.isSet("apply"), p.isSet("rollback"));
    QTextStream(stdout) << result.join('\n') << '\n'
                        << (p.isSet("apply") || p.isSet("rollback")
                                ? "Settings saved. Restart affected "
                                  "applications or use your next login."
                                : "Plan only.")
                        << '\n';
    return 0;
  } catch (const std::exception &e) {
    QTextStream(stderr) << e.what() << '\n';
    return 1;
  }
}
