#pragma once
#include <QtCore>
#include <QtNetwork>
#include <functional>
namespace ez80 {
QJsonArray dhcpLeases(const QString &path);
class NetworkTest : public QObject {
    Q_OBJECT
    QString server, address, errorText;
    int stage = 0, login = 0, mark = 0;
    quint16 udpPort, tcpPort;
    bool udpOk = false, tcpOk = false, complete = false;
    QElapsedTimer readyTime;
    QTcpSocket tcp;
    QUdpSocket udp;
    QTimer timeout;
    QByteArray pattern, received;
    void exchange(bool stream);

  public:
    explicit NetworkTest(const QString &server, quint16 udpPort = 4000, quint16 tcpPort = 4001);
    void advance(const QByteArray &output, const QJsonArray &leases,
                 const std::function<void(QByteArray)> &send);
    bool done() const { return complete; }
    QJsonObject report() const;
  signals:
    void failed(const QString &error);
};
} // namespace ez80
