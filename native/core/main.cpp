// SPDX-License-Identifier: GPL-2.0-or-later
#include "../setup/files.hpp"
#include <QCommandLineParser>
#include <QCoreApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QLockFile>
#include <QProcess>
#include <QTextStream>

namespace {
using namespace doro_files;
const QString stateDir = ".local/state/doroshell-native/";
const QString record = stateDir + "core.json";
const QString rc = ".config/openbox/rc.xml";
struct Step {
  QString name, receipt, program;
  QStringList options;
};
const QList<Step> legacySteps{
    {"openbox-default", rc, {}, {}},
    {"update-command",
     ".local/bin/doroshell-update",
     "doroshell-maintenance",
     {}},
    {"remove-command",
     ".local/bin/doroshell-remove",
     "doroshell-maintenance",
     {}},
    {"launchers", stateDir + "launchers.json", "doroshell-setup", {}},
    {"theme", ".local/state/doroshell/theme.json", "doroshell-theme", {}},
    {"cursor",
     ".local/state/lxqt-comfort/cursor-install.json",
     "doroshell-cursor",
     {}},
    {"session", stateDir + "session.json", "doroshell-setup", {"--session"}},
    {"panel", stateDir + "panel.json", "doroshell-panel-profile", {}},
    {"desktop", stateDir + "desktop.json", "doroshell-setup", {"--desktop"}},
    {"input", stateDir + "input.json", "doroshell-setup", {"--input"}}};
// Receipts store the actual order in which stages were first acquired.
// Additions append after existing stages so reverse-order removal restores
// overlapping rc.xml and globalkeyshortcuts.conf snapshots correctly.
const QStringList names{"core",         "none",           "menu",
                        "native-panel", "theme",          "cursor",
                        "snapping",     "screenshots",    "maintenance",
                        "wallpaper",    "display",        "input-settings",
                        "clipboard",    "start-shortcut", "single-desktop",
                        "taskbar",      "taskbar-size",   "taskbar-drag"};
const QStringList groups{
    "menu-entries", "clipboard-entry", "screenshot-entry", "recent",
    "snap",         "print-key",       "start-key"};
QList<Step> catalog() {
  auto result = legacySteps;
  for (const auto &name : groups)
    result.append({name,
                   stateDir + name + ".json",
                   "doroshell-setup",
                   {"--scope", name}});
  return result;
}
QStringList arrayStrings(const QJsonValue &v) {
  if (!v.isArray())
    fail("Invalid saved selection");
  QStringList out;
  for (const auto &entry : v.toArray()) {
    if (!entry.isString() || entry.toString().isEmpty() ||
        out.contains(entry.toString()))
      fail("Malformed or duplicate saved selection");
    out << entry.toString();
  }
  return out;
}
const QStringList fullSelection{
    "menu",           "native-panel",      "theme",
    "cursor",         "snapping",          "screenshots",
    "maintenance",    "wallpaper",         "display",
    "input-settings", "default-start-key", "default-clipboard-entry"};
QStringList wantedSteps(QStringList mods) {
  for (const auto &m : mods)
    if (!names.contains(m) && !fullSelection.contains(m))
      fail("Unknown core module: " + m);
  if (mods.contains("core"))
    mods << fullSelection;
  if (mods.contains("clipboard") || mods.contains("taskbar") ||
      mods.contains("taskbar-size") || mods.contains("taskbar-drag"))
    mods << "native-panel";
  if (mods.contains("native-panel") || mods.contains("input-settings") ||
      mods.contains("start-shortcut"))
    mods << "menu";
  if (mods.contains("display"))
    mods << "wallpaper";
  QStringList out;
  if (mods.contains("theme") || mods.contains("snapping") ||
      mods.contains("single-desktop"))
    out << "openbox-default";
  if (mods.contains("maintenance"))
    out << "update-command" << "remove-command";
  if (mods.contains("menu"))
    out << "menu-entries" << "recent";
  if (mods.contains("default-clipboard-entry") || mods.contains("clipboard"))
    out << "clipboard-entry";
  if (mods.contains("screenshots"))
    out << "screenshot-entry";
  if (mods.contains("theme"))
    out << "theme";
  if (mods.contains("cursor"))
    out << "cursor";
  if (mods.contains("snapping"))
    out << "snap";
  if (mods.contains("default-start-key"))
    out << "start-key";
  if (mods.contains("screenshots"))
    out << "print-key";
  if (mods.contains("native-panel"))
    out << "panel";
  if (mods.contains("wallpaper"))
    out << "desktop";
  if (mods.contains("input-settings"))
    out << "input";
  return out;
}
QString legacyGroup(const QString &stage) {
  if (QStringList{"menu-entries", "clipboard-entry", "screenshot-entry"}
          .contains(stage))
    return "launchers";
  if (QStringList{"snap", "recent", "print-key", "start-key"}.contains(stage))
    return "session";
  return {};
}
const QStringList modes{"plan",    "apply",   "remove",
                        "recover", "refresh", "packages"};
const QStringList presets{"windows", "polar", "heretic", "spring"};

QJsonObject stockOpenbox() {
  auto roots = qEnvironmentVariable("XDG_CONFIG_DIRS", "/etc/xdg")
                   .split(':', Qt::SkipEmptyParts);
  if (roots.isEmpty())
    roots.append("/etc/xdg");
  for (const auto &root : roots) {
    if (!QDir::isAbsolutePath(root))
      fail("Relative system config directory");
    QFile f(root + "/openbox/rc.xml");
    if (!f.exists())
      continue;
    if (!QFileInfo(f).isFile() || !f.open(QIODevice::ReadOnly))
      fail("Cannot read Openbox defaults");
    auto data = f.read(1024 * 1024 + 1);
    if (f.error() != QFileDevice::NoError || data.isEmpty() ||
        data.size() > 1024 * 1024)
      fail("Invalid Openbox defaults");
    return {{"exists", true},
            {"mode", 0600},
            {"data", QString::fromLatin1(data.toBase64())}};
  }
  fail("Install Openbox first. Its default rc.xml is missing.");
}

QByteArray child(const QString &home, const QString &program,
                 const QStringList &args, bool capture = false) {
  QProcess proc;
  auto env = QProcessEnvironment::systemEnvironment();
  env.insert("HOME", home);
  // Isolate explicit temp homes. Installed profiles currently use standard XDG
  // paths.
  env.insert("XDG_CONFIG_HOME", home + "/.config");
  env.insert("XDG_STATE_HOME", home + "/.local/state");
  env.insert("XDG_DATA_HOME", home + "/.local/share");
  env.insert("XDG_CACHE_HOME", home + "/.cache");
  proc.setProcessEnvironment(env);
  proc.setProcessChannelMode(capture ? QProcess::ForwardedErrorChannel
                                     : QProcess::ForwardedChannels);
  proc.start(QCoreApplication::applicationDirPath() + "/" + program, args);
  if (!proc.waitForStarted() || !proc.waitForFinished(-1) ||
      proc.exitStatus() != QProcess::NormalExit || proc.exitCode() != 0)
    fail(program + " " + args.join(' ') + " failed");
  return capture ? proc.readAllStandardOutput() : QByteArray{};
}

bool validPanel(const QString &name) {
  static const QRegularExpression format("^panel[1-9][0-9]*$");
  return format.match(name).hasMatch();
}
QJsonObject selection(const QString &home, const QString &panel,
                      QStringList requested, QJsonObject j,
                      QList<Step> &steps) {
  const bool fresh = j.isEmpty();
  if (fresh) {
    j = {{"version", 2},
         {"next", 0},
         {"panel", panel},
         {"active", false},
         {"phase", "install"},
         {"owned", QJsonArray{}},
         {"inputPrefsAbsent", false},
         {"preset", "windows"},
         {"seed", absent()},
         {"steps", QJsonArray{}},
         {"modules", QJsonArray{}}};
    if (requested.isEmpty())
      requested << "core";
  }
  auto existing = arrayStrings(j["steps"]),
       modules = arrayStrings(j["modules"]);
  auto owned = j["owned"].toArray();
  auto wanted = wantedSteps(requested);
  if (!panel.isEmpty() && !existing.contains("panel") &&
      !wanted.contains("panel"))
    fail("--panel requires the native-panel module.");
  if (!panel.isEmpty() && existing.contains("panel") && j["panel"] != panel)
    fail("Requested panel differs from the recorded selection.");
  if (!panel.isEmpty())
    j["panel"] = panel;
  auto available = catalog();
  for (const auto &name : wanted) {
    if (existing.contains(name) || existing.contains(legacyGroup(name)))
      continue;
    if (!fresh && j["phase"] != "installed")
      fail("Finish the pending core transaction before extending its scope.");
    const auto step =
        *std::find_if(available.cbegin(), available.cend(),
                      [&](const Step &v) { return v.name == name; });
    bool exists = false;
    if (step.program == "doroshell-maintenance") {
      auto alias =
          path(home, ".local/bin") + '/' + QFileInfo(step.receipt).fileName();
      QFileInfo current(alias);
      exists = current.exists() || current.isSymLink();
      if (exists &&
          (!current.isSymLink() ||
           current.symLinkTarget() != QCoreApplication::applicationDirPath() +
                                          "/doroshell-maintenance"))
        fail("Existing maintenance command needs migration: " + alias);
    } else {
      auto f = path(home, step.receipt);
      exists = QFileInfo::exists(f);
      if (exists && !QFileInfo(f).isFile())
        fail("Invalid existing " + step.receipt);
      const auto group = legacyGroup(name);
      if (!group.isEmpty() &&
          QFileInfo::exists(path(home, stateDir + group + ".json")))
        exists = true;
      // An explicitly installed Alt+F1 module already owns this binding.
      // Keep its rollback receipt when adding the complete core later.
      if (name == "start-key" &&
          (QFileInfo::exists(
               path(home, stateDir + "modules/start-shortcut.json")) ||
           QFileInfo::exists(
               path(home, ".local/state/lxqt-comfort/menu-integration.json"))))
        exists = true;
      if (name == "theme") {
        auto theme = QJsonDocument::fromJson(
                         child(home, "doroshell-theme", {"--status"}, true))
                         .object();
        if (!presets.contains(theme["preset"].toString()) ||
            theme["pending"].toBool())
          fail("Resolve the existing theme transaction first.");
        j["preset"] = theme["preset"];
      }
      if (name == "openbox-default" && !exists)
        j["seed"] = stockOpenbox();
      if (name == "input")
        j["inputPrefsAbsent"] = !QFileInfo::exists(
            path(home, ".config/doroshell/input-preferences.json"));
      if (name == "panel") {
        if (QFileInfo::exists(
                path(home, ".local/state/doroshell/native-panel.json")) ||
            QFileInfo::exists(path(home, ".local/bin/doroshell-native-panel")))
          fail("Migrate the RC2 panel first.");
        if (exists && !panel.isEmpty())
          fail("An independently managed panel already exists.");
        if (!exists) {
          QStringList args{"--plan"};
          if (!panel.isEmpty())
            args << "--panel" << panel;
          child(home, step.program, args);
        }
      }
    }
    existing << name;
    owned.append(!exists);
    steps << step;
  }
  if (!fresh && existing.size() > j["steps"].toArray().size())
    j["phase"] = "extend";
  for (const auto &name : requested)
    if (!modules.contains(name))
      modules << name;
  j["modules"] = QJsonArray::fromStringList(modules);
  j["steps"] = QJsonArray::fromStringList(existing);
  j["owned"] = owned;
  return j;
}
QJsonObject load(const QString &name, QList<Step> &steps) {
  auto state = read(name, 3 * 1024 * 1024);
  if (state == absent())
    return {};
  if (state["mode"].toInt() != 0600)
    fail("Unsafe core receipt permissions");
  auto j = QJsonDocument::fromJson(bytes(state)).object();
  if (j["version"] == 1 && j.size() == 9) {
    QStringList old;
    for (const auto &step : legacySteps)
      old << step.name;
    j["steps"] = QJsonArray::fromStringList(old);
    j["modules"] = QJsonArray{"core"};
    j["version"] = 2;
  }
  auto recorded = arrayStrings(j["steps"]),
       modules = arrayStrings(j["modules"]);
  auto expected = wantedSteps(modules);
  QStringList covered;
  for (const auto &stage : recorded) {
    if (stage == "session" || stage == "launchers") {
      for (const auto &group : groups)
        if (legacyGroup(group) == stage)
          covered << group;
    } else
      covered << stage;
  }
  expected.sort();
  covered.sort();
  if (expected != covered)
    fail("Saved module list does not match the installation stages");
  auto available = catalog();
  for (const auto &name : recorded) {
    auto it = std::find_if(available.cbegin(), available.cend(),
                           [&](const Step &s) { return s.name == name; });
    if (it == available.cend())
      fail("Unknown saved stage");
    steps << *it;
  }
  const auto phase = j["phase"].toString();
  int n = j["next"].toInt(-1);
  auto owned = j["owned"].toArray();
  if (j.size() != (phase == "subset" ? 12 : 11) ||
      (phase == "subset" && !j["subset"].isObject()) ||
      !j["panel"].isString() ||
      (!j["panel"].toString().isEmpty() &&
       !validPanel(j["panel"].toString())) ||
      !j["inputPrefsAbsent"].isBool() || !j["active"].isBool() ||
      (j["active"].toBool() &&
       ((phase != "install" && phase != "extend") || n >= steps.size())) ||
      j["version"] != 2 ||
      !QStringList{"install", "extend", "installed", "remove", "subset"}
           .contains(phase) ||
      n < 0 || n > steps.size() ||
      ((phase == "installed" || phase == "subset") && n != steps.size()) ||
      j["next"] != QJsonValue(n) || owned.size() != steps.size() ||
      !presets.contains(j["preset"].toString()))
    fail("Invalid core receipt");
  for (const auto &v : owned)
    if (!v.isBool())
      fail("Invalid core ownership");
  auto seed = j["seed"].toObject();
  validate(seed);
  int seedIndex = recorded.indexOf("openbox-default");
  if ((seed != absent()) != (seedIndex >= 0 && owned[seedIndex].toBool()) ||
      (seed != absent() && seed["mode"] != 0600))
    fail("Invalid Openbox backup");
  return j;
}

void save(const QString &name, const QJsonObject &j) {
  atomic(name, QJsonDocument(j).toJson(QJsonDocument::Compact), 0600);
}

void runStep(const QString &home, const QJsonObject &j, int n, const Step &s,
             bool remove) {
  if (!j["owned"].toArray()[n].toBool())
    return;
  if (s.program == "doroshell-maintenance") {
    auto target =
        QCoreApplication::applicationDirPath() + "/doroshell-maintenance";
    auto alias =
        path(home, ".local/bin") + '/' + QFileInfo(s.receipt).fileName();
    QFileInfo current(alias);
    if (current.exists() || current.isSymLink()) {
      if (!current.isSymLink() || current.symLinkTarget() != target)
        fail("Preserving edited maintenance command: " + alias);
      if (remove) {
        if (!QFile::remove(alias))
          fail("Cannot remove " + alias);
        syncParent(alias);
      }
    } else if (!remove) {
      if (!QFileInfo(target).isExecutable())
        fail("Missing maintenance command: " + target);
      makeParents(alias);
      if (!QFile::link(target, alias))
        fail("Cannot register " + alias);
      syncParent(alias);
    }
    return;
  }
  if (s.program.isEmpty()) {
    auto p = path(home, rc);
    auto current = read(p), seed = j["seed"].toObject();
    if (current != absent() && current != seed)
      fail("Preserving edited Openbox configuration: " + p);
    auto target = remove ? absent() : seed;
    if (current != target)
      write(p, target);
    return;
  }
  auto args = s.options;
  if (s.name == "theme") {
    if (remove &&
        QFileInfo::exists(
            path(home, ".local/state/doroshell/theme-native-pending.json"))) {
      // A failed forward operation may have left a pending apply.
      QFile pending(
          path(home, ".local/state/doroshell/theme-native-pending.json"));
      if (!pending.open(QIODevice::ReadOnly))
        fail("Cannot read pending theme transaction");
      auto intent =
          QJsonDocument::fromJson(pending.read(64 * 1024 * 1024 + 1)).object();
      if (intent.value("restore") == false)
        child(home, s.program, {"--apply", j["preset"].toString()});
    }
    if (remove && !QFileInfo::exists(path(home, s.receipt)) &&
        !QFileInfo::exists(
            path(home, ".local/state/doroshell/theme-native-pending.json")))
      return;
    args = remove ? QStringList{"--restore"}
                  : QStringList{"--apply", j["preset"].toString()};
  } else if (s.name == "cursor") {
    args << (remove ? "--rollback" : "--apply");
  } else {
    child(home, s.program, args + QStringList{"--recover"});
    args << (remove ? "--undo" : "--apply");
    if (!remove && s.name == "panel" && !j["panel"].toString().isEmpty())
      args << "--panel" << j["panel"].toString();
  }
  child(home, s.program, args);
  if (remove && s.name == "input" && j["inputPrefsAbsent"].toBool() &&
      QFileInfo::exists(
          path(home, ".config/doroshell/input-preferences.json"))) {
    QStringList options{"--remove-first-login"};
    if (home != QDir::homePath())
      options << "--offline";
    child(home, "doroshell-input-preferences", options);
  }
}

void refreshOwned(const QString &home, const QJsonObject &j,
                  const QList<Step> &steps) {
  // The desktop autostart pins digests of three bundled binaries. Recompute
  // those after a release swap, and update the managed input entry to its
  // checked launcher while preserving each component's original baseline.
  for (int i = 0; i < steps.size(); ++i) {
    if ((steps[i].name != "desktop" && steps[i].name != "input") ||
        !j["owned"].toArray()[i].toBool())
      continue;
    if (!QFileInfo::exists(path(home, steps[i].receipt)))
      fail("Missing managed " + steps[i].name + " receipt");
    runStep(home, j, i, steps[i], false);
  }
}

// Only these configuration files are shared by native base stages. When
// removing an earlier layer, unwind a later owner's existing transaction and
// reapply its normal edit on the restored configuration. Its receipt then has
// the correct baseline for a subsequent removal.
QStringList sharedFiles(const QString &name) {
  if (name == "session")
    return {"openbox", "shortcuts"};
  if (QStringList{"snap", "theme", "openbox-default"}.contains(name))
    return {"openbox"};
  if (QStringList{"print-key", "start-key"}.contains(name))
    return {"shortcuts"};
  return {};
}
struct Subset {
  QStringList remaining;
  QList<int> retained, undo, reapply;
};
Subset planSubset(const QJsonObject &j, const QList<Step> &stages,
                  const QStringList &requested) {
  Subset out;
  out.remaining = arrayStrings(j["modules"]);
  if (out.remaining.contains("core") && !requested.contains("core")) {
    bool expands = false;
    for (const auto &m : requested)
      if (fullSelection.contains(m) || m == "clipboard")
        expands = true;
    if (expands) {
      out.remaining.removeAll("core");
      for (const auto &m : fullSelection)
        if (!out.remaining.contains(m))
          out.remaining << m;
    }
  }
  for (const auto &m : requested) {
    if (!names.contains(m))
      fail("Unknown removal module: " + m);
    if (m == "none")
      continue;
    out.remaining.removeAll(m);
    if (m == "core")
      for (const auto &member : fullSelection)
        out.remaining.removeAll(member);
    if (m == "menu")
      out.remaining.removeAll("default-start-key");
    if (m == "clipboard")
      out.remaining.removeAll("default-clipboard-entry");
  }
  const auto wanted = wantedSteps(out.remaining);
  QSet<QString> changing;
  for (int i = 0; i < stages.size(); ++i) {
    auto name = stages[i].name;
    bool keep = wanted.contains(name);
    if (name == "session" || name == "launchers") {
      int present = 0, total = 0;
      for (const auto &g : groups)
        if (legacyGroup(g) == name) {
          ++total;
          present += wanted.contains(g);
        }
      if (present && present != total)
        fail("The older combined " + name +
             " receipt cannot be partially removed.");
      keep = present > 0;
    }
    if (keep)
      out.retained << i;
    if (!j["owned"].toArray()[i].toBool())
      continue;
    auto files = sharedFiles(name);
    bool overlaps = std::any_of(files.cbegin(), files.cend(),
                                [&](auto &f) { return changing.contains(f); });
    if (!keep || overlaps) {
      if (keep && name == "session")
        fail("The older combined session receipt cannot be safely rebased.");
      out.undo.prepend(i);
      if (keep)
        out.reapply << i;
      for (const auto &f : files)
        changing.insert(f);
    }
  }
  return out;
}
void removeSubset(const QString &home, const QString &filename, QJsonObject j,
                  const QList<Step> &stages, QStringList requested) {
  requested.removeDuplicates();
  requested.sort();
  const bool pending = j["phase"] == "subset";
  auto detail = j.value("subset").toObject();
  if (pending) {
    const auto old = arrayStrings(detail["request"]);
    if (!requested.isEmpty() && requested != old)
      fail("Finish the recorded partial removal with --recover.");
    requested = old;
  } else if (j["phase"] != "installed")
    fail("Finish the pending installation before partial removal.");
  if (requested.isEmpty())
    fail("Partial removal needs a recorded module selection.");
  auto plan = planSubset(j, stages, requested);
  if (!pending && plan.remaining == arrayStrings(j["modules"])) {
    QTextStream(stdout) << "The requested change leaves the recorded module "
                           "selection unchanged.\n";
    return;
  }
  if (!pending) {
    // Capture each owner's presence before starting the first change. A missing
    // receipt cannot prove that the selected configuration has been restored.
    for (int i : plan.undo) {
      const auto &stage = stages[i];
      if (!stage.program.isEmpty() &&
          stage.program != "doroshell-maintenance" &&
          !QFileInfo::exists(path(home, stage.receipt)))
        fail("Missing managed receipt: " + stage.receipt);
    }
    QString preset = j["preset"].toString();
    for (auto i : plan.reapply)
      if (stages[i].name == "theme") {
        auto status = QJsonDocument::fromJson(
                          child(home, "doroshell-theme", {"--status"}, true))
                          .object();
        if (status["pending"].toBool() ||
            !presets.contains(status["preset"].toString()))
          fail("Resolve the existing theme transaction first.");
        preset = status["preset"].toString();
      }
    detail = {{"request", QJsonArray::fromStringList(requested)},
              {"progress", 0},
              {"preset", preset}};
    j["phase"] = "subset";
    j["subset"] = detail;
    save(filename, j);
  }
  auto actions = plan.undo + plan.reapply;
  int cursor = detail.value("progress").toInt(-1);
  if (detail.size() != 3 || cursor < 0 || cursor > actions.size() ||
      !presets.contains(detail["preset"].toString()))
    fail("Invalid pending partial removal");
  auto transaction = j;
  transaction["preset"] = detail["preset"];
  while (cursor < actions.size()) {
    int i = actions[cursor];
    if (stages[i].name == "theme" && plan.reapply.contains(i) &&
        QFileInfo::exists(path(home, stages[i].receipt)) &&
        !QFileInfo::exists(
            path(home, ".local/state/doroshell/theme-native-pending.json"))) {
      auto now = QJsonDocument::fromJson(
                     child(home, "doroshell-theme", {"--status"}, true))
                     .object();
      if (now["preset"] != detail["preset"])
        fail("Theme selection changed while removing modules; preserving it.");
    }
    runStep(home, transaction, i, stages[i], cursor < plan.undo.size());
    detail["progress"] = ++cursor;
    j["subset"] = detail;
    save(filename, j);
  }
  QStringList stageNames;
  QJsonArray owners;
  for (int i : plan.retained) {
    stageNames << stages[i].name;
    owners.append(j["owned"].toArray()[i]);
  }
  if (!stageNames.contains("openbox-default"))
    j["seed"] = absent();
  if (!stageNames.contains("panel"))
    j["panel"] = "";
  j.remove("subset");
  j["phase"] = "installed";
  j["next"] = stageNames.size();
  j["steps"] = QJsonArray::fromStringList(stageNames);
  j["modules"] = QJsonArray::fromStringList(plan.remaining);
  j["owned"] = owners;
  j["preset"] = detail["preset"];
  save(filename, j);
  QTextStream(stdout) << "Remaining modules: " << plan.remaining.join(", ")
                      << "\n";
}
void run(const QString &home, const QString &op, const QString &panel,
         const QStringList &requested) {
  QFileInfo h(home);
  if (!h.isDir() || h.canonicalFilePath() != home || h.ownerId() != getuid())
    fail("Choose a canonical, user-owned home directory");
  if (home == QDir::homePath()) {
    for (auto [key, suffix] :
         QList<QPair<QString, QString>>{{"XDG_CONFIG_HOME", "/.config"},
                                        {"XDG_STATE_HOME", "/.local/state"},
                                        {"XDG_DATA_HOME", "/.local/share"}}) {
      auto value = qEnvironmentVariable(key.toLatin1().constData());
      if (!value.isEmpty() && QDir::cleanPath(value) != home + suffix)
        fail("Unsupported custom " + key);
    }
  }
  if (op == "packages") {
    child(home, "doroshell-setup", {"--packages"});
    return;
  }
  auto name = path(home, record);
  std::unique_ptr<QLockFile> lock;
  if (op != "plan") {
    makeParents(name);
    lock = std::make_unique<QLockFile>(path(home, stateDir + "core.lock"));
    if (!lock->tryLock())
      fail("Another core transaction is active");
  }
  QList<Step> steps;
  auto j = load(name, steps);
  if (j.value("phase") == "subset") {
    if (op == "recover" || (op == "remove" && !requested.isEmpty()))
      return removeSubset(home, name, j, steps, requested);
    fail("Finish the pending partial removal with --recover.");
  }
  if (op == "remove" && !requested.isEmpty()) {
    if (!j.isEmpty())
      removeSubset(home, name, j, steps, requested);
    return;
  }
  if (op == "apply" && j.value("phase") == "remove")
    fail("Finish the pending removal with --recover");
  if (op == "refresh" && j["phase"] != "installed" && j["phase"] != "extend")
    fail("Refresh requires an installed core selection");
  auto previous = j;
  if (op == "plan" || op == "apply" || op == "refresh")
    j = selection(home, panel, requested, j, steps);
  if (op == "plan") {
    QTextStream out(stdout);
    out << "Core transaction: " << j["phase"].toString() << "\n";
    out << "Modules: " << arrayStrings(j["modules"]).join(", ") << "\n";
    if (!j["panel"].toString().isEmpty())
      out << "Selected taskbar: " << j["panel"].toString() << "\n";
    for (int i = 0; i < steps.size(); ++i)
      out << (j["owned"].toArray()[i].toBool() ? "Manage " : "Preserve ")
          << steps[i].name << "\n";
    return;
  }
  if (j.isEmpty())
    return;
  if (j != previous)
    save(name, j);
  auto phase = j["phase"].toString();
  if (op == "remove" && phase != "remove") {
    // An in-flight forward step may already have created its own receipt.
    if ((phase == "install" || phase == "extend") && j["active"].toBool())
      j["next"] = qMin(int(steps.size()), j["next"].toInt() + 1);
    j["active"] = false;
    j["phase"] = "remove";
    save(name, j);
    phase = "remove";
  }
  if (phase == "installed") {
    refreshOwned(home, j, steps);
    return;
  }
  auto n = j["next"].toInt();
  if (phase == "install" || phase == "extend") {
    while (n < steps.size()) {
      if (!j["active"].toBool()) {
        if (j["owned"].toArray()[n].toBool()) {
          auto receipt = path(home, QFileInfo(steps[n].receipt).path()) + '/' +
                         QFileInfo(steps[n].receipt).fileName();
          QFileInfo current(receipt);
          if (current.exists() || current.isSymLink())
            fail("New ownership or personal configuration appeared during "
                 "install: " +
                 receipt);
        }
        j["active"] = true;
        save(name, j);
      }
      runStep(home, j, n, steps[n], false);
      j["active"] = false;
      j["next"] = ++n;
      save(name, j);
    }
    if (phase == "extend")
      refreshOwned(home, j, steps);
    j["phase"] = "installed";
    save(name, j);
  } else {
    while (n > 0) {
      runStep(home, j, n - 1, steps[n - 1], true);
      j["next"] = --n;
      save(name, j);
    }
    write(name, absent());
  }
}
} // namespace

