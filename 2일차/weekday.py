import calendar
from datetime import datetime

RED = "\033[91m"
BLUE = "\033[94m"
BOLD = "\033[1m"
RESET = "\033[0m"

HEADERS = ("일", "월", "화", "수", "목", "금", "토")
HEADER_COLORS = (RED, "", "", "", "", "", BLUE)


def colorize(text: str, color: str) -> str:
    if not color:
        return text
    return f"{color}{text}{RESET}"


def print_month_calendar(year: int, month: int) -> None:
    calendar.setfirstweekday(calendar.SUNDAY)
    weeks = calendar.monthcalendar(year, month)

    print(f"\n{BOLD}{year}년 {month}월{RESET}\n")

    header_line = "  ".join(
        colorize(f"{name:>2}", color) for name, color in zip(HEADERS, HEADER_COLORS)
    )
    print(header_line)
    print("-" * 22)

    for week in weeks:
        row = []
        for col, day in enumerate(week):
            if day == 0:
                row.append("   ")
                continue

            text = f"{day:>2}"
            if col == 0:
                text = colorize(text, RED)
            elif col == 6:
                text = colorize(text, BLUE)
            row.append(text)

        print("  ".join(row))


def main():
    print("년, 월을 입력하면 해당 달의 달력을 보여드립니다.")
    year = int(input("년: "))
    month = int(input("월: "))

    datetime(year, month, 1)
    print_month_calendar(year, month)


if __name__ == "__main__":
    main()
