// SPDX-License-Identifier: GPL-2.0-or-later
#include "state.hpp"

#include <QCoreApplication>
#include <QDeadlineTimer>
#include <QFile>
#include <QJsonDocument>
#include <QProcess>
#include <QProcessEnvironment>
#include <algorithm>
#include <cerrno>
#include <csignal>
#include <fcntl.h>
#include <optional>
#include <poll.h>
#include <sys/file.h>
#include <sys/stat.h>
#include <unistd.h>

namespace display
{
namespace
{
volatile std::sig_atomic_t stopped = 0;
void cancel(int) { stopped = 1; }

void writeMessage(const QJsonObject &message)
{
    const auto bytes = QJsonDocument(message).toJson(QJsonDocument::Compact) + '\n';
    qsizetype offset = 0;
    while (offset < bytes.size()) {
        const auto n = write(STDOUT_FILENO, bytes.constData() + offset, bytes.size() - offset);
        if (n < 0 && errno == EINTR)
            continue;
        if (n <= 0)
            return; // Broken UI output must never abort rollback.
        offset += n;
    }
}

class Commands
{
  public:
    std::optional<QDeadlineTimer> decision;
    QByteArray run(const QString &program, const QStringList &args) const
    {
        const int timeout = decision ? int(std::min<qint64>(4000, decision->remainingTime())) : 4000;
        if (timeout <= 0)
            throw Error("Confirmation deadline reached", "deadline");
        QDeadlineTimer deadline(timeout, Qt::PreciseTimer);
        auto env = QProcessEnvironment::systemEnvironment();
        env.insert("LC_ALL", "C");
        QProcess process;
        process.setProcessEnvironment(env);
        process.start(program, args, QIODevice::ReadOnly);
        if (!process.waitForStarted(int(deadline.remainingTime()))) {
            if (decision && decision->hasExpired())
                throw Error("Confirmation deadline reached", "deadline");
            throw Error(program + " unavailable or timed out",
                        process.error() == QProcess::Timedout ? "command_timeout" : "command_unavailable");
        }
        if (!process.waitForFinished(int(deadline.remainingTime()))) {
            process.kill();
            process.waitForFinished(1000);
            if (decision && decision->hasExpired())
                throw Error("Confirmation deadline reached", "deadline");
            throw Error(program + " unavailable or timed out", "command_timeout");
        }
        const auto error = process.readAllStandardError().trimmed();
        if (process.exitStatus() != QProcess::NormalExit || process.exitCode() || error.contains("ERROR:"))
            throw Error(program + ": " +
                            (error.isEmpty() ? QString("operation failed") : QString::fromLocal8Bit(error)),
                        "command_failed");
        return process.readAllStandardOutput();
    }
    State snapshot() const
    {
        if (qEnvironmentVariable("XDG_SESSION_TYPE", "x11") != "x11")
            throw Error("These controls require an X11 session");
        auto state = parse(run("xrandr", {"--current", "--verbose"}));
        try {
            auto reply = run("nvidia-settings", {"-t", "-q", "[screen:0]/SyncToVBlank"}).trimmed();
            if (reply != "0" && reply != "1")
                throw Error("NVIDIA OpenGL SyncToVBlank unavailable on X screen 0");
            state.values["vsync"] = reply.toInt();
            state.values["vsync_reason"] = "";
        } catch (const Error &e) {
            if (e.reason == "deadline")
                throw;
            state.values["vsync"] = QJsonValue::Null;
            state.values["vsync_reason"] =
                "NVIDIA OpenGL control unavailable. Intel/AMD: use application VSync settings.";
        }
        return state;
    }
};

template <class F> void phase(const QString &name, F operation)
{
    try {
        operation();
    } catch (Error &e) {
        e.phase(name);
        throw;
    }
}

class Transaction
{
  public:
    Transaction(Commands &driver, const QJsonObject &request) : commands(driver)
    {
        static const QStringList keys{"token", "output", "mode", "vsync"};
        for (const auto &key : request.keys())
            if (!keys.contains(key))
                throw Error("Invalid display request");
        before = commands.snapshot();
        if (request["token"] != token(before))
            throw Error("Display settings changed. Reload before applying.");
        expected = before;
        auto outputs = expected.values["outputs"].toArray();
        const auto name = request.value("output"), mode = request.value("mode");
        if (!(name.isUndefined() || name.isNull()) || !(mode.isUndefined() || mode.isNull())) {
            const auto allowed = options(before)["outputs"].toArray();
            const auto index = namedOutput(allowed, name);
            bool valid = false;
            if (index >= 0)
                for (const auto &m : allowed.at(index).toObject()["modes"].toArray())
                    valid |= m.toObject()["id"] == mode;
            if (!valid)
                throw Error("Choose an advertised refresh mode at the current resolution");
            target = namedOutput(outputs, name);
            auto output = outputs.at(target).toObject();
            originalMode = output["current"].toString();
            requestedMode = mode.toString();
            outputName = name.toString();
            output["current"] = mode;
            outputs[target] = output;
            expected.values["outputs"] = outputs;
        }
        if (request.contains("vsync")) {
            auto vsync = request.value("vsync");
            if (before.values["vsync"].isNull() || !vsync.isDouble() ||
                (vsync.toDouble() != 0 && vsync.toDouble() != 1))
                throw Error("NVIDIA OpenGL VSync is unsupported or the value is invalid");
            expected.values["vsync"] = vsync;
        }
    }