int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  QCommandLineParser p;
  p.setApplicationDescription(
      "Stage or remove the DoroShell core for the next LXQt login.");
  p.addHelpOption();
  p.addOption({"home", "Target user home.", "directory", QDir::homePath()});
  p.addOption({"modules", "Select or add core modules.", "names"});
  p.addOption({"panel", "LXQt panel to customize.", "panelN"});
  for (const auto &mode : modes)
    p.addOption({mode, "Core " + mode});
  p.process(app);
  QStringList selected;
  for (const auto &mode : modes)
    if (p.isSet(mode))
      selected << mode;
  if (selected.size() > 1 ||
      (!p.isSet("modules") && !p.positionalArguments().isEmpty()))
    p.showHelp(2);
  try {
    auto mode = selected.value(0, "plan");
    if (p.isSet("panel") &&
        (!validPanel(p.value("panel")) ||
         (mode != "apply" && mode != "plan" && mode != "refresh")))
      fail("--panel requires a panel name such as panel2 and --plan or "
           "--apply.");
    QStringList modules;
    if (p.isSet("modules")) {
      if (mode != "apply" && mode != "plan" && mode != "refresh" &&
          mode != "remove")
        fail("Select modules for plan, apply, refresh, or removal.");
      modules = p.values("modules") + p.positionalArguments();
      for (const auto &m : modules)
        if (!names.contains(m))
          fail("Unknown core module: " + m);
    }
    run(QDir::cleanPath(p.value("home")), mode, p.value("panel"), modules);
    return 0;
  } catch (const std::exception &e) {
    QTextStream(stderr) << e.what() << Qt::endl;
    return 1;
  }
}
