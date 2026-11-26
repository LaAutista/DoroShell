// SPDX-License-Identifier: GPL-2.0-or-later
#include "import.hpp"
#include <QDeadlineTimer>
#include <QFile>
#include <QTemporaryFile>
#include <cerrno>
#include <fcntl.h>
#include <poll.h>
#include <signal.h>
#include <spawn.h>
#include <sys/wait.h>
#include <unistd.h>

extern char **environ;

bool importScreenshot(const QImage &image, const QString &editor, int timeoutMs) {
    QTemporaryFile png;
    if (!png.open() || !image.save(&png, "PNG") || !png.flush() ||
        png.size() > 256LL * 1024 * 1024 || !png.seek(0))
        return false;
    int ack[2];
    if (pipe2(ack, O_CLOEXEC))
        return false;
    posix_spawn_file_actions_t files;
    pid_t pid = -1;
    QByteArray binary = QFile::encodeName(editor);
    char option[] = "--import-png";
    char *args[] = {binary.data(), option, nullptr};
    if (posix_spawn_file_actions_init(&files) == 0) {
        if (posix_spawn_file_actions_adddup2(&files, png.handle(), STDIN_FILENO) == 0 &&
            posix_spawn_file_actions_adddup2(&files, ack[1], STDOUT_FILENO) == 0 &&
            posix_spawn(&pid, args[0], &files, nullptr, args, environ) != 0)
            pid = -1;
        posix_spawn_file_actions_destroy(&files);
    }
    close(ack[1]);
    bool accepted = false;
    if (pid > 0) {
        QDeadlineTimer deadline(timeoutMs);
        QByteArray answer;
        const QByteArray expected("IMPORTED\n");
        pollfd fd{ack[0], POLLIN, 0};
        while (!deadline.hasExpired() && answer.size() < expected.size()) {
            int ready = poll(&fd, 1, int(deadline.remainingTime()));
            if (ready < 0 && errno == EINTR)
                continue;
            char buf[32];
            if (ready <= 0)
                break;
            auto count = read(ack[0], buf, sizeof(buf));
            if (count <= 0)
                break;
            answer.append(buf, count);
            if (!expected.startsWith(answer))
                break;
        }
        accepted = answer == expected;
        if (!accepted) {
            kill(pid, SIGKILL);
            while (waitpid(pid, nullptr, 0) == -1 && errno == EINTR) {}
        }
    }
    close(ack[0]);
    return accepted;
}
