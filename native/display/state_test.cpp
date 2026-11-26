// SPDX-License-Identifier: GPL-2.0-or-later
#include "state.hpp"
#include <QJsonDocument>
#include <cstdio>

int main()
{
    using namespace display;
    const QByteArray raw = "Screen 0: minimum 8 x 8, current 1920 x 1080, maximum 32767 x 32767\n"
                           "DP-0 connected primary 1920x1080+0+0 (0x11) normal (normal left inverted right x "
                           "axis y axis) 500mm x 300mm\n"
                           "\tCRTC: 0\n\tTimestamp: 12\n"
                           "  1920x1080 (0x11) 148.500MHz +HSync +VSync *current\n"
                           "        h: width 1920 start 2008 end 2052 total 2200 skew 0 clock 67.50KHz\n"
                           "        v: height 1080 start 1084 end 1089 total 1125 clock 60.00Hz\n"
                           "  1920x1080 (0x12) 148.500MHz +HSync +VSync\n"
                           "        h: width 1920 start 2008 end 2052 total 2200 skew 0 clock 67.50KHz\n"
                           "        v: height 1080 start 1084 end 1089 total 1125 clock 144.00Hz\n";
    auto require = [](bool value, const char *message) {
        if (!value)
            throw std::runtime_error(message);
    };
    try {
        auto baseline = parse(raw);
        baseline.values["vsync"] = 1;
        baseline.values["vsync_reason"] = "";
        require(token(baseline) == "f4c706d8ba8a4b273f29471d2a2e597a89e7c4aa2d8a9fde1a2ddeb767b7afb3",
                "State token differs from RC2 fixture");
        auto publicState = options(baseline);
        auto out = publicState["outputs"].toArray().at(0).toObject();
        require(out["current"] == "0x11" && out["modes"].toArray().size() == 2, "Lost compatible mode");
        auto changed = parse(QByteArray(raw).replace("500mm x 300mm", "490mm x 310mm"));
        require(changed.values["layout"] == baseline.values["layout"] &&
                    changed.values["outputs"] != baseline.values["outputs"],
                "NVIDIA mode-specific sizes must be independently protected");
        auto protectedEdid = parse(raw + "\tEDID: private-serial\n\tColorspace: Original\n");
        auto differentEdid = parse(raw + "\tEDID: other-serial\n\tColorspace: Changed\n");
        auto diff = differences(protectedEdid, differentEdid);
        const auto redacted = QJsonDocument(diff).toJson();
        require(redacted.contains("Colorspace") && redacted.contains("other protected properties") &&
                    !redacted.contains("serial") && !redacted.contains("Changed"),
                "Invalid protected-property diagnostics");
        require(parse(QByteArray(raw).replace("Timestamp: 12", "Timestamp: 999")).values["layout"] ==
                    baseline.values["layout"],
                "Timestamp changed layout token");
        require(
            options(parse(QByteArray(raw).replace("+VSync *current", "+VSync Interlace *current")))["outputs"]
                .toArray()
                .isEmpty(),
            "Interlaced current mode accepted");
        const auto cloned = raw + QByteArray(raw.mid(raw.indexOf("DP-0"))).replace("DP-0", "DP-1");
        require(options(parse(cloned))["outputs"].toArray().isEmpty(), "Shared CRTC exposed");
        try {
            parse(QByteArray(raw).replace("DP-0", "XWAYLAND0"));
            return 1;
        } catch (const Error &) {
        }
        try {
            parse(raw.left(raw.lastIndexOf("v: height")));
            return 1;
        } catch (const Error &) {
        }
    } catch (const std::exception &e) {
        std::fprintf(stderr, "%s\n", e.what());
        return 1;
    }
    return 0;
}
