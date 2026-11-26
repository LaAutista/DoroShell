#include "cursor.hpp"
#include <QtCore>
#include <QtEndian>
#include <X11/Xcursor/Xcursor.h>
#include <iostream>
#include <zlib.h>

namespace {
void check(bool condition, const char *message) {
  if (!condition)
    throw std::runtime_error(message);
}
void put(const QString &path, QByteArray bytes) {
  check(QDir().mkpath(QFileInfo(path).absolutePath()), "mkdir");
  QFile f(path);
  check(f.open(QIODevice::WriteOnly) && f.write(bytes) == bytes.size(),
        "write fixture");
}
QByteArray get(const QString &path) {
  QFile f(path);
  check(f.open(QIODevice::ReadOnly), "read file");
  return f.readAll();
}
QByteArray be(quint32 value) {
  value = qToBigEndian(value);
  return QByteArray(reinterpret_cast<char *>(&value), 4);
}
QByteArray chunk(const QByteArray &name, const QByteArray &value) {
  auto body = name + value;
  return be(value.size()) + body +
         be(crc32(0, reinterpret_cast<const Bytef *>(body.constData()),
                  body.size()));
}
QByteArray png(const QImage &im) {
  QByteArray out;
  QBuffer b(&out);
  b.open(QIODevice::WriteOnly);
  check(im.save(&b, "PNG"), "encode image");
  return out;
}
QByteArray dataChunks(const QByteArray &png) {
  QByteArray result;
  for (int i = 8; i + 12 <= png.size();) {
    auto len = qFromBigEndian<quint32>(png.constData() + i);
    if (png.mid(i + 4, 4) == "IDAT")
      result += png.mid(i + 8, len);
    i += 12 + len;
  }
  return result;
}
QByteArray posterFixture() {
  QImage poster(30, 30, QImage::Format_ARGB32);
  poster.fill(Qt::blue);
  auto pngBytes = png(poster);
  QByteArray bytes = pngBytes.left(33) + chunk("acTL", be(2) + be(0)) +
                     chunk("IDAT", dataChunks(pngBytes));
  for (int i = 0; i < 2; ++i) {
    QImage tile(4, 4, QImage::Format_ARGB32);
    tile.fill(Qt::red);
    QByteArray control =
        be(2 * i) + be(4) + be(4) + be(i ? 18 : 4) + be(6) +
        QByteArray::fromHex(i ? "000401000100" : "000301000100");
    control[22] = char(0);
    control[23] = char(100);
    bytes += chunk("fcTL", control) +
             chunk("fdAT", be(2 * i + 1) + dataChunks(png(tile)));
  }
  return bytes + chunk("IEND", {});
}
void base(const QString &dir) {
  check(QDir().mkpath(dir + "/cursors"), "base mkdir");
  auto *img = XcursorImageCreate(30, 30);
  check(img, "base image");
  img->size = 30;
  img->xhot = 3;
  img->yhot = 2;
  for (int i = 0; i < 900; ++i)
    img->pixels[i] = i % 31 == 0 ? 0xffeeeeee : 0;
  auto *images = XcursorImagesCreate(1);
  images->images[0] = img;
  images->nimage = 1;
  check(XcursorFilenameSaveImages(QFile::encodeName(dir + "/cursors/default"),
                                  images),
        "base Xcursor");
  XcursorImagesDestroy(images);
}
} // namespace
int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  if (argc != 2)
    return 2;
  QTemporaryDir t;
  try {
    auto home = t.path() + "/home";
    check(t.isValid() && QDir().mkpath(home), "sandbox");
    qputenv("HOME", QFile::encodeName(home));
    qputenv("XDG_CONFIG_HOME", QFile::encodeName(home + "/.config"));
    auto baseDir = t.path() + "/base";
    base(baseDir);
    auto anim = t.path() + "/fixture.apng";
    put(anim, posterFixture());
    auto decoded = cursor::decode(anim);
    check(decoded.frames.size() == 2 && decoded.frames[0].delay == 30 &&
              decoded.frames[1].delay == 40,
          "poster and frame timing");
    check(decoded.frames[0].pixels.pixel(4, 6) == 0xffff0000 &&
              decoded.frames[1].pixels.pixel(4, 6) == 0 &&
              decoded.frames[1].pixels.pixel(18, 6) == 0xffff0000,
          "APNG disposal and canvas offsets");
    auto cfg = home + "/.config/lxqt/session.conf",
         theme = home + "/.icons/DoroShell-Loading/",
         receipt = home + "/.local/state/lxqt-comfort/cursor-install.json";
    put(cfg, "[Mouse]\ncursor_theme=base\n[Other]\ncustom=yes\n");
    auto original = get(cfg);
    auto run = [&](QStringList flags) {
      QProcess p;
      p.start(argv[1], QStringList{"--base", baseDir, "--home", home} + flags);
      check(p.waitForFinished(20000), "cursor CLI timeout");
      if (p.exitCode())
        std::cerr << p.readAllStandardError().constData();
      return p.exitCode();
    };
    check(!run({"--plan"}) && !QFileInfo::exists(theme) &&
              !QFileInfo::exists(receipt),
          "plan no writes; packaged APNG decodes");
    check(!run({"--plan", "--asset", "gif"}), "packaged GIF decodes");
    put(theme + "cursors/arrow", "prior arrow");
    QFile::setPermissions(theme + "cursors/arrow",
                          QFile::ReadOwner | QFile::WriteOwner);
    check(!run({"--image", anim, "--pink-pointer", "--apply"}), "apply");
    auto baseline = get(receipt);
    check(!run({"--image", anim, "--pink-pointer", "--apply"}) &&
              get(receipt) == baseline,
          "repeat preserves baseline");
    auto *images =
        XcursorFilenameLoadAllImages(QFile::encodeName(theme + "cursors/wait"));
    check(images && images->nimage == 10, "load actual Xcursor file");
    for (int i = 0; i < images->nimage; ++i) {
      auto *f = images->images[i];
      check(f->delay == (i % 2 ? 40 : 30) && f->xhot == f->size / 2 &&
                f->yhot == f->size / 2,
            "hotspot and delay");
      if (f->size == 30)
        check(f->pixels[6 * 30 + (i % 2 ? 18 : 4)] == 0xffff0000,
              "pixel matches APNG");
    }
    XcursorImagesDestroy(images);
    check(get(theme + "cursors/left_ptr") == get(theme + "cursors/default") &&
              get(theme + "cursors/watch") == get(theme + "cursors/wait"),
          "aliases");
    check(!run({"--gif", anim, "--apply"}) &&
              get(theme + "cursors/arrow") == "prior arrow" &&
              !QFileInfo::exists(theme + "cursors/default"),
          "restore previous optional pointer");
    auto managed = get(cfg);
    put(cfg, managed + "# personal\n");
    check(run({"--rollback"}) != 0 && get(cfg) == managed + "# personal\n",
          "conflict refused");
    put(cfg, managed);
    // Exercise either side of an interrupted RC2 apply checkpoint.
    auto rec = QJsonDocument::fromJson(get(receipt)).object();
    auto e = rec[".config/lxqt/session.conf"].toObject();
    e["pending_from"] = QString::fromLatin1(
        QCryptographicHash::hash(original, QCryptographicHash::Sha256).toHex());
    e["pending_mode"] = e["mode"];
    rec[".config/lxqt/session.conf"] = e;
    put(receipt, QJsonDocument(rec).toJson());
    put(cfg, original);
    check(!run({"--gif", anim, "--apply"}) && get(cfg) == managed,
          "interrupted receipt reapplied");
    check(!run({"--rollback"}) && get(cfg) == original &&
              get(theme + "cursors/arrow") == "prior arrow" &&
              !QFileInfo::exists(receipt) &&
              !QFileInfo::exists(theme + "cursors/wait"),
          "full rollback");
    auto linkHome = t.path() + "/symlink-home";
    QDir().mkpath(linkHome);
    QFile::link(t.path(), linkHome + "/.icons");
    bool rejected = false;
    try {
      cursor::change(linkHome, anim, baseDir, false, false, false);
    } catch (...) {
      rejected = true;
    }
    check(rejected, "refuse linked destinations");
  } catch (const std::exception &e) {
    std::cerr << e.what() << '\n';
    return 1;
  }
  return 0;
}