    void apply()
    {
        if (commands.snapshot() != before)
            throw Error("Concurrent display edit; reload before applying", "external_change");
        if (target >= 0 && requestedMode != originalMode) {
            modeAttempted = true;
            setMode(requestedMode);
        }
        if (expected.values["vsync"] != before.values["vsync"]) {
            vsyncAttempted = true;
            setVsync(expected.values["vsync"]);
        }
        phase("apply_verification", [&] {
            auto actual = commands.snapshot(), calibrated = expected;
            calibrated.values["outputs"] = expectedOutputs(actual);
            if (actual != calibrated)
                throw Error("Driver did not apply the requested state exactly", "state_mismatch",
                            differences(calibrated, actual));
            expected = std::move(calibrated);
            verified = true;
        });
    }

    void verify()
    {
        const auto actual = commands.snapshot();
        if (actual != expected)
            throw Error("Display state changed; refusing Keep", "state_mismatch",
                        differences(expected, actual));
    }

    void revert()
    {
        auto current = commands.snapshot();
        QStringList errors;
        QJsonArray evidence;
        auto record = [&](Error error) {
            errors << QString::fromStdString(error.what());
            error.phase("recovery");
            for (const auto &e : error.diagnostics)
                if (evidence.size() < 3)
                    evidence.append(e);
        };
        if (vsyncAttempted && current.values["vsync"] != before.values["vsync"]) {
            if (current.values["vsync"] == expected.values["vsync"]) {
                try {
                    setVsync(before.values["vsync"]);
                } catch (const Error &e) {
                    record(e);
                }
            } else
                record(Error("NVIDIA setting changed elsewhere; left untouched", "external_change",
                             differences(before, current)));
        }
        if (modeAttempted) {
            const auto outputs = current.values["outputs"].toArray();
            const auto index = namedOutput(outputs, outputName);
            if (index < 0 || outputs.at(index).toObject()["current"] != originalMode) {
                if (current.values["layout"] == before.values["layout"] &&
                    outputs == expectedOutputs(current)) {
                    try {
                        setMode(originalMode);
                    } catch (const Error &e) {
                        record(e);
                    }
                } else
                    record(Error("Display disconnected or layout changed; no forced reconnect or overwrite",
                                 "external_change", differences(before, current)));
            }
        }
        if (errors.isEmpty()) {
            const auto restored = commands.snapshot();
            if (restored != before)
                record(Error("Original state not restored exactly; reload and inspect display settings",
                             "state_mismatch", differences(before, restored)));
        }
        if (!errors.isEmpty()) {
            Error error(errors.join("; "), "operation_failed", differences(before, current));
            error.diagnostics = evidence;
            throw error;
        }
    }

  private:
    Commands &commands;
    State before, expected;
    int target = -1;
    QString requestedMode, originalMode, outputName;
    bool modeAttempted = false, vsyncAttempted = false, verified = false;

