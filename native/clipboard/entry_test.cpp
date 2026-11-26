#include "entry.hpp"
#include <QCoreApplication>
#include <cstdio>

int main(int argc, char **argv) {
  QCoreApplication app(argc, argv);
  QMimeData data;
  data.setText("ordinary");
  data.setHtml("<b>ordinary</b>");
  auto entry = clip::snapshot(&data);
  if (!entry || !entry->complete)
    return 1;
  auto decoded = clip::decode(clip::encode(*entry));
  if (!decoded || decoded->identity() != entry->identity())
    return 2;
  data.setData("arbitrary", "original");
  if (clip::snapshot(&data)->complete)
    return 3;
  data.setData("x-kde-passwordManagerHint", "secret");
  if (clip::snapshot(&data))
    return 4;
  QMimeData files;
  files.setText("file:///example");
  files.setData("x-special/gnome-copied-files", "cut\nfile:///example");
  auto captured = clip::snapshot(&files);
  if (!captured || captured->mime(true)->data("x-special/gnome-copied-files") !=
                       "copy\nfile:///example")
    return 5;
  if (captured->mime(false)->data("x-special/gnome-copied-files") !=
      "cut\nfile:///example")
    return 6;
  QImage image(32, 40, QImage::Format_ARGB32);
  image.fill(Qt::red);
  QMimeData picture;
  picture.setImageData(image);
  auto photo = clip::snapshot(&picture);
  if (!photo || !photo->complete)
    return 7;
  auto restored = clip::decode(clip::encode(*photo));
  if (!restored || restored->image != image)
    return 8;
  return 0;
}
