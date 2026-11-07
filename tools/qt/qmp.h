#pragma once
#include <QtCore>
#include <QLocalSocket>
#include <functional>

namespace ez80 {
class Qmp : public QObject {
    Q_OBJECT
    QLocalSocket socket;
    QByteArray buffer;
    int nextId = 0;
    QHash<int, std::function<void(QJsonValue)>> callbacks;
    bool greeted = false;
    QString memoryPath;
    int pendingButtons = 0;
    bool haveButtonState = false;

  public:
    explicit Qmp(QObject *parent = nullptr);
    void open(const QString &path);
    void call(const QString &command, const QJsonObject &args = {},
              std::function<void(QJsonValue)> done = {});
    void buttons(int mask);
    void flush();
    bool ready = false;
  signals:
    void connected();
    void error(const QString &message);
};
} // namespace ez80
