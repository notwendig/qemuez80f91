#include "network.h"
#include "common.h"
#include <QtEndian>

namespace ez80 {
QJsonArray dhcpLeases(const QString &path) {
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly))
        return {};
    auto data = file.readAll();
    if (data.size() < 24)
        return {};
    auto magic = data.first(4).toHex();
    if (magic != "d4c3b2a1" && magic != "a1b2c3d4")
        return {};
    auto u8 = [](const QByteArray &b, int at) { return quint8(b[at]); };
    auto be16 = [](const QByteArray &b, int at) {
        return qFromBigEndian<quint16>(b.constData() + at);
    };
    auto ipText = [](const QByteArray &b) {
        return QHostAddress(qFromBigEndian<quint32>(b.constData())).toString();
    };
    QJsonArray leases;
    qsizetype at = 24;
    while (at + 16 <= data.size()) {
        quint32 length = magic == "d4c3b2a1" ? qFromLittleEndian<quint32>(data.constData() + at + 8)
                                             : qFromBigEndian<quint32>(data.constData() + at + 8);
        at += 16;
        if (length > quint64(data.size() - at))
            break;
        auto frame = data.mid(at, length);
        at += length;
        if (frame.size() < 42 || frame.mid(12, 2) != QByteArray::fromHex("0800"))
            continue;
        auto ip = frame.mid(14);
        int ihl = (u8(ip, 0) & 15) * 4;
        if (ihl < 20 || u8(ip, 9) != 17 || ip.size() < ihl + 8)
            continue;
        if (be16(ip, ihl) != 67 || be16(ip, ihl + 2) != 68)
            continue;
        int size = be16(ip, ihl + 4);
        if (size < 8 || ihl + size > ip.size())
            continue;
        auto boot = ip.mid(ihl + 8, size - 8);
        if (boot.size() < 240 || u8(boot, 0) != 2 ||
            boot.mid(236, 4) != QByteArray::fromHex("63825363"))
            continue;
        QMap<int, QByteArray> options;
        bool valid = true;
        for (int pos = 240; pos < boot.size();) {
            int kind = u8(boot, pos++);
            if (kind == 255)
                break;
            if (kind == 0)
                continue;
            if (pos >= boot.size()) {
                valid = false;
                break;
            }
            int count = u8(boot, pos++);
            if (pos + count > boot.size()) {
                valid = false;
                break;
            }
            options[kind] = boot.mid(pos, count);
            pos += count;
        }
        if (!valid || options.value(53) != QByteArray(1, '\x05'))
            continue;
        auto server = options.value(54, ip.mid(12, 4));
        if (server.size() != 4)
            continue;
        QStringList mac;
        for (unsigned char c : boot.mid(28, 6))
            mac << QString("%1").arg(c, 2, 16, QChar('0'));
        QJsonObject lease{{"server", ipText(server)},
                          {"address", ipText(boot.mid(16, 4))},
                          {"mac", mac.join(':')}};
        if (!leases.contains(lease))
            leases.append(lease);
    }
    return leases;
}
NetworkTest::NetworkTest(const QString &expected, quint16 udpNumber, quint16 tcpNumber)
    : server(expected), udpPort(udpNumber), tcpPort(tcpNumber) {
    timeout.setSingleShot(true);
    connect(&timeout, &QTimer::timeout, this, [this] {
        errorText = "Echo-Zeitlimit überschritten";
        emit failed(errorText);
    });
    connect(&tcp, &QTcpSocket::connected, this, [this] { tcp.write(pattern); });
    connect(&tcp, &QTcpSocket::errorOccurred, this, [this] {
        errorText = tcp.errorString();
        emit failed(errorText);
    });
    connect(&udp, &QUdpSocket::errorOccurred, this, [this] {
        errorText = udp.errorString();
        emit failed(errorText);
    });
    connect(&tcp, &QTcpSocket::readyRead, this, [this] {
        received += tcp.readAll();
        if (received.size() >= pattern.size()) {
            timeout.stop();
            tcp.disconnectFromHost();
            if (received != pattern) {
                errorText = "TCP-Echo ist nicht bytegleich";
                emit failed(errorText);
            } else
                tcpOk = complete = true;
        }
    });
    connect(&udp, &QUdpSocket::readyRead, this, [this] {
        received += udp.readAll();
        if (received.size() >= pattern.size()) {
            timeout.stop();
            if (received != pattern) {
                errorText = "UDP-Echo ist nicht bytegleich";
                emit failed(errorText);
            } else
                udpOk = true;
        }
    });
}
void NetworkTest::exchange(bool stream) {
    pattern.resize(stream ? 4000 : 1000);
    received.clear();
    for (int i = 0; i < pattern.size(); ++i)
        pattern[i] = char(i % 251);
    timeout.start(8000);
    if (stream)
        tcp.connectToHost(address, tcpPort);
    else {
        udp.connectToHost(address, udpPort);
        udp.write(pattern);
    }
}
void NetworkTest::advance(const QByteArray &output, const QJsonArray &leases,
                          const std::function<void(QByteArray)> &send) {
    for (auto value : leases) {
        auto lease = value.toObject();
        if (lease["mac"] == "00:90:23:00:01:01" && lease["server"] == server)
            address = lease["address"].toString();
    }
    if (login == 0 && output.contains("Login:")) {
        send("anonymous\r");
        login = 1;
    } else if (login == 1 && output.contains("Password:")) {
        send("anonymous\r");
        login = 2;
    }
    if (!readyTime.isValid() && output.contains("ZTP "))
        readyTime.start();
    if (stage == 0 && !address.isEmpty() && readyTime.isValid() && readyTime.elapsed() > 500) {
        mark = output.size();
        send("bsdudpserver\r");
        stage = 1;
    } else if ((stage == 1 || stage == 4) &&
               output.mid(mark).contains("Enter the server's port number to listen:")) {
        send(stage == 1 ? "4000\r" : "4001\r");
        ++stage;
    } else if (stage == 2 && output.mid(mark).contains("Server is bound to the port 4000")) {
        exchange(false);
        stage = 3;
    } else if (stage == 3 && udpOk && output.contains("Sent 1000 bytes")) {
        mark = output.size();
        send("bsdtcpserver\r");
        stage = 4;
    } else if (stage == 5 && output.mid(mark).contains("Server is Listening on port 4001")) {
        exchange(true);
        stage = 6;
    }
}
QJsonObject NetworkTest::report() const {
    return {{"dhcp_verified", !address.isEmpty()},
            {"address", address.isEmpty() ? QJsonValue() : QJsonValue(address)},
            {"udp_echo_ok", udpOk},
            {"tcp_echo_ok", tcpOk},
            {"error", errorText.isEmpty() ? QJsonValue() : QJsonValue(errorText)}};
}
} // namespace ez80
