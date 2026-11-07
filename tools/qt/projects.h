#pragma once
#include "common.h"
namespace ez80 {
struct Options {
    QString mode = "start", qemu = defaultQemu(), zds = defaultZds(), out, dev, hostname;
    QString bridge = "br0", helper = "/usr/libexec/qemu-bridge-helper", server = "192.168.77.1";
    QString winePrefix = "/tmp/qemuez80f91-zds-wine", nic = "none", bios,
            machine = "ez80f91-minimal";
    QString state, serial, fsRoot = rootPath() + "/cpm-files";
    QStringList cs = {"", "", "", ""};
    int port = 4040, devport = 0x1000;
    double seconds = 0;
    bool run = false, kit = false, headless = false, rebuild = false, prepareOnly = false;
    bool test = false, debug = false, noViews = false;
};
void prepareDemo(Options &options);
void prepareF24(Options &options);
} // namespace ez80
