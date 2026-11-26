#include "hub.hpp"
#include <QApplication>
#include <QCommandLineParser>
int main(int argc, char **argv) {
  QApplication app(argc, argv);
  app.setApplicationName("DoroShell Settings");
  QCommandLineParser parser;
  parser.addHelpOption();
  parser.process(app);
  if (!parser.positionalArguments().isEmpty())
    return 2;
  SettingsHub hub;
  hub.show();
  return app.exec();
}
