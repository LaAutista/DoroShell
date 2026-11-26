// SPDX-License-Identifier: GPL-2.0-or-later
// Standalone C++20, also compiled by the first-install bootstrap before Qt is
// installed.
#include "../compatibility/packages.hpp"
#include <algorithm>
#include <cctype>
#include <cerrno>
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <filesystem>
#include <fstream>
#include <iostream>
#include <optional>
#include <regex>
#include <sstream>
#include <stdexcept>
#include <string>
#include <sys/file.h>
#include <sys/stat.h>
#include <sys/syscall.h>
#include <sys/wait.h>
#include <unistd.h>
#include <vector>

namespace fs = std::filesystem;
using Args = std::vector<std::string>;
using namespace std::string_literals;

namespace maintenance {
[[noreturn]] void fail(const std::string &s) { throw std::runtime_error(s); }

struct Result {
  int code;
  std::string output;
};
Result process(const Args &args, bool capture = false) {
  int fds[2];
  if (capture && pipe2(fds, O_CLOEXEC))
    fail("Could not create pipe");
  std::vector<char *> argv;
  for (auto &a : args)
    argv.push_back(const_cast<char *>(a.c_str()));
  argv.push_back(nullptr);
  pid_t child = fork();
  if (child < 0)
    fail("Could not start " + args.front());
  if (child == 0) {
    if (capture) {
      close(fds[0]);
      if (dup2(fds[1], STDOUT_FILENO) < 0)
        _exit(125);
      close(fds[1]);
    }
    setenv("GIT_TERMINAL_PROMPT", "0", 1);
    if (capture)
      setenv("LC_ALL", "C", 1);
    execvp(argv[0], argv.data());
    perror(argv[0]);
    _exit(127);
  }
  std::string output;
  if (capture) {
    close(fds[1]);
    char buf[4096];
    ssize_t n;
    while ((n = read(fds[0], buf, sizeof(buf))) != 0) {
      if (n < 0) {
        if (errno == EINTR)
          continue;
        break;
      }
      if (output.size() < 1024 * 1024)
        output.append(buf, n);
    }
    close(fds[0]);
  }
  int status;
  while (waitpid(child, &status, 0) < 0)
    if (errno != EINTR)
      fail("Could not wait for " + args.front());
  return {WIFEXITED(status) ? WEXITSTATUS(status) : 128, output};
}
std::string run(const Args &a, bool capture = false) {
  auto result = process(a, capture);
  if (result.code)
    fail(a.front() + " failed (" + std::to_string(result.code) + ")");
  while (!result.output.empty() && result.output.back() == '\n')
    result.output.pop_back();
  return result.output;
}

void ensureDir(const fs::path &p, bool create = true) {
  struct stat st{};
  if (lstat(p.c_str(), &st) < 0 && errno == ENOENT && create) {
    ensureDir(p.parent_path());
    if (mkdir(p.c_str(), 0700) < 0 && errno != EEXIST)
      fail("Cannot create " + p.string());
  }
  if (lstat(p.c_str(), &st) < 0 || !S_ISDIR(st.st_mode) ||
      st.st_uid != getuid())
    fail("Expected a user-owned directory: " + p.string());
}
fs::path tempDir(const fs::path &base, std::string prefix) {
  auto name = (base / (prefix + "XXXXXX")).string();
  if (!mkdtemp(name.data()))
    fail("Cannot create staging directory");
  return name;
}

std::optional<std::string> readText(const fs::path &p) {
  struct stat st{};
  if (lstat(p.c_str(), &st) < 0 && errno == ENOENT)
    return {};
  if (!S_ISREG(st.st_mode) || st.st_uid != getuid() || st.st_size > 1048576)
    fail("Unexpected state file " + p.string());
  std::ifstream f(p);
  if (!f)
    fail("Cannot read " + p.string());
  return std::string(std::istreambuf_iterator<char>(f), {});
}
void atomicText(const fs::path &dest, const std::string &text) {
  auto name = (dest.parent_path() / ".write-XXXXXX").string();
  int fd = mkstemp(name.data());
  if (fd < 0)
    fail("Cannot create transaction record");
  bool ok = true;
  size_t off = 0;
  while (off < text.size()) {
    auto n = write(fd, text.data() + off, text.size() - off);
    if (n < 0 && errno == EINTR)
      continue;
    if (n <= 0) {
      ok = false;
      break;
    }
    off += n;
  }
  if (fsync(fd) < 0)
    ok = false;
  if (close(fd) < 0)
    ok = false;
  if (!ok || rename(name.c_str(), dest.c_str()) < 0) {
    unlink(name.c_str());
    fail("Cannot save " + dest.string());
  }
}
void syncDirectory(const fs::path &dir) {
  int fd = open(dir.c_str(), O_DIRECTORY | O_CLOEXEC | O_NOFOLLOW);
  if (fd < 0)
    fail("Cannot open transaction directory");
  int result = fsync(fd);
  close(fd);
  if (result < 0)
    fail("Could not persist runtime selection");
}
struct Lock {
  int fd;
  explicit Lock(const fs::path &path)
      : fd(open(path.c_str(), O_CREAT | O_NOFOLLOW | O_CLOEXEC | O_RDWR,
                0600)) {
    struct stat st{};
    if (fd < 0 || fstat(fd, &st) < 0 || !S_ISREG(st.st_mode) ||
        st.st_uid != getuid() || flock(fd, LOCK_EX | LOCK_NB) < 0)
      fail("Another update is active or lock is unsafe");
  }
  ~Lock() { close(fd); }
};
bool validRef(const std::string &s) {
  return std::regex_match(s, std::regex("[A-Za-z0-9][A-Za-z0-9._/-]{0,199}")) &&
         s.find("..") == s.npos && s.find("//") == s.npos && s.back() != '/';
}
struct Options {
  std::string action = "plan", channel, ref, kind, panel, rc2Revision;
  fs::path home, current;
  bool packages = true, force = false;
  Args extras;
  Args base;
  bool explicitScope = false;
};
const Args optionalModules{"single-desktop", "clipboard",    "wallpaper-glass",
                           "start-shortcut", "taskbar-size", "taskbar",
                           "taskbar-drag",   "dolphin",      "kate",
                           "kate-dark",      "dolphin-dark"};
bool contains(const Args &a, const std::string &s) {
  return std::find(a.begin(), a.end(), s) != a.end();
}
void extra(Args &modules, const std::string &name) {
  if (name == "wallpaper" || name == "display" || name == "input-settings")
    return; // already in native core
  if (!contains(optionalModules, name))
    fail("Unsupported optional module: " + name);
  if (!contains(modules, name))
    modules.push_back(name);
}
const Args baseModules{"core",      "menu",     "native-panel",  "theme",
                       "cursor",    "snapping", "screenshots",   "maintenance",
                       "wallpaper", "display",  "input-settings"};
void append(Args &list, const std::string &s) {
  if (!contains(list, s))
    list.push_back(s);
}
void choose(Options &o, const std::string &s, bool with) {
  if (contains(baseModules, s)) {
    if (with && s != "wallpaper" && s != "display" && s != "input-settings")
      fail("Use --modules to select a base module: " + s);
    append(o.base, s);
  } else
    extra(o.extras, s);
}
Args scope(const Options &o, bool installed) {
  Args list = o.base;
  if (!installed && !o.explicitScope)
    append(list, "core");
  for (const auto &name : o.extras) {
    if (name == "clipboard" || name == "single-desktop" ||
        name == "start-shortcut")
      append(list, name);
    if (name.starts_with("taskbar"))
      append(list, name);
  }
  if (list.empty() && o.explicitScope)
    list.emplace_back("none");
  return list;
}
Options parse(Args a) {
  Options o;
  if (auto h = getenv("HOME"))
    o.home = h;
  auto command = fs::path(a.front()).filename().string();
  a.erase(a.begin());
  if (command == "doroshell-update")
    command = "update";
  else if (command == "doroshell-remove")
    command = "remove";
  else if (!a.empty() && !a[0].starts_with("-")) {
    command = a.front();
    a.erase(a.begin());
  } else
    command = "bootstrap";
  if (command == "update")
    o.action = "apply";
  else if (command == "remove" || command == "repair" || command == "rollback")
    o.action = command;
  else if (command != "bootstrap")
    fail("Unknown maintenance command: " + command);
  bool mode = false, removeFlag = false;
  for (size_t i = 0; i < a.size(); ++i) {
    const auto key = a[i];
    auto value = [&]() {
      if (++i >= a.size() || a[i].empty() || a[i][0] == '-')
        fail("Missing value for " + key);
      return a[i];
    };
    if (key == "--apply" || key == "--plan" || key == "--recover" ||
        key == "--prerequisites") {
      if (mode || command == "repair" || command == "remove" ||
          command == "rollback")
        fail("Conflicting actions");
      mode = true;
      o.action = key.substr(2);
    } else if (key == "--remove" && command == "bootstrap")
      removeFlag = true;
    else if (key == "--channel") {
      if (!o.channel.empty())
        fail("Choose one release channel");
      o.channel = value();
    } else if (key == "--rc2-revision") {
      if (!o.rc2Revision.empty() || command != "bootstrap")
        fail("Invalid RC2 revision option");
      o.rc2Revision = value();
      if (!std::regex_match(o.rc2Revision, std::regex("[0-9a-f]{40}")))
        fail("Invalid RC2 revision");
    } else if (key == "--ref") {
      if (!o.ref.empty())
        fail("Choose one source revision");
      o.ref = value();
    } else if (key == "--home")
      o.home = value();
    else if (key == "--kind")
      o.kind = value();
    else if (key == "--current")
      o.current = value();
    else if (key == "--panel")
      o.panel = value();
    else if (key == "--with")
      choose(o, value(), true);
    else if (key == "--modules") {
      Args list;
      while (i + 1 < a.size() && !a[i + 1].starts_with("-"))
        list.push_back(a[++i]);
      if (list.empty())
        fail("--modules requires at least one module name");
      o.explicitScope = true;
      for (const auto &v : list)
        choose(o, v, false);
    } else if (key == "--force")
      o.force = true;
    else if (key == "--no-packages")
      o.packages = false;
    else if (key == "--help" || key == "-h")
      o.action = "help";
    else
      fail("Unsupported option: " + key);
  }
  if (removeFlag) {
    if (o.action != "apply" && o.action != "plan")
      fail("Conflicting removal action");
    o.action = o.action == "apply" ? "remove" : "plan-remove";
  }
  if (!o.rc2Revision.empty() && !o.ref.empty() && o.ref != o.rc2Revision)
    fail("Conflicting RC2 release revision");
  if (!o.rc2Revision.empty() && o.ref == o.rc2Revision)
    o.ref.clear();
  if (!o.channel.empty() && o.channel != "stable" && o.channel != "development")
    fail("Invalid channel");
  if (!o.ref.empty() && (!validRef(o.ref) || o.channel == "stable"))
    fail("Invalid revision or stable override");
  if (!o.panel.empty() &&
      !std::regex_match(o.panel, std::regex("panel[1-9][0-9]*")))
    fail("Invalid panel ID");
  if (!o.panel.empty() && o.action != "apply" && o.action != "plan")
    fail("--panel requires --apply or --plan");
  if ((!o.extras.empty() || !o.base.empty()) && o.action != "apply" &&
      o.action != "plan" &&
      !(o.explicitScope && (o.action == "remove" || o.action == "plan-remove")))
    fail("Choose optional modules with --apply or --plan");
  if (o.action == "repair") {
    if ((o.kind != "desktop" && o.kind != "input" && o.kind != "panel") ||
        !o.current.is_absolute() || !o.ref.empty() || !o.channel.empty() ||
        !o.panel.empty())
      fail("Invalid repair selection");
  } else if (!o.kind.empty() || !o.current.empty() || o.force)
    fail("Repair options require repair");
  return o;
}

constexpr auto repo = "https://github.com/LaAutista/DoroShell.git";
bool revision(const std::string &s) {
  return std::regex_match(s, std::regex("[0-9a-f]{40}"));
}
std::string git(const fs::path &dir, Args args, bool capture = true) {
  Args cmd{"git", "-C", dir, "-c", "credential.helper="};
  cmd.insert(cmd.end(), args.begin(), args.end());
  return run(cmd, capture);
}
void verifySource(const fs::path &dir, const std::string &rev) {
  ensureDir(dir, false);
  if (!revision(rev) || git(dir, {"rev-parse", "HEAD"}) != rev ||
      !git(dir,
           {"status", "--porcelain=v1", "--untracked-files=all", "--ignored"})
           .empty())
    fail("Source checkout has changed: " + dir.string());
}
std::string fetch(const fs::path &root, const std::string &ref,
                  const std::string &url = repo) {
  auto tmp = tempDir(root, ".fetch-");
  try {
    git(tmp, {"init", "--quiet"});
    git(tmp, {"fetch", "--depth=1", "--", url, ref});
    git(tmp, {"checkout", "--quiet", "--detach", "FETCH_HEAD"});
    auto rev = git(tmp, {"rev-parse", "HEAD"});
    verifySource(tmp, rev);
    auto dest = root / rev;
    if (fs::symlink_status(dest).type() == fs::file_type::not_found)
      fs::rename(tmp, dest);
    else {
      verifySource(dest, rev);
      fs::remove_all(tmp);
    }
    return rev;
  } catch (...) {
    fs::remove_all(tmp);
    throw;
  }
}

struct Selection {
  std::string rev, channel, id;
};
std::string encode(const Selection &s) {
  return s.rev + "\n" + s.channel + "\n" + s.id + "\n";
}
Selection decode(const std::string &text) {
  std::istringstream f(text);
  Selection s;
  f >> s.rev >> s.channel >> s.id;
  if (!revision(s.rev) ||
      (s.channel != "development" && s.channel != "stable") ||
      !std::regex_match(s.id, std::regex("build-[A-Za-z0-9]{6}")) ||
      encode(s) != text)
    fail("Invalid native release receipt");
  return s;
}
std::optional<Selection> selected(const fs::path &dir) {
  if (fs::symlink_status(dir).type() == fs::file_type::not_found)
    return {};
  ensureDir(dir, false);
  auto text = readText(dir / ".doroshell-release");
  if (!text)
    fail("Preserving unowned runtime directory: " + dir.string());
  return decode(*text);
}
void exchange(const fs::path &next, const fs::path &current) {
  if (selected(current)) {
    if (syscall(SYS_renameat2, AT_FDCWD, next.c_str(), AT_FDCWD,
                current.c_str(), RENAME_EXCHANGE) < 0)
      fail("Atomic runtime exchange failed: " + std::string(strerror(errno)));
  } else
    fs::rename(next, current);
  syncDirectory(next.parent_path());
  syncDirectory(current.parent_path());
}
bool migrated(const fs::path &h) {
  return fs::exists(h / ".local/state/doroshell-native/migration.json") ||
         fs::exists(h / ".local/state/lxqt-comfort/menu-install.json") ||
         fs::exists(h / ".local/state/doroshell/native-panel.json") ||
         fs::exists(h / ".local/state/doroshell/deployment.json");
}
void deploy(const fs::path &current, const Options &o, std::string mode,
            bool legacy) {
  auto prog =
      current / "bin" / (legacy ? "doroshell-migrate" : "doroshell-core");
  Args args{prog, "--home", o.home,
            legacy && mode == "remove" ? "--undo" : "--" + mode};
  if (!o.panel.empty() &&
      (mode == "plan" || mode == "apply" || mode == "refresh"))
    args.insert(args.end(), {"--panel", o.panel});
  if (!legacy && !o.base.empty() &&
      (mode == "apply" || mode == "plan" || mode == "refresh" ||
       mode == "remove")) {
    args.push_back("--modules");
    args.insert(args.end(), o.base.begin(), o.base.end());
  }
  run(args);
  if (legacy && mode == "remove")
    std::cout << "Restored RC2. Run the restored doroshell-remove command to "
                 "remove RC2.\n";
}
void deploy(const fs::path &current, const Options &o, std::string mode) {
  deploy(current, o, mode, migrated(o.home));
}

void prerequisites(bool apply, bool mayInstall) {
  Args required;
  for (const auto &package : doro::packages::all)
    required.emplace_back(package.name);
  Args query{"pacman", "-T"};
  query.insert(query.end(), required.begin(), required.end());
  auto missing = process(query, true);
  if (!missing.code)
    return;
  if (missing.code != 127) {
    std::cerr << "Could not query Arch package dependencies.\n";
    fail("Check pacman first");
  }
  std::cerr << "Prerequisites:\n" << missing.output;
  if (!apply)
    return;
  if (!mayInstall || missing.output.empty())
    fail("Install missing prerequisites first");
  Args command{"sudo", "pacman", "-Syu", "--needed"};
  command.insert(command.end(), required.begin(), required.end());
  run(command);
  run(query, true);
}

bool healthy(const fs::path &exe) {
  if (access(exe.c_str(), X_OK) != 0 || !fs::is_regular_file(exe))
    return false;
  auto r = process({"/usr/bin/ldd", "-r", exe}, true);
  return !r.code && r.output.find("not found") == r.output.npos &&
         r.output.find("undefined symbol") == r.output.npos;
}
std::string component(std::string kind) {
  if (kind == "desktop")
    return "pcmanfm-qt";
  if (kind == "input")
    return "lxqt-config-input";
  return "lxqt-panel";
}
const Args bundleFiles{"doroshell-core",
                       "doroshell-migrate",
                       "doroshell-maintenance",
                       "lxqt-panel",
                       "pcmanfm-qt",
                       "doroshell-video-worker",
                       "lxqt-config-input",
                       "doroshell-start",
                       "doroshell-display",
                       "doroshell-network",
                       "doroshell-setup",
                       "doroshell-panel-profile",
                       "doroshell-clipboard",
                       "doroshell-desktop",
                       "doroshell-screenshot",
                       "doroshell-input-preferences",
                       "doroshell-snap",
                       "doroshell-input-overrides",
                       "doroshell-cursor",
                       "doroshell-theme",
                       "doroshell-portable",
                       "doroshell-settings",
                       "doroshell-route",
                       "doroshell-screengrab-import",
                       "doroshell-wallpaper",
                       "doroshell-check",
                       "doroshell-config-input",
                       "doroshell-modules"};
void validateBundle(const fs::path &bin) {
  for (const auto &name : bundleFiles)
    if (!healthy(bin / name))
      fail("Missing or unloadable native component: " + (bin / name).string());
}
struct Choice {
  std::string name, claim;
  bool pending;
};
using Choices = std::vector<Choice>;
bool buildId(const std::string &id) {
  return std::regex_match(id, std::regex("build-[A-Za-z0-9]{6}"));
}
std::string choiceText(const Choices &choices) {
  std::string data;
  for (const auto &c : choices)
    data += c.name + " " + c.claim + (c.pending ? " pending\n" : " selected\n");
  return data;
}
Choices selections(const fs::path &root) {
  auto text = readText(root / "optional-selections").value_or("");
  std::istringstream in(text);
  Choices out;
  Args seen;
  std::string name, id, phase;
  while (in >> name >> id >> phase) {
    if (!contains(optionalModules, name) || contains(seen, name) ||
        !buildId(id))
      fail("Invalid optional module selection");
    seen.push_back(name);
    out.push_back({name, id, phase == "pending"});
  }
  if (choiceText(out) != text)
    fail("Invalid optional module transaction");
  return out;
}
void saveChoices(const fs::path &root, const Choices &choices) {
  if (choices.empty())
    fs::remove(root / "optional-selections");
  else
    atomicText(root / "optional-selections", choiceText(choices));
  syncDirectory(root);
}
void module(const fs::path &current, const Options &o, const Choice &c,
            const std::string &mode) {
  run({current / "bin/doroshell-modules", c.name, "--home", o.home, "--" + mode,
       "--claim", c.claim});
}
void addOptions(const fs::path &root, const Options &o, const std::string &id,
                const Args &requested) {
  auto choices = selections(root);
  auto current = root / "current";
  for (auto &name : requested) {
    auto nativeReceipt =
        o.home / ".local/state/doroshell-native/modules" / (name + ".json");
    auto entry = std::find_if(choices.begin(), choices.end(),
                              [&](const auto &c) { return c.name == name; });
    if (entry != choices.end()) {
      if (!entry->pending && name != "taskbar-drag" &&
          !fs::exists(nativeReceipt)) {
        entry->pending = true;
        saveChoices(root, choices);
      }
      continue;
    }
    // Pre-existing settings retain their original owner and rollback receipt.
    if (fs::exists(o.home / ".local/state/doroshell" / (name + ".json")) ||
        fs::exists(nativeReceipt))
      continue;
    choices.push_back({name, id, true});
    saveChoices(root, choices);
  }
  for (auto &c : choices) {
    if (c.pending) {
      module(current, o, c, "recover");
      module(current, o, c, "apply");
      c.pending = false;
      saveChoices(root, choices);
    }
  }
}
void removeOptions(const fs::path &root, const Options &o,
                   const std::string &onlyBuild = {},
                   const Args *onlyNames = nullptr) {
  auto choices = selections(root);
  for (size_t i = choices.size(); i-- > 0;) {
    auto c = choices[i];
    if (!onlyBuild.empty() && c.claim != onlyBuild)
      continue;
    if (onlyNames && !contains(*onlyNames, c.name))
      continue;
    if (c.name != "taskbar-drag") {
      module(root / "current", o, c, "recover");
      module(root / "current", o, c, "undo");
    }
    choices.erase(choices.begin() + i);
    saveChoices(root, choices);
  }
}
struct Change {
  Selection release;
  std::string previous, stage;
  bool refresh = false, legacy = false;
  std::string panel{};
  Args extras{};
  Args base{};
};
std::string record(const Change &p) {
  auto head = p.previous + " " + p.stage + " " +
              (p.refresh ? "refresh" : "apply") + " " +
              (p.legacy ? "migrate" : "core") + " " +
              (p.panel.empty() ? "-" : p.panel);
  for (auto &v : p.extras)
    head += " " + v;
  for (auto &v : p.base)
    head += " @" + v;
  return head + "\n" + encode(p.release);
}
Change change(const std::string &text) {
  auto pos = text.find('\n');
  if (pos == text.npos)
    fail("Incomplete update transaction record");
  Change p{decode(text.substr(pos + 1)), {}, {}};
  std::istringstream f(text.substr(0, pos));
  std::string mode, target;
  f >> p.previous >> p.stage >> mode >> target >> p.panel;
  for (std::string opt; f >> opt;) {
    if (opt.starts_with("@")) {
      auto name = opt.substr(1);
      if (!contains(baseModules, name) && name != "single-desktop" &&
          name != "clipboard" && name != "start-shortcut" && name != "none" &&
          name != "taskbar" && name != "taskbar-size" && name != "taskbar-drag")
        fail("Invalid core scope in pending release");
      append(p.base, name);
    } else
      extra(p.extras, opt);
  }
  if (p.panel == "-")
    p.panel.clear();
  p.refresh = mode == "refresh";
  p.legacy = target == "migrate";
  const std::regex id("build-[A-Za-z0-9]{6}");
  if ((p.previous != "none" && !std::regex_match(p.previous, id)) ||
      !std::regex_match(p.stage, id) || (p.refresh && p.previous == "none") ||
      (!p.panel.empty() &&
       (p.legacy ||
        !std::regex_match(p.panel, std::regex("panel[1-9][0-9]*")))) ||
      record(p) != text)
    fail("Invalid release transaction");
  return p;
}
// Optional receipts overlay Openbox, LXQt and application configuration.
// Unwind affected overlays in reverse before an earlier owner changes its
// snapshot; reapply them in original order to capture the new baseline.
bool overlaps(const std::string &name, const Args &base, const Args &optional) {
  if (contains(optional, name))
    return true;
  auto core = [&](const std::string &s) {
    return contains(base, "core") || contains(base, s);
  };
  if (name == "single-desktop")
    return core("snapping") || core("theme") || core("single-desktop");
  if (name == "start-shortcut")
    return core("screenshots") || core("start-shortcut");
  auto panel = [](const std::string &s) {
    return s == "clipboard" || s.starts_with("taskbar");
  };
  if (panel(name))
    return core("native-panel") ||
           std::any_of(optional.begin(), optional.end(), panel) ||
           std::any_of(base.begin(), base.end(), panel);
  if (name == "kate" || name == "dolphin")
    return contains(optional, "kate") || contains(optional, "dolphin");
  if (name.ends_with("-dark"))
    return core("theme");
  return false;
}
template <typename Action>
void baseTransaction(const fs::path &root, const Options &o,
                     const std::string &transaction, const Args &base,
                     const Args &removing, Action act) {
  auto file = root / "optional-layers";
  auto saved = readText(file);
  std::string phase = "suspend";
  if (saved) {
    auto newline = saved->find('\n');
    if (newline == saved->npos)
      fail("Invalid optional layer journal");
    if (saved->substr(newline + 1) != transaction) {
      if (saved->substr(0, newline) != "complete")
        fail("Finish the earlier optional module transaction first");
    } else
      phase = saved->substr(0, newline);
  }
  auto affected = [&] {
    auto list = selections(root);
    std::erase_if(list, [&](auto &c) {
      return c.pending || !overlaps(c.name, base, removing);
    });
    return list;
  };
  auto checkpoint = [&](std::string p) {
    atomicText(file, p + "\n" + transaction);
    syncDirectory(root);
    phase = std::move(p);
  };
  if (!saved && affected().empty()) {
    act();
    checkpoint("complete");
    return;
  }
  if (phase == "suspend") {
    checkpoint("suspend");
    auto list = affected();
    for (auto it = list.rbegin(); it != list.rend(); ++it) {
      module(root / "current", o, *it, "recover");
      module(root / "current", o, *it, "suspend");
    }
    checkpoint("base");
  }
  if (phase == "base") {
    act();
    checkpoint("resume");
  }
  if (phase == "resume") {
    for (const auto &c : affected()) {
      module(root / "current", o, c, "recover");
      module(root / "current", o, c, "resume");
    }
    checkpoint("complete");
  }
  if (phase != "complete")
    fail("Invalid optional module transaction phase");
}
void resume(const fs::path &root, Options o) {
  auto pending = readText(root / "pending");
  if (!pending)
    return;
  auto p = change(*pending);
  o.panel = p.panel;
  o.base = p.base;
  auto current = root / "current", next = root / p.stage / "activation";
  auto active = selected(current);
  if (!active || encode(*active) != encode(p.release)) {
    if ((active ? active->id : "none") != p.previous)
      fail("Selected runtime changed during staging");
    auto proposed = selected(next);
    if (!proposed || encode(*proposed) != encode(p.release))
      fail("Incomplete staged runtime; preserving current build");
    if (p.stage != p.release.id)
      removeOptions(root, o, p.previous);
    exchange(next, current);
  }
  baseTransaction(root, o, *pending, p.base, {}, [&] {
    if (p.refresh)
      deploy(current, o, "refresh", p.legacy);
    else {
      deploy(current, o, "recover", p.legacy);
      deploy(current, o, "apply", p.legacy);
    }
  });
  addOptions(root, o, p.release.id, p.extras);
  if (p.previous != p.release.id)
    atomicText(root / "last-switch", *pending);
  syncDirectory(root);
  fs::remove(root / "pending");
  syncDirectory(root);
  fs::remove(root / "optional-layers");
}
void rollback(const fs::path &root, const Options &o) {
  auto prior = readText(root / "pending");
  if (prior) {
    auto p = change(*prior);
    if (p.previous == p.release.id)
      fail("Optional configuration is pending. Use --recover or remove.");
    if (p.stage == p.release.id) {
      auto active = selected(root / "current");
      if (active && active->id == p.previous) {
        fs::remove(root / "pending");
        syncDirectory(root);
        return;
      }
    }
    if (auto layer = readText(root / "optional-layers")) {
      auto n = layer->find('\n');
      if (n == layer->npos || layer->substr(n + 1) != *prior)
        fail("Finish the earlier optional transaction before rollback");
      // Finish a partially applied base transaction before restoring its
      // overlays. Recovery never reinstalls a missing core.
      if (layer->substr(0, n) == "base")
        deploy(root / "current", o, "recover", p.legacy);
      for (const auto &c : selections(root))
        if (!c.pending && overlaps(c.name, p.base, {})) {
          module(root / "current", o, c, "recover");
          module(root / "current", o, c, "resume");
        }
      fs::remove(root / "optional-layers");
      syncDirectory(root);
    }
  }
  if (!prior)
    prior = readText(root / "last-switch");
  if (!prior)
    fail("No release switch to roll back");
  auto p = change(*prior);
  if (p.previous == "none")
    fail("First installation has no predecessor; use remove to undo it");
  if (p.stage != p.release.id) {
    resume(root, o);
    return;
  } // already rolling back
  auto current = selected(root / "current");
  if (!current || current->id != p.release.id)
    fail("Cannot roll back a different selection");
  auto predecessor = selected(root / p.stage / "activation");
  if (!predecessor || predecessor->id != p.previous)
    fail("Previous build unavailable");
  Change back{*predecessor, current->id, p.stage, true, p.legacy};
  atomicText(root / "pending", record(back));
  resume(root, o);
}

void beginRemoval(const fs::path &root, const Selection &active, bool legacy,
                  const Options &o) {
  std::string data = active.id + (legacy ? " migrate\n" : " core\n");
  if (o.explicitScope) {
    if (legacy)
      fail("RC2 partial removal requires its original installer. Native "
           "removal restores the previous RC2 installation.");
    Change partial{active, active.id, active.id, true,
                   false,  {},        o.extras,  scope(o, true)};
    data = "partial\n" + record(partial);
  }
  atomicText(root / "removing", data);
  syncDirectory(root);
}
void finishRemoval(const fs::path &root, Options o, const Selection &active) {
  auto state = readText(root / "removing");
  if (!state)
    fail("Missing removal transaction");
  o.base.clear();
  o.panel.clear();
  if (state->starts_with("partial\n")) {
    auto p = change(state->substr(8));
    if (encode(p.release) != encode(active) || p.legacy ||
        p.previous != active.id || p.stage != active.id || !p.refresh ||
        p.base.empty())
      fail("Invalid partial removal transaction");
    o.base = p.base;
    baseTransaction(root, o, *state, p.base, p.extras, [&] {
      removeOptions(root, o, {}, &p.extras);
      if (o.base != Args{"none"})
        deploy(root / "current", o, "remove", false);
    });
  } else {
    auto legacy = *state == active.id + " migrate\n";
    if (!legacy && *state != active.id + " core\n")
      fail("Release changed during removal");
    removeOptions(root, o);
    deploy(root / "current", o, "remove", legacy);
  }
  fs::remove(root / "pending");
  fs::remove(root / "removing");
  syncDirectory(root);
  fs::remove(root / "optional-layers");
}
void prepareChoices(Options &o, bool legacy, bool installed) {
  if (legacy) {
    if (o.explicitScope || !o.base.empty())
      fail("RC2 migration retains the installed base selection. Omit --modules "
           "and select optional additions with --with.");
    return;
  }
  if (!installed && (!o.explicitScope || contains(o.base, "core")) &&
      !contains(o.extras, "single-desktop"))
    o.extras.insert(o.extras.begin(), "single-desktop");
  o.base = scope(o, installed);
}
std::string environment(const char *key) {
  auto value = getenv(key);
  return value ? value : "";
}
Args installBlockers(const fs::path &home, const fs::path &osRelease) {
  Args issues;
  std::ifstream in(osRelease);
  std::string id, like;
  for (std::string line; std::getline(in, line);) {
    auto equals = line.find('=');
    if (equals == line.npos)
      continue;
    auto key = line.substr(0, equals), value = line.substr(equals + 1);
    if (value.size() >= 2 && (value.front() == '"' || value.front() == '\'') &&
        value.back() == value.front())
      value = value.substr(1, value.size() - 2);
    if (key == "ID")
      id = value;
    if (key == "ID_LIKE")
      like = value;
  }
  bool arch = id == "arch";
  std::istringstream family(like);
  for (std::string name; family >> name;)
    if (name == "arch")
      arch = true;
  if (!arch)
    issues.emplace_back("Install on Arch Linux or an Arch-based distribution.");
  std::istringstream desktops(environment("XDG_CURRENT_DESKTOP"));
  bool lxqt = false;
  for (std::string name; std::getline(desktops, name, ':');) {
    std::transform(name.begin(), name.end(), name.begin(),
                   [](unsigned char c) { return std::tolower(c); });
    if (name == "lxqt")
      lxqt = true;
  }
  if (!lxqt)
    issues.emplace_back("Log in to LXQt before installing DoroShell.");
  auto session = environment("XDG_SESSION_TYPE");
  if (session.empty())
    session = !environment("WAYLAND_DISPLAY").empty() ? "wayland"
              : !environment("DISPLAY").empty()       ? "x11"
                                                      : "unknown";
  if (session != "x11")
    issues.emplace_back("Select the LXQt X11 session at login.");
  for (const auto &[var, sub] : {std::pair{"XDG_CONFIG_HOME", ".config"},
                                 {"XDG_DATA_HOME", ".local/share"},
                                 {"XDG_STATE_HOME", ".local/state"}}) {
    auto value = environment(var);
    if (!value.empty() && fs::path(value).lexically_normal() != (home / sub))
      issues.push_back(std::string(var) + " must use " + (home / sub).string());
  }
  return issues;
}
int perform(Options o, const fs::path &osRelease = "/etc/os-release") {
  if (o.action == "help") {
    std::cout
        << "doroshell-maintenance bootstrap "
           "[--apply|--plan|--recover|--prerequisites] [--channel "
           "development|stable] [--ref REV] [--no-packages] [--home "
           "PATH] [--panel panelN] [--modules NAME...] [--with MODULE]...\n"
           "doroshell-maintenance update | remove | rollback | repair "
           "--kind panel|desktop|input --current PATH [--force]\n";
    return 0;
  }
  if (getuid() == 0)
    fail("Run as your normal desktop user");
  if (!o.home.is_absolute() || fs::canonical(o.home) != o.home)
    fail("Expected canonical home path");
  ensureDir(o.home, false);
  if (!o.panel.empty() && migrated(o.home))
    fail("RC2 migration preserves the existing panel selection. Omit --panel.");
  auto root = o.home / ".local/share/doroshell/native",
       current = root / "current";
  for (fs::path p = o.home;
       const auto &part : fs::path(".local/share/doroshell/native")) {
    p /= part;
    if (fs::symlink_status(p).type() == fs::file_type::not_found)
      break;
    ensureDir(p, false);
  }
  bool managed =
      fs::exists(o.home / ".local/state/doroshell-native/core.json") ||
      fs::exists(o.home / ".local/state/doroshell-native/migration.json");
  if ((o.action == "apply" || o.action == "plan") && !managed) {
    auto issues = installBlockers(o.home, osRelease);
    if (!issues.empty()) {
      for (auto &issue : issues)
        std::cerr << "Installation blocked: " << issue << '\n';
      return 1;
    }
  }
  if (o.action == "plan" || o.action == "prerequisites") {
    prerequisites(false, false);
    std::cout << "Build the selected DoroShell release and stage it for next "
                 "login.\n";
    if (o.action == "plan") {
      auto active = selected(current);
      prepareChoices(o, migrated(o.home),
                     fs::is_regular_file(
                         o.home / ".local/state/doroshell-native/core.json"));
      for (const auto &name : o.base)
        std::cout << "Base module: " << name << "\n";
      if (active)
        deploy(current, o, "plan");
      for (const auto &name : o.extras) {
        std::cout << "Optional module: " << name << "\n";
        if (active)
          run({current / "bin/doroshell-modules", name, "--plan", "--home",
               o.home});
      }
    }
    return 0;
  }
  if (o.action == "plan-remove") {
    auto active = selected(current);
    if (!active) {
      std::cout << "No native installation selected.\n";
      return 0;
    }
    if (o.explicitScope && migrated(o.home))
      fail("RC2 partial removal requires its original installer");
    std::cout << (o.explicitScope ? "Selected modules will be removed:"
                                  : "The native installation will be removed.")
              << '\n';
    if (o.explicitScope)
      for (const auto &name : scope(o, true))
        std::cout << "Base module: " << name << '\n';
    for (const auto &c : selections(root))
      if (!o.explicitScope || contains(o.extras, c.name))
        std::cout << "Optional module: " << c.name << '\n';
    return 0;
  }
  if (o.action != "apply" && !fs::exists(root))
    fail("No installed native build");
  ensureDir(root);
  Lock lock(root / "update.lock");
  if (readText(root / "removing")) {
    if (o.action != "remove" && o.action != "recover")
      fail("Finish the pending removal with --recover.");
    auto active = selected(current);
    if (!active)
      fail("The bundle selected for removal is missing");
    finishRemoval(root, o, *active);
    return 0;
  }
  if (o.action == "rollback") {
    rollback(root, o);
    return 0;
  }
  if (auto pending = readText(root / "pending")) {
    if (o.action == "remove") {
      if (o.explicitScope)
        fail("Recover the pending installation before requesting partial "
             "removal.");
      auto p = change(*pending);
      auto active = selected(current);
      // Explicit full removal can cancel a partially extended installation,
      // including layers already suspended at the current selection.
      if (active && (active->id == p.release.id || active->id == p.previous)) {
        beginRemoval(root, *active, p.legacy, o);
        finishRemoval(root, o, *active);
      } else if (active)
        fail("Unexpected selection during interrupted install");
      fs::remove(root / "pending");
      return 0;
    }
    if (o.action != "apply" && o.action != "recover")
      fail("Complete the pending update with --recover first");
    resume(root, o);
    return 0;
  }
  auto active = selected(current);
  if (o.action == "remove" || o.action == "recover") {
    if (!active)
      fail("No installed native build");
    if (o.action == "remove") {
      beginRemoval(root, *active, migrated(o.home), o);
      finishRemoval(root, o, *active);
    } else
      deploy(current, o, o.action);
    return 0;
  }
  auto sources = root / "sources";
  ensureDir(sources);
  bool legacy = migrated(o.home);
  auto receipt =
      o.home / (legacy ? ".local/state/doroshell-native/migration.json"
                       : ".local/state/doroshell-native/core.json");
  bool installed = fs::is_regular_file(receipt);
  if (o.action == "apply")
    prepareChoices(o, legacy, installed);
  if (installed && !o.panel.empty() && o.base.empty())
    fail("This installation already selected its panel. Omit --panel when "
         "updating it.");
  std::string channel = o.channel.empty()
                            ? (active ? active->channel : "development")
                            : o.channel;
  if (channel == "stable" && !o.ref.empty())
    fail("A stable installation must use the stable tag");
  std::string rev;
  if (o.action == "repair") {
    if (!active ||
        fs::weakly_canonical(o.current) !=
            fs::weakly_canonical(current / "bin" / component(o.kind)))
      fail("Component selection changed");
    if (!installed)
      fail("Native install removed");
    if (!o.force && healthy(o.current) &&
        (o.kind != "desktop" ||
         (healthy(current / "bin/doroshell-video-worker") &&
          healthy(current / "bin/doroshell-display"))))
      return 0;
    auto stamp = root / ("repair-" + active->id);
    if (!o.force && fs::exists(stamp) &&
        fs::file_time_type::clock::now() - fs::last_write_time(stamp) <
            std::chrono::hours(24))
      fail("Rebuild was attempted within the last day");
    auto logfile = root / "repair.log";
    (void)readText(stamp);
    int fd =
        open(logfile.c_str(),
             O_WRONLY | O_NOFOLLOW | O_CREAT | O_CLOEXEC | O_NONBLOCK, 0600);
    struct stat st{};
    if (fd < 0 || fstat(fd, &st) < 0 || !S_ISREG(st.st_mode) ||
        st.st_uid != getuid() || st.st_nlink != 1 || ftruncate(fd, 0) < 0 ||
        dup2(fd, STDERR_FILENO) < 0 || dup2(fd, STDOUT_FILENO) < 0)
      fail("Cannot open private repair log");
    close(fd);
    (void)nice(10);
    atomicText(stamp, "attempt\n");
    rev = active->rev;
    (void)process({"notify-send", "DoroShell",
                   "Rebuilding desktop components for the next login."});
  } else {
    prerequisites(true, o.packages);
    auto ref = channel == "stable"      ? "refs/tags/stable"
               : !o.rc2Revision.empty() ? o.rc2Revision
               : o.ref.empty()          ? "refs/heads/main"
                                        : o.ref;
    rev = fetch(sources, ref);
    if (!o.rc2Revision.empty() && rev != o.rc2Revision)
      fail("The stable tag changed after RC2 selected it. Retry the update.");
    if (active && active->rev == rev && active->channel == channel) {
      if (o.extras.empty() && o.base.empty())
        deploy(current, o, installed ? "refresh" : "apply", legacy);
      else {
        atomicText(root / "pending",
                   record({*active, active->id, active->id, installed, legacy,
                           o.panel, o.extras, o.base}));
        syncDirectory(root);
        resume(root, o);
      }
      return 0;
    }
  }
  auto source = sources / rev;
  verifySource(source, rev);
  auto build = tempDir(root, "build-");
  if (channel == "stable") {
    auto check = build / "check-release.cmake";
    atomicText(check, R"(cmake_minimum_required(VERSION 3.22)
file(READ "${RELEASE}" json LIMIT 1048576)
string(JSON channel GET "${json}" channel)
if(NOT channel STREQUAL "stable")
    message(FATAL_ERROR "The release at the stable tag is not declared stable")
endif()
)");
    run({"cmake", "-DRELEASE=" + (source / "release.json").string(), "-P",
         check});
  }
  Selection release{rev, channel, build.filename()};
  run({"cmake", "-S", source, "-B", build, "-G", "Ninja",
       "-DCMAKE_BUILD_TYPE=Release", "-DBUILD_TESTING=OFF",
       "-DDOROSHELL_BUILD_LXQT_PANEL=ON"});
  // Upstream targets run their own four-job builds. Serialize those projects
  // so an update does not start four independent compiler pools on a laptop.
  run({"cmake", "--build", build, "--target", "doroshell-bundle", "--parallel",
       "1"});
  auto runtime = build / "native/upstream/runtime";
  validateBundle(runtime / "bin");
  auto next = build / "activation";
  run({"cp", "-a", "--", runtime, next});
  atomicText(next / ".doroshell-release", encode(release));
  if (installed && !fs::is_regular_file(receipt))
    fail("Native install removed during build; leaving it unstaged");
  atomicText(root / "pending",
             record({release, active ? active->id : "none", release.id,
                     installed && active.has_value(), legacy, o.panel, o.extras,
                     o.base}));
  syncDirectory(root);
  resume(root, o);
  if (o.action == "repair")
    (void)process(
        {"notify-send", "DoroShell",
         "Rebuilt desktop components are ready for your next login."});
  std::cout << "DoroShell is staged for your next login.\n";
  return 0;
}
} // namespace maintenance
#ifndef DOROSHELL_MAINTENANCE_TEST
int main(int argc, char **argv) {
  try {
    return maintenance::perform(maintenance::parse(Args(argv, argv + argc)));
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
}
#endif
