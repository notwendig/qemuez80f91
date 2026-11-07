#pragma once
#include <QtWidgets>

namespace ez80 {
// Fixed cells keep CR, backspace and ANSI cursor addressing usable for CP/M.
class Terminal : public QAbstractScrollArea {
    Q_OBJECT
    struct Attributes {
        int foreground = -1, background = -1;
        bool bold = false, dim = false, italic = false, underline = false, inverse = false;
        bool operator==(const Attributes &other) const {
            return foreground == other.foreground && background == other.background &&
                   bold == other.bold && dim == other.dim && italic == other.italic &&
                   underline == other.underline && inverse == other.inverse;
        }
    } attributes, savedAttributes;
    struct Cell {
        QChar character = ' ';
        Attributes attributes;
    };
    using Line = QVector<Cell>;
    QList<Line> history;
    QVector<Line> screen;
    int row = 0, column = 0, savedRow = 0, savedColumn = 0;
    int columns = 80, rows = 40, cellWidth = 9, cellHeight = 18;
    bool interruptStopsSession = true, carriageReturnOnLinefeed = false;
    QByteArray escape;
    bool inEscape = false, inOsc = false, cursorVisible = true;
    Line blankLine() const;
    static QColor color(int value, bool background = false);
    void rendition(const QList<QByteArray> &fields);
    void newline();
    void csi(char command);

  protected:
    void paintEvent(QPaintEvent *) override;
    void keyPressEvent(QKeyEvent *) override;

  public:
    explicit Terminal(QWidget *parent = nullptr, QSize characters = QSize(80, 40));
    void feed(const QByteArray &data);
    QString text() const;
    QSize characterSize() const { return {columns, rows}; }
    void setInterruptStopsSession(bool enabled) { interruptStopsSession = enabled; }
    void setCarriageReturnOnLinefeed(bool enabled) { carriageReturnOnLinefeed = enabled; }
  signals:
    void input(const QByteArray &data);
    void stopRequested();
};
} // namespace ez80