    void setMode(const QString &id) { commands.run("xrandr", {"--output", outputName, "--mode", id}); }
    void setVsync(QJsonValue setting)
    {
        commands.run("nvidia-settings", {"-a", QString("[screen:0]/SyncToVBlank=%1").arg(setting.toInt())});
    }
    QJsonArray expectedOutputs(const State &actual) const
    {
        auto list = expected.values["outputs"].toArray();
        if (!modeAttempted || verified)
            return list;
        auto wished = list.at(target).toObject();
        if (!wished.contains("reported_mm"))
            return list;
        const auto found = actual.values["outputs"].toArray();
        const auto index = namedOutput(found, outputName);
        if (index >= 0 && found[index].toObject().contains("reported_mm")) {
            wished["reported_mm"] = found[index].toObject()["reported_mm"];
            list[target] = wished;
        }
        return list;
    }
};

void guard(const QJsonObject &request)
{
    Commands commands;
    Transaction txn(commands, request);
    bool kept = false;
    std::optional<Error> failure, expired;
    try {
        phase("apply", [&] { txn.apply(); });
        writeMessage({{"pending", true}, {"seconds", 15}});
        commands.decision.emplace(15000, Qt::PreciseTimer);
        while (!commands.decision->hasExpired() && !stopped) {
            pollfd input{STDIN_FILENO, POLLIN, 0};
            int count = poll(&input, 1, int(std::min<qint64>(250, commands.decision->remainingTime())));
            if (count < 0) {
                if (errno == EINTR)
                    continue;
                throw Error("Cannot wait for display confirmation");
            }
            if (count > 0) {
                char data[64];
                const auto n = read(STDIN_FILENO, data, sizeof(data));
                if (n == 5 && QByteArrayView(data, 5) == "keep\n" && !commands.decision->hasExpired()) {
                    phase("keep_verification", [&] { txn.verify(); });
                    kept = !stopped && !commands.decision->hasExpired();
                }
                break;
            }
            phase("periodic_verification", [&] { txn.verify(); });
        }
    } catch (const Error &e) {
        if (e.reason == "deadline")
            expired = e;
        else
            failure = e;
    }
    commands.decision.reset();
    if (!kept) {
        try {
            phase("recovery", [&] { txn.revert(); });
        } catch (Error &recovery) {
            if (failure || expired) {
                auto earlier = failure ? *failure : *expired;
                auto &events = earlier.diagnostics;
                for (const auto &e : recovery.diagnostics)
                    if (events.size() < 3)
                        events.append(e);
                if (failure) {
                    auto changes = earlier.changes;
                    for (const auto &d : recovery.changes)
                        if (changes.size() < 32)
                            changes.append(d);
                    Error merged(QString::fromStdString(earlier.what()) +
                                     "; recovery failed: " + recovery.what(),
                                 "operation_failed", changes);
                    merged.diagnostics = events;
                    throw merged;
                }
                recovery.diagnostics = events;
            }
            throw;
        }
    }
    if (failure)
        throw *failure;
    writeMessage({{"done", true}, {"kept", kept}});
}

class RuntimeLock
{
  public:
    RuntimeLock()
    {
        const auto runtime = qgetenv("XDG_RUNTIME_DIR");
        const auto path = runtime.isNull() ? QByteArray("/run/user/") + QByteArray::number(getuid()) : runtime;
        int directory = open(path.constData(), O_RDONLY | O_DIRECTORY | O_NOFOLLOW | O_CLOEXEC);
        struct stat info{};
        if (directory < 0 || fstat(directory, &info) || info.st_uid != getuid() || info.st_mode & 0077) {
            if (directory >= 0)
                close(directory);
            throw Error("A private user runtime directory is required");
        }
        fd = openat(directory, "doroshell-display.lock", O_CREAT | O_RDWR | O_NOFOLLOW | O_CLOEXEC, 0600);
        close(directory);
        if (fd < 0)
            throw Error("Cannot open private display lock");
        if (flock(fd, LOCK_EX | LOCK_NB)) {
            close(fd);
            throw Error("Another display confirmation is pending");
        }
    }
    ~RuntimeLock() { close(fd); }
    RuntimeLock(const RuntimeLock &) = delete;
    RuntimeLock &operator=(const RuntimeLock &) = delete;

  private:
    int fd;
};

int start(const QStringList &args)
{
    std::signal(SIGPIPE, SIG_IGN);
    try {
        if (args == QStringList{"query"}) {
            writeMessage(options(Commands{}.snapshot()));
            return 0;
        }
        if (args.size() != 2 || args[0] != "apply")
            throw Error("Expected query or apply JSON");
        RuntimeLock lock;
        std::signal(SIGTERM, cancel);
        std::signal(SIGINT, cancel);
        const auto request = QJsonDocument::fromJson(args[1].toUtf8());
        if (!request.isObject())
            throw Error("Invalid display request");
        guard(request.object());
        return 0;
    } catch (Error &error) {
        error.phase("preflight");
        writeMessage({{"error", QString::fromStdString(error.what())},
                      {"differences", error.changes},
                      {"diagnostics", error.diagnostics}});
        return 1;
    }
}
} // namespace
} // namespace display
int main(int argc, char **argv)
{
    QCoreApplication app(argc, argv);
    return display::start(app.arguments().mid(1));
}
