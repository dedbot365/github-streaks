import requests
import json
import sys
import os
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import svgwrite

def fetch_contributions(username):
    """Fetch contribution calendar data using GitHub GraphQL API."""
    query = """
    query($userName: String!, $from: DateTime!, $to: DateTime!) {
      user(login: $userName) {
        contributionsCollection(from: $from, to: $to) {
          contributionCalendar {
            totalContributions
            weeks {
              contributionDays {
                date
                contributionCount
              }
            }
          }
        }
      }
    }
    """

    to_date = datetime.utcnow()
    from_date = to_date - timedelta(days=365)  # exactly 365 days - safe for GitHub limit

    variables = {
        "userName": username,
        "from": from_date.isoformat() + "Z",
        "to": to_date.isoformat() + "Z"
    }

    token = os.getenv("GITHUB_TOKEN")
    if not token or len(token) < 10:
        raise ValueError("GITHUB_TOKEN environment variable is missing or invalid!")
    print(f"DEBUG: Token prefix = {token[:4]}... (length: {len(token)})")

    headers = {
        'Authorization': f'Bearer {token}',
        'User-Agent': 'Streak-Stats-Generator'
    }

    url = "https://api.github.com/graphql"
    response = requests.post(url, json={'query': query, 'variables': variables}, headers=headers)

    if response.status_code != 200:
        raise Exception(f"GraphQL HTTP error: {response.status_code} - {response.text}")

    data = response.json()
    if 'errors' in data:
        raise Exception(f"GraphQL errors: {json.dumps(data['errors'], indent=2)}")

    user_data = data.get('data', {}).get('user')
    if not user_data:
        raise Exception(f"User '{username}' not found or no contribution data available")

    calendar = user_data['contributionsCollection']['contributionCalendar']
    total_contribs = calendar['totalContributions']

    daily_counts = {}
    for week in calendar['weeks']:
        for day in week['contributionDays']:
            count = day['contributionCount']
            if count > 0:
                date_str = day['date'][:10]  # YYYY-MM-DD
                daily_counts[date_str] = count

    return daily_counts, total_contribs


def calculate_streaks(daily_counts):
    """Calculate current streak, longest streak."""
    if not daily_counts:
        return 0, 0

    dates = sorted(daily_counts.keys())
    total_days = len(dates)

    # Current streak (from today backwards)
    current = 0
    today = datetime.utcnow().date()
    for date_str in reversed(dates):
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        delta = (today - date).days
        if delta == 0 or delta == current:
            current += 1
        elif delta > current:
            break

    # Longest streak
    longest = 0
    streak = 0
    prev_date = None
    for date_str in dates:
        date = datetime.strptime(date_str, '%Y-%m-%d').date()
        if prev_date is None or (date - prev_date).days == 1:
            streak += 1
            longest = max(longest, streak)
        else:
            streak = 1
        prev_date = date

    return current, longest


def generate_svg(current_streak, longest_streak, total_contribs, username):
    dwg = svgwrite.Drawing('assets/streak.svg', size=('495px', '195px'),
                           profile='full', debug=False)

    # Background with gradient
    dwg.add(dwg.rect(insert=(0, 0), size=('100%', '100%'), rx=10, ry=10,
                     fill='url(#bgGrad)'))

    bg_grad = dwg.linearGradient(start=(0, 0), end=(0, '100%'),
                                 id='bgGrad', gradientUnits='userSpaceOnUse')
    bg_grad.add_stop_color(offset=0, color='#0d1117')
    bg_grad.add_stop_color(offset=1, color='#161b22')
    dwg.defs.add(bg_grad)

    # Title
    dwg.add(dwg.text('Contribution Streak', insert=(247.5, 35),
                     fill='#58a6ff', font_family='sans-serif', font_size=24,
                     font_weight='bold', text_anchor='middle'))

    # Flame icon (simplified & fixed path)
    flame = dwg.g(transform='translate(30, 40) scale(1.8)', fill='#f59e0b')
    flame.add(dwg.path(d="M10 2C11 2 12 3 12 4c0 1-1 2-2 3-1 1-2 0-2 0-1-1-2-2-2-3 0-1 1-2 2-2zm0 20c-1 0-2-1-2-2 0-1 1-2 2-2s2 1 2 2c0 1-1 2-2 2zM10 10c-2 0-4 2-4 4s2 4 4 4 4-2 4-4-2-4-4-4z"))
    dwg.add(flame)

    # Stats boxes
    stats = [
        (current_streak, "Current Streak", 100),
        (longest_streak, "Longest Streak", 247.5),
        (total_contribs, "Contributions", 395)
    ]

    for value, label, x in stats:
        # Number
        dwg.add(dwg.text(str(value), insert=(x, 90),
                         fill='white', font_family='monospace', font_size=32,
                         font_weight='bold', text_anchor='middle'))
        # Label
        dwg.add(dwg.text(label, insert=(x, 120),
                         fill='#8b949e', font_family='sans-serif', font_size=14,
                         text_anchor='middle'))

    # Username footer
    dwg.add(dwg.text(f'@{username}', insert=(247.5, 170),
                     fill='#8b949e', font_family='sans-serif', font_size=14,
                     text_anchor='middle'))

    # Create output directory
    os.makedirs('assets', exist_ok=True)
    dwg.save()


if __name__ == '__main__':
    if len(sys.argv) < 2:
        raise ValueError("Username (repository owner) must be provided as argument")

    username = sys.argv[1].strip()
    print(f"Generating streak stats for GitHub user: {username}")

    daily_counts, total_contribs = fetch_contributions(username)
    print(f"Total contributions (last 365 days): {total_contribs}")
    print(f"Days with contributions: {len(daily_counts)}")

    current, longest = calculate_streaks(daily_counts)
    print(f"Current streak: {current}")
    print(f"Longest streak: {longest}")

    generate_svg(current, longest, total_contribs, username)
    print("SVG generated successfully")
