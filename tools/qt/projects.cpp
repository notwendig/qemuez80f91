#include "projects.h"
#include <QtXml>

namespace ez80 {
static QDomDocument xml(const QString &path) {
    QDomDocument doc;
    auto result = doc.setContent(readFile(path));
    if (!result)
        fail("Ungültiges XML: " + path);
    return doc;
}
static void text(QDomElement element, const QString &value) {
    while (!element.firstChild().isNull())
        element.removeChild(element.firstChild());
    element.appendChild(element.ownerDocument().createTextNode(value));
}
static QDomElement child(QDomElement parent, const QString &tag, const QString &attribute,
                         const QString &value) {
    for (auto e = parent.firstChildElement(tag); !e.isNull(); e = e.nextSiblingElement(tag))
        if (e.attribute(attribute) == value)
            return e;
    fail("ZDS-Projekt: " + tag + " " + value + " fehlt");
}
void prepareDemo(Options &o) {
    if (o.out.isEmpty())
        o.out = rootPath() + "/build/ztp-tcpudp-ram";
    o.out = QFileInfo(o.out).absoluteFilePath();
    QDir().mkpath(o.out);
    bool valid = false;
    try {
        auto m = readObject(o.out + "/build.json");
        valid =
            m["filesystem"] == "ram" && m["memory_profile"] == "qemu" &&
            QFileInfo(m["project"].toString()).absoluteFilePath() ==
                QFileInfo(o.zds + "/ZTP2.5.1/ZTP/SamplePrograms/TCPUDPDemo").absoluteFilePath() &&
            digest(o.out + "/tcpudp.bin") == m["sha256"].toString();
    } catch (const std::exception &) {
    }
    if (o.rebuild || !valid)
        runCommand("python3",
                   {rootPath() + "/examples/ztp_tcpudp/build.py", "--zds",
                    QFileInfo(o.zds).absoluteFilePath(), "--filesystem", "ram", "--out", o.out});
}
void prepareF24(Options &o) {
    if (o.out.isEmpty())
        o.out = rootPath() + "/build/f24";
    o.out = QFileInfo(o.out).absoluteFilePath();
    QDir().mkpath(o.out);
    bool valid = false;
    try {
        auto m = readObject(o.out + "/camel.json");
        valid = QFileInfo::exists(o.out + "/camel.lod") &&
                digest(o.out + "/camel.bin") == m["binary_sha256"].toString() &&
                m["upstream_commit"] == "af47e6520adc220cef5ee7e9ab96f0c336f7e299";
        auto sources = m["sources"].toObject();
        if (sources.isEmpty())
            valid = false;
        for (auto i = sources.begin(); i != sources.end(); ++i)
            valid = valid && digest(o.out + '/' + i.key()) == i.value().toString();
        for (auto name : {"kit.inc", "kit_font.inc"})
            valid = valid &&
                    sources[name].toString() == digest(rootPath() + "/examples/camelf91/" + name);
    } catch (const std::exception &) {
        valid = false;
    }
    if (o.rebuild || !valid)
        runCommand("python3", {rootPath() + "/examples/camelf91/build.py", "--zds", o.zds, "--out",
                               o.out, "--wine-prefix", o.winePrefix, "--debug-info"});
    auto doc = xml(rootPath() + "/subprojects/CAMELF91_24/camel_f91.zdsproj");
    auto root = doc.documentElement();
    root.setAttribute("configuration", "Debug");
    auto files = root.firstChildElement("files");
    while (!files.firstChild().isNull())
        files.removeChild(files.firstChild());
    for (auto module : {"CAMLF91d", "CAMLF91e", "CAMLF91h", "CAMLF91t", "cstartup",
                        "init_params_f91", "vectors24", "zsldevinitdummy", "poll_bsp"}) {
        auto f = doc.createElement("file");
        f.setAttribute("filter-key", "");
        text(f, QString(module) + ".asm");
        files.appendChild(f);
    }
    auto configs = root.firstChildElement("configurations");
    for (auto node = configs.firstChild(); !node.isNull();) {
        auto next = node.nextSibling();
        if (node.toElement().attribute("name") != "Debug")
            configs.removeChild(node);
        node = next;
    }
    auto config = configs.firstChildElement();
    if (config.isNull())
        fail("ZDS-Projekt: Debug-Konfiguration fehlt");
    auto option = [&](const QString &tool, const QString &name, const QString &value) {
        auto opts = child(config.firstChildElement("tools"), "tool", "name", tool)
                        .firstChildElement("options");
        QDomElement found;
        for (auto e = opts.firstChildElement("option"); !e.isNull();
             e = e.nextSiblingElement("option"))
            if (e.attribute("name") == name) {
                found = e;
                break;
            }
        if (found.isNull()) {
            found = doc.createElement("option");
            found.setAttribute("name", name);
            found.setAttribute("type", "string");
            found.setAttribute("change-action", "none");
            opts.appendChild(found);
        }
        text(found, value);
    };
    option("General", "outputdir", ".\\");
    option("Assembler", "include",
           ".;" + windowsPath(o.zds + "/include/zilog") + ';' +
               windowsPath(o.zds + "/include/std"));
    option("Assembler", "define", "FLASHED=0,_EZ80ACCLAIM!=1,_DEBUG");
    option("Debugger", "target", "QEMU_CAMEL24");
    option("Debugger", "debugtool", "EthernetSmartCable");
    option("Linker", "of", "camel");
    option("Linker", "createnew", "false");
    option("Linker", "linkctlfile", "camel.linkcmd");
    option("Linker", "objlibmods", windowsPath(o.zds + "/lib/std/chelpD.lib"));
    option("Linker", "exeform", "OMF695,INTEL32");
    auto breaks = root.firstChildElement("breakpoints");
    while (!breaks.firstChild().isNull())
        breaks.removeChild(breaks.firstChild());
    writeFile(o.out + "/camel24.zdsproj", doc.toByteArray(2));
    auto target = xml(rootPath() + "/subprojects/CAMELF91_24/eZ80F91_99C0879_Debug.ztgt");
    target.documentElement().setAttribute("name", "QEMU_CAMEL24");
    text(target.documentElement()
             .firstChildElement("ExtFlash")
             .firstChildElement("externalAutoSelect"),
         "false");
    writeFile(o.out + "/QEMU_CAMEL24.ztgt", target.toByteArray(2));
    QStringList commands = {"cd \"" + windowsPath(o.out) + "\"",
                            "log \"" + windowsPath(o.out + "/zds-session.log") + "\"",
                            "log on",
                            "open project \"camel24.zdsproj\"",
                            "debugtool set \"EthernetSmartCable\"",
                            "debugtool set \"ipAddress\" \"127.0.0.1\"",
                            "reset",
                            "print \"F24_READY PC=%x\" reg PC",
                            "log off"};
    writeFile(o.out + "/start.cmd", (commands.join('\n') + '\n').toUtf8());
}
} // namespace ez80
