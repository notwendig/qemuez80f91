#include "terminal.h"

namespace ez80 {
Terminal::Terminal(QWidget *parent, QSize characters) : QAbstractScrollArea(parent) {
    columns = qMax(1, characters.width());
    rows = qMax(1, characters.height());
    setFont(QFontDatabase::systemFont(QFontDatabase::FixedFont));
    auto f = font();
    f.setPointSize(11);
    if (rows > 24) {
        // Keep 80-column alignment while fitting forty rows above the kit controls.
        int width = QFontMetrics(f).horizontalAdvance('M');
        f.setPointSize(9);
        f.setLetterSpacing(QFont::AbsoluteSpacing,
                           qMax(0.0, width - QFontMetricsF(f).horizontalAdvance('M')));
    }
    setFont(f);
    QFontMetrics fm(font());
    cellWidth = qRound(QFontMetricsF(font()).horizontalAdvance(QStringLiteral("MM")) / 2);
    cellHeight = fm.height();
    screen.fill(blankLine(), rows);
    setFocusPolicy(Qt::StrongFocus);
    setVerticalScrollBarPolicy(Qt::ScrollBarAlwaysOn);
    setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    setFixedSize(columns * cellWidth + 22, rows * cellHeight + 8);
    connect(verticalScrollBar(), &QScrollBar::valueChanged, viewport(),
            qOverload<>(&QWidget::update));
    setContextMenuPolicy(Qt::CustomContextMenu);
    connect(this, &QWidget::customContextMenuRequested, this, [this](QPoint point) {
        QMenu menu;
        menu.addAction("Bildschirm kopieren", this,
                       [this] { QApplication::clipboard()->setText(text()); });
        menu.addAction("Einfügen", this, [this] {
            emit input(QApplication::clipboard()
                           ->text()
                           .replace("\r\n", "\n")
                           .replace('\n', '\r')
                           .toLatin1());
        });
        menu.exec(mapToGlobal(point));
    });
}
Terminal::Line Terminal::blankLine() const {
    return Line(columns, Cell{' ', attributes});
}
QString Terminal::text() const {
    QStringList lines;
    for (const auto &line : screen) {
        QString text;
        for (const auto &cell : line)
            text += cell.character;
        lines << text;
    }
    return lines.join('\n');
}
QColor Terminal::color(int value, bool background) {
    static const char *palette[] = {
        "#000000", "#cd0000", "#00cd00", "#cdcd00", "#0000ee", "#cd00cd", "#00cdcd", "#e5e5e5",
        "#7f7f7f", "#ff0000", "#00ff00", "#ffff00", "#5c5cff", "#ff00ff", "#00ffff", "#ffffff"};
    if (value < 0)
        return QColor(background ? "#111c22" : "#d4e5de");
    if (value >= 0x1000000)
        return QColor::fromRgb(value & 0xffffff);
    if (value < 16)
        return QColor(palette[value]);
    if (value < 232) {
        static const int levels[] = {0, 95, 135, 175, 215, 255};
        int cube = value - 16;
        return QColor(levels[cube / 36], levels[(cube / 6) % 6], levels[cube % 6]);
    }
    int gray = 8 + 10 * (value - 232);
    return QColor(gray, gray, gray);
}
void Terminal::rendition(const QList<QByteArray> &fields) {
    for (int i = 0; i < fields.size(); ++i) {
        bool ok = true;
        int code = fields[i].isEmpty() ? 0 : fields[i].toInt(&ok);
        if (!ok)
            continue;
        switch (code) {
        case 0: attributes = {}; break;
        case 1: attributes.bold = true; break;
        case 2: attributes.dim = true; break;
        case 3: attributes.italic = true; break;
        case 4: attributes.underline = true; break;
        case 7: attributes.inverse = true; break;
        case 22: attributes.bold = attributes.dim = false; break;
        case 23: attributes.italic = false; break;
        case 24: attributes.underline = false; break;
        case 27: attributes.inverse = false; break;
        case 39: attributes.foreground = -1; break;
        case 49: attributes.background = -1; break;
        case 38:
        case 48: {
            int value = -1;
            if (i + 2 < fields.size() && fields[i + 1] == "5") {
                int index = fields[i + 2].toInt(&ok);
                if (ok && index >= 0 && index <= 255)
                    value = index;
                i += 2;
            } else if (i + 4 < fields.size() && fields[i + 1] == "2") {
                int rgb[3];
                bool valid = true;
                for (int c = 0; c < 3; ++c) {
                    rgb[c] = fields[i + 2 + c].toInt(&ok);
                    valid = valid && ok && rgb[c] >= 0 && rgb[c] <= 255;
                }
                if (valid)
                    value = 0x1000000 | rgb[0] << 16 | rgb[1] << 8 | rgb[2];
                i += 4;
            }
            if (value >= 0) {
                if (code == 38)
                    attributes.foreground = value;
                else
                    attributes.background = value;
            }
            break;
        }
        default:
            if (code >= 30 && code <= 37) attributes.foreground = code - 30;
            else if (code >= 40 && code <= 47) attributes.background = code - 40;
            else if (code >= 90 && code <= 97) attributes.foreground = code - 90 + 8;
            else if (code >= 100 && code <= 107) attributes.background = code - 100 + 8;
            break;
        }
    }
}
void Terminal::newline() {
    if (++row < rows)
        return;
    history.append(screen.takeFirst());
    if (history.size() > 5000)
        history.removeFirst();
    screen.append(blankLine());
    row = rows - 1;
}
void Terminal::csi(char command) {
    auto fields = escape.mid(1).split(';');
    auto number = [&](int i, int fallback = 1) {
        if (i >= fields.size())
            return fallback;
        bool ok;
        int n = fields[i].toInt(&ok);
        return ok && n > 0 ? qMin(n, 10000) : fallback;
    };
    int count = number(0);
    switch (command) {
    case 'A':
        row = qMax(0, row - count);
        break;
    case 'B':
        row = qMin(rows - 1, row + count);
        break;
    case 'C':
        column = qMin(columns - 1, column + count);
        break;
    case 'D':
        column = qMax(0, column - count);
        break;
    case 'G':
        column = qBound(0, count - 1, columns - 1);
        break;
    case 'd':
        row = qBound(0, count - 1, rows - 1);
        break;
    case 'H':
    case 'f':
        row = qBound(0, count - 1, rows - 1);
        column = qBound(0, number(1) - 1, columns - 1);
        break;
    case 'J': {
        int mode = number(0, 0);
        if (mode == 2 || mode == 3) {
            screen.fill(blankLine());
            if (mode == 3)
                history.clear();
        } else if (mode == 0) {
            for (int r = row + 1; r < rows; ++r)
                screen[r] = blankLine();
            for (int c = column; c < columns; ++c)
                screen[row][c] = Cell{' ', attributes};
        } else if (mode == 1) {
            for (int r = 0; r < row; ++r)
                screen[r] = blankLine();
            for (int c = 0; c <= qMin(column, columns - 1); ++c)
                screen[row][c] = Cell{' ', attributes};
        }
        break;
    }
    case 'K': {
        int mode = number(0, 0);
        int start = mode == 0 ? qMin(column, columns) : 0;
        int end = mode == 1 ? qMin(column + 1, columns) : columns;
        if (mode >= 0 && mode <= 2)
            for (int c = start; c < end; ++c)
                screen[row][c] = Cell{' ', attributes};
        break;
    }
    case 'm':
        rendition(fields);
        break;
    case 'h':
    case 'l':
        if (escape == "[?25")
            cursorVisible = command == 'h';
        break;
    case 's':
        savedRow = row;
        savedColumn = column;
        break;
    case 'u':
        row = savedRow;
        column = savedColumn;
        break;
    default:
        break; // Unsupported terminal modes are consumed without printing them.
    }
}
void Terminal::feed(const QByteArray &data) {
    for (unsigned char ch : data) {
        if (inOsc) {
            if (ch == 7 || (ch == '\\' && escape.endsWith('\x1b'))) {
                inOsc = false;
                escape.clear();
            } else {
                escape = QByteArray(1, char(ch));
            }
            continue;
        }
        if (inEscape) {
            if (escape.isEmpty() && ch == ']') {
                inOsc = true;
                inEscape = false;
                continue;
            }
            if (escape.isEmpty() && ch == '[') {
                escape += char(ch);
                continue;
            }
            if (escape.startsWith('[')) {
                if (ch >= 0x40 && ch <= 0x7e) {
                    csi(char(ch));
                    inEscape = false;
                    escape.clear();
                } else if (escape.size() < 64)
                    escape += char(ch);
                else {
                    inEscape = false;
                    escape.clear();
                }
            } else {
                if (ch == '7') {
                    savedRow = row;
                    savedColumn = column;
                    savedAttributes = attributes;
                }
                if (ch == '8') {
                    row = savedRow;
                    column = savedColumn;
                    attributes = savedAttributes;
                }
                inEscape = false;
            }
            continue;
        }
        if (ch == 27) {
            inEscape = true;
            escape.clear();
        } else if (ch == '\r')
            column = 0;
        else if (ch == '\n') {
            newline();
            if (carriageReturnOnLinefeed)
                column = 0;
        } else if (ch == '\b' || ch == 127)
            column = qMax(0, column - 1);
        else if (ch == '\t')
            column = qMin(columns - 1, (column / 8 + 1) * 8);
        else if (ch >= 32) {
            if (column >= columns) {
                column = 0;
                newline();
            }
            screen[row][column++] = Cell{QChar(ch), attributes};
        }
    }
    auto *bar = verticalScrollBar();
    bool bottom = bar->value() == bar->maximum();
    bar->setRange(0, history.size());
    bar->setPageStep(rows);
    if (bottom)
        bar->setValue(bar->maximum());
    viewport()->update();
}
void Terminal::paintEvent(QPaintEvent *) {
    QPainter p(viewport());
    p.fillRect(viewport()->rect(), color(-1, true));
    int offset = verticalScrollBar()->value();
    for (int line = 0; line < rows; ++line) {
        int index = offset + line;
        const auto &cells = index < history.size() ? history[index] : screen[index - history.size()];
        for (int start = 0; start < columns;) {
            const auto &style = cells[start].attributes;
            int end = start + 1;
            while (end < columns && cells[end].attributes == style)
                ++end;
            int foreground = style.foreground;
            if (style.bold && foreground >= 0 && foreground < 8)
                foreground += 8;
            QColor fg = color(foreground), bg = color(style.background, true);
            if (style.inverse)
                std::swap(fg, bg);
            if (style.dim)
                fg = fg.darker(160);
            int top = 4 + line * cellHeight;
            p.fillRect(4 + start * cellWidth, top, (end - start) * cellWidth, cellHeight, bg);
            auto styledFont = font();
            styledFont.setBold(style.bold);
            styledFont.setItalic(style.italic);
            styledFont.setUnderline(style.underline);
            p.setFont(styledFont);
            p.setPen(fg);
            QString text;
            for (int c = start; c < end; ++c)
                text += cells[c].character;
            p.drawText(4 + start * cellWidth, top + QFontMetrics(styledFont).ascent(), text);
            start = end;
        }
    }
    int cursorLine = history.size() + row - offset;
    if (cursorVisible && hasFocus() && cursorLine >= 0 && cursorLine < rows)
        p.fillRect(4 + qMin(column, columns - 1) * cellWidth,
                   4 + (cursorLine + 1) * cellHeight - 2, cellWidth, 2,
                   color(attributes.foreground));
}
void Terminal::keyPressEvent(QKeyEvent *event) {
    QByteArray data;
    if (event->matches(QKeySequence::Paste)) {
        data =
            QApplication::clipboard()->text().replace("\r\n", "\n").replace('\n', '\r').toLatin1();
    } else if (event->modifiers().testFlag(Qt::ControlModifier) && event->key() == Qt::Key_C) {
        if (interruptStopsSession) {
            emit stopRequested();
            return;
        }
        data = "\x03";
    } else if (event->modifiers().testFlag(Qt::ControlModifier) && event->key() >= Qt::Key_A &&
               event->key() <= Qt::Key_Z) {
        data += char(event->key() - Qt::Key_A + 1);
    } else {
        switch (event->key()) {
        case Qt::Key_Return:
        case Qt::Key_Enter:
            data = "\r";
            break;
        case Qt::Key_Backspace:
            data = "\x08";
            break;
        case Qt::Key_Delete:
            data = "\x1b[3~";
            break;
        case Qt::Key_Up:
            data = "\x1b[A";
            break;
        case Qt::Key_Down:
            data = "\x1b[B";
            break;
        case Qt::Key_Right:
            data = "\x1b[C";
            break;
        case Qt::Key_Left:
            data = "\x1b[D";
            break;
        case Qt::Key_Home:
            data = "\x1b[H";
            break;
        case Qt::Key_End:
            data = "\x1b[F";
            break;
        default:
            data = event->text().toLatin1();
        }
    }
    if (!data.isEmpty()) {
        verticalScrollBar()->setValue(verticalScrollBar()->maximum());
        emit input(data);
    }
}
} // namespace ez80
