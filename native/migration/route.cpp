// SPDX-License-Identifier: GPL-2.0-or-later
// RC2 shortcuts address fixed launcher names. The installer appends an argv
// array to this ELF so exec reaches the selected bundle in its original path.
#include "selection.hpp"
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QVector>
#include <cstdio>
#include <unistd.h>
int main(int argc, char **argv) {
  QFile self("/proc/self/exe");
  if (!self.open(QIODevice::ReadOnly) || !self.seek(self.size() - 8))
    return 126;
  bool ok = false;
  auto length = self.read(8).toUInt(&ok, 16);
  if (!ok || !length || length > 65536 || !self.seek(self.size() - 8 - length))
    return 126;
  auto cmd = QJsonDocument::fromJson(self.read(length)).array();
  if (cmd.isEmpty() || !cmd.first().toString().startsWith('/'))
    return 126;
  QList<QByteArray> args;
  QStringList fixed;
  for (const auto &v : cmd)
    fixed << v.toString();
  for (const auto &v : migration::select(fixed))
    args << QFile::encodeName(v);
  QVector<char *> pointers;
  for (auto &arg : args)
    pointers << arg.data();
  for (int i = 1; i < argc; ++i)
    pointers << argv[i];
  pointers << nullptr;
  execv(pointers[0], pointers.data());
  perror("DoroShell launcher");
  return 126;
}
