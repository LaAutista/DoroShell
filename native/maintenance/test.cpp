// SPDX-License-Identifier: GPL-2.0-or-later
#define DOROSHELL_MAINTENANCE_TEST
#include "main.cpp"
namespace m = maintenance;
void expect(bool b, const std::string &s) {
  if (!b)
    m::fail(s);
}
template <class F> void refuses(F f, const char *why) {
  try {
    f();
  } catch (const std::exception &) {
    return;
  }
  m::fail(why);
}
void test(const fs::path &home) {
  auto root = home / "native";
  m::ensureDir(root);
  auto source = root / "upstream";
  m::ensureDir(source);
  m::git(source, {"init", "-b", "main", "-q"});
  m::atomicText(source / "example", "revision 1");
  m::git(source, {"add", "example"});
  m::git(source, {"-c", "user.name=Tester", "-c",
                  "user.email=test@example.invalid", "commit", "-qm", "one"});
  m::git(source, {"tag", "stable"});
  auto src = root / "sources";
  m::ensureDir(src);
  auto one = m::fetch(src, "refs/heads/main", source);
  expect(m::fetch(src, "refs/tags/stable", source) == one,
         "Tag checkout disagrees");
  m::atomicText(src / one / "example", "personal");
  refuses([&] { m::fetch(src, "main", source); }, "Overwrote changed checkout");
  auto build = m::tempDir(root, "build-");
  auto runtime = build / "activation";
  m::ensureDir(runtime / "bin");
  fs::create_symlink("/usr/bin/true", runtime / "bin/doroshell-core");
  m::Selection s{one, "development", build.filename()};
  m::atomicText(runtime / ".doroshell-release", m::encode(s));
  m::atomicText(root / "pending", m::record({s, "none", s.id, false, false}));
  m::Options o;
  o.home = home;
  m::resume(root, o);
  auto current = root / "current";
  expect(m::selected(current)->rev == one && !fs::exists(root / "pending"),
         "First stage incomplete");
  auto nextBuild = m::tempDir(root, "build-");
  auto next = nextBuild / "activation";
  m::ensureDir(next / "bin");
  fs::create_symlink("/usr/bin/false", next / "bin/doroshell-core");
  m::Selection newer{one, "stable", nextBuild.filename()};
  m::atomicText(next / ".doroshell-release", m::encode(newer));
  m::atomicText(root / "pending",
                m::record({newer, s.id, newer.id, true, false}));
  refuses([&] { m::resume(root, o); }, "Configuration failure hidden");
  expect(m::selected(current)->id == newer.id &&
             m::selected(next)->id == s.id && fs::exists(root / "pending"),
         "Lost incumbent or recovery evidence");
  fs::remove(current / "bin/doroshell-core");
  fs::create_symlink("/usr/bin/true", current / "bin/doroshell-core");
  m::resume(root, o);
  expect(m::selected(current)->id == newer.id &&
             m::selected(next)->id == s.id && !fs::exists(root / "pending"),
         "Retry toggled release twice");
  m::rollback(root, o);
  expect(m::selected(current)->id == s.id && m::selected(next)->id == newer.id,
         "Rollback failed to restore previous exact bundle");
  m::rollback(root, o);
  expect(m::selected(current)->id == s.id, "Repeated rollback toggled release");
  refuses(
      [&] { m::change("../path " + s.id + " refresh core\n" + m::encode(s)); },
      "Unsafe transaction path");
  fs::create_directory(root / "unowned");
  refuses([&] { m::exchange(next, root / "unowned"); },
          "Overwrote unowned runtime");
  fs::create_directory_symlink(root / "unowned", root / "link");
  refuses([&] { m::exchange(next, root / "link"); },
          "Followed conflicting symlink");
  m::Lock lock(root / "update.lock");
  refuses([&] { m::Lock other(root / "update.lock"); },
          "Concurrent switch allowed");
  expect(m::healthy("/usr/bin/true") && !m::healthy(root / "missing"),
         "Loader gate disagrees");
  expect(m::parse({"doroshell-update", "--channel", "stable"}).action ==
             "apply",
         "Stable update alias");
  expect(m::parse({"doroshell-remove"}).action == "remove", "Remove alias");
  refuses([] { m::parse({"maintenance", "bootstrap", "--apply", "--plan"}); },
          "Accepted conflicting actions");
  refuses(
      [] { m::parse({"maintenance", "bootstrap", "--ref", "../override"}); },
      "Accepted unsafe revision");
  refuses(
      [] {
        m::parse({"maintenance", "repair", "--kind", "panel", "--current",
                  "relative"});
      },
      "Accepted relative repair path");
}
// Exercise the public CLI, Git checkout, CMake bundle build, deployment
// dispatch and repair with a local repository and tiny native stand-in ELFs.
void installedCli(const fs::path &home, const fs::path &tool,
                  const fs::path &modules, const fs::path &self,
                  const fs::path &core, const fs::path &setup) {
  auto fixture = home / "upstream", bin = home / "fixture-bin";
  m::ensureDir(fixture);
  m::ensureDir(bin);
  fs::create_symlink(self, bin / "pacman");
  fs::create_symlink("/usr/bin/true", bin / "notify-send");
  setenv("HOME", home.c_str(), 1);
  setenv("GIT_CONFIG_GLOBAL", (home / "test.gitconfig").c_str(), 1);
  setenv("GIT_CONFIG_NOSYSTEM", "1", 1);
  setenv("XDG_CURRENT_DESKTOP", "X-CachyOS:lXQt", 1);
  setenv("XDG_SESSION_TYPE", "x11", 1);
  for (auto var : {"XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"})
    unsetenv(var);
  auto calls = home / "package-query.log";
  setenv("DOROSHELL_TEST_PACKAGE_CALLS", calls.c_str(), 1);
  auto path = bin.string() + ":/usr/bin";
  setenv("PATH", path.c_str(), 1);
  // Rewrite only this fixture's hardcoded public URL, with no network access.
  m::run({"git", "config", "--global",
          "url.file://" + fixture.string() + ".insteadOf", m::repo});
  m::git(fixture, {"init", "-q", "-b", "main"});
  std::string cmake =
      "cmake_minimum_required(VERSION 3.22)\nproject(Release NONE)\n"
      "set(bin \"${CMAKE_BINARY_DIR}/native/upstream/runtime/bin\")\n"
      "file(MAKE_DIRECTORY \"${bin}\")\nadd_custom_target(doroshell-bundle)\n";
  for (const auto &name : m::bundleFiles) {
    auto source = name == "doroshell-modules" ? modules
                  : (name == "doroshell-core" || name == "doroshell-migrate")
                      ? self
                      : fs::path("/usr/bin/true");
    cmake += "configure_file([==[" + source.string() + "]==] \"${bin}/" + name +
             "\" COPYONLY)\n";
  }
  m::atomicText(fixture / "CMakeLists.txt", cmake);
  auto commit = [&] {
    m::git(fixture, {"add", "."});
    m::git(fixture,
           {"-c", "user.name=Test", "-c", "user.email=test@example.invalid",
            "commit", "-qm", "fixture"});
  };
  m::atomicText(fixture / "release.json", R"({"channel":"development"})");
  commit();
  m::git(fixture, {"tag", "stable"});
  auto cli = [&](Args args) {
    args.insert(args.begin(), tool);
    return m::process(args).code;
  };
  auto root = home / ".local/share/doroshell/native",
       current = root / "current";
  auto distro = home / "os-release.fixture";
  m::Options fresh;
  fresh.home = home;
  fresh.action = "apply";
  auto blocked = [&](const std::string &label) {
    expect(m::perform(fresh, distro) != 0 && !fs::exists(root) &&
               !fs::exists(calls),
           label +
               ": package request or state mutation occurred before preflight");
  };
  m::atomicText(distro, "ID=fedora\nID_LIKE=archipelago\n");
  blocked("Wrong distribution");
  m::atomicText(distro, "ID=cachyos\nID_LIKE=\"linux arch\"\n");
  setenv("XDG_CURRENT_DESKTOP", "KDE", 1);
  blocked("KDE");
  setenv("XDG_CURRENT_DESKTOP", "LXQt", 1);
  setenv("XDG_SESSION_TYPE", "wayland", 1);
  blocked("Wayland");
  fresh.action = "plan";
  blocked("Wayland plan");
  fresh.action = "apply";
  setenv("XDG_SESSION_TYPE", "x11", 1);
  for (auto var : {"XDG_CONFIG_HOME", "XDG_DATA_HOME", "XDG_STATE_HOME"}) {
    setenv(var, (home / "custom").c_str(), 1);
    blocked(var);
    unsetenv(var);
  }
  expect(m::installBlockers(home, distro).empty(),
         "Arch derivative with declared LXQt/X11 was refused");
  if (!m::installBlockers(home, "/etc/os-release").empty()) {
    expect(cli({"bootstrap", "--apply"}) != 0 && !fs::exists(root) &&
               !fs::exists(calls),
           "Public unsupported-host refusal");
    std::cout << "Positive public CLI fixture requires an Arch test host. "
                 "Negative preflight cases passed.\n";
    return;
  }
  auto rc = home / ".config/openbox/rc.xml";
  m::ensureDir(rc.parent_path());
  std::string original = "<openbox_config><desktops><number>4</number></"
                         "desktops></openbox_config>\n";
  m::atomicText(rc, original);
  auto mime = home / ".config/mimeapps.list";
  m::atomicText(mime, "[Default Applications]\ntext/plain=user.desktop;\n");
  expect(!cli({"bootstrap", "--plan"}) && !fs::exists(root),
         "Plan created native state");
  expect(
      cli({"bootstrap", "--apply", "--channel", "stable", "--no-packages"}) &&
          !fs::exists(current),
      "Development metadata was accepted as a stable release");
  expect(!cli({"bootstrap", "--apply", "--no-packages", "--panel", "panel2",
               "--with", "dolphin"}),
         "Fresh install failed");
  auto first = *m::selected(current);
  auto receipt = home / ".local/state/doroshell-native/core.json";
  m::ensureDir(receipt.parent_path());
  m::atomicText(receipt, "fixture\n");
  expect(m::readText(rc)->find("<number>1</number>") != std::string::npos &&
             m::readText(mime)->find("org.kde.dolphin") != std::string::npos,
         "Fresh managed modules were not applied");
  auto helper = current / "bin/doroshell-modules";
  fs::rename(helper, current / "bin/module.saved");
  fs::create_symlink("/usr/bin/false", helper);
  expect(cli({"update", "--with", "kate", "--no-packages"}) &&
             fs::exists(root / "pending"),
         "Optional failure was lost");
  fs::remove(helper);
  fs::rename(current / "bin/module.saved", helper);
  expect(!cli({"bootstrap", "--recover"}) &&
             m::readText(mime)->find("org.kde.kate") != std::string::npos &&
             !fs::exists(root / "pending"),
         "Optional recovery failed");
  expect(!cli({"update", "--no-packages"}) &&
             m::selected(current)->id == first.id,
         "No-op update rebuilt release");
  m::atomicText(fixture / "release.json", R"({"channel":"stable"})");
  commit();
  m::git(fixture, {"tag", "-f", "stable"});
  expect(cli({"bootstrap", "--apply", "--channel", "stable", "--rc2-revision",
              first.rev, "--no-packages"}) != 0 &&
             m::selected(current)->id == first.id,
         "RC2 stable race selected a newer release");
  expect(!cli({"bootstrap", "--apply", "--channel", "development",
               "--rc2-revision", first.rev, "--no-packages"}) &&
             m::selected(current)->id == first.id,
         "RC2 selected revision was ignored after main advanced");
  expect(cli({"bootstrap", "--apply", "--ref", "main", "--rc2-revision",
              first.rev}) != 0,
         "RC2 override allowed");
  expect(!cli({"update", "--no-packages", "--channel", "stable", "--with",
               "wallpaper-glass"}),
         "Updating to stable failed");
  auto glass = home / ".config/doroshell/wallpaper-glass.json";
  expect(fs::exists(glass), "Missing release-specific optional module");
  expect(!cli({"rollback"}) && !fs::exists(glass) &&
             m::readText(mime)->find("org.kde.kate") != std::string::npos,
         "Binary rollback did not restore preceding optional selection");
  expect(!cli({"update", "--channel", "stable", "--no-packages"}),
         "Repeat update after rollback failed");
  auto second = *m::selected(current);
  expect(second.channel == "stable" && second.rev != first.rev &&
             fs::exists(root / second.id / "activation/bin/lxqt-panel"),
         "Update lost previous binaries");
  fs::remove(current / "bin/lxqt-panel");
  expect(!cli({"repair", "--kind", "panel", "--current",
               (current / "bin/lxqt-panel").string()}),
         "Repair failed");
  auto repaired = *m::selected(current);
  expect(repaired.rev == second.rev && repaired.id != second.id &&
             m::healthy(current / "bin/lxqt-panel"),
         "Repair did not rebuild the same revision");
  fs::remove(receipt);
  expect(cli({"repair", "--force", "--kind", "panel", "--current",
              (current / "bin/lxqt-panel").string()}) &&
             m::selected(current)->id == repaired.id,
         "Resurrected removed installation");
  expect(!cli({"remove"}) && m::readText(rc) == original &&
             m::readText(mime) ==
                 "[Default Applications]\ntext/plain=user.desktop;\n" &&
             !fs::exists(root / "optional-selections"),
         "Reverse removal did not restore shared optional files");
  auto scoped = home / "other home";
  m::ensureDir(scoped);
  expect(!cli({"bootstrap", "--home", scoped, "--apply", "--modules", "kate",
               "--no-packages"}),
         "Optional-only install failed");
  expect(m::readText(scoped / "calls")->find("--apply --modules none") !=
                 std::string::npos &&
             !fs::exists(scoped / ".config/openbox/rc.xml"),
         "Partial install unexpectedly requested full core or seeded defaults");
  auto legacy = home / "RC2";
  auto oldReceipt = legacy / ".local/state/doroshell/kate.json";
  m::ensureDir(oldReceipt.parent_path());
  m::atomicText(oldReceipt, "old receipt");
  m::atomicText(oldReceipt.parent_path() / "deployment.json", "old deployment");
  expect(!cli({"bootstrap", "--home", legacy, "--apply", "--with", "kate",
               "--with", "wallpaper-glass", "--no-packages"}),
         "Legacy migration plus optional add failed");
  expect(!cli({"remove", "--home", legacy}) &&
             m::readText(oldReceipt) == "old receipt" &&
             !fs::exists(legacy / ".config/doroshell/wallpaper-glass.json"),
         "RC2 selection or newly added native module incorrectly restored");
  // Put the real core, module and launcher transaction binaries into a new
  // fixture release so three coordinators exercise the same Openbox file.
  cmake += "configure_file([==[" + core.string() +
           "]==] \"${bin}/doroshell-core\" COPYONLY)\n";
  cmake += "configure_file([==[" + setup.string() +
           "]==] \"${bin}/doroshell-setup\" COPYONLY)\n";
  m::atomicText(fixture / "CMakeLists.txt", cmake);
  commit();
  auto layered = home / "Layered";
  auto xml = layered / ".config/openbox/rc.xml";
  m::ensureDir(xml.parent_path());
  auto originalOpenbox =
      "<openbox_config><!--personal before install--><keyboard></keyboard><desktops><number>4</number></desktops></openbox_config>\n"s;
  m::atomicText(xml, originalOpenbox);
  fs::permissions(xml, fs::perms::owner_read | fs::perms::owner_write |
                           fs::perms::group_read);
  auto inLayer = [&](Args args) {
    args.insert(args.end(), {"--home", layered});
    return cli(args);
  };
  auto layerRoot = layered / ".local/share/doroshell/native";
  expect(!inLayer({"bootstrap", "--apply", "--modules", "single-desktop",
                   "--no-packages"}),
         "Initial single-desktop scope failed");
  auto snap = layerRoot / "current/bin/doroshell-snap",
       held = layerRoot / "current/bin/snap.held";
  fs::rename(snap, held);
  expect(inLayer({"update", "--modules", "snapping", "--no-packages"}) != 0 &&
             fs::exists(layerRoot / "pending"),
         "Failed base extension did not retain transaction");
  expect(m::readText(xml) == originalOpenbox,
         "Optional was not safely suspended during blocked base extension");
  fs::rename(held, snap);
  expect(!inLayer({"bootstrap", "--recover"}) &&
             m::readText(xml)->find("<number>1</number>") !=
                 std::string::npos &&
             m::readText(xml)->find("DoroShell native snapping") !=
                 std::string::npos,
         "Recover lost optional or base settings");
  expect(
      !inLayer({"bootstrap", "--remove", "--apply", "--modules", "snapping"}) &&
          m::readText(xml)->find("<number>1</number>") != std::string::npos &&
          m::readText(xml)->find("DoroShell native snapping") ==
              std::string::npos,
      "Partial removal damaged retained optional");
  expect(!inLayer({"remove"}) && m::readText(xml) == originalOpenbox &&
             (fs::status(xml).permissions() & fs::perms::all) ==
                 (fs::perms::owner_read | fs::perms::owner_write |
                  fs::perms::group_read),
         "Complete removal lost original XML bytes or permissions");
  expect(!inLayer({"bootstrap", "--apply", "--modules", "single-desktop",
                   "--no-packages"}),
         "Second scoped install failed");
  fs::rename(snap, held);
  expect(inLayer({"update", "--modules", "snapping", "--no-packages"}) != 0 &&
             !inLayer({"remove"}) && m::readText(xml) == originalOpenbox,
         "Cancel of interrupted base addition failed to restore the home");
  auto key = layered / ".config/lxqt/globalkeyshortcuts.conf";
  m::ensureDir(key.parent_path());
  m::atomicText(key, "[Personal.9]\nEnabled=false\n");
  auto initialShortcut = m::readText(key);
  expect(!inLayer({"bootstrap", "--apply", "--modules", "start-shortcut",
                   "--no-packages"}) &&
             !inLayer({"update", "--modules", "screenshots", "--no-packages"}),
         "Shortcut/screenshot layered install failed");
  auto screenshot =
      layered / ".local/share/applications/doroshell-screenshot.desktop";
  auto screenshotOriginal = m::readText(screenshot).value();
  auto mode = fs::status(screenshot).permissions();
  m::atomicText(screenshot, screenshotOriginal + "# personal edit\n");
  fs::permissions(screenshot, mode);
  expect(inLayer({"remove", "--modules", "screenshots"}) != 0 &&
             fs::exists(layerRoot / "removing") &&
             m::readText(screenshot) ==
                 screenshotOriginal + "# personal edit\n",
         "Partial removal overwrote personal edit");
  m::atomicText(screenshot, screenshotOriginal);
  fs::permissions(screenshot, mode);
  expect(!inLayer({"bootstrap", "--recover"}) &&
             m::readText(key)->find("Alt%2BF1") != std::string::npos &&
             !fs::exists(screenshot),
         "Partial removal retry lost original Alt+F1");
  expect(!inLayer({"remove"}) && m::readText(key) == initialShortcut,
         "Shortcut file did not restore exactly");
  setenv("XDG_SESSION_TYPE", "wayland", 1);
  setenv("XDG_CURRENT_DESKTOP", "KDE", 1);
  expect(!cli({"bootstrap", "--recover", "--home", scoped}) &&
             !cli({"remove", "--home", scoped}),
         "Recovery or removal blocked outside LXQt");
}
void testBootstrapAsset(const fs::path &tmp, const fs::path &script,
                        const fs::path &asset, const fs::path &self) {
  auto bin = tmp / "tools";
  m::ensureDir(bin);
  for (auto name : {"mktemp", "rm", "chmod", "sha256sum"})
    fs::create_symlink(fs::path("/usr/bin") / name, bin / name);
  for (auto name : {"curl", "uname"})
    fs::create_symlink(self, bin / name);
  setenv("PATH", bin.c_str(), 1);
  setenv("TMPDIR", tmp.c_str(), 1);
  setenv("DOROSHELL_TEST_BOOTSTRAP_ASSET", asset.c_str(), 1);
  auto invoke = [&] {
    return m::process({"/usr/bin/bash", script, "--help"}, true);
  };
  auto result = invoke();
  expect(!result.code &&
             result.output.find("doroshell-maintenance bootstrap") !=
                 std::string::npos,
         "Verified GCC-less asset did not run");
  auto bad = tmp / "corrupt";
  m::atomicText(bad, "invalid bootstrap");
  setenv("DOROSHELL_TEST_BOOTSTRAP_ASSET", bad.c_str(), 1);
  expect(invoke().code != 0, "Corrupt bootstrap accepted");
  setenv("DOROSHELL_TEST_ARCH", "aarch64", 1);
  setenv("DOROSHELL_TEST_BOOTSTRAP_ASSET", asset.c_str(), 1);
  expect(invoke().code != 0, "Unsupported prebuilt architecture accepted");
}
int main(int argc, char **argv) {
  auto leaf = fs::path(argv[0]).filename();
  if (leaf == "uname") {
    std::cout << (getenv("DOROSHELL_TEST_ARCH") ? getenv("DOROSHELL_TEST_ARCH")
                                                : "x86_64")
              << '\n';
    return 0;
  }
  if (leaf == "curl") {
    Args args(argv + 1, argv + argc);
    if (!m::contains(args,
                     "https://github.com/LaAutista/DoroShell/releases/download/"
                     "v0.3.0-rc.1/doroshell-bootstrap-linux-x86_64") ||
        args.size() < 3 || args[args.size() - 2] != "-o" ||
        !getenv("DOROSHELL_TEST_BOOTSTRAP_ASSET"))
      return 2;
    fs::copy_file(getenv("DOROSHELL_TEST_BOOTSTRAP_ASSET"), args.back());
    return 0;
  }
  if (leaf == "pacman") {
    auto log = getenv("DOROSHELL_TEST_PACKAGE_CALLS");
    if (!log || argc < 2 || std::string(argv[1]) != "-T")
      return 2;
    std::ofstream(log, std::ios::app) << "query\n";
    return 0;
  }
  if (leaf == "doroshell-core" || leaf == "doroshell-migrate") {
    if (argc < 4 || std::string(argv[1]) != "--home")
      return 2;
    std::ofstream calls(fs::path(argv[2]) / "calls", std::ios::app);
    for (int i = 3; i < argc; ++i)
      calls << argv[i] << ' ';
    calls << '\n';
    return calls ? 0 : 1;
  }
  auto tmp = m::tempDir(fs::temp_directory_path(), "doroshell-release-test-");
  try {
    if (argc == 4 && std::string(argv[1]) == "--bootstrap-asset") {
      testBootstrapAsset(tmp, argv[2], argv[3], fs::canonical(argv[0]));
      fs::remove_all(tmp);
      return 0;
    }
    test(tmp);
    if (argc == 5 && getuid() != 0)
      installedCli(tmp, argv[1], argv[2], fs::canonical(argv[0]), argv[3],
                   argv[4]);
    fs::remove_all(tmp);
    return 0;
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    fs::remove_all(tmp);
    return 1;
  }
}
