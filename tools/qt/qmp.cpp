#include "qmp.h"

namespace ez80 {
Qmp::Qmp(QObject *parent) : QObject(parent) {
    connect(&socket, &QLocalSocket::readyRead, this, [this] {
        buffer += socket.readAll();
        while (buffer.contains('\n')) {
            int end = buffer.indexOf('\n');
            auto line = buffer.left(end);
            buffer.remove(0, end + 1);
            QJsonParseError parse;
            auto doc = QJsonDocument::fromJson(line, &parse);
            if (parse.error || !doc.isObject()) {
                emit error("Ungültige QMP-Antwort");
                continue;
            }
            auto reply = doc.object();
            if (!greeted) {
                if (!reply.contains("QMP")) {
                    emit error("Ungültige QMP-Begrüßung");
                    continue;
                }
                greeted = true;
                call("qmp_capabilities", {}, [this](QJsonValue) {
                    ready = true;
                    call("qom-list", {{"path", "/machine/unattached"}}, [this](QJsonValue value) {
                        for (auto child : value.toArray()) {
                            auto item = child.toObject();
                            if (item["type"] == "child<ez80f91-memory>") {
                                memoryPath = "/machine/unattached/" + item["name"].toString();
                                if (haveButtonState)
                                    buttons(pendingButtons);
                                break;
                            }
                        }
                    });
                    emit connected();
                });
            } else if (reply.contains("id")) {
                auto cb = callbacks.take(reply["id"].toInt());
                if (reply.contains("error"))
                    emit error(reply["error"].toObject()["desc"].toString());
                else if (cb)
                    cb(reply["return"]);
            }
        }
    });
    connect(&socket, &QLocalSocket::errorOccurred, this,
            [this] { emit error(socket.errorString()); });
    connect(&socket, &QLocalSocket::disconnected, this, [this] {
        ready = false;
        emit error("QMP-Verbindung beendet");
    });
}
void Qmp::open(const QString &path) {
    if (socket.state() != QLocalSocket::UnconnectedState && socket.serverName() == path)
        return;
    socket.abort();
    ready = greeted = false;
    buffer.clear();
    callbacks.clear();
    memoryPath.clear();
    socket.connectToServer(path);
}
void Qmp::call(const QString &command, const QJsonObject &args,
               std::function<void(QJsonValue)> done) {
    if (socket.state() != QLocalSocket::ConnectedState) {
        emit error("QMP nicht verbunden");
        return;
    }
    int id = ++nextId;
    callbacks.insert(id, std::move(done));
    QJsonObject message{{"execute", command}, {"id", id}};
    if (!args.isEmpty())
        message["arguments"] = args;
    socket.write(QJsonDocument(message).toJson(QJsonDocument::Compact) + '\n');
    QTimer::singleShot(5000, this, [this, id] {
        if (callbacks.remove(id))
            emit error("QMP-Antwortzeit überschritten");
    });
}
void Qmp::buttons(int mask) {
    pendingButtons = mask;
    haveButtonState = true;
    if (!ready) {
        emit error("Emulator nicht erreichbar");
        return;
    }
    if (!memoryPath.isEmpty())
        call("qom-set", {{"path", memoryPath}, {"property", "kit-buttons"}, {"value", mask}});
}
void Qmp::flush() {
    socket.flush();
    if (socket.bytesToWrite())
        socket.waitForBytesWritten(200);
}
} // namespace ez80
